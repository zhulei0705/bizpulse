"""T08.1 阶段C：企业池扩量 —— 官网验证 + 多源类型覆盖 + 档案补全（全部真实采集）。

流程（任务书十九/二十/二十三/二十四）：
1. 选定无官网的真实商业企业（来自已审计的中标供应商池）；
2. 搜索引擎发现官网候选 → 抓取 → 页面内出现企业名称证据才确认（不猜域名）；
3. 确认后：官网 SourceRecord 入库（OFFICIAL_WEBSITE），企业 WEBSITE_VERIFIED + domain/website；
4. 官网站内发现招聘页/新闻页 → OFFICIAL_CAREERS / OFFICIAL_NEWS SourceRecord（Source Type 多样性）；
5. 从已审计公告的"供应商地址"回填 province/city（真实证据，规则映射）；
6. 跑 expansion_quality_gate 输出报告。

红线：抓取失败/名称证据不足 → 保持原状，绝不猜测；不绕过任何访问控制；限速。
"""
from __future__ import annotations

import hashlib
import base64
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.constants import is_source_platform_domain  # noqa: E402
from app.db import model_imports  # noqa: F401,E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.company import Company  # noqa: E402
from app.models.source import Source, SourceRecord  # noqa: E402
from app.services import extractor  # noqa: E402
from app.services.audit import write_audit  # noqa: E402
from app.services.company_discovery import discover_website_sections  # noqa: E402
from app.services.expansion_gate import expansion_quality_gate  # noqa: E402

REPORT_DIR = ROOT / "docs" / "reports"
FETCH_DELAY = 1.2
SEARCH_DELAY = 4.0
MAX_CANDIDATES = 3
TARGET_WEBSITE_VERIFICATIONS = 12

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}

# 供应商名称的常见修饰成分（剥离后用于官网名称证据匹配）
_SUFFIXES = ("股份有限公司", "有限责任公司", "有限公司", "集团")
_REGION_PREFIXES = ("黑龙江省", "浙江省", "湖北省", "湖南省", "广东省", "江苏省", "山东省", "四川省",
                    "陕西省", "河北省", "河南省", "北京市", "上海市", "天津市", "重庆市",
                    "深圳", "广州", "苏州", "武汉", "成都", "西安", "杭州", "南京", "中山", "东莞",
                    "广东", "江苏", "浙江", "山东", "湖北", "湖南", "四川", "陕西", "河北", "河南")

PROVINCES = ("北京", "天津", "上海", "重庆", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
             "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东",
             "广西", "海南", "四川", "贵州", "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆")


def _unwrap_bing(url: str) -> str:
    """Bing 将结果包装成 bing.com/ck/a 跳转链接，目标 URL base64 编码在 u 参数（a1 前缀）。"""
    if "bing.com/ck/" not in url:
        return url
    qs = parse_qs(urlparse(url).query)
    u = qs.get("u", [""])[0]
    if u.startswith("a1"):
        b64 = u[2:] + "=" * (-len(u[2:]) % 4)
        try:
            decoded = base64.urlsafe_b64decode(b64).decode("utf-8", "ignore")
            if decoded.startswith("http"):
                return decoded
        except Exception:  # noqa: BLE001
            pass
    return url


def _ddg_links(endpoint: str, query: str) -> list[str]:
    """DuckDuckGo HTML/Lite 端点解析真实结果链接。"""
    r = httpx.get(endpoint, params={"q": query}, headers=_UA, timeout=20, follow_redirects=True)
    if r.status_code != 200:
        return []
    urls: list[str] = []
    for a in BeautifulSoup(r.text, "html.parser").select("a.result__a[href], a.result-link[href]"):
        href = a["href"]
        if "uddg=" in href:  # DDG 跳转包装
            qs = parse_qs(urlparse(href).query)
            if qs.get("uddg"):
                urls.append(unquote(qs["uddg"][0]))
        elif href.startswith("http"):
            urls.append(href)
    return urls


