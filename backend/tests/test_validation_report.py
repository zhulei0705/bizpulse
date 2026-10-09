"""T07 实验报告与 CSV 导出测试。"""
from tests.helpers_t06 import make_company, make_experiment, make_target


def _interaction(client, exp, target, **overrides):
    body = {"company_id": target["company_id"], "experiment_id": exp["id"], "target_id": target["id"]}
    body.update(overrides)
    return client.post("/api/v1/interactions", json=body)


def _advance(client, target, *statuses):
    for s in statuses:
        client.patch(f"/api/v1/experiment-targets/{target['id']}", json={"status": s})


def test_report_reject_distribution_from_real_outcomes(client):
    exp = make_experiment(client, status="RUNNING")
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"], with_opportunity=False)
    _advance(client, target, "RESEARCHING", "READY_TO_CONTACT", "CONTACTED", "REPLIED", "QUALIFIED", "MEETING", "QUOTED")
    client.patch(f"/api/v1/experiment-targets/{target['id']}", json={
        "status": "REJECTED", "reject_reason": "PRICE_HIGH",
    })
    report = client.get(f"/api/v1/experiments/{exp['id']}/report").json()["data"]
    assert report["real_results"]["reject_reason_distribution"] == {"PRICE_HIGH": 1}


def test_report_reply_distribution_from_real_replies(client):
    exp = make_experiment(client, status="RUNNING")
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"], with_opportunity=False)
    _advance(client, target, "RESEARCHING", "READY_TO_CONTACT", "CONTACTED")
    _interaction(client, exp, target, interaction_type="REPLY", direction="INBOUND", result="NEED_MORE_INFO")
    report = client.get(f"/api/v1/experiments/{exp['id']}/report").json()["data"]
    assert report["real_results"]["reply_category_distribution"] == {"NEED_MORE_INFO": 1}


def test_report_score_buckets_track_reply(client):
    """Opportunity 质量指标：分数桶 × 真实回复（任务书四十九）。"""
    exp = make_experiment(client, status="RUNNING")
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"])
    _advance(client, target, "RESEARCHING", "READY_TO_CONTACT", "CONTACTED")
    _interaction(client, exp, target, interaction_type="REPLY", direction="INBOUND", result="POSITIVE")
    report = client.get(f"/api/v1/experiments/{exp['id']}/report").json()["data"]
    buckets = report["real_results"]["opportunity_score_buckets"]
    assert buckets, "至少一个分数桶"
    bucket = next(iter(buckets.values()))
    assert bucket["count"] == 1
    assert bucket["replied"] == 1


def test_csv_export_contains_real_columns(client):
    import csv
    import io

    exp = make_experiment(client, status="RUNNING")
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"], with_opportunity=False)
    _advance(client, target, "RESEARCHING", "READY_TO_CONTACT", "CONTACTED")

    resp = client.get(f"/api/v1/experiments/{exp['id']}/export.csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    rows = list(csv.reader(io.StringIO(resp.content.decode("utf-8-sig"))))
    header = rows[0]
    for col in ["company", "opportunity_score", "contact_status", "reply", "meeting", "quote", "outcome", "reject_reason", "selection_reason"]:
        assert col in header, f"CSV 缺少列 {col}"
    data_row = rows[1]
    assert data_row[header.index("company")] == company["company_name"]
    assert data_row[header.index("contact_status")] == "CONTACTED"


def test_report_404_for_missing_experiment(client):
    assert client.get("/api/v1/experiments/exp_missing/report").status_code == 404
    assert client.get("/api/v1/experiments/exp_missing/export.csv").status_code == 404
