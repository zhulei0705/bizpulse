"""T08.1 收尾修正：
1. ingest 路径创建的真实主体回填 discovery_source_url（来自其真实来源记录，可追溯）；
2. 去重重复审计日志（脚本曾执行两次导致 T08_EXPERIMENT_AUDITED / LEGACY_UNVERIFIED_CONTACT 各多一条）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app.db import model_imports  # noqa: F401,E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.audit import AuditLog  # noqa: E402
from app.models.company import Company  # noqa: E402
from app.services.audit import write_audit  # noqa: E402


def backfill_discovery_urls(db) -> list[dict]:
    fixed = []
    for c in db.scalars(select(Company).where(
        Company.status == "ACTIVE",
        Company.discovery_source_url.is_(None),
        Company.verification_status.in_(["PUBLIC_SOURCE_VERIFIED", "WEBSITE_VERIFIED"]),
    )).all():
        record_url = next((r.url for r in c.source_records if r.url), None)
        if not record_url:
            continue
        c.discovery_source_url = record_url
        write_audit(db, "T08_DISCOVERY_URL_BACKFILLED", "company", c.id, {
            "company_name": c.company_name, "discovery_source_url": record_url,
            "basis": "来自该公司挂接的真实来源记录（可追溯）",
        })
        fixed.append({"company": c.company_name, "url": record_url})
    return fixed


def dedupe_audit_logs(db) -> list[str]:
    removed = []
    for action in ("T08_EXPERIMENT_AUDITED", "LEGACY_UNVERIFIED_CONTACT"):
        rows = db.scalars(select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.created_at)).all()
        for extra in rows[1:]:  # 保留最早一条，删除脚本重复执行产生的多余条目
            db.delete(extra)
            removed.append(f"{action}:{extra.id}")
    return removed


def main() -> None:
    db = SessionLocal()
    try:
        fixed = backfill_discovery_urls(db)
        removed = dedupe_audit_logs(db)
        db.commit()
        result = {"discovery_url_backfilled": fixed, "audit_logs_removed": removed}
        (ROOT / "_t08_out.txt").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()
