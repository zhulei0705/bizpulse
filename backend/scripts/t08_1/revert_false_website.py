"""T08.1 阶段D纠正：回滚误验证的官网（上海祥浦 → shuididp.cn 为第三方 ICP 备案查询页）。

阶段D实时复核发现：https://www.shuididp.cn 页面标题为"上海凭安网络科技有限公司"，
祥浦全名仅出现在页脚备案展示区 —— 该站点不是祥浦官网。处理：
- company.website/domain 置空，verification_status 回退 PUBLIC_SOURCE_VERIFIED；
- 误归属的官网/新闻/招聘 SourceRecord 删除（内容本身可再采集，但归属错误必须清除）；
- 全程审计留痕（T08_WEBSITE_VERIFICATION_REVERTED）。
"""
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
from app.models.company import Company  # noqa: E402
from app.models.signal import Signal  # noqa: E402
from app.models.source import SourceRecord  # noqa: E402
from app.services.audit import write_audit  # noqa: E402

REVERT_TARGETS = {
    "cmp_736049f0fb4449a69fd1124e": {  # 上海祥浦建设工程监理咨询有限责任公司
        "company_name": "上海祥浦建设工程监理咨询有限责任公司",
        "bad_domain": "www.shuididp.cn",
        "reason": "shuididp.cn 实为第三方 ICP 备案查询页（上海凭安网络科技），祥浦全名仅在页脚备案区出现",
    },
}


def main() -> None:
    db = SessionLocal()
    reverted = []
    try:
        for company_id, spec in REVERT_TARGETS.items():
            c = db.get(Company, company_id)
            if c is None or c.domain != spec["bad_domain"]:
                continue  # 已回滚（幂等）
            before = {"website": c.website, "domain": c.domain,
                      "verification_status": c.verification_status}
            # 删除误归属记录（官网/招聘/新闻采集记录的 url 挂在坏域名下）
            removed = []
            for r in db.scalars(select(SourceRecord).where(SourceRecord.company_id == c.id)).all():
                if spec["bad_domain"] in (r.url or ""):
                    # 该记录被信号引用时先解除（CONTRACT_AWARD 信号挂的是 ccgp 记录，不受影响）
                    for s in db.scalars(select(Signal).where(Signal.source_record_id == r.id)).all():
                        s.source_record_id = r.parent_record_id or s.source_record_id
                    db.delete(r)
                    removed.append(r.url)
            c.website = None
            c.domain = None
            c.verification_status = "PUBLIC_SOURCE_VERIFIED"
            c.verified_at = None
            write_audit(db, "T08_WEBSITE_VERIFICATION_REVERTED", "company", c.id, {
                "before": before, "after": {"verification_status": "PUBLIC_SOURCE_VERIFIED"},
                "reason": spec["reason"], "removed_records": removed,
                "reverted_at": datetime.now(timezone.utc).isoformat(),
            })
            reverted.append({"company": c.company_name, "removed_records": len(removed)})
        db.commit()
        (ROOT / "_t08_out.txt").write_text(json.dumps({"reverted": reverted}, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
        print(json.dumps({"reverted": reverted}, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()
