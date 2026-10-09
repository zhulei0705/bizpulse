"""T08.2 规则扩展（诚邀英才/职等你来 → HIRING）后重新分析 t082 已采集页面。

注意：review_batch1 的拒绝清单是批次1的处置，这里只跑 regen_signals（新信号 VALID 待审）。
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
from app.models.company import Company  # noqa: E402
from app.models.source import SourceRecord  # noqa: E402
from app.services.enrichment_runner import _signals_from_record  # noqa: E402


def main() -> None:
    db = SessionLocal()
    created = 0
    try:
        records = db.scalars(select(SourceRecord).where(
            SourceRecord.metadata_json.like('%"t082_enrichment"%'))).all()
        for record in records:
            company = db.get(Company, record.company_id) if record.company_id else None
            if company is None:
                continue
            page_type = (record.metadata_json or {}).get("page_type") or "OTHER"
            created += len(_signals_from_record(db, company, record, page_type))
        db.commit()
        (ROOT / "_t08_out.txt").write_text(json.dumps({"regenerated": created}, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({"regenerated": created}, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()
