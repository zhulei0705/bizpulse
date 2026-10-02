# -*- coding: utf-8 -*-
"""T05 真实数据验证脚本：对已批准信号的公司强制重新运行机会分析，
输出候选分数明细（含 evidence 分），验证来源等级修复（C→A）对评分的影响。
用法：python t05_real_analyze.py
"""
import json
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"

# 三家真实验证公司（上个会话入库：中科院理论物理研究所 / 清华大学 / 华南理工大学）
TARGETS = ["中国科学院理论物理研究所", "清华大学", "华南理工大学"]


def call(method: str, path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    # 1. 找到目标公司
    companies = {}
    page = 1
    while True:
        r = call("GET", f"/companies?page={page}&page_size=50")
        items = r["data"]["items"]
        for c in items:
            companies[c["company_name"]] = c["id"]
        if len(items) < 50 or page > 10:
            break
        page += 1

    missing = [n for n in TARGETS if n not in companies]
    if missing:
        raise SystemExit(f"未找到公司：{missing}；现有：{sorted(companies)}")

    # 2. 逐家强制重新分析
    for name in TARGETS:
        cid = companies[name]
        r = call("POST", f"/companies/{cid}/analyze-opportunities", {"force": True})
        d = r["data"]
        print(f"\n=== {name} ===")
        print(f"  status={d['status']} reason={d['reason']} created={d['candidates_created']} "
              f"updated={d['candidates_updated']} need_more_evidence={d['need_more_evidence']} "
              f"bundles={d['bundles']} llm_used={d['llm_used']}")

        # 3. 输出该公司的候选分数明细
        cr = call("GET", f"/opportunity-candidates?company_id={cid}&page_size=20")
        for cand in cr["data"]["items"]:
            print(f"  候选[{cand['id']}] {cand['title']}")
            print(f"    status={cand['status']} total={cand['total_score']} grade={cand['grade']} "
                  f"cap={cand.get('grade_cap_reason')}")
            bd = cand.get("score_breakdown") or {}
            if bd:
                print(f"    breakdown: {json.dumps(bd, ensure_ascii=False)}")

    # 4. 汇总所有候选状态
    print("\n--- 全部候选 ---")
    cr = call("GET", "/opportunity-candidates?page_size=50")
    for cand in cr["data"]["items"]:
        print(f"  {cand['title']:<30} status={cand['status']:<18} total={cand['total_score']:<6} "
              f"grade={cand['grade']}")


if __name__ == "__main__":
    main()
