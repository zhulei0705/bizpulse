"""只读正式库保护快照与依赖/Git审计，不创建业务记录。"""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT.parent / "docs/reports/t10_c1"
OUT.mkdir(parents=True, exist_ok=True)
def snapshot():
    with sqlite3.connect(f"file:{ROOT / 'data/bizpulse.db'}?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        tables = ["experiments", "experiment_targets", "interactions", "quotes", "experiment_outcomes", "companies", "signals", "opportunities"]
        return {t: [dict(r) for r in db.execute(f"SELECT * FROM {t} ORDER BY id")] for t in tables}
if __name__ == "__main__":
    name = sys.argv[1]
    state = snapshot()
    # 不发布客户原始数据；仅保存每张表的稳定哈希与行数。
    import hashlib
    hashes = {t: {"count": len(rows), "sha256": hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()).hexdigest()} for t,rows in state.items()}
    (OUT / f"protected_{name}.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
    for filename, command in ((f"git_{name}.txt", ["git", "status", "--short"]),
                              (f"dependencies_{name}.txt", [sys.executable, "-m", "pip", "freeze"])):
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        (OUT / filename).write_text(result.stdout, encoding="utf-8")
    print(json.dumps(hashes))
