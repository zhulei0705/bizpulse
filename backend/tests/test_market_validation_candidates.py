"""T07 市场验证候选测试：真实数据聚合、细分场景、人工决定原则。

注意：测试库为 session 级共享，聚合断言按本测试专属的 pain_category 场景过滤。
"""
import uuid

from fastapi.testclient import TestClient

from tests.helpers_t06 import make_approved_opportunity, make_company


def _unique_category() -> str:
    """用 uuid 后缀制造独立场景，避免与其他测试数据串场。"""
    return f"OTHER_{uuid.uuid4().hex[:6].upper()}"


def _seed(client: TestClient, category: str, *, industry: str | None = None):
    company = make_company(client)
    if industry:
        client.patch(f"/api/v1/companies/{company['id']}", json={"industry": industry})
    opp = make_approved_opportunity(client, company["id"], pain_category=category)
    return company, opp


def _candidate(data: dict, category: str) -> dict | None:
    return next((c for c in data["candidates"] if c["primary_pain"] == category), None)


def test_candidates_grouped_by_scenario(client):
    """市场候选按细分场景（pain_category）聚合，不是大行业。"""
    category = _unique_category()
    c1, o1 = _seed(client, category, industry="制造业")
    c2, o2 = _seed(client, category, industry="科研院所")

    data = client.get("/api/v1/markets/validation-candidates").json()["data"]
    candidate = _candidate(data, category)
    assert candidate is not None, data["candidates"]
    # 细分场景名（pain_category label），不是"制造业/互联网"这类大行业
    assert candidate["market_name"].endswith("场景")
    assert candidate["opportunity_count"] >= 2
    assert candidate["company_count"] >= 2
    assert {c1["company_name"], c2["company_name"]} <= set(candidate["company_names"])
    assert candidate["rank"] >= 1
    assert "机会" in candidate["recommendation_basis"]


def test_candidates_stats_from_real_data(client):
    category = _unique_category()
    company, opp = _seed(client, category, industry="教育")
    data = client.get("/api/v1/markets/validation-candidates").json()["data"]
    candidate = _candidate(data, category)
    assert candidate is not None
    # 该场景只有本测试种的企业（独立 category）
    assert candidate["company_names"] == [company["company_name"]]
    assert candidate["opportunity_count"] == 1
    assert candidate["avg_opportunity_score"] == opp["total_score"]
    # 没有真实联系人与回复时为 0（REAL_DATA_ONLY）
    assert candidate["reachable_company_count"] == 0
    assert candidate["replied_company_count"] == 0


def test_candidates_empty_when_no_approved_opportunity(client):
    """没有任何已审核机会的独立场景不输出候选（不硬凑）。"""
    category = _unique_category()
    make_company(client)  # 只建企业，不建机会
    data = client.get("/api/v1/markets/validation-candidates").json()["data"]
    assert _candidate(data, category) is None


def test_sufficiency_reports_shortfall_honestly(client):
    """数据充足性：真实不足时明确报缺口（任务书六十四），不生成假公司。"""
    category = _unique_category()
    _seed(client, category)
    data = client.get("/api/v1/markets/validation-candidates").json()["data"]["sufficiency"]
    assert data["company_count"] >= 1
    assert data["target_count"] == 30
    assert data["shortfall"] == data["target_count"] - data["eligible_company_count"]
    assert data["sufficient"] is (data["shortfall"] == 0)
    if data["shortfall"] > 0:
        assert "不足" in data["message"]


def test_candidates_require_approved_only(client):
    """未审核机会不计入市场候选。"""
    category = _unique_category()
    company = make_company(client)
    source = client.post("/api/v1/sources", json={
        "name": f"源未审核{uuid.uuid4().hex[:5]}", "source_type": "OFFICIAL_WEBSITE",
        "base_url": "https://unrev.example.com", "reliability_grade": "A", "reliability_score": 90,
    }).json()["data"]
    record = client.post(f"/api/v1/sources/{source['id']}/records", json={
        "company_id": company["id"], "url": "https://unrev.example.com/a", "title": "t",
    }).json()["data"]
    signal = client.post("/api/v1/signals", json={
        "company_id": company["id"], "source_record_id": record["id"],
        "signal_type": "SALES_HIRING", "title": "招聘", "confidence": 80,
    }).json()["data"]
    client.post("/api/v1/opportunities", json={
        "company_id": company["id"], "primary_signal_id": signal["id"],
        "title": "未审核", "problem": "x", "solution": "y",
        "pain_score": 80, "budget_score": 80, "intent_score": 80,
        "urgency_score": 80, "agent_fit_score": 80, "reachability_score": 60, "evidence_score": 40,
    })
    data = client.get("/api/v1/markets/validation-candidates").json()["data"]
    # 未审核机会不产生场景候选（同场景其他测试数据不受影响）
    assert _candidate(data, category) is None
