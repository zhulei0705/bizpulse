"""T05 真实数据验证（第三轮）：人工审核闭环 + 批量 job + 正式机会详情检查。"""
import json
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"


def api(method: str, path: str, payload: dict | None = None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


TARGETS = {"中国科学院理论物理研究所", "清华大学", "华南理工大学"}
cands = [c for c in api("GET", "/opportunity-candidates?page_size=50")["data"]["items"]
         if c["company_name"] in TARGETS]

# 1) 人工审核：批准理论物理所（真实判断：官方招标、预算 400 万明确、截止日期临近，值得进入验证）
target = next(c for c in cands if c["company_name"] == "中国科学院理论物理研究所")
approved = api("POST", f"/opportunity-candidates/{target['id']}/approve",
               {"note": "人工检查：真实招标公告（ccgp.gov.cn 官方），预算400万明确，投标截止2026-10-21，批准进入正式机会队列"})
print("审核通过:", json.dumps(approved["data"], ensure_ascii=False))

opp_id = approved["data"]["opportunity_id"]
detail = api("GET", f"/opportunities/{opp_id}")["data"]
print("\n正式机会详情检查：")
print("  title:", detail["title"])
print("  stage:", detail["stage"], "review_status:", detail["review_status"], "grade:", detail["grade"])
print("  why_now:", (detail["why_now"] or "")[:80])
print("  risk_notes:", detail["risk_notes"])
print("  validation_questions:", detail["validation_questions"][:2])
print("  score_breakdown keys:", sorted((detail.get("score_breakdown") or {}).keys()))
print("  recommended_next_action:", detail["recommended_next_action"])
print("  evidence_count:", detail["evidence_count"])
print("  evidences[0]:", json.dumps(detail["evidences"][0], ensure_ascii=False)[:200] if detail.get("evidences") else None)

# 2) 批量分析 job（真实运行：输入 hash 未变的企业应跳过）
job = api("POST", "/jobs/analyze-opportunities", {})
print("\n批量分析 job:", json.dumps(job["data"], ensure_ascii=False))

# 3) STALE 验证已在单元测试覆盖；检查审计日志包含 T05 动作
logs = api("GET", "/logs/audit?page_size=30")["data"]["items"]
t05_actions = [l["action"] for l in logs if l["action"].startswith(("OPPORTUNITY", "CANDIDATE"))]
print("\nT05 审计动作（最近）:", t05_actions[:8])
