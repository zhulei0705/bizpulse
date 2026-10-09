"""T09-B1 收尾：把两条 Evidence 的 live 验证结果写入实验快照与报告。"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app.db import model_imports  # noqa: F401,E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.experiment import Experiment  # noqa: E402
from app.services.audit import write_audit  # noqa: E402

LIVE_RESULTS = [
    {"item": "990万元中标事实（2026-09-30公告）",
     "url": "http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20260930_27433686.htm",
     "http_status": 200, "live_quote_found": True},
    {"item": "招聘信息（2026-04-30官网新闻）",
     "url": "https://www.hb3dp.com/news/2/",
     "http_status": 200, "live_quote_found": True},
]


def main() -> None:
    db = SessionLocal()
    try:
        experiment = db.scalar(select(Experiment).where(
            Experiment.name.like("BizPulse 第一轮真实客户微验证%")))
        snapshot = experiment.snapshot_json or {}
        b1 = snapshot.get("t09_b1") or {}
        checks = b1.get("evidence_recheck") or []
        for item in checks:
            for lr in LIVE_RESULTS:
                if item["item"].startswith(lr["item"].split("（")[0]) and "990" in item["item"] and "990" in lr["item"]:
                    item["live_page"] = f"HTTP {lr['http_status']}，引文在live页面：{lr['live_quote_found']}"
                if "招聘" in item["item"] and "招聘" in lr["item"]:
                    item["live_page"] = f"HTTP {lr['http_status']}，引文在live页面：{lr['live_quote_found']}"
                if "官网联系信息" in item["item"]:
                    item["live_page"] = "HTTP 200，邮箱/标注/热线在live页面：True（见 contact_recheck）"
        b1["evidence_live_verified_at"] = datetime.now(timezone.utc).isoformat()
        snapshot["t09_b1"] = b1
        experiment.snapshot_json = snapshot
        experiment.updated_at = datetime.now(timezone.utc)
        write_audit(db, "T09B1_EVIDENCE_LIVE_VERIFIED", "experiment", experiment.id,
                    {"live_results": LIVE_RESULTS})
        db.commit()

        # 更新报告表格
        report_path = ROOT / "docs" / "reports" / "T09-B1_hanbang_ready.md"
        text = report_path.read_text(encoding="utf-8")
        text = text.replace(
            "| 990万元中标事实（2026-09-30公告） | 中标（成交）金额：990.0000000（万元） | ✅ | — |",
            "| 990万元中标事实（2026-09-30公告） | 中标（成交）金额：990.0000000（万元） | ✅ | HTTP 200，引文在live页面 ✅ |")
        text = text.replace(
            "| 招聘信息（2026-04-30官网新闻，非'近期'） | 五一职等你来！汉邦激光诚邀英才，共拓金属 3D 打印新征程 | ✅ | — |",
            "| 招聘信息（2026-04-30官网新闻，非'近期'） | 五一职等你来！汉邦激光诚邀英才，共拓金属 3D 打印新征程 | ✅ | HTTP 200，引文在live页面 ✅ |")
        text = text.replace(
            "| 官网联系信息（国内业务邮箱/服务热线） | hb3d@hb3dp.com | ✅ | — |",
            "| 官网联系信息（国内业务邮箱/服务热线） | hb3d@hb3dp.com | ✅ | HTTP 200，邮箱/标注/热线在live页面 ✅ |")
        report_path.write_text(text, encoding="utf-8")
        print(json.dumps({"updated": True}, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()
