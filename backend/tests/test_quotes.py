"""T06 报价测试：状态保护（VIEWED 不假设）、报价≠收入、目标联动。"""
from tests.helpers_t06 import make_company, make_experiment, make_target


def _quote_body(client, company_id, exp_id, target_id, **overrides):
    body = {
        "company_id": company_id, "experiment_id": exp_id, "target_id": target_id,
        "amount": 9800, "currency": "CNY", "billing_type": "PILOT",
        "scope": "海外线索挖掘 1 个月试点",
    }
    body.update(overrides)
    return body


def test_quote_created_and_advances_target(client):
    exp = make_experiment(client, status="RUNNING")
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"])
    # 先推进到 MEETING
    client.patch(f"/api/v1/experiment-targets/{target['id']}", json={"status": "RESEARCHING"})
    client.patch(f"/api/v1/experiment-targets/{target['id']}", json={"status": "READY_TO_CONTACT"})
    client.patch(f"/api/v1/experiment-targets/{target['id']}", json={"status": "CONTACTED"})

    resp = client.post("/api/v1/quotes", json=_quote_body(client, company["id"], exp["id"], target["id"], status="SENT"))
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "SENT"
    assert data["sent_at"]

    row = next(x for x in client.get(f"/api/v1/experiments/{exp['id']}/targets").json()["data"] if x["id"] == target["id"])
    assert row["status"] == "QUOTED"


def test_quote_viewed_requires_sent(client):
    """关键：没有发送过的报价不能假设客户已查看（VIEWED）。"""
    exp = make_experiment(client)
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"])
    resp = client.post("/api/v1/quotes", json=_quote_body(client, company["id"], exp["id"], target["id"], status="VIEWED", sent_at=None))
    assert resp.status_code == 422
    assert "VIEWED" in resp.json()["detail"]


def test_quote_status_enum_guard(client):
    exp = make_experiment(client)
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"])
    created = client.post("/api/v1/quotes", json=_quote_body(client, company["id"], exp["id"], target["id"])).json()["data"]
    bad = client.patch(f"/api/v1/quotes/{created['id']}", json={"status": "MAYBE_READ"})
    assert bad.status_code == 422


def test_quotes_not_counted_as_revenue(client):
    """关键测试 3：只有报价不能算 Revenue。"""
    exp = make_experiment(client, status="RUNNING")
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"])
    client.post("/api/v1/quotes", json=_quote_body(client, company["id"], exp["id"], target["id"], status="ACCEPTED"))
    metrics = client.get(f"/api/v1/experiments/{exp['id']}/metrics").json()["data"]
    assert metrics["contracted_revenue"] == 0
    assert metrics["received_revenue"] == 0
    assert metrics["quotes"] >= 1
