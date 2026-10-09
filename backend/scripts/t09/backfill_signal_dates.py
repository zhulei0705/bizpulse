"""T09：信号发布日期回填（证据原文中的真实日期，可校验）。

依据（证据原文逐条核对）：
- 汉邦 HIRING：新闻列表"五一职等你来！汉邦激光诚邀英才..."条目尾注 "30 2026 / 04" → 2026-04-30
- 神州数码 NEW_PRODUCT："全'芯'发布！...新一代产品矩阵 09 / 18" → 2026-09-18
- 神州数码 AI_TRANSFORMATION："...入选服贸会成果展示，多行业AI落地获认可 09 / 22" → 2026-09-22
回填后重算 actionability 并审计留痕。远通 NEW_OFFICE 证据无日期 → 不回填（保持筛选排除）。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app.db import model_imports  # noqa: F401,E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.signal import Signal  # noqa: E402
from app.services.actionability import compute_signal_actionability, record_signal_actionability  # noqa: E402
from app.services.audit import write_audit  # noqa: E402

BACKFILLS = [
    ("广东汉邦激光科技有限公司", "HIRING", datetime(2026, 4, 30), "新闻条目尾注 30 2026 / 04"),
    ("神州数码信息系统有限公司", "NEW_PRODUCT", datetime(2026, 9, 18), "新闻条目尾注 09 / 18"),
    ("神州数码信息系统有限公司", "AI_TRANSFORMATION", datetime(2026, 9, 22), "新闻条目尾注 09 / 22"),
]


def main() -> None:
    db = SessionLocal()
    result = []
    try:
        for company_name, signal_type, published_at, basis in BACKFILLS:
            from app.models.company import Company

            company = db.scalar(select(Company).where(Company.company_name == company_name))
            if company is None:
                continue
            signal = db.scalar(select(Signal).where(
                Signal.company_id == company.id, Signal.signal_type == signal_type,
                Signal.status == "APPROVED"))
            if signal is None or signal.published_at is not None:
                continue  # 幂等
            before = None
            signal.published_at = published_at
            payload = dict(signal.payload_json or {})
            payload["published_at_basis"] = basis
            payload["actionability"] = {"status": compute_signal_actionability(db, signal),
                                        "computed_by": "rule_actionability_v1"}
            signal.payload_json = payload
            write_audit(db, "T09_SIGNAL_DATE_BACKFILLED", "signal", signal.id, {
                "published_at": published_at.isoformat(), "basis": basis,
                "evidence_quote": (signal.description or "")[:120],
            })
            result.append({"signal": signal.id, "type": signal_type,
                           "published_at": published_at.isoformat(),
                           "actionability": payload["actionability"]["status"]})
        db.commit()
        (ROOT / "_t09_out.txt").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()
