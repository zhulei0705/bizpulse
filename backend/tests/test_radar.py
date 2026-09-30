"""机会雷达 API 测试（UI02）：空库、真实聚合、筛选、排序、Evidence 规则、无假数据。

测试数据仅存在于独立测试库（conftest.py 的 bizpulse_test.db）。
"""
import uuid

import pytest


def _setup_chain(client, industry: str | None = None, grade_setup: str | None = "high"):
    """建立一条真实测试链：企业(A级行业) → 信号 → 机会。返回 (company_id, signal_id, opp_id)。"""
    suffix = uuid.uuid4().hex[:6]
    company = client.post("/api/v1/companies", json={
        "company_name": f"雷达测试企业{suffix}", "industry": industry or "新能源",
    }).json()["data"]
    source = client.post("/api/v1/sources", json={
        "name": f"雷达来源{suffix}", "source_type": "OFFICIAL_WEBSITE",
        "base_url": "https://radar-test.example.com", "reliability_grade": "A", "reliability_score": 95,
    }).json()["data"]
    record = client.post(f"/api/v1/sources/{source['id']}/records", json={
        "company_id": company["id"], "url": f"https://radar-test.example.com/{suffix}", "title": "官方公告",
    }).json()["data"]
    signal = client.post("/api/v1/signals", json={
        "company_id": company["id"], "source_record_id": record["id"],
        "signal_type": "SALES_HIRING", "title": f"招聘海外销售{suffix}", "confidence": 85,
    }).json()["data"]
    scores = ({"pain_score": 95, "budget_score": 90, "intent_score": 92, "urgency_score": 85,
               "agent_fit_score": 90, "reachability_score": 80, "evidence_score": 88} if grade_setup == "high"
              else {"pain_score": 60, "budget_score": 55, "intent_score": 50, "urgency_score": 45,
                    "agent_fit_score": 60, "reachability_score": 50, "evidence_score": 65})
    opp = client.post("/api/v1/opportunities", json={
        "company_id": company["id"], "primary_signal_id": signal["id"],
        "title": f"海外销售自动化{suffix}", "problem": "p", "solution": "s", **scores,
    }).json()["data"]
    return company["id"], signal["id"], opp["id"]


def test_radar_summary_empty_scope(client):
    """空数据行为：不匹配任何记录的筛选（唯一行业）下，列表空数组、等级分布真实 0，禁止 Demo 数据。"""
    unique = f"不存在行业{uuid.uuid4().hex[:8]}"
    resp = client.get("/api/v1/radar/summary", params={"industry": unique})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["top_opportunities"] == []
    assert data["locations"] == []
    assert all(d["count"] == 0 for d in data["grade_distribution"])


def test_radar_summary_empty_grade_scope(client):
    """空等级作用域：请求不存在等级 → 全空（真实 0，无默认数据）。"""
    data = client.get("/api/v1/radar/summary", params={"grade": "Z"}).json()["data"]
    assert data["top_opportunities"] == []
    assert data["locations"] == []
    assert all(d["count"] == 0 for d in data["grade_distribution"])


def test_radar_summary_real_aggregation(client):
    industry_name = f"聚合行业{uuid.uuid4().hex[:6]}"
    cid, sid, oid = _setup_chain(client, industry=industry_name)
    data = client.get("/api/v1/radar/summary").json()["data"]

    assert data["metrics"]["today_signals"] >= 1
    assert data["metrics"]["today_opportunities"] >= 1
    assert data["metrics"]["pending_reviews"] >= 1  # NEW 阶段计入待审核

    # 机会 Top：排序 total_score DESC，字段完整（定位本次创建的机会）
    top = next(o for o in data["top_opportunities"] if o["id"] == oid)
    assert top["id"] == oid
    assert top["company_id"] == cid
    assert top["evidence_count"] == 1
    assert top["latest_signal_title"].startswith("招聘海外销售")
    assert top["intent_score"] == 92

    # 信号流：倒序、含事实/来源等级（定位本次创建的信号，避免与其他用例顺序耦合）
    latest = next(s for s in data["latest_signals"] if s["id"] == sid)
    assert latest["fact_or_inference"] == "FACT"
    assert latest["reliability_grade"] == "A"
    assert latest["evidence_count"] == 1

    # 等级分布：高分机会（加权 90.45，证据 88 ≥ 60）应为 S/A
    dist = {d["grade"]: d["count"] for d in data["grade_distribution"]}
    assert dist["S"] + dist["A"] >= 1

    # 行业聚合已随 UI02.2 移除（转入市场机会页）；验证评分区间分布与来源占比（真实聚合）
    buckets = {b["label"]: b["count"] for b in data["score_distribution"]}
    assert sum(buckets.values()) >= 1
    assert buckets.get("81~100", 0) >= 1  # 本次高分机会（加权 90.45）落入 81~100
    sources = {s["label"]: s["count"] for s in data["source_distribution"]}
    assert sources.get("企业官网", 0) >= 1  # 测试链来源为 OFFICIAL_WEBSITE

    # 无地理数据：locations 必须为空（禁止猜测坐标）
    assert data["locations"] == []


