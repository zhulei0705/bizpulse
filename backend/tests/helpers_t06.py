"""T06 测试辅助：实验/目标/互动/联系人构造器（走真实 API，保证校验路径一致）。"""
import uuid
from datetime import datetime,timezone

from fastapi.testclient import TestClient

from app.db.session import SessionLocal


def uniq(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:6]}"


def make_company(client: TestClient, name: str | None = None, *, domain: str | None = None) -> dict:
    suffix = uuid.uuid4().hex[:6]
    return client.post("/api/v1/companies", json={
        "company_name": name or f"验证企业{suffix}",
        "domain": domain or f"{suffix}.example.com",
    }).json()["data"]


def make_experiment(client: TestClient, **overrides) -> dict:
    body = {
        "name": f"获客验证实验{uniq()}",
        "hypothesis": "制造业海外获客依赖人工，AI 线索挖掘可显著缩短时间",
        "target_customer": "20~200 人制造企业",
        "value_proposition": "降低销售寻找海外潜在客户所需时间",
        "offer_description": "海外线索挖掘 SaaS（试点）",
        "price_amount": 9800,
        "price_currency": "CNY",
        "price_type": "PILOT",
        "target_company_count": 30,
        "target_contacts": 30,
        "target_replies": 5,
        "target_meetings": 3,
        "target_quotes": 2,
        "target_pilots": 1,
        "target_wins": 1,
        "success_criteria": "回复率>=10%；至少1个付费试点",
        "failure_criteria": "回复率<3%",
        "status": "READY",
    }
    body.update(overrides)
    resp = client.post("/api/v1/experiments", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def make_approved_opportunity(client: TestClient, company_id: str, *, pain_category: str = "SALES_EFFICIENCY") -> dict:
    """创建信号 + 机会并人工审核通过（READY），可直接加入实验。

    pain_category：关联一个带类别的 PainPoint（T07 市场候选按场景聚合时使用）。
    """
    suffix = uuid.uuid4().hex[:6]
    published=datetime.now(timezone.utc).isoformat()
    source = client.post("/api/v1/sources", json={
        "name": f"验证来源{suffix}", "source_type": "OFFICIAL_WEBSITE",
        "base_url": "https://t06.example.com", "reliability_grade": "A", "reliability_score": 92,
    }).json()["data"]
    record = client.post(f"/api/v1/sources/{source['id']}/records", json={
        "company_id": company_id, "url": f"https://t06.example.com/news/{suffix}", "title": "官方公告",
        "raw_text": '离线夹具：招聘海外销售经理，公告时间 '+published,
        "published_at": published,
    }).json()["data"]
    signal = client.post("/api/v1/signals", json={
        "company_id": company_id, "source_record_id": record["id"],
        "signal_type": "SALES_HIRING", "title": "招聘海外销售经理", "confidence": 85,
        "published_at": published,
    }).json()["data"]
    pain = client.post("/api/v1/pain-points", json={
        "company_id": company_id, "category": pain_category,
        "description": "海外线索获取依赖人工，每周投入大量时间", "confidence": 70, "status": "INFERRED",
    }).json()["data"]
    opp = client.post("/api/v1/opportunities", json={
        "company_id": company_id, "primary_signal_id": signal["id"], "pain_point_id": pain["id"],
        "title": "海外销售线索获取自动化", "problem": "海外线索获取依赖人工", "solution": "AI 自动化线索获取",
        "pain_score": 90, "budget_score": 90, "intent_score": 90,
        "urgency_score": 80, "agent_fit_score": 90, "reachability_score": 70,
        "evidence_score": 65, "confidence": 80,
        "validation_questions": [
            "目前这项工作是谁负责？",
            "每周大约投入多少时间？",
            "现在怎么解决？最大的问题是什么？",
        ],
    }).json()["data"]
    approved = client.post(f"/api/v1/opportunities/{opp['id']}/review", json={"action": "approve", "note": "T06 测试审核"})
    assert approved.status_code == 200, approved.text
    # 人工批准信号（真实操作：Signal 必须人工批准才能进入机会分析）
    from app.models.signal import Signal as SignalModel

    with SessionLocal() as db:
        row = db.get(SignalModel, signal["id"])
        row.status = "APPROVED"
        db.commit()
    return client.get(f"/api/v1/opportunities/{opp['id']}").json()["data"]


def make_target(client: TestClient, experiment_id: str, company_id: str, *, with_opportunity: bool = True) -> dict:
    opportunity_id = None
    if with_opportunity:
        opportunity_id = make_approved_opportunity(client, company_id)["id"]
    resp = client.post(f"/api/v1/experiments/{experiment_id}/targets", json={
        "company_id": company_id, "opportunity_id": opportunity_id,
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def make_contact(client: TestClient, company_id: str, *, verified: bool = True, email: str | None = None) -> dict:
    suffix = uuid.uuid4().hex[:6]
    body = {
        "name": f"联系人{suffix}",
        "title": "采购负责人",
        "email": email or f"buyer{suffix}@t06-company.example.com",
        "source_type": "OFFICIAL_WEBSITE",
    }
    if verified:
        body["verification_status"] = "VERIFIED_PUBLIC"
        body["source_url"] = f"https://t06-company.example.com/contact/{suffix}"
    else:
        body["verification_status"] = "UNVERIFIED"
    resp = client.post(f"/api/v1/companies/{company_id}/contacts", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]