def search_web(query: str) -> list[str]:
    """官网候选发现：DDG HTML → DDG Lite → Bing（Bing 无 JS 模式常返回无关结果，
    由后续"页面名称证据"验证兜底过滤）。多通道合并，host 去重。"""
    urls: list[str] = []
    for endpoint in ("https://html.duckduckgo.com/html/", "https://lite.duckduckgo.com/lite/"):
        try:
            urls.extend(_ddg_links(endpoint, query))
        except Exception:  # noqa: BLE001 - 单通道失败继续
            pass
        if urls:
            break
    if not urls:
        try:
            r = httpx.get("https://www.bing.com/search", params={"q": query, "setlang": "zh-hans"},
                          headers=_UA, timeout=20, follow_redirects=True)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.select("li.b_algo h2 a[href]"):
                    urls.append(_unwrap_bing(a["href"]))
        except Exception:  # noqa: BLE001
            pass
    # 过滤：http(s)、非平台域名、去 host 重复
    result: list[str] = []
    seen_hosts: set[str] = set()
    for u in urls:
        if not u.startswith(("http://", "https://")):
            continue
        host = (urlparse(u).hostname or "").lower()
        if not host or is_source_platform_domain(host) or host in seen_hosts:
            continue
        seen_hosts.add(host)
        result.append(u)
        if len(result) >= MAX_CANDIDATES:
            break
    return result


def _name_candidates(company_name: str) -> list[str]:
    """官网名称证据候选：全称 → 去括号 → 去后缀 → 再去地域前缀 → 品牌渐进前缀（≥4字）。
    全部由真实名称规则派生，不新增词；匹配时取最长命中作为证据。"""
    name = company_name.strip()
    cands = [name]
    no_paren = re.sub(r"[（(][^（）()]*[）)]", "", name)
    cands.append(no_paren)
    stripped = no_paren
    for suffix in _SUFFIXES:
        if stripped.endswith(suffix) and len(stripped) - len(suffix) >= 4:
            stripped = stripped[: -len(suffix)]
    cands.append(stripped)
    region_stripped = stripped
    for region in _REGION_PREFIXES:
        if stripped.startswith(region) and len(stripped) - len(region) >= 4:
            region_stripped = stripped[len(region):]
            cands.append(region_stripped)
            break
    # 品牌渐进前缀（4~8 字，长→短）：官网页脚通常出现品牌简称
    base = region_stripped
    for width in range(min(8, len(base)), 3, -1):
        cands.append(base[:width])
    seen: set[str] = set()
    return [c for c in cands if len(c) >= 4 and not (c in seen or seen.add(c))]


# 官网候选（来源可追溯）：① 本次会话内搜索引擎真实返回结果；② 知名品牌官网。
# 候选≠结论：必须通过"页面出现企业名称证据"验证才入库。
CURATED_CANDIDATES: dict[str, dict] = {
    "广东汉邦激光科技有限公司": {"urls": ["https://www.hb3dp.com/", "https://www.hb3dp.com/profile.html"],
                     "note": "会话内 DDG 搜索结果"},
    "德赛集团有限公司": {"urls": ["http://www.desaygroup.com/", "https://www.desay.com.cn/"],
                   "note": "会话内 DDG 搜索结果"},
    "费勉科技（上海）股份有限公司": {"urls": ["http://www.fermi-instruments.com/", "https://www.fermi.com/"],
                       "note": "会话内 DDG 搜索结果"},
    "深圳齐心集团股份有限公司": {"urls": ["https://www.comix.com.cn/", "https://www.comix.com.cn/about/",
                                  "https://www.comix.com.cn/gsjj/"], "note": "知名品牌官网候选（页面名称验证确认）"},
    "神州数码信息系统有限公司": {"urls": ["https://www.digitalchina.com/"], "note": "知名品牌官网候选（页面名称验证确认）"},
    "中国图书进出口（集团）有限公司": {"urls": ["https://www.cnpiec.com.cn/"], "note": "知名品牌官网候选（页面名称验证确认）"},
    "武汉华日精密激光股份有限公司": {"urls": ["https://www.whhrlaser.cn/", "https://www.whhrlaser.com/"],
                       "note": "品牌官网候选（页面名称验证确认）"},
}


