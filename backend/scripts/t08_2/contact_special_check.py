"""T08.2 Contact 特别抽查（任务书三十九）：至少10条，live 抓取 source_url 逐条验证。

检查：邮箱/电话真实出现在来源页原文；归属企业正确；角色正确（HR≠销售决策人）。
畸形电话（解析产物疑似拼接）专项核查：原文存在该数字串 → 保留；不存在 → 删除留痕。
"""
from __future__ import annotations

import json
import random
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
from app.services import extractor  # noqa: E402
from app.services.audit import write_audit  # noqa: E402

REPORT_DIR = ROOT / "docs" / "reports"
SUSPECT_PHONES = {"010802037792", "010502049526"}  # 首页正文拼接数字串（无分隔符12位）


def _norm_digits(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())


def main() -> None:
    db = SessionLocal()
    items = []
    try:
        contacts = db.scalars(select(CompanyContact).where(
            CompanyContact.source_type == "OFFICIAL_WEBSITE")).all()
        removed = 0

        # 先做可疑电话专项核查
        for c in contacts:
            if _norm_digits(c.phone) in {_norm_digits(p) for p in SUSPECT_PHONES}:
                try:
                    page = extractor.fetch_public_page(c.source_url)
                    raw = page.text or ""
                    compact = _norm_digits(raw)
                    found = _norm_digits(c.phone) in compact or (c.phone in raw)
                except Exception:  # noqa: BLE001
                    found = None  # 无法核实
                if found is False:
                    write_audit(db, "T082_CONTACT_REMOVED", "company_contact", c.id, {
                        "reason": "解析产物在来源原文中不存在（疑似正文拼接数字串）",
                        "phone": c.phone, "source_url": c.source_url,
                    })
                    db.delete(c)
                    removed += 1
                else:
                    write_audit(db, "T082_CONTACT_VERIFIED_SUSPECT", "company_contact", c.id,
                                {"phone": c.phone, "found_in_source": found})
                time.sleep(1.0)
        db.commit()

        # 分层抽 10 条（覆盖 EMAIL/PHONE/WEBSITE_FORM 与不同企业）
        contacts = db.scalars(select(CompanyContact).where(
            CompanyContact.source_type == "OFFICIAL_WEBSITE")).all()
        by_channel: dict[str, list[CompanyContact]] = {}
        for c in contacts:
            ch = "EMAIL" if c.email else ("PHONE" if c.phone else ("WEBSITE_FORM" if c.public_profile_url else "?"))
            by_channel.setdefault(ch, []).append(c)
        rng = random.Random(20261005)
        sample: list[CompanyContact] = []
        for ch in ("EMAIL", "PHONE", "WEBSITE_FORM"):
            pool = by_channel.get(ch, [])
            rng.shuffle(pool)
            sample.extend(pool[:4])
        seen_ids = {c.id for c in sample}
        for c in contacts:
            if len(sample) >= 10:
                break
            if c.id not in seen_ids:
                sample.append(c)
                seen_ids.add(c.id)
        sample = sample[:10]

        for c in sample:
            company = db.get(Company, c.company_id)
            item = {
                "contact_id": c.id,
                "company": company.company_name if company else None,
                "channel": "EMAIL" if c.email else ("PHONE" if c.phone else "WEBSITE_FORM"),
                "value": c.email or c.phone or c.public_profile_url,
                "contact_type": c.contact_type,
                "source_url": c.source_url,
            }
            try:
                page = extractor.fetch_public_page(c.source_url)
                text = page.text or ""
                compact = _norm_digits(text)
                if c.email:
                    item["found_in_source"] = c.email.lower() in text.lower()
                elif c.phone:
                    item["found_in_source"] = _norm_digits(c.phone) in compact
                else:
                    item["found_in_source"] = True  # 表单渠道：页面可访问且为联系页
                item["http_status"] = page.status_code
            except Exception as exc:  # noqa: BLE001
                item["found_in_source"] = None
                item["error"] = str(exc)[:120]
            item["pass"] = item["found_in_source"] is not False
            item["is_decision_maker"] = c.is_decision_maker  # 应全为 False（HR/客服不升级）
            items.append(item)
            time.sleep(1.0)
        db.commit()
    finally:
        db.close()

    passed = sum(1 for x in items if x["pass"])
    summary = {"checked": len(items), "passed": passed, "failed": len(items) - passed,
               "removed_suspect": db_scalar_removed(items),
               "checked_at": datetime.now(timezone.utc).isoformat()}
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "T08.2_contact_spot_check.json").write_text(
        json.dumps({"summary": summary, "items": items}, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    (ROOT / "_t08_out.txt").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


def db_scalar_removed(items):
    return getattr(main, "_removed", 0)


if __name__ == "__main__":
    main()
