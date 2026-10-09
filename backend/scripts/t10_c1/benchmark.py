"""真实采集沙盒 A/B；不写正式库，不生成销售事实。中断后逐行结果仍保留。"""
from __future__ import annotations
import ast
import json
import os
import sys
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from app.collectors.crawl_policy import SafeFetch, CrawlStopped, digest
from app.collectors.crawl4ai_adapter import Crawl4AIAdapter, verify_quote, validate_crawl_evidence
from app.collectors.web import WebPageCollector
from app.services import extractor
OUT = ROOT.parent / "docs/reports/t10_c1"

class RSSMeter:
    def __enter__(self):
        import psutil
        self.process=psutil.Process()
        self.peak=0
        self.done=threading.Event()
        def sample():
            while not self.done.is_set():
                self.peak=max(self.peak,self.process.memory_info().rss)
                self.done.wait(.025)
        self.thread=threading.Thread(target=sample,daemon=True)
        self.thread.start()
        return self
    def __exit__(self,*args):
        self.done.set();self.thread.join()


def setup_permission():
    # 站点所有者明确标注“用于验证采集技术”的沙盒；登录端点永不选入。
    client = SafeFetch({"toscrape.com"})
    result = client.get("https://toscrape.com/")
    html = result.text()
    if result.status != 200 or "Web Scraping Sandbox" not in html or "JavaScript generated content" not in html:
        raise CrawlStopped("PERMISSION_CHANGED_STOP")
    (OUT/"permission_source.html").write_text(html,encoding="utf-8")
    rule = dict(status="ALLOWED", terms_url="https://toscrape.com/",permission_url="https://toscrape.com/",
                permission_quote="A website that lists quotes from famous people. It has many endpoints showing the quotes in many different ways, each of them including new scraping challenges for you",
                reviewed_by="T10-C1公开许可审计（采集技术沙盒，不是企业商业样本）",
                reviewed_at=datetime.now(timezone.utc).isoformat(),expires_at="2026-10-09T00:00:00+00:00",
                permission_snapshot_hash=digest(html), interval_seconds=2,
                allowed_path_prefixes=["/page/", "/js/page/", "/static/"],
                scope="仅 quotes.toscrape.com 公开测试路径；禁止登录、用户数据与外部链接")
    path=OUT/"sandbox_permission.json"
    path.write_text(json.dumps({"quotes.toscrape.com":rule},ensure_ascii=False,indent=2),encoding="utf-8")
    os.environ["CRAWL4AI_PERMISSION_FILE"]=str(path)
    os.environ["CRAWL4AI_ENABLED"]="true"


def expected_quotes(html: str, dynamic: bool) -> list[str]:
    soup=BeautifulSoup(html,"html.parser")
    if not dynamic:
        return [n.get_text(strip=True) for n in soup.select(".quote .text")]
    # 页内原始 JSON 数据为真实对照依据，解析不执行任何网页代码。
    import re
    match=re.search(r"var data = (\[.*?\]);",html,re.S)
    if not match:
        raise CrawlStopped("REFERENCE_UNVERIFIED")
    return [r["text"] for r in json.loads(match[1])]