def _verify_name_on_page(company_name: str, title: str | None, text: str) -> str | None:
    """页面标题/正文出现企业名称证据（最长候选优先）→ 返回命中的证据词；都没有 → None。

    防 ICP 备案页脚陷阱（真实案例：第三方备案查询页页脚含目标公司全名）：
    若只有"全称"命中且命中位置在正文后段（页脚/备案区），不作为官网证据；
    品牌级候选（≥4字）或标题/正文前段命中仍有效。
    """
    haystack = f"{title or ''} {text[:6000]}"
    main_area = f"{title or ''} {text[:3000]}"
    candidates = _name_candidates(company_name)
    for cand in candidates:  # 长候选在前（全称→品牌前缀）
        if cand in haystack:
            is_full_name = cand == company_name
            if is_full_name and cand not in main_area and (title or "") and cand not in title:
                continue  # 全称仅出现在页脚备案区 → 证据不足
            return cand
    return None


def _get_or_create_source(db, *, source_type: str, name: str, grade: str = "B", score: int = 70) -> Source:
    src = db.scalar(select(Source).where(Source.source_type == source_type))
    if src is None:
        src = Source(name=name, source_type=source_type, reliability_grade=grade,
                     reliability_score=score, enabled=True, collector_type="manual_url",
                     notes="T08.1 官网/招聘/新闻真实采集（抓取失败或证据不足不入库）")
        db.add(src)
        db.flush()
    return src


def _persist_record(db, *, source: Source, company: Company, url: str, title: str | None,
                    text: str, http_status: int, collected_via: str) -> SourceRecord | None:
    fingerprint = hashlib.sha256(f"{url}\n{title or ''}\n{(text or '')[:2000]}".encode("utf-8")).hexdigest()
    existing = db.scalar(select(SourceRecord).where(
        SourceRecord.source_id == source.id, SourceRecord.content_hash == fingerprint))
    if existing is not None:
        return existing
    record = SourceRecord(
        source_id=source.id, company_id=company.id, url=url, canonical_url=url,
        title=title, raw_text=(text or "")[:60000], content_hash=fingerprint,
        http_status=http_status, content_type="text/html", language="zh",
        source_reliability=source.reliability_grade, verification_status="VERIFIED",
        last_verified_at=datetime.now(timezone.utc), company_resolve_status="EXACT",
        metadata_json={"collected_via": collected_via},
    )
    db.add(record)
    db.flush()
    company.source_count = (company.source_count or 0) + 1
    write_audit(db, "T08_OFFICIAL_SITE_RECORD", "source_record", record.id,
                {"company_id": company.id, "url": url, "via": collected_via})
    return record


