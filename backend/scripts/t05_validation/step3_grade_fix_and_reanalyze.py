"""T05 真实数据验证（第二轮）：来源等级人工修正 A、误报信号驳回、重新分析。"""
import json
import time
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"


def api(method: str, path: str, payload: dict | None = None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


TARGETS = {"中国科学院理论物理研究所", "清华大学", "华南理工大学"}

# 1) 来源等级人工修正：ccgp.gov.cn 为政府官方来源 → A
sources = api("GET", "/sources?page_size=100")["data"]["items"]
for source in sources:
    if source.get("base_url") and "ccgp.gov.cn" in (source.get("base_url") or ""):
        patched = api("PATCH", f"/sources/{source['id']}", {"reliability_grade": "A", "reliability_score": 95})
        print(f"来源升级 A：{source['name']} -> {patched['data']['reliability_grade']}")

# 2) 人工驳回误报信号
signals = api("GET", "/signals?page_size=100")["data"]["items"]
companies = {c["id"]: c["company_name"] for c in api("GET", "/companies?page_size=100")["data"]["items"]}
for signal in signals:
    cname = companies.get(signal["company_id"], "")
    if cname not in TARGETS:
        continue
    if signal["signal_type"] in {"NEW_PRODUCT", "POLICY_IMPACT"}:
        rejected = api("POST", f"/signals/{signal['id']}/reject",
                       {"note": "人工检查：规则误报（公告页导航/政策字样触发），与招标事实无关"})
        print(f"驳回误报信号：{cname} {signal['signal_type']} -> {rejected['data']['status']}")

# 3) 重新分析（force 跳过输入 hash——因为信号状态变化应已改变 hash，但 force 确保刷新）
for company in api("GET", "/companies?page_size=100")["data"]["items"]:
    if company["company_name"] in TARGETS:
        result = api("POST", f"/companies/{company['id']}/analyze-opportunities", {"force": True})
        print(f"重新分析 {company['company_name']}: created={result['data']['candidates_created']} updated={result['data']['candidates_updated']}")

# 4) 输出候选（人工检查视图）
cands = api("GET", "/opportunity-candidates?page_size=50")["data"]
print(f"\n共 {cands['total']} 个候选\n")
for item in cands["items"]:
    if item["company_name"] not in TARGETS:
        continue
    print("-" * 72)
    print(f"【{item['status']}】{item['title']}")
    print(f"  总分 {item['total_score']} / {item['grade']} (cap={item['grade_cap_reason']})  置信度 {item['confidence']}")
    print(f"  分项: pain={item['pain_score']} budget={item['budget_score']} intent={item['intent_score']} "
          f"urgency={item['urgency_score']} fit={item['agent_fit_score']} reach={item['reachability_score']} evidence={item['evidence_score']}")
    print(f"  Pain: {item['pain_category_label']} | 下一步: {item['recommended_next_action']}")
    print(f"  why_now: {item['why_now']}")
    print(f"  风险: {'; '.join(item['risk_notes'])}")
    breakdown = item.get("score_breakdown") or {}
    budget_reasons = (breakdown.get("budget") or {}).get("reasons") or []
    print(f"  Budget依据: {'; '.join(budget_reasons[:2])}")
