def test_core_business_chain(client):
    company = client.post("/api/v1/companies", json={"company_name": "真实测试企业"})
    assert company.status_code == 200
    company_id = company.json()["data"]["id"]

    source = client.post("/api/v1/sources", json={
        "name": "官方来源测试",
        "source_type": "OFFICIAL_WEBSITE",
        "base_url": "https://example.com",
        "reliability_grade": "A",
        "reliability_score": 95
    })
    assert source.status_code == 200
    source_id = source.json()["data"]["id"]

    record = client.post(f"/api/v1/sources/{source_id}/records", json={
        "company_id": company_id,
        "url": "https://example.com/news/1",
        "title": "公开测试记录",
        "raw_text": "这是单元测试写入的明确测试数据，不是生产数据。"
    })
    assert record.status_code == 200
    record_id = record.json()["data"]["id"]

    signal = client.post("/api/v1/signals", json={
        "company_id": company_id,
        "source_record_id": record_id,
        "signal_type": "HIRING",
        "title": "测试招聘信号",
        "confidence": 90,
        "reliability_score": 95
    })
    assert signal.status_code == 200
    signal_id = signal.json()["data"]["id"]

    opportunity = client.post("/api/v1/opportunities", json={
        "company_id": company_id,
        "primary_signal_id": signal_id,
        "title": "测试机会",
        "problem": "测试问题",
        "solution": "测试方案",
        "pain_score": 90,
        "budget_score": 90,
        "intent_score": 90,
        "urgency_score": 80,
        "agent_fit_score": 90,
        "reachability_score": 70,
        "evidence_score": 40,
        "confidence": 80
    })
    assert opportunity.status_code == 200
    data = opportunity.json()["data"]
    assert data["grade"] == "B"  # evidence gate

    dashboard = client.get("/api/v1/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["data"]["today_new_companies"] >= 1
