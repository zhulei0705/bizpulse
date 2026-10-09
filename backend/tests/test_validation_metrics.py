"""T07 验证指标测试：reachable_rate / positive_reply_rate（真实联系人驱动）。"""
from tests.helpers_t06 import make_company, make_contact, make_experiment, make_target


def _interaction(client, exp, target, **overrides):
    body = {"company_id": target["company_id"], "experiment_id": exp["id"], "target_id": target["id"]}
    body.update(overrides)
    return client.post("/api/v1/interactions", json=body)


def _advance(client, target, *statuses):
    for s in statuses:
        client.patch(f"/api/v1/experiment-targets/{target['id']}", json={"status": s})


def test_reachable_rate_counts_companies_with_real_contacts(client):
    """Reachable Rate = 有真实可用联系人的目标企业 / 目标企业总数。"""
    exp = make_experiment(client, status="RUNNING")
    c1 = make_company(client)
    c2 = make_company(client)
    t1 = make_target(client, exp["id"], c1["id"], with_opportunity=False)
    t2 = make_target(client, exp["id"], c2["id"], with_opportunity=False)
    make_contact(client, c1["id"], verified=True)  # 只有 c1 可触达

    metrics = client.get(f"/api/v1/experiments/{exp['id']}/metrics").json()["data"]
    assert metrics["reachable_count"] == 1
    assert metrics["reachable_rate"] == 50.0
    assert t1 and t2  # 两个目标都在


def test_positive_reply_rate(client):
    exp = make_experiment(client, status="RUNNING")
    c1 = make_company(client)
    c2 = make_company(client)
    t1 = make_target(client, exp["id"], c1["id"], with_opportunity=False)
    t2 = make_target(client, exp["id"], c2["id"], with_opportunity=False)
    for t in (t1, t2):
        _advance(client, t, "RESEARCHING", "READY_TO_CONTACT", "CONTACTED")
    _interaction(client, exp, t1, interaction_type="REPLY", direction="INBOUND", result="POSITIVE")
    _interaction(client, exp, t2, interaction_type="REPLY", direction="INBOUND", result="NOT_NOW")

    metrics = client.get(f"/api/v1/experiments/{exp['id']}/metrics").json()["data"]
    assert metrics["replied"] == 2
    assert metrics["reply_rate"] == 100.0
    assert metrics["positive_reply_rate"] == 50.0


def test_no_reply_no_positive_rate(client):
    """0 回复时 positive_reply_rate 为 0，不除零。"""
    exp = make_experiment(client, status="RUNNING")
    company = make_company(client)
    make_target(client, exp["id"], company["id"], with_opportunity=False)
    metrics = client.get(f"/api/v1/experiments/{exp['id']}/metrics").json()["data"]
    assert metrics["positive_reply_rate"] == 0
