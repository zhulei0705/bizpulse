"""T08.1：修正域名 slug 命名的历史真实企业（haidilao/BYD）。

依据：它们各自挂有真实官网采集记录（A级、页面标题含真实名称）。
- haidilao → 海底捞（https://www.haidilao.com 页面标题"海底捞"）
- BYD → 比亚迪（https://www.byd.com/cn/news 页面标题"比亚迪新闻中心"）
名称以页面标题为证据（不做超出证据的全称推断），类型 COMPANY，
验证状态升级 WEBSITE_VERIFIED（官网已抓取验证），全程审计留痕。幂等。
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
from app.services.audit import write_audit  # noqa: E402

RENAMES = {
    "haidilao": {"new_name": "海底捞", "website": "https://www.haidilao.com", "domain": "www.haidilao.com"},
    "BYD": {"new_name": "比亚迪", "website": "https://www.byd.com", "domain": "www.byd.com"},
}


def main() -> None:
    db = SessionLocal()
    changed = []
    try:
        for old_name, spec in RENAMES.items():
            c = db.scalar(select(Company).where(Company.company_name == old_name))
            if c is None:
                continue  # 已改名（幂等）
            before = {"company_name": c.company_name, "website": c.website, "domain": c.domain,
                      "organization_type": c.organization_type, "verification_status": c.verification_status}
            c.company_name = spec["new_name"]
            c.normalized_name = spec["new_name"].lower()
            c.website = spec["website"]
            c.domain = spec["domain"]
            c.organization_type = "COMPANY"
            c.verification_status = "WEBSITE_VERIFIED"
            c.verified_at = datetime.now(timezone.utc)
            write_audit(db, "T08_COMPANY_RENAMED", "company", c.id, {
                "before": before,
                "after": {"company_name": c.company_name, "website": c.website, "domain": c.domain,
                          "organization_type": "COMPANY", "verification_status": "WEBSITE_VERIFIED"},
                "basis": "已有真实官网采集记录（A级），页面标题含真实名称；域名 slug 命名修正",
            })
            changed.append({"company_id": c.id, "before": before, "after": spec["new_name"]})
        db.commit()
        (ROOT / "_t08_out.txt").write_text(json.dumps({"renamed": changed}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"renamed": changed}, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()
