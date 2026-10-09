"""T08 企业数据质量测试：代码计算（官网/行业/地区/类型/来源/验证时间），LLM 不参与。"""
import uuid

from app.db.session import SessionLocal
from app.models.company import Company
from app.services.company_quality import compute_data_quality, refresh_company_quality, signal_density


def _mk_company(**overrides) -> Company:
    suffix = uuid.uuid4().hex[:6]
    defaults = dict(company_name=f"质量企业{suffix}", normalized_name=f"zl{suffix}", source_count=0)
    defaults.update(overrides)
    company = Company(**defaults)
    return company


def test_quality_empty_company_low():
    with SessionLocal() as db:
        company = _mk_company()
        db.add(company)
        db.commit()
        score = compute_data_quality(db, company)
        assert score <= 10  # 空档案几乎无分


def test_quality_full_profile_high():
    with SessionLocal() as db:
        from datetime import datetime, timezone
        company = _mk_company(
            domain="quality-full.example.com", industry="制造业", city="苏州",
            organization_type="COMPANY", verification_status="WEBSITE_VERIFIED",
            verified_at=datetime.now(timezone.utc),
        )
        db.add(company)
        db.commit()
        score = compute_data_quality(db, company)
        assert score >= 85  # 官网30+行业15+地区15+类型15+验证时间10+记录10=95（截断100）
        refreshed = refresh_company_quality(db, company)
        assert company.company_data_quality == refreshed


def test_signal_density_counts(db_session=None):
    with SessionLocal() as db:
        from datetime import datetime, timedelta, timezone

        from app.models.signal import Signal
        from tests.helpers_t06 import make_approved_opportunity
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            suffix = uuid.uuid4().hex[:6]
            company = client.post("/api/v1/companies", json={"company_name": f"密度企业{suffix}"}).json()["data"]
            source = client.post("/api/v1/sources", json={
                "name": f"密度源{suffix}", "source_type": "OFFICIAL_WEBSITE",
                "base_url": "https://density.example.com", "reliability_grade": "A", "reliability_score": 92,
            }).json()["data"]
            record = client.post(f"/api/v1/sources/{source['id']}/records", json={
                "company_id": company["id"], "url": f"https://density.example.com/{suffix}", "title": "t",
            }).json()["data"]
            make_approved_opportunity(client, company["id"])

            # 45 天前的一条旧信号
            old_signal = Signal(
                company_id=company["id"], source_record_id=record["id"], signal_type="HIRING",
                title="旧信号", confidence=70, status="APPROVED", fact_or_inference="FACT",
                collected_at=datetime.now(timezone.utc) - timedelta(days=45),
            )
            db.add(old_signal)
            db.commit()

            density = signal_density(db, company["id"])
            assert density["signals_7d"] >= 1  # T04 流程产出的是新信号
            assert density["signals_30d"] >= 1
            assert density["signals_90d"] >= density["signals_30d"] + 1  # 45 天前的旧信号计入 90d
