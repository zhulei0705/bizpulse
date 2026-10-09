"""受控单页诊断，仅测试沙盒；保留本地 SDK 日志，不用于生产批量。"""
import json
import os
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from app.collectors.crawl_policy import SafeFetch
OUT=ROOT.parent/"docs/reports/t10_c1/diagnostic"
OUT.mkdir(parents=True,exist_ok=True)
client=SafeFetch({"quotes.toscrape.com"})
response=client.get("https://quotes.toscrape.com/js/page/1/")
payload=dict(url=response.final_url,html=response.text(),domains=sorted(client.domains),
             pins={k:sorted(v) for k,v in client.pins.items()},wait_ms=800,interval=2,
             bytes_used=client.bytes,requests_used=client.requests)
(OUT/"input.json").write_text(json.dumps(payload),encoding="utf-8")
env={k:v for k,v in os.environ.items() if k.upper() in {"PATH","SYSTEMROOT","WINDIR","TEMP","TMP","COMSPEC","LOCALAPPDATA","USERPROFILE","HOMEDRIVE","HOMEPATH"}}
env.update(PYTHONIOENCODING="utf-8",PLAYWRIGHT_BROWSERS_PATH=str(ROOT/".browsers"),CRAWL4_AI_BASE_DIRECTORY=str(ROOT/"data/crawl4ai_cache"))
with (OUT/"worker.log").open("w",encoding="utf-8") as log:
    proc=subprocess.run([sys.executable,"-m","app.collectors.crawl4ai_worker",str(OUT)],cwd=ROOT,env=env,stdout=log,stderr=log,timeout=50,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
print((OUT/"worker.log").read_text(encoding="utf-8")[:8000])
output=json.loads((OUT/"output.json").read_text(encoding="utf-8"))
print(json.dumps({k:v for k,v in output.items() if k!="html"}))
