"""T08.2 执行前审计：41家商业企业 Coverage Audit + Coverage Gap + Enrichment Priority + Top20 选择。

输出 docs/reports/T08.2_coverage_audit.json（执行前基线，任务书四/五/六/七）。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import model_imports  # noqa: F401,E402
from app.db.session import SessionLocal  # noqa: E402
from app.services.company_coverage import (  # noqa: E402
    coverage_audit_all,
    data_funnel,
    enrichment_priority,
    scenario_distribution,
)

REPORT_DIR = ROOT / "docs" / "reports"


def main() -> None:
    db = SessionLocal()
    try:
        audits = coverage_audit_all(db, organization_type="COMPANY")
        ranked = []
        for a in audits:
            p = enrichment_priority(db, a)
            ranked.append({**p, "audit": a})
        ranked.sort(key=lambda x: -x["priority_score"])
        funnel = data_funnel(db)
        scenarios = scenario_distribution(db)

        top20 = ranked[:20]
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "pre_funnel": funnel,
            "pre_scenarios": scenarios,
            "company_count": len(audits),
            "top20": [
                {
                    "rank": i + 1,
                    "company_id": r["company_id"],
                    "company_name": r["company_name"],
                    "priority_score": r["priority_score"],
                    "factors": r["factors"],
                    "coverage_gap": r["coverage_gap"],
                    "official_website": r["official_website"],
                    "website_verified": r["audit"]["website_verified"],
                    "source_record_count": r["audit"]["source_record_count"],
                    "actionable_signal_count": r["audit"]["actionable_signal_count"],
                    "selection_reason": (
                        f"优先级{r['priority_score']}分；缺口{len(r['coverage_gap'])}项"
                        f"（{'、'.join(r['coverage_gap']) or '无'}）；"
                        f"官网{'已验证 ' + str(r['official_website']) if r['official_website'] else '未知'}；"
                        f"行动信号{r['audit']['actionable_signal_count']}条"
                    ),
                }
                for i, r in enumerate(top20)
            ],
            "audits": audits,
        }
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        (REPORT_DIR / "T08.2_coverage_audit.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        (ROOT / "_t08_out.txt").write_text(json.dumps({
            "funnel": funnel, "scenarios": scenarios,
            "top20": [(r["company_name"], r["priority_score"], r["coverage_gap"], r["official_website"]) for r in top20],
        }, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        print(json.dumps({"funnel": funnel, "scenarios": scenarios, "top20_first5": [r["company_name"] for r in top20[:5]]},
                         ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()
