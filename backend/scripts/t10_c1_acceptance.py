"""T10-C1 验收工具：只读正式库、离线探针、独立真实对照；不修业务实现。"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
OUT=ROOT.parent/"docs/reports/t10_c1_acceptance"
OUT.mkdir(parents=True,exist_ok=True)

def write(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8")

def sha(value):
    return hashlib.sha256(value).hexdigest()

def snapshot(stage):
    uri=f"file:{(ROOT/'data/bizpulse.db').as_posix()}?mode=ro"
    with sqlite3.connect(uri,uri=True) as db:
        db.row_factory=sqlite3.Row
        db.execute("BEGIN")
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        result={}
        for table in tables:
            escaped='"'+table.replace('"','""')+'"'
            rows=[json.dumps(dict(r),ensure_ascii=False,sort_keys=True,default=lambda v:v.hex() if isinstance(v,bytes) else str(v)) for r in db.execute("SELECT * FROM "+escaped)]
            result[table]=dict(count=len(rows),sha256=sha("\n".join(sorted(rows)).encode()))
    raw={p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in (ROOT/"data/raw").rglob("*") if p.is_file()}
    write(f"business_{stage}.json",result)
    write(f"raw_{stage}.json",raw)
    status=subprocess.run(["git","status","--short"],cwd=ROOT.parent,capture_output=True,text=True,encoding="utf-8").stdout
    (OUT/f"git_{stage}.txt").write_text(status,encoding="utf-8")
    print(json.dumps(dict(stage=stage,tables=len(result),raw_files=len(raw))))

def probes():
    from app.db import model_imports
    from app.collectors import crawl4ai_adapter as module
    from app.collectors.crawl_policy import SafeFetch,Response,check_url,CrawlStopped
    from app.models.source import SourceRecord
    from app.models.signal import Signal
    from app.services.actionability import compute_actionability_by_rules
    from app.core.config import Settings
    html='<html><title>验收离线夹具</title><body><article><nav>夹具导航入口</nav><p>此内容为离线验收夹具，禁止计入真实商业样本。</p><footer>夹具网站页脚</footer></article><time id="date">2020年01月01日</time></body></html>'
    with tempfile.TemporaryDirectory(prefix="bizpulse-c1-acceptance-") as directory:
        root=Path(directory)
        (root/"data").mkdir()
        rule=dict(status="ALLOWED",terms_url="https://example.com/terms",permission_url="https://example.com/terms",
            permission_quote="OFFLINE_TEST_FIXTURE",reviewed_by="OFFLINE_TEST_FIXTURE",reviewed_at=datetime.now(timezone.utc).isoformat(),
            expires_at="2099-01-01T00:00:00+00:00",allowed_path_prefixes=["/news/"])
        permission=root/"permission.json"
        permission.write_text(json.dumps({"example.com":rule}),encoding="utf-8")
        env=dict(CRAWL4AI_ENABLED="true",CRAWL4AI_PERMISSION_FILE=str(permission),NO_AUTO_APPROVAL="true",
                 REAL_DATA_ONLY="true",NO_FAKE_DATA="true",NO_FAKE_EVIDENCE="true")
        with patch.dict(os.environ,env),patch.object(module,"BASE_DIR",root),patch.object(SafeFetch,"get",lambda self,url:Response(url,url,200,"text/html",html.encode(),{})):
            adapter=module.Crawl4AIAdapter(SimpleNamespace(id="OFFLINE_FIXTURE",base_url="https://example.com/news/1"),
                 {"css_selector":"article","field_css":{"published_at":"#date"}})
            item=adapter.fetch()[0]
            module.validate_crawl_evidence(item)
            record=SourceRecord(raw_text=item.raw_text,published_at=item.published_at,metadata_json=item.extra)
            signal=Signal(signal_type="NEW_PRODUCT",published_at=record.published_at,collected_at=datetime.now(timezone.utc))
            encoded_rejected=True
            try:check_url("https://example.com/news/1?%74oken=OFFLINE_TEST_VALUE",{"example.com"});encoded_rejected=False
            except CrawlStopped:pass
            settings=Settings(_env_file=None)
            result=dict(synthetic=True,network_requests=0,business_writes=0,
                css_nav_removed="夹具导航入口" not in item.raw_text,css_footer_removed="夹具网站页脚" not in item.raw_text,
                default_dom_nav_removed="夹具导航入口" not in module.extract_dom(html,item.url)[2],
                default_dom_footer_removed="夹具网站页脚" not in module.extract_dom(html,item.url)[2],
                structured_date=item.extra["structured_fields"]["published_at"],
                collected_item_published_at=str(item.published_at),source_record_published_at=str(record.published_at),
                downstream_old_event_status=compute_actionability_by_rules(signal),
                percent_encoded_credential_rejected=encoded_rejected,
                runtime_flags={k:hasattr(settings,k.lower()) for k in ("REAL_DATA_ONLY","NO_FAKE_DATA","NO_FAKE_EVIDENCE","NO_AUTO_APPROVAL")},
                effective_no_fake_data=settings.no_fake_data,effective_opportunity_auto_approve=settings.opportunity_auto_approve,
                signal_auto_approve_threshold=settings.signal_auto_approve_threshold,
                source_url_preserved=item.url=="https://example.com/news/1",snapshot_validation_pass=True)
            write("offline_probes.json",result)
            print(json.dumps(result,ensure_ascii=True))

def archived_and_history():
    from app.collectors.crawl4ai_adapter import validate_crawl_evidence
    from app.collectors.base import CollectedItem
    original=ROOT.parent/"docs/reports/t10_c1"
    rows=[json.loads(s) for s in (original/"ab_results.jsonl").read_text(encoding="utf-8").splitlines()]
    pairs=refs=0
    failures=[]
    for row in rows:
        if "metadata" not in row:continue
        meta=row["metadata"]
        try:
            text=(ROOT/meta["cleaned_text_path"]).read_text(encoding="utf-8")
            item=CollectedItem(url=row["url"],canonical_url=meta["final_url"],raw_text=text,extra=meta)
            validate_crawl_evidence(item)
            for e in row["evidence"]:
                assert text[e["start"]:e["end"]]==e["quote"]
                refs+=1
            pairs+=1
        except Exception as exc:failures.append(dict(url=row["url"],reason=type(exc).__name__))
    with sqlite3.connect(f"file:{(ROOT/'data/bizpulse.db').as_posix()}?mode=ro",uri=True) as db:
        db.row_factory=sqlite3.Row
        records={r["id"]:dict(r) for r in db.execute("SELECT id,raw_text,raw_html_path FROM source_records")}
        evidence=list(db.execute("SELECT id,source_record_id,quoted_text,start_offset,end_offset FROM signal_evidences"))
        errors=[];exact=missing_offset=missing_record=0
        for e in evidence:
            record=records.get(e["source_record_id"])
            if not record:missing_record+=1;continue
            text=record["raw_text"] or ""
            if e["start_offset"] is None or e["end_offset"] is None:
                missing_offset+=1
                if e["quoted_text"] not in text:errors.append(dict(evidence_id=e["id"],record_id=e["source_record_id"],reason="QUOTE_NOT_FOUND"))
            elif text[e["start_offset"]:e["end_offset"]]==e["quoted_text"]:exact+=1
            else:errors.append(dict(evidence_id=e["id"],record_id=e["source_record_id"],reason="OFFSET_OR_QUOTE_MISMATCH"))
        missing=[dict(record_id=r["id"],path=r["raw_html_path"]) for r in records.values() if r["raw_html_path"] and not (ROOT/r["raw_html_path"]).is_file()]
        historical=db.execute("SELECT COUNT(*) FROM signals WHERE signal_type='CONTRACT_AWARD'").fetchone()[0]
        approved=db.execute("SELECT COUNT(*) FROM signals WHERE status='APPROVED'").fetchone()[0]
    result=dict(archive_urls_verified=pairs,archive_quotes_verified=refs,archive_failures=failures,
         production_records=len(records),production_missing_declared_snapshots=missing,
         production_evidence=len(evidence),exact_offsets=exact,missing_offsets=missing_offset,missing_records=missing_record,
         quote_or_offset_errors=errors,contract_award_count=historical,existing_approved_signals=approved)
    write("evidence_audit.json",result)
    print(json.dumps({k:v for k,v in result.items() if k not in {"production_missing_declared_snapshots","quote_or_offset_errors"}},ensure_ascii=True))
    print(json.dumps(dict(missing_snapshots=len(missing),quote_errors=len(errors))))

def live():
    spec=importlib.util.spec_from_file_location("c1_acceptance_benchmark",ROOT/"scripts/t10_c1/benchmark.py")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.OUT=OUT
    module.setup_permission()
    urls=[(f"https://quotes.toscrape.com/page/{i}/",False) for i in range(1,11)]+[(f"https://quotes.toscrape.com/js/page/{i}/",True) for i in range(1,11)]
    write("planned_urls.json",[url for url,_ in urls])
    with (OUT/"live_ab_results.jsonl").open("w",encoding="utf-8") as log:
        for url,dynamic in urls:
            try:
                row=module.run_url(url,dynamic)
                status=dict(url=url,old_effective=row["old"]["effective_body"],new_effective=row["new"]["effective_body"],seconds=row["new"]["elapsed_seconds"])
            except Exception as exc:
                from app.collectors.crawl_policy import CrawlStopped
                row=dict(url=url,status="STOPPED",reason=str(exc) if isinstance(exc,CrawlStopped) else type(exc).__name__,at=datetime.now(timezone.utc).isoformat())
                log.write(json.dumps(row,ensure_ascii=False)+"\n");log.flush();print(json.dumps(row),flush=True)
                break
            log.write(json.dumps(row,ensure_ascii=False)+"\n");log.flush();print(json.dumps(status),flush=True)

def report():
    rows=[json.loads(s) for s in (ROOT.parent/'docs/reports/t10_c1/ab_results.jsonl').read_text(encoding='utf-8').splitlines()]
    before=json.loads((OUT/'business_before.json').read_text(encoding='utf-8'))
    after=json.loads((OUT/'business_after.json').read_text(encoding='utf-8'))
    raw_before=json.loads((OUT/'raw_before.json').read_text(encoding='utf-8'))
    raw_after=json.loads((OUT/'raw_after.json').read_text(encoding='utf-8'))
    import re
    def summary(name):
        text=(OUT/name).read_text(encoding='utf-8-sig')
        return next((line.strip('= ').strip() for line in reversed(text.splitlines()) if re.search(r'\d+ passed',line)),'结果见原始日志')
    table=['|URL|类型|旧/新获取|旧/新有效正文|旧/新引用数|旧/新耗时秒|新浏览器峰值MiB|','|---|---|---|---|---|---|---|']
    for r in rows:
        a,b=r['old'],r['new'];rss=b.get('peak_rss_bytes')
        table.append(f"|{r['url']}|{r['category']}|{a['fetch_success']}/{b['fetch_success']}|{a['effective_body']}/{b['effective_body']}|{a['traceable_quotes']}/{b['traceable_quotes']}|{a['elapsed_seconds']}/{b['elapsed_seconds']}|{round(rss/1048576,2) if rss else '未启动浏览器'}|")
    metrics={}
    for side in ('old','new'):
        metrics[side]={key:round(sum(r[side][key] for r in rows)/len(rows),4) for key in ('noise_rate','elapsed_seconds')}
        metrics[side].update(fetch=sum(r[side]['fetch_success'] for r in rows),body=sum(r[side]['effective_body'] for r in rows),quotes=sum(r[side]['traceable_quotes'] for r in rows),bytes=sum(r[side]['bytes'] for r in rows))
    write('summary.json',dict(archived_metrics=metrics,business_tables_unchanged=before==after,baseline_raw_files_unchanged=all(raw_after.get(k)==v for k,v in raw_before.items()),collection_tests=summary('collection_tests.txt'),full_pytest=summary('full_pytest.txt'),new_live_urls=0,archived_urls=len(rows),verdict='FAIL'))
    content=f'''# T10-C1 验收与 T10-C2 设计门禁报告

验收日期：2026-10-08。项目：D:\\myAI\\bizpulse。结论：**FAIL**。现有 Crawl4AI 已集成，但证据一致性、发布时间传递、清洗、安全和禁止自动批准规则未满足验收要求。按用户门禁停止，不制定或开发 T10-C2。

## 1. 当前状态与复用审计

项目路径真实存在，原报告 `T10-C1_CRAWL4AI_INTEGRATION_REPORT.md` 存在并已阅读；其结论为技术验证部分通过，不能视为完成。Git 有大量既有未提交修改，验收未覆盖、撤销或提交这些修改；完整清单见 `t10_c1_acceptance/git_before.txt` 与 `git_after.txt`。

已审计 README、依赖、Source/SourceRecord、Evidence、Signal、Opportunity、Job、采集注册和统一调度、质量门、Actionability、分析批准逻辑。拟复用现有 FastAPI/SQLAlchemy、采集注册与调度、SourceRecord 版本和内容去重、Evidence、既有质量门与人工审核。此次仅增加验收工具、日志和报告，不修改业务实现，不做数据库迁移。

`crawl4ai_adapter.py`、`crawl_policy.py`、`crawl_fields.py`、`crawl4ai_worker.py` 已存在；注册可选 crawl4ai，由现有 collection_engine 调度。默认 HTTP，不无条件启动 Chromium；动态渲染要求诊断标记。网页数据只进入未核实记录，适配器不直接生成 Signal/Opportunity。HTTP、RSS、手动 URL 注册仍在；没有找到独立 API 来源适配器，API 接口与来源 API 通道不能混为一谈。CSV 等兼容性由现有全量测试覆盖，不能据此声称所有真实来源端到端已验证。

实际项目虚拟环境：Crawl4AI **0.9.4**、Playwright **1.63.0**、psutil **7.2.2**，`pip check` 无依赖冲突；SDK 可选依赖固定在 requirements-crawl4ai.txt，锁文件记录安装环境。浏览器由项目 `.browsers` 初始化，方法见 backend/docs/CRAWL4AI.md。验收没有安装或修改全局 Python。

## 2. 数据库隔离与业务数据保护

测试 conftest 明确设置 `sqlite:///./data/bizpulse_test.db`，正式库为 backend/data/bizpulse.db；测试完成释放连接并删除测试库。正式库审计采用 SQLite mode=ro。前后比对全部 {len(before)} 张业务表的行数及排序后内容 SHA256：一致={before==after}。原有 {len(raw_before)} 个原文文件内容全部保持={all(raw_after.get(k)==v for k,v in raw_before.items())}。

T09 实验、客户及 READY_TO_CONTACT 状态包含在全表比对中，未变更；没有新建 Interaction、发送消息或批准正式机会。正式库已有 50 条 APPROVED Signal、40 条 CONTRACT_AWARD，是历史存量，不是本次输出。CONTRACT_AWARD 规则保持历史信号/不可行动；未转换为当前招标机会。采购日期、预算、供应商、参数缺失保持 UNKNOWN。

## 3. 真实 URL 对照与停止记录

**本次新增真实批量执行 0 条**：只读正式证据审计发现 4 条原文与 Evidence 偏移不一致，立即触发质量停止条件，未执行已准备的新增采集。禁止用旧数据冒充本轮新采集。

复核上一轮真实执行的 20 个不同 URL（10 静态、10 JS），采集时间保留在原 ab_results.jsonl，原始/最终 URL、快照和许可元数据均保留。20 份快照验证及 200 个新适配器引用偏移全部通过。本次只验证归档，没有重新访问这些20页面。[网站所有者许可说明](https://toscrape.com/)说明该网站提供抓取沙盒。本轮业务场景新增样本 **0**；采购公告、招聘、新闻、技术资料及真实日期/主体准确率仍未验证，不能把沙盒引用当作商业证据。

旧适配器对照复用了旧正文解析，但网络请求经过安全代理，不能声称原旧网络传输全链路未改动。噪声率是沙盒“非目标引用字符比例”，不是人工标注的业务正文噪声率。此前两次中断（DNS 与导航超时）在原报告保留，最终20条成功不意味着无执行失败。

{chr(10).join(table)}

汇总（旧/新）：获取 {metrics['old']['fetch']}/20、{metrics['new']['fetch']}/20；有效正文 {metrics['old']['body']}/20、{metrics['new']['body']}/20；引用可追溯 {metrics['old']['quotes']}/200、{metrics['new']['quotes']}/200；平均噪声比例 {metrics['old']['noise_rate']:.2%}/{metrics['new']['noise_rate']:.2%}；平均耗时 {metrics['old']['elapsed_seconds']}/{metrics['new']['elapsed_seconds']} 秒；传输字节 {metrics['old']['bytes']}/{metrics['new']['bytes']}。JS 有效正文由0/10恢复到10/10。SDK峰值是采样进程树RSS，非计费成本；CPU、网络和浏览器开销不能外推大规模成本。可用 Signal=0、Actionable Signal=0；商业严重主体误判数、日期主体准确率 **未验证**，不是0误判结论。

## 4. 证据链与必须修复的问题

正式库138条 SourceRecord、52条 SignalEvidence：48条精确偏移一致、**4条不一致**、5条声明快照缺失。完整记录ID与问题见 `t10_c1_acceptance/evidence_audit.json`。这些是本次只读发现的存量缺陷，不能直接归因 Crawl4AI；仍足以阻止全链路验收。不得改写原文使证据“通过”，应从可信原版本恢复或隔离缺陷证据，重做人工确认。

|必须修复/补证|本次依据|复验条件|
|---|---|---|
|证据引用不一致与缺失快照|4条偏移不一致、5文件缺失|版本、哈希、精确引用一致；无法恢复的存量标记不可用并阻止下游采用|
|CSS 分支导航/页脚过滤|离线 article 包含 nav/footer，两者留在正文；默认解析分支正确过滤|CSS 与默认路径均验证过滤，保留原始/清洗文本区别|
|发布时间标准字段断链|2020-01-01被提取到metadata，但item/SourceRecord.published_at=None|可信显式日期进入标准链；不明时区保持未知，不能凭采集时间推定历史事件近期|
|错误可行动性风险|上述离线 NEW_PRODUCT 的规则结果 ACTIONABLE_NOW|历史发布时间不能被丢弃，缺失事件时间不得当作已证实近期事件|
|编码凭证 URL 防护|`?%74oken=OFFLINE_TEST_VALUE` 被 check_url 接受，未发送网络请求|规范解码后检查敏感键和重定向目标，日志不泄露凭证|
|全局禁止自动批准未落地|Settings仅存在no_fake_data；分析器仍按置信度/来源等级自动批准Signal|NO_AUTO_APPROVAL实际覆盖所有采集衍生分析入口；既有人工审批可用且不误批|
|相关测试失败与共享来源等级污染|手动来源预期C，实际A；其他测试会把共享来源升级A|明确可靠性继承业务规则并隔离测试，不通过改断言掩盖来源等级污染|
|业务真实样本不足|20条均为引用沙盒，无采购/技术资料|修复证据门后合法来源重新对照；不足如实报告，日期/主体需人工真值|
|PDF受控解析未验收|当前拒绝PDF，不将占位符当正文|若纳入验收需明确大小/页数/解析策略和失败证据；否则清楚限定为不支持|

离线探针结果见 offline_probes.json，全部是明确标记的测试夹具，网络请求0、业务写入0，禁止计为真实样本。原始快照/清洗版本、原URL保留及归档哈希校验通过；上述结论不代表生产证据链整体合格。

现有安全设计包含站点人工许可、robots、DNS公共地址与连接固定、同域重定向、资源/超时上限和浏览器请求截获；其既有自动测试不能代替真实各站点条款审查。失败回退和限流有测试覆盖，但真实商业动态站点的回退效果仍未验证。浏览器成功不等于合法可采集。网页指令不进入LLM执行。

## 5. 本轮回归测试

先运行16个采集/证据/归属/生命周期相关测试文件，再执行项目虚拟环境 `python -m pytest` 全量测试：

- 采集相关：**{summary('collection_tests.txt')}**。
- 全量 pytest：**{summary('full_pytest.txt')}**。
- 原始日志：collection_tests.txt、full_pytest.txt。

相关测试失败：test_evidence_chain.py::test_ingest_records_reliability_snapshot_and_rejects_empty_page，期望来源快照C，实际A。共享手动来源等级在既有测试间会被升级，相关与全量测试顺序不同；不能仅凭全量通过忽略独立相关套件失败。已验证原有HTTP/RSS/API端点的自动测试，不据此宣称真实政府站点采集和全部主体归属正确。

验收工具初次离线探针因未注册 ORM Company 模型失败，补齐工具初始化后重跑成功；不计入pytest失败，未修改业务代码。历史证据问题触发停止，不执行新增批量。

## 6. T10-C1 结论与 T10-C2 门禁

**T10-C1：FAIL。** 失败具有已复现的功能/安全缺陷和正式证据链不一致依据，而不只是外网样本阻塞。

以下内容全部 **未启动**：T10-C2 ProcurementProject/ProcurementLifecycle/RequirementSpec/SupplierProduct/RequirementMatch/MatchExplanation/HumanReview 数据模型；跨公告生命周期、参数匹配算法、Evidence计算追溯、API、数据库迁移、分阶段开发任务和成本设计。按用户“FAIL或BLOCKED时停止，不设计后续实现任务”的明确门禁，本报告不提供这些后续方案。

下一步仅建议修复并复验上述 T10-C1 阻断项，正式证据一致性恢复前不扩量；验收PASS后才单独制定最小C2方案。当前已停止，等待人工验收；无C2业务功能代码、自动触达或扩量。
'''
    (ROOT.parent/'docs/reports/T10_C1_ACCEPTANCE_AND_C2_DESIGN.md').write_text(content,encoding='utf-8')

if __name__=="__main__":
    mode=sys.argv[1]
    if mode in {"before","after_tests","after"}:snapshot(mode)
    elif mode=="probes":probes()
    elif mode=="evidence":archived_and_history()
    elif mode=="live":live()
    elif mode=="report":report()
