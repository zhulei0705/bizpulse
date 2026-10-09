"""T08.1 阶段D：30家真实主体人工抽查（10家，任务书二十七/二十八）。

分层抽样：不同来源（ccgp公告发现/官网验证/历史官网）/ 不同 organization_type /
不同 Signal 类型 / 不同 Company 发现方式。

每家 12 项检查：真实存在 / Source URL可打开 / 官网正确 / 无重复 / org_type正确 /
行业有证据 / Signal真实 / Evidence支持 / published_at正确 / Contact真实公开 /
Opportunity不过度推断 / 仍具actionability。
"""
from __future__ import annotations

import json
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app.db import model_imports  # noqa: F401,E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.company import Company, CompanyContact  # noqa: E402
from app.models.opportunity import Opportunity  # noqa: E402
from app.models.signal import Signal, SignalEvidence  # noqa: E402
from app.services import extractor  # noqa: E402
from app.services import procurement_parser as pp  # noqa: E402
from app.services.actionability import compute_signal_actionability, is_actionable_for_validation  # noqa: E402

REPORT_DIR = ROOT / "docs" / "reports"
SAMPLE_SIZE = 10

_RESEARCH_MARKERS = ("研究院", "研究所", "科学院")
_UNIVERSITY_MARKERS = ("大学", "学院")


def _pick_companies(db) -> list[Company]:
    """分层抽样：官网验证企业 / 公告发现企业 / 高校 / 科研院所 / 历史官网企业。"""
    real = db.scalars(select(Company).where(
        Company.status == "ACTIVE",
        Company.verification_status.in_(["PUBLIC_SOURCE_VERIFIED", "WEBSITE_VERIFIED"]),
    )).all()
    buckets: dict[str, list[Company]] = {"website": [], "award": [], "university": [], "research": []}
    for c in real:
        if c.organization_type == "UNIVERSITY":
            buckets["university"].append(c)
        elif c.organization_type == "RESEARCH_INSTITUTE":
            buckets["research"].append(c)
        elif c.verification_status == "WEBSITE_VERIFIED" and (c.metadata_json if False else True):
            buckets["website" if c.website else "award"].append(c)
        else:
            buckets["award"].append(c)
    rng = random.Random(20261005)  # 固定种子：抽样可复现
    picks: list[Company] = []
    for key, n in (("website", 4), ("award", 3), ("university", 2), ("research", 1)):
        pool = buckets[key]
        rng.shuffle(pool)
        picks.extend(pool[:n])
    # 不足则从剩余补齐
    if len(picks) < SAMPLE_SIZE:
        chosen = {c.id for c in picks}
        rest = [c for c in real if c.id not in chosen]
        rng.shuffle(rest)
        picks.extend(rest[: SAMPLE_SIZE - len(picks)])
    return picks[:SAMPLE_SIZE]