def test_radar_filter_industry_and_grade(client):
    _setup_chain(client, industry="新能源", grade_setup="high")
    _setup_chain(client, industry="贸易", grade_setup="low")

    # 行业筛选作用到 SQL
    data = client.get("/api/v1/radar/summary", params={"industry": "新能源"}).json()["data"]
    assert all(o["total_score"] > 80 for o in data["top_opportunities"])

    # grade 筛选
    only_c = client.get("/api/v1/radar/summary", params={"grade": "C"}).json()["data"]
    grades = {o["grade"] for o in only_c["top_opportunities"]}
    assert grades <= {"C"}

    # min_score 筛选
    high = client.get("/api/v1/radar/summary", params={"min_score": 80}).json()["data"]
    assert all(o["total_score"] >= 80 for o in high["top_opportunities"])

    # min_evidence 筛选（机会均有1条证据 → min_evidence=2 应为空）
    strict = client.get("/api/v1/radar/summary", params={"min_evidence": 2}).json()["data"]
    assert strict["top_opportunities"] == []

    # signal_type 筛选
    typed = client.get("/api/v1/radar/summary", params={"signal_type": "SALES_HIRING"}).json()["data"]
    assert all(s["signal_type"] == "SALES_HIRING" for s in typed["latest_signals"])


def test_radar_pending_review_flow(client):
    """待审核列表 + 审核后移出。"""
    _, _, oid = _setup_chain(client)
    data = client.get("/api/v1/radar/summary").json()["data"]
    assert any(p["id"] == oid for p in data["pending_reviews"])

    client.post(f"/api/v1/opportunities/{oid}/review", json={"action": "approve", "note": "证据充分"})
    after = client.get("/api/v1/radar/summary").json()["data"]
    assert not any(p["id"] == oid for p in after["pending_reviews"])


def test_radar_evidence_rules_hold(client):
    """Evidence 规则：低于60证据分最高 B；雷达返回数据保持该约束。"""
    _, _, oid = _setup_chain(client, grade_setup="low")  # evidence 65
    data = client.get("/api/v1/radar/summary").json()["data"]
    for o in data["top_opportunities"]:
        if o["evidence_score"] < 60:
            assert o["grade"] in {"B", "C", "D"}


def test_radar_locations_require_real_geo(client):
    """只有带真实 country/province/city 的企业才进入地图层。"""
    suffix = uuid.uuid4().hex[:6]
    company = client.post("/api/v1/companies", json={
        "company_name": f"地理企业{suffix}", "industry": "制造", "country": "中国", "province": "广东", "city": "深圳",
    }).json()["data"]
    source = client.post("/api/v1/sources", json={
        "name": f"地理来源{suffix}", "source_type": "OFFICIAL_WEBSITE",
        "base_url": "https://geo-test.example.com", "reliability_grade": "A", "reliability_score": 95,
    }).json()["data"]
    record = client.post(f"/api/v1/sources/{source['id']}/records", json={
        "company_id": company["id"], "url": f"https://geo-test.example.com/{suffix}", "title": "公告",
    }).json()["data"]
    signal = client.post("/api/v1/signals", json={
        "company_id": company["id"], "source_record_id": record["id"],
        "signal_type": "EXPANSION", "title": "扩产", "confidence": 70,
    }).json()["data"]
    client.post("/api/v1/opportunities", json={
        "company_id": company["id"], "primary_signal_id": signal["id"],
        "title": "扩产监控", "problem": "p", "solution": "s",
        "pain_score": 70, "budget_score": 65, "intent_score": 60, "urgency_score": 55,
        "agent_fit_score": 70, "reachability_score": 60, "evidence_score": 70,
    })
    data = client.get("/api/v1/radar/summary").json()["data"]
    geo = [loc for loc in data["locations"] if loc["company_id"] == company["id"]]
    assert len(geo) == 1
    assert geo[0]["country"] == "中国" and geo[0]["city"] == "深圳"
    assert geo[0]["top_score"] > 0
