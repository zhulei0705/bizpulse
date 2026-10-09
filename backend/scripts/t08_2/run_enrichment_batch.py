"""T08.2 Top20 分批深挖（任务书三十六/三十七：5家 → 检查 → 5家 → 检查 → 10家）。

- 已有官网：直接走 enrich_company 管线；
- 官网未知：先用 可追溯候选/DDG 发现并验证官网（同 T08.1 规则），验证通过才深挖；
- 单页失败不中断；产出全部 VALID 待人工审核。

用法：python scripts/t08_2/run_enrichment_batch.py --batch 1|2|3
"""
from __future__ import annotations

import argparse
import json
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
from app.models.company import Company  # noqa: E402
from app.services.audit import write_audit  # noqa: E402
from app.services.enrichment_runner import enrich_company  # noqa: E402

REPORT_DIR = ROOT / "docs" / "reports"
BATCH_REPORT = REPORT_DIR / "T08.2_enrichment_batches.json"

# Top20（来自 T08.2_coverage_audit.json 的优先级排序，前14有官网）
BATCHES: dict[int, list[str]] = {
    1: ["中科睿华科技（北京）有限公司", "费勉科技（上海）股份有限公司", "苏州云帆氢能科技有限公司",
        "江苏华安科研仪器有限公司", "上海新一名实业（集团）有限公司"],
    2: ["神州数码信息系统有限公司", "中国图书进出口（集团）有限公司", "海底捞", "比亚迪",
        "湖北创联石油科技有限公司"],
    3: ["湖南京升缘供应链有限公司", "德赛集团有限公司", "北京远通信德科技有限公司",
        "广东汉邦激光科技有限公司", "深圳齐心集团股份有限公司", "上海格奥光电技术有限公司",
        "武汉华日精密激光股份有限公司", "北京天码科技有限责任公司", "江西电信信息产业有限公司",
        "中国电信股份有限公司凉山分公司"],
}

# 官网未知的可追溯候选（T08.1 会话内搜索结果/知名品牌官网；页面名称验证不过即放弃）
CURATED: dict[str, list[str]] = {
    "深圳齐心集团股份有限公司": ["https://www.comix.com.cn/", "https://www.comix.com.cn/about/", "https://www.comix.com.cn/gsjj/"],
}


def _discover_website(db, company: Company) -> dict:
    """官网未知 → 候选验证/DDG 发现（同 T08.1 规则：页面名称证据必须命中）。"""
    from urllib.parse import urlparse

    from app.services import extractor
    from app.services.company_discovery import SECTION_PATTERNS  # noqa: F401
    from scripts.t08_1.expand_company_pool import (  # 复用 T08.1 已验证的发现逻辑
        _verify_name_on_page,
        search_web,
    )

    candidates = list(CURATED.get(company.company_name, []))
    if not candidates:
        candidates = search_web(f"{company.company_name} 官网")
        time.sleep(3.0)
    for url in candidates[:4]:
        try:
            page = extractor.fetch_public_page(url)
        except Exception:  # noqa: BLE001
            time.sleep(1.2)
            continue
        if page.status_code != 200:
            continue
        matched = _verify_name_on_page(company.company_name, page.title, page.text or "")
        if not matched:
            continue
        host = (urlparse(page.final_url).hostname or "").lower()
        origin = f"{urlparse(page.final_url).scheme}://{urlparse(page.final_url).netloc}"
        before = {"verification_status": company.verification_status, "domain": company.domain}
        company.domain = host
        company.website = origin
        company.verification_status = "WEBSITE_VERIFIED"
        company.verified_at = company.verified_at or __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        if page.meta_description and not company.company_description:
            company.company_description = page.meta_description[:500]
        write_audit(db, "T082_COMPANY_WEBSITE_VERIFIED", "company", company.id,
                    {"before": before, "after": {"domain": host, "website": origin},
                     "name_evidence": matched, "candidates": candidates[:4]})
        return {"status": "VERIFIED", "domain": host, "evidence": matched}
    return {"status": "NOT_FOUND", "candidates": candidates[:4]}


def run_batch(batch_no: int) -> None:
    names = BATCHES[batch_no]
    db = SessionLocal()
    results = []
    try:
        for name in names:
            company = db.scalar(select(Company).where(Company.company_name == name))
            if company is None:
                results.append({"company_name": name, "error": "company not found"})
                continue
            entry: dict = {"company_name": name, "company_id": company.id}
            if not company.website:
                discovery = _discover_website(db, company)
                entry["website_discovery"] = discovery
                db.commit()
                if discovery["status"] != "VERIFIED":
                    entry["enrich"] = {"skipped": "官网未知（发现失败不猜测）"}
                    results.append(entry)
                    continue
            summary = enrich_company(db, company)
            entry["enrich"] = summary
            results.append(entry)
            db.commit()

        report = {"batch": batch_no, "ran_at": datetime.now(timezone.utc).isoformat(), "results": results}
        existing = json.loads(BATCH_REPORT.read_text(encoding="utf-8")) if BATCH_REPORT.exists() else {"batches": []}
        existing["batches"] = [b for b in existing["batches"] if b["batch"] != batch_no] + [report]
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        BATCH_REPORT.write_text(json.dumps(existing, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        (ROOT / "_t08_out.txt").write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        print(json.dumps({"batch": batch_no, "companies": len(results)}, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, required=True, choices=[1, 2, 3])
    args = parser.parse_args()
    run_batch(args.batch)
