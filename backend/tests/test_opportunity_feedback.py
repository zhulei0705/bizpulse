"""T06 Opportunity Feedback 测试：预测 Score vs 真实结果（只积累数据，不自动训练）。"""
from tests.helpers_t06 import make_company, make_experiment, make_target


def test_feedback_created_on_rejection(client):
    """目标被真实拒绝 → 自动生成 opportunity_feedback（预测分 + 拒绝原因）。"""
    exp = make_experiment(client, status="RUNNING")
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"])  # 带已审核机会
    for status in ["RESEARCHING", "READY_TO_CONTACT", "CONTACTED"]:
        client.patch(f"/api/v1/experiment-targets/{target['id']}", json={"status": status})
    rejected = client.patch(f"/api/v1/experiment-targets/{target['id']}", json={
        "status": "REJECTED", "reject_reason": "ALREADY_HAVE_SOLUTION", "notes": "客户明确说已有供应商",
    })
    assert rejected.status_code == 200

    feedback = client.get(f"/api/v1/opportunities/{target['opportunity_id']}/feedback").json()["data"]
    assert len(feedback) == 1
    row = feedback[0]
    assert row["predicted_score"] == target.get("opportunity_score") or row["predicted_score"] > 0
    assert row["actual_reply"] is False
    assert row["actual_win"] is False
    assert row["reject_reason"] == "ALREADY_HAVE_SOLUTION"


def test_feedback_created_on_win(client):
    exp = make_experiment(client, status="RUNNING")
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"])
    for status in ["RESEARCHING", "READY_TO_CONTACT", "CONTACTED", "REPLIED", "QUALIFIED", "MEETING", "QUOTED", "PILOT"]:
        assert client.patch(f"/api/v1/experiment-targets/{target['id']}", json={"status": status}).status_code == 200
    won = client.patch(f"/api/v1/experiment-targets/{target['id']}", json={"status": "WON", "contract_amount": 9800})
    assert won.status_code == 200

    feedback = client.get(f"/api/v1/opportunities/{target['opportunity_id']}/feedback").json()["data"]
    assert len(feedback) == 1
    row = feedback[0]
    assert row["actual_reply"] is True
    assert row["actual_meeting"] is True
    assert row["actual_quote"] is True
    assert row["actual_pilot"] is True
    assert row["actual_win"] is True
    assert row["actual_revenue"] == 9800
    assert row["predicted_score"] > 0  # helpers 创建的已审核机会预测分

    # 机会阶段同步为 WON
    opp = client.get(f"/api/v1/opportunities/{target['opportunity_id']}").json()["data"]
    assert opp["stage"] == "WON"


def test_feedback_empty_before_validation(client):
    exp = make_experiment(client)
    company = make_company(client)
    target = make_target(client, exp["id"], company["id"])
    feedback = client.get(f"/api/v1/opportunities/{target['opportunity_id']}/feedback").json()["data"]
    assert feedback == []