def verify_official_website(db, company: Company) -> dict:
    """发现并验证企业官网；成功 → 持久化记录并升级 WEBSITE_VERIFIED。

    候选来源顺序：① 人工整理的可追溯候选（会话内真实搜索结果/知名品牌官网）；
    ② 搜索引擎实时发现（DDG，限速）。候选≠结论：页面名称证据验证不过即放弃。
    """
    if company.domain or company.website:
        return {"company": company.company_name, "status": "ALREADY_VERIFIED", "domain": company.domain}

    curated = CURATED_CANDIDATES.get(company.company_name)
    candidate_urls: list[str] = list(curated["urls"]) if curated else []
    candidate_note = curated["note"] if curated else None
    searched = False
    if not candidate_urls:
        candidate_urls = search_web(f"{company.company_name} 官网")
        searched = True
        time.sleep(SEARCH_DELAY)

    for url in candidate_urls[:MAX_CANDIDATES + 2]:
        try:
            page = extractor.fetch_public_page(url)
        except Exception as exc:  # noqa: BLE001 单个候选失败继续
            time.sleep(FETCH_DELAY)
            continue
        time.sleep(FETCH_DELAY)
        if page.status_code != 200:
            continue
        matched = _verify_name_on_page(company.company_name, page.title, page.text or "")
        if not matched:
            continue
        host = (urlparse(page.final_url).hostname or "").lower()
        origin = f"{urlparse(page.final_url).scheme}://{urlparse(page.final_url).netloc}"
        source = _get_or_create_source(db, source_type="OFFICIAL_WEBSITE", name="企业官网采集")
        record = _persist_record(db, source=source, company=company, url=page.final_url,
                                 title=page.title, text=page.text, http_status=page.status_code,
                                 collected_via="official_website_verification")
        before = {"verification_status": company.verification_status, "domain": company.domain,
                  "website": company.website}
        company.domain = host
        company.website = origin
        company.verification_status = "WEBSITE_VERIFIED"
        company.verified_at = datetime.now(timezone.utc)
        if page.meta_description and not company.company_description:
            company.company_description = page.meta_description[:500]
        write_audit(db, "T08_COMPANY_WEBSITE_VERIFIED", "company", company.id, {
            "before": before,
            "after": {"domain": host, "website": origin, "verification_status": "WEBSITE_VERIFIED"},
            "name_evidence": matched, "record_id": record.id if record else None,
            "candidate_note": candidate_note, "searched_live": searched,
        })
        return {"company": company.company_name, "status": "VERIFIED", "domain": host,
                "url": page.final_url, "name_evidence": matched, "candidate_note": candidate_note}
    return {"company": company.company_name, "status": "NOT_FOUND",
            "candidates": candidate_urls, "candidate_note": candidate_note, "searched_live": searched}


def collect_site_sections(db, company: Company) -> dict:
    """官网站内发现招聘/新闻页（Source Type 多样性）；抓取失败留痕不入库。"""
    if not company.website:
        return {"company": company.company_name, "careers": None, "news": None}
    try:
        discovery = discover_website_sections(company.website, max_pages=8)
    except Exception as exc:  # noqa: BLE001
        return {"company": company.company_name, "error": str(exc)[:120]}
    result = {"company": company.company_name}
    for dimension, source_type, name in (
        ("CAREERS", "OFFICIAL_CAREERS", "企业官方招聘"),
        ("NEWS", "OFFICIAL_NEWS", "企业官方新闻"),
    ):
        target = next((p for p in discovery.pages if p.dimension == dimension), None)
        if target is None:
            result[dimension.lower()] = None
            continue
        try:
            page = extractor.fetch_public_page(target.url)
            time.sleep(FETCH_DELAY)
        except Exception as exc:  # noqa: BLE001
            result[dimension.lower()] = f"fetch_failed: {str(exc)[:80]}"
            continue
        if page.status_code != 200 or not (page.text or "").strip():
            result[dimension.lower()] = "empty"
            continue
        src = _get_or_create_source(db, source_type=source_type, name=name)
        record = _persist_record(db, source=src, company=company, url=page.final_url,
                                 title=page.title, text=page.text, http_status=page.status_code,
                                 collected_via=f"official_{dimension.lower()}_discovery")
        result[dimension.lower()] = record.id if record else "exists"
    return result


def backfill_region_from_award(db, company: Company) -> str | None:
    """从已审计中标公告的"供应商地址"回填 province（真实证据 + 省名规则映射）。

    多供应商公告：地址必须取"供应商名称：{本主体}"之后的那条，不得误取其他包件供应商地址。
    """
    if company.province:
        return None
    for signal in company.signals:
        if signal.signal_type != "CONTRACT_AWARD":
            continue
        record = signal.source_record
        if record is None:
            continue
        raw = record.raw_text or ""
        anchor = raw.find(f"供应商名称：{company.company_name}")
        search_from = anchor + 1 if anchor >= 0 else 0
        match = re.search(r"供应商地址[：:]\s*([^\s，,。；;]{4,40})", raw[search_from:])
        if not match:
            continue
        address = match.group(1)
        for province in PROVINCES:
            if province in address:
                company.province = province if len(province) >= 2 else None
                if province in ("北京", "天津", "上海", "重庆"):
                    company.province = province + "市"
                write_audit(db, "T08_COMPANY_REGION_BACKFILLED", "company", company.id,
                            {"province": company.province, "evidence": address, "signal_id": signal.id})
                return province
    return None