def run_url(url: str, dynamic: bool) -> dict:
    row=dict(url=url,category="JS_SANDBOX" if dynamic else "STATIC_SANDBOX",collected_at=datetime.now(timezone.utc).isoformat(),commercial_sample=False)
    source=SimpleNamespace(id="t10-c1-sandbox",base_url=url)
    old_client=SafeFetch({"quotes.toscrape.com"})
    pages=[]
    def old_fetch(target):
        response=old_client.get(target)
        pages.append(response)
        return extractor.parse_html(target,response.final_url,response.status,response.content_type,response.text())
    # 原 Adapter/旧解析逻辑不变；统一安全传输封装，避免旧 follow_redirects 的 SSRF 缺口。
    started=time.monotonic()
    with RSSMeter() as old_rss, patch.object(extractor,"fetch_public_page",old_fetch):
        old=WebPageCollector(source,{"url":url,"max_retries":1}).fetch()[0]
    old_seconds=time.monotonic()-started
    if not pages or pages[0].status != 200:
        raise CrawlStopped("OLD_FETCH_FAILED")
    html=pages[0].text()
    quotes=expected_quotes(html,dynamic)
    if not quotes:
        raise CrawlStopped("REFERENCE_EMPTY")
    config={"url":url,"mode":"js" if dynamic else "http","css_selector":".quote .text"}
    if dynamic:
        config["js_diagnosis"]={"marker":"var data =", "reason":"HTTP 原始 DOM 无 .quote .text；正文由页内脚本写入，数据可从原文 JSON 对照", "http_failure":"PARSE_EMPTY"}
    started=time.monotonic()
    with RSSMeter() as new_rss:
        new=Crawl4AIAdapter(source,config).fetch()[0]
    new_seconds=time.monotonic()-started
    validate_crawl_evidence(new)
    new_text=new.raw_text or ""
    old_text=old.raw_text or ""
    old_hits=sum(q in old_text for q in quotes)
    new_hits=sum(q in new_text for q in quotes)
    trace=[]
    for q in quotes:
        start=new_text.find(q)
        good=verify_quote(new,q,start,start+len(q),new.extra["cleaned_text_hash"])
        trace.append(dict(quote=q,start=start,end=start+len(q),text_hash=new.extra["cleaned_text_hash"],traceable=good))
    if new_hits and not all(t["traceable"] for t in trace):
        raise CrawlStopped("EVIDENCE_MISMATCH_STOP")
    key=digest(url)[:16]
    (OUT/"samples").mkdir(exist_ok=True)
    (OUT/"samples"/f"{key}.old.html").write_text(html,encoding="utf-8")
    (OUT/"samples"/f"{key}.old.txt").write_text(old_text,encoding="utf-8")
    import shutil
    for field in ("raw_html_path","raw_text_path","cleaned_text_path","rendered_html_path","raw_bytes_path"):
        if field in new.extra:
            source_path=ROOT/new.extra[field]
            suffix=source_path.name.split(".",1)[1]
            shutil.copyfile(source_path,OUT/"samples"/f"{key}.new.{suffix}")
    old_chars=sum(len(q) for q in quotes if q in old_text)
    new_chars=sum(len(q) for q in quotes if q in new_text)
    row.update(expected_quotes=len(quotes),old=dict(fetch_success=old.http_status==200,adapter_status=old.parse_status,
               effective_body=old_hits==len(quotes),quote_recall=old_hits/len(quotes),
               noise_rate=round(max(0,1-old_chars/max(len(old_text.replace('\n','')),1)),4),
               elapsed_seconds=round(old_seconds,3),bytes=old_client.bytes,requests=old_client.requests,
               python_peak_rss_bytes=old_rss.peak,traceable_quotes=old_hits),
               new=dict(fetch_success=True,effective_body=new_hits==len(quotes),quote_recall=new_hits/len(quotes),
               noise_rate=round(max(0,1-new_chars/max(len(new_text.replace('\n','')),1)),4),
               **new.extra["resources"], traceable_quotes=sum(t["traceable"] for t in trace),
               python_peak_rss_bytes=new_rss.peak,
               render_status=new.extra["render_status"]), evidence=trace,metadata=new.extra,
               date_accuracy="NOT_APPLICABLE",subject_accuracy="NOT_APPLICABLE",usable_signals=0,actionable_signals=0,
               signal_quality="UNVERIFIED_NO_COMMERCIAL_SAMPLE",severe_misattribution="UNVERIFIED_NO_SUBJECT_EXTRACTION")
    return row


if __name__ == "__main__":
    OUT.mkdir(parents=True,exist_ok=True)
    setup_permission()
    urls=[(f"https://quotes.toscrape.com/page/{i}/",False) for i in range(1,11)] + [(f"https://quotes.toscrape.com/js/page/{i}/",True) for i in range(1,11)]
    if "--smoke" in sys.argv:
        urls=[urls[10]]
    if "--js" in sys.argv:
        urls=urls[10:]
    file=OUT/("smoke.jsonl" if "--smoke" in sys.argv else "ab_results.jsonl")
    previous=[]
    if "--resume" in sys.argv:
        previous=[json.loads(line) for line in file.read_text(encoding="utf-8").splitlines()]
        backup=OUT/("ab_attempt_"+datetime.now(timezone.utc).strftime("%H%M%S")+".jsonl")
        backup.write_text(file.read_text(encoding="utf-8"),encoding="utf-8")
        previous=[r for r in previous if "old" in r and "new" in r]
        done={r["url"] for r in previous}
        urls=[entry for entry in urls if entry[0] not in done]
    with file.open("w",encoding="utf-8") as stream:
        for row in previous:
            stream.write(json.dumps(row,ensure_ascii=False)+"\n")
        for url,dynamic in urls:
            try:
                row=run_url(url,dynamic)
            except Exception as exc:
                row=dict(url=url,status="STOPPED",reason=str(exc) if isinstance(exc,CrawlStopped) else type(exc).__name__,collected_at=datetime.now(timezone.utc).isoformat())
                stream.write(json.dumps(row,ensure_ascii=False)+"\n");stream.flush()
                print(json.dumps(row,ensure_ascii=True),flush=True)
                break
            stream.write(json.dumps(row,ensure_ascii=False)+"\n");stream.flush()
            print(json.dumps({"url":url,"old_body":row["old"]["effective_body"],"new_body":row["new"]["effective_body"],"seconds":row["new"]["elapsed_seconds"],"render":row["new"]["render_status"]},ensure_ascii=True),flush=True)
