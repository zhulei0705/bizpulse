"""T08.2 Validation Ready v2 回归（任务书二十八）：需要 ACTIONABLE_NOW 信号。"""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.company import Company
from app.models.signal import Signal
from tests.helpers_t06 import make_company, make_approved_opportunity

NOW = datetime.now(timezone.utc)


def _verify(client, company_id: str):
    with TestClient(app):
        with SessionLocal() as db:
            row = db.get(Company, company_id)
            row.verification_status = "WEBSITE_VERIFIED"
            row.organization_type = "COMPANY"
            db.commit()


def test_full_chain_with_hiring_signal_is_ready(client):
    """完整链路 + SALES_HIRING（当前行为 → ACTIONABLE_NOW）→ ready。"""
    company = make_company(client)
    make_approved_opportunity(client, company["id"])  # SALES_HIRING 信号
    _verify(client, company["id"])

    data = client.get("/api/v1/companies/validation-ready").json()["data"]
    ids = [x["company_id"] for x in data["items"]]
    assert company["id"] in ids
    row = next(x for x in data["items"] if x["company_id"] == company["id"])
    assert row["checks"]["actionable_now_signal"] is True
    assert row["actionable_now_signal_count"] >= 1


def test_watch_only_company_not_ready():
    """仅有 WATCH 信号（过期事件，无 ACTIONABLE_NOW）的企业不得进入验证池（任务书二十八）。"""
    from app.services.validation_readiness import company_readiness

    suffix = uuid.uuid4().hex[:6]
    with SessionLocal() as db:
        c = Company(company_name=f"仅WATCH企业{suffix}", normalized_name=f"仅watch企业{suffix}".lower(),
                    organization_type="COMPANY", verification_status="WEBSITE_VERIFIED",
                    website="https://watchonly.example.com", domain="watchonly.example.com",
                    discovery_source_url="https://watchonly.example.com")
        db.add(c)
        db.flush()
        from app.models.source import Source, SourceRecord

        src = Source(name=f"WATCH源{suffix}", source_type="OFFICIAL_WEBSITE",
                     reliability_grade="B", reliability_score=75)
        db.add(src)
        db.flush()
        rec = SourceRecord(source_id=src.id, company_id=c.id,
                           url=f"https://watchonly.example.com/news/{suffix}",
                           title="新闻", raw_text="关于页事实：公司设有子公司（无日期）",
                           content_hash=f"h-{suffix}", http_status=200)
        db.add(rec)
        db.flush()
        # 带发布时间且超过 90 天 → 事件过期 → WATCH（不再当前行动窗口）
        sig = Signal(company_id=c.id, source_record_id=rec.id, signal_type="NEW_OFFICE",
                     title="旧闻", confidence=72, status="APPROVED",
                     published_at=NOW - timedelta(days=120), payload_json={})
        db.add(sig)
        db.commit()
        cid = c.id
        sid = sig.id

    state = company_readiness(SessionLocal(), cid)
    assert state["signal_actionability"][sid] == "WATCH"
    assert state["checks"]["actionable_now_signal"] is False
    assert state["validation_ready"] is False


def test_v2_checks_exposed_in_api(client):
    company = make_company(client)
    make_approved_opportunity(client, company["id"])
    _verify(client, company["id"])
    data = client.get("/api/v1/companies/validation-ready").json()["data"]
    row = next(x for x in data["items"] if x["company_id"] == company["id"])
    assert "actionable_now_signal" in row["checks"]
    assert "signal_actionability" in row