def _derive_province(company: Company) -> tuple[str | None, str | None]:
    """按当前规则重导出 province（返回 (province, evidence_address)）。"""
    for signal in company.signals:
        if signal.signal_type != "CONTRACT_AWARD":
            continue
        record = signal.source_record
        if record is None:
            continue
        raw = record.raw_text or ""
        anchor = raw.find(f"供应商名称：{company.company_name}")
        search_from = anchor + 1 if anchor >= 0 else 0
        match = re.search(r"供应商地址[：:]\s*([^\s，，。；;]{4,40})", raw[search_from:])
        if not match:
            continue
        address = match.group(1)
        for province in PROVINCES:
            if province in address:
                if province in ("北京", "天津", "上海", "重庆"):
                    province = province + "市"
                return province, address
    return None, None


def correct_region_backfills(db) -> list[dict]:
    """修正历史回填：多供应商公告曾把首位供应商地址误配给其他主体（如德赛集团）。"""
    corrected = []
    real_companies = db.scalars(select(Company).where(
        Company.status == "ACTIVE",
        Company.verification_status.in_(["PUBLIC_SOURCE_VERIFIED", "WEBSITE_VERIFIED"]),
    )).all()
    for company in real_companies:
        if not company.province:
            continue
        new_province, evidence = _derive_province(company)
        if new_province and new_province != company.province:
            write_audit(db, "T08_COMPANY_REGION_CORRECTED", "company", company.id, {
                "before": company.province, "after": new_province,
                "evidence": evidence, "company_name": company.company_name,
            })
            company.province = new_province
            corrected.append({"company": company.company_name,
                              "before": company.province, "after": new_province})
    return corrected


def main() -> None:
    db = SessionLocal()
    report: dict = {"verified": [], "section_results": [], "region_backfilled": [], "skipped": []}
    try:
        # 1) 官网验证：优先可追溯候选的品牌企业，其次真实商业企业；分公司无独立官网，跳过
        targets = db.scalars(select(Company).where(
            Company.status == "ACTIVE",
            Company.organization_type == "COMPANY",
            Company.domain.is_(None),
            Company.website.is_(None),
            Company.verification_status.in_(["PUBLIC_SOURCE_VERIFIED"]),
        )).all()
        targets = [c for c in targets if "分公司" not in c.company_name and len(c.company_name) >= 6]
        curated_first = [c for c in targets if c.company_name in CURATED_CANDIDATES]
        others = [c for c in targets if c.company_name not in CURATED_CANDIDATES]
        targets = (curated_first + others)[:TARGET_WEBSITE_VERIFICATIONS]
        for company in targets:
            result = verify_official_website(db, company)
            db.commit()
            report["verified"].append(result)
            if result["status"] == "VERIFIED":
                sections = collect_site_sections(db, company)
                db.commit()
                report["section_results"].append(sections)

        # 2) 地域修正 + 回填（全部真实主体）
        report["region_corrected"] = correct_region_backfills(db)
        real_companies = db.scalars(select(Company).where(
            Company.status == "ACTIVE",
            Company.verification_status.in_(["PUBLIC_SOURCE_VERIFIED", "WEBSITE_VERIFIED"]),
        )).all()
        for company in real_companies:
            province = backfill_region_from_award(db, company)
            if province:
                report["region_backfilled"].append({"company": company.company_name, "province": province})
        db.commit()

        gate = expansion_quality_gate(db)
        report["gate"] = gate
        db.commit()

        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        (REPORT_DIR / "T08.1_expansion_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        (ROOT / "_t08_out.txt").write_text(json.dumps(
            {"verified": report["verified"], "gate": gate}, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8")
        print(json.dumps({"gate_passed": gate["passed"], "gate": gate["gates"],
                          "verified_count": sum(1 for v in report["verified"] if v["status"] == "VERIFIED")},
                         ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()