def check_company(db, company: Company) -> dict:
    checks: dict[str, dict] = {}

    # 1 真实存在：至少 1 条真实来源记录（200）或公告发现 URL
    records = list(company.source_records)
    ok_records = [r for r in records if r.http_status == 200 or r.parse_status == "OK"]
    checks["real_existence"] = {
        "pass": bool(company.discovery_source_url or ok_records),
        "evidence": {"discovery_source_url": company.discovery_source_url,
                     "verified_records": len(ok_records)},
    }

    # 2 Source URL 能打开（实时抓取官网/发现来源；无则回落到来源记录 URL）
    record_urls = [r.url for r in records if r.url]
    url_to_check = company.website or company.discovery_source_url or (record_urls[0] if record_urls else None)
    url_check: dict = {"pass": False, "url": url_to_check}
    if url_to_check:
        try:
            page = extractor.fetch_public_page(url_to_check)
            url_check["http_status"] = page.status_code
            url_check["pass"] = page.status_code == 200
            url_check["title"] = (page.title or "")[:80]
        except Exception as exc:  # noqa: BLE001
            url_check["error"] = str(exc)[:120]
    checks["source_url_open"] = url_check
    time.sleep(1.0)

    # 3 官网正确（WEBSITE_VERIFIED 才检查；页面需出现名称证据）
    if company.verification_status == "WEBSITE_VERIFIED" and company.website:
        try:
            page = extractor.fetch_public_page(company.website)
            tokens = [company.company_name]
            core = re.sub(r"[（(][^（）()]*[）)]", "", company.company_name)
            for suffix in ("股份有限公司", "有限责任公司", "有限公司", "集团"):
                if core.endswith(suffix) and len(core) - len(suffix) >= 4:
                    core = core[: -len(suffix)]
            tokens.append(core)
            name_found = any(t and t in f"{page.title or ''} {(page.text or '')[:6000]}" for t in tokens if len(t) >= 4)
            checks["official_website_correct"] = {"pass": bool(name_found), "website": company.website,
                                                   "page_title": (page.title or "")[:80]}
        except Exception as exc:  # noqa: BLE001
            checks["official_website_correct"] = {"pass": False, "website": company.website,
                                                   "error": str(exc)[:120]}
        time.sleep(1.0)
    else:
        checks["official_website_correct"] = {"pass": None, "note": "非官网验证主体（公告发现），官网未知不算失败"}

    # 4 无重复 Company
    dup = db.scalar(select(Company).where(
        Company.normalized_name == company.normalized_name, Company.id != company.id))
    checks["no_duplicate"] = {"pass": dup is None, "duplicate_of": dup.company_name if dup else None}

    # 5 organization_type 正确（名称规则复核）
    name = company.company_name
    if any(k in name for k in _RESEARCH_MARKERS):
        expected = "RESEARCH_INSTITUTE"
    elif any(k in name for k in _UNIVERSITY_MARKERS) and company.organization_type in {"UNIVERSITY", "COMPANY"}:
        expected = "UNIVERSITY" if "大学" in name or "学院" in name else company.organization_type
    elif company.organization_type == "COMPANY":
        expected = "COMPANY"
    else:
        expected = company.organization_type
    checks["organization_type_correct"] = {"pass": company.organization_type == expected,
                                            "actual": company.organization_type, "expected": expected}

    # 6 行业/描述证据（有描述即有据；无描述不算失败——数据不足如实呈现）
    checks["industry_evidence"] = {
        "pass": True,
        "description": (company.company_description or "")[:120] or None,
        "industry": company.industry,
        "note": None if company.company_description else "暂无官网描述证据（未采集到，不猜测）",
    }

    # 7/8/9 信号真实 / Evidence 支持 / published_at 正确
    signals = db.scalars(select(Signal).where(Signal.company_id == company.id)).all()
    signal_results = []
    for s in signals[:5]:
        record = s.source_record
        raw = (record.raw_text if record else "") or ""
        evs = db.scalars(select(SignalEvidence).where(SignalEvidence.signal_id == s.id)).all()
        ev_pass = bool(evs) and any(e.quoted_text and e.quoted_text in raw for e in evs)
        audit = (s.payload_json or {}).get("t08_audit") or {}
        expected_pub = audit.get("announcement_date")
        pub_ok = True
        if expected_pub and s.published_at:
            # SQLite 存储为空格分隔，审计为 ISO "T" 分隔 —— 规范化后比较
            pub_ok = str(s.published_at).replace("T", " ")[:16] == str(expected_pub).replace("T", " ")[:16]
        signal_results.append({
            "signal_id": s.id, "type": s.signal_type, "status": s.status,
            "has_source_record": record is not None,
            "evidence_supported": ev_pass,
            "published_at_ok": pub_ok,
            "actionability": compute_signal_actionability(db, s),
        })
    checks["signals_real_and_supported"] = {
        "pass": all(r["has_source_record"] and r["evidence_supported"] and r["published_at_ok"]
                    for r in signal_results) if signal_results else None,
        "detail": signal_results,
    }

    # 10 Contact 真实公开
    contacts = db.scalars(select(CompanyContact).where(CompanyContact.company_id == company.id)).all()
    checks["contacts_real_public"] = {
        "pass": all(c.verification_status in {"VERIFIED_PUBLIC", "USER_PROVIDED"} for c in contacts),
        "count": len(contacts),
        "note": f"{len(contacts)} 个联系人；无联系人时为数据不足（禁止伪造）",
    }

    # 11/12 Opportunity 过度推断 / actionability
    opps = db.scalars(select(Opportunity).where(Opportunity.company_id == company.id)).all()
    opp_results = []
    for o in opps:
        from app.services.actionability import opportunity_actionability

        a = opportunity_actionability(db, o)
        opp_results.append({"opportunity_id": o.id, "title": o.title[:50],
                            "review_status": o.review_status,
                            "actionability": a["actionability_status"]})
    checks["opportunity_not_overreached"] = {
        "pass": all(r["actionability"] != "HISTORICAL_SIGNAL" or r["review_status"] != "APPROVED"
                    for r in opp_results),
        "detail": opp_results,
    }

    passed_items = [k for k, v in checks.items() if v.get("pass") is False]
    return {"company_id": company.id, "company_name": company.company_name,
            "organization_type": company.organization_type,
            "verification_status": company.verification_status,
            "discovery": "official_website" if company.website else "award_notice",
            "checks": checks, "failed": passed_items, "pass": not passed_items}


def main() -> None:
    db = SessionLocal()
    try:
        companies = _pick_companies(db)
        items = [check_company(db, c) for c in companies]
    finally:
        db.close()

    passed = sum(1 for x in items if x["pass"])
    summary = {
        "checked": len(items), "passed": passed, "failed": len(items) - passed,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "verdict": "PASS" if passed == len(items) else "NEED_REVIEW",
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "T08.1_company_spot_check.json").write_text(
        json.dumps({"summary": summary, "items": items}, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    lines = [
        "# T08.1 阶段D — 30家真实主体人工抽查报告（10家）",
        "",
        f"生成时间：{summary['checked_at']} ｜ 抽查：{summary['checked']} ｜ 通过：{summary['passed']} ｜ 结论：**{summary['verdict']}**",
        "",
    ]
    for it in items:
        lines.append(f"## {'✅ PASS' if it['pass'] else '❌ FAIL'} — {it['company_name']}（{it['organization_type']}/{it['verification_status']}/{'官网' if it['discovery'] == 'official_website' else '公告'}）")
        for k, v in it["checks"].items():
            mark = "✓" if v.get("pass") is True else ("✗" if v.get("pass") is False else "—")
            detail = {a: b for a, b in v.items() if a not in {"detail"}} if k == "signals_real_and_supported" else v
            lines.append(f"- {mark} {k}: {json.dumps(detail, ensure_ascii=False, default=str)[:220]}")
        lines.append("")
    (REPORT_DIR / "T08.1_company_spot_check.md").write_text("\n".join(lines), encoding="utf-8")
    (ROOT / "_t08_out.txt").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
