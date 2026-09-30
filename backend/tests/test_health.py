def test_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["service"] == "BizPulse"


def test_system_info(client):
    response = client.get("/api/v1/system/info")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "商脉 BizPulse"
    assert data["database"] == "connected"
    assert data["no_fake_data"] is True
