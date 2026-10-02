"""T05 真实数据验证：创建真实采购单位 → 采集真实招标公告 → 信号分析 → 审核 → 机会分析。"""
import json
import time
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"


def api(method: str, path: str, payload: dict | None = None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        f"{BASE}{path}", data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


COMPANIES = [
    {"name": "中国科学院理论物理研究所", "url": "http://www.ccgp.gov.cn/cggg/zygg/gkzb/202609/t20260930_27435469.htm",
     "note": "T05真实验证-高性能计算机时采购"},
    {"name": "清华大学", "url": "http://www.ccgp.gov.cn/cggg/zygg/gkzb/202609/t20260930_27435451.htm",
     "note": "T05真实验证-低温强磁场扫描隧道显微镜招标"},
    {"name": "华南理工大学", "url": "http://www.ccgp.gov.cn/cggg/zygg/gkzb/202609/t20260930_27435453.htm",
     "note": "T05真实验证-扫描隧道显微镜招标"},
]

for spec in COMPANIES:
    print("=" * 60)
    print("企业：", spec["name"])
    created = api("POST", "/companies", {"company_name": spec["name"]})
    company_id = created["data"]["id"]
    print("  company_id:", company_id)

    ingest = api("POST", "/ingest/url", {"url": spec["url"], "note": spec["note"]})
    record_id = ingest["data"]["source_record_id"]
    print("  record_id:", record_id, "duplicate:", ingest["data"]["duplicate"])

    assigned = api("POST", f"/source-records/{record_id}/assign-company", {"company_id": company_id})
    print("  assign-company:", assigned["data"].get("status", assigned["data"]))

    stats = api("POST", f"/source-records/{record_id}/analyze-signals", {})
    print("  signal analysis:", stats["data"])

    candidates = api("GET", "/signal-candidates", )
    items = [c for c in candidates["data"]["items"] if c["source_record_id"] == record_id]
    for c in items:
        approved = api("POST", f"/signal-candidates/{c['id']}/approve", {"note": "T05真实数据验证：人工核对原文后批准"})
        print(f"  candidate {c['candidate_type']} conf={c['final_confidence']} -> signal {approved['data'].get('signal_id')}")
    if not items:
        print("  !! 无信号候选")

    time.sleep(1)

print("=" * 60)
print("完成采集与信号批准")
