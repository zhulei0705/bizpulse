"""只从真实执行产物生成统计/报告，不补齐缺失样本或商务验证值。"""
import json
import re
import statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT.parent/"docs/reports/t10_c1"
def read(name): return (OUT/name).read_text(encoding="utf-8")
def mean(rows,side,key): return statistics.mean(r[side][key] for r in rows) if rows else 0
if __name__=="__main__":
    all_rows=[json.loads(line) for line in read("ab_results.jsonl").splitlines()]
    rows=[r for r in all_rows if "old" in r and "new" in r]
    stopped=[r for r in all_rows if r not in rows]
    static=[r for r in rows if r["category"]=="STATIC_SANDBOX"]
    js=[r for r in rows if r["category"]=="JS_SANDBOX"]
    counts={side:dict(fetch=sum(r[side]["fetch_success"] for r in rows),body=sum(r[side]["effective_body"] for r in rows),
                     trace=sum(r[side]["traceable_quotes"] for r in rows),seconds=round(mean(rows,side,"elapsed_seconds"),3),
                     noise=round(mean(rows,side,"noise_rate")*100,2),bytes=sum(r[side]["bytes"] for r in rows)) for side in ("old","new")}
    expected=sum(r["expected_quotes"] for r in rows)
    before=json.loads(read("protected_before.json"));after=json.loads(read("protected_after.json"))
    assert before==after
    full=read("full_pytest_final.txt") if (OUT/"full_pytest_final.txt").exists() else read("full_pytest.txt")
    summary=re.findall(r"\d+ passed.*",full)[-1]
    record=json.loads(read("isolated_record_validation.json"))
    table=[]
    for i,r in enumerate(rows,1):
        table.append(f'| {i} | [{r["category"]} / {r["url"].split("/")[-2]}]({r["url"]}) | 是/是 | {"是" if r["old"]["effective_body"] else "否"}/{"是" if r["new"]["effective_body"] else "否"} | {r["old"]["noise_rate"]*100:.1f}/{r["new"]["noise_rate"]*100:.1f}% | {r["old"]["traceable_quotes"]}/{r["new"]["traceable_quotes"]}（应有{r["expected_quotes"]}） | {r["old"]["elapsed_seconds"]:.2f}/{r["new"]["elapsed_seconds"]:.2f} |')
    peak=max((r["new"]["peak_rss_bytes"] or 0 for r in rows),default=0)/1024**2
    groups=[]
    for label,group in (("静态",static),("JS",js)):
        groups.append(f'| {label} | {len(group)} | {sum(r["old"]["effective_body"] for r in group)}/{sum(r["new"]["effective_body"] for r in group)} | {mean(group,"old","elapsed_seconds"):.2f}/{mean(group,"new","elapsed_seconds"):.2f} |')
    selected=[]
    for group in (static,js):
        for index in sorted(set([0,len(group)//3,len(group)*2//3,len(group)-1])):
            if group:
                row=group[index]
                matching=next(r for r in record["rows"] if r["url"]==row["url"])
                selected.append(dict(url=row["url"],record_id=matching["record_id"],version=matching["version"],
                    text_hash=row["metadata"]["cleaned_text_hash"],quote_count=row["expected_quotes"],
                    review_status="PENDING_HUMAN_REVIEW",checks=["打开原始及渲染HTML并核对目标DOM","逐条复核字符偏移/文本哈希","确认无登录/验证码/访问绕过","确认未把名言作者当企业或采购主体","确认缺失日期/金额/主体保持UNKNOWN","确认无APPROVED Signal或READY Opportunity"]))
    (OUT/"human_review_queue.json").write_text(json.dumps(selected,ensure_ascii=False,indent=2),encoding="utf-8")
    report=f'''# T10-C1 Crawl4AI 增量采集集成与质量验证报告

日期：2026-10-08。项目：`D:\\myAI\\bizpulse`，路径已确认存在。交付状态：**可选适配器已集成，技术验证部分通过；完整商业采集质量验收未通过，不建议进入 T10-C2 扩量。** 新通道保持默认关闭，等待人工验收。

## 1. 现有架构审计与复用

- 阅读 `backend/README.md`、依赖、Collectors、Source/SourceRecord、Signal/SignalEvidence、Opportunity、CollectionJob、采集中心 API，以及 EvidenceQualityGate、Reliability、主体归属、Actionability 与审核实现。根目录没有 README，后端 README 的“5 passed”是旧说明；本轮改动前实际基线为 **533 passed、5 warnings、74.41 秒**。
- 原链路为 registry → CollectorAdapter → run_collection_job → persist_collected → SourceRecord 版本链。保持 `/sources/{{id}}/run` API 的请求/响应、Job 状态机与旧 Adapter 行为；新增一个可选注册项，不增加表、迁移、前端或独立微服务。SDK 仅在一个有界子进程中运行。
- SourceRecord 已有 URL、正文、快照路径、内容哈希、时间、版本号、父版本、最新标记及 metadata，足以复用。旧、新正文相同仍使用既有去重规则。
- 新通道保存待核实 SourceRecord，暂不自动关联企业，也不调用旧 `create_rule_signals` 的 `VALID` 快捷路径。原 EvidenceQualityGate、Reliability、主体归属、Actionability 和审核模块未替换；需要人工归属后按现有流程分析和审核。
- 发现旧 HTTP 仅请求前检查 DNS、旧 Job `/jobs/{{id}}/run` 使用另一路抓取，存在重定向/DNS 固定缺口。本轮未宣称这些旧路径已完成安全升级。A/B 为避免触及该缺口，对旧 Adapter 使用同一安全 HTTP 桥接，旧提取逻辑不变。
- 已发现并回归 HTTP、RSS、人工 URL、CSV 导入及现有 API；未找到独立 API/Excel 采集 Adapter，不能宣称未存在的通道已获验证。
- Git 开始时已有大量 T06～T10-A 的已修改/未跟踪文件，全部保留，没有 reset/清理/提交。`git_before.txt` 是开始改造后首次保存的清单；最初状态来自前置命令，不将整个 Git diff 归为本任务改动。

## 2. 本轮修改文件

新增：

- `backend/app/collectors/crawl4ai_adapter.py`：可选适配器、原始/清洗快照、子进程资源监视、入库前证据一致性校验。
- `backend/app/collectors/crawl4ai_worker.py`：SDK 和浏览器请求桥接；禁止任意来源注入 hook/JS/凭证配置。
- `backend/app/collectors/crawl_policy.py`：站点路径许可、robots、域名频率、DNS 固定、每跳重检、字节/请求限制。
- `backend/app/collectors/crawl_fields.py`：显式 CSS 字段及严格日期、人民币金额、采购人/供应商/代理角色校验；缺失保持 UNKNOWN。
- `backend/requirements-crawl4ai.txt`、`backend/requirements-crawl4ai.lock.txt`、`backend/docs/CRAWL4AI.md`、`backend/tests/test_crawl4ai_adapter.py`。
- `backend/scripts/t10_c1/`：只读保护审计、真实 A/B、单页诊断、隔离库映射验收、报告生成。

修改：registry 新增注册；collection_engine 仅对 crawl4ai 入库前校验快照并关闭自动主体/信号生成；`.gitignore` 排除浏览器、缓存及本地许可文件。该引擎文件中原先已有的 PARSE_SUCCESS 兼容改动属于前序任务，未把它算作本轮新增。

另修复 `backend/tests/conftest.py` 与 `backend/tests/test_web_collector.py` 的文件隔离：所有旧 HTTP 测试快照改写 pytest 临时目录，删除既有测试对正式 `data/raw` 的递归清理。该问题在最终入库验收时发现，已用本轮报告内真实归档原件逐字节恢复本轮快照。历史快照可能曾被该遗留测试删除，缺少任务开始时的完整磁盘清单，**历史快照完整性未验证，必须人工从备份核查**；未用重抓原文冒充旧版本。

## 3. 依赖版本与初始化

实际项目虚拟环境 Python **3.14.7**；Crawl4AI **0.9.4**、Playwright **1.63.0**、psutil **7.2.2**。完整实际安装的 116 项依赖固定于 `backend/requirements-crawl4ai.lock.txt`，安装位置为 `backend/.venv`，没有安装全局 Python 包。

[官方 v0.9.4 发布](https://github.com/unclecode/crawl4ai/releases/tag/v0.9.4)与[官方安全公告](https://github.com/unclecode/crawl4ai/security)说明该版本的 robots/预览 SSRF 等补丁；仍须由应用提供 URL/出口控制。未据此宣称所有间接依赖无漏洞。SDK 参数依据[官方文档](https://docs.crawl4ai.com/api/parameters/)。

安装命令：

```powershell
Set-Location D:\\myAI\\bizpulse\\backend
.venv\\Scripts\\python.exe -m pip install -r requirements-crawl4ai.txt -c requirements-crawl4ai.lock.txt
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Get-Location) '.browsers'
$env:CRAWL4_AI_BASE_DIRECTORY = Join-Path (Get-Location) 'data/crawl4ai_cache'
$env:PYTHONIOENCODING = 'utf-8'
.venv\\Scripts\\python.exe -m playwright install chromium
.venv\\Scripts\\python.exe -m pip check
```

实测安装 Chromium **153.0.8010.12 / Playwright revision 1243**，位于 `backend/.browsers`；SDK 缓存明确位于项目内。`pip check`：No broken requirements found。普通 HTTP 模式不启动 Chromium；SDK 只用于来源许可明确、配置了真实 JS 诊断的页面。

## 4. 真实样本对照与范围限制

最终完成 **{len(rows)} 个唯一 URL 的完整 A/B**，静态 {len(static)}、JS {len(js)}；原计划 20 个。最终文件中的中止记录 {len(stopped)} 条。站点所有者[公开采集沙盒说明](https://toscrape.com/)明确提供用于验证采集技术的静态和 JavaScript 端点，许可原文/哈希保存于 `permission_source.html` 与 `sandbox_permission.json`。未访问登录端点，没有将 robots 允许视为网站许可。

**这不是 {len(rows)} 条真实采购公告。采购公告、采购意向、公司新闻、招聘和产品技术资料的合规业务样本为 0。** 这些类型缺少经过审查、带路径范围的站点许可；没有为了数量抓取未核实来源。因此日期/主体/Signal/Actionability 的商业正确性未验证。

A/B 方法：同 URL 两次真实安全 HTTP 请求；旧 WebPageCollector/旧 parse_html 不变，但传输被安全桥接替换；新静态路径用 CSS 提取，新 JS 路径真实运行 Crawl4AI/Chromium。不是原 HTTP 无安全封装的全端到端性能对比。静态真值为 DOM `.quote .text`；JS 真值为原始 HTML 内 JSON 数据，JSON 只解析、不执行。页面实际正文逐条与真值比较。

| # | 实际 URL/类型 | 获取旧/新 | 有效正文旧/新 | 目标外文本旧/新 | 回溯条目旧/新 | 耗时秒旧/新 |
|---|---|---|---|---|---|---|
{chr(10).join(table)}

“目标外文本”是按字符计算的技术沙盒噪声代理：1 − 命中的目标名言字符数/去换行后的正文字符数。作者/标签在商业场景可能有用，本统计不能代表采购公告人工评估的噪声率。正文有效率要求该页所有目标文本完整提取。证据回溯率检验记录正文、字符偏移、文本哈希和快照一致性，不等于证据业务质量已通过。

完整对照分母为 {len(rows)}，旧/新页面获取成功 {counts['old']['fetch']}/{counts['new']['fetch']}；有效正文 {counts['old']['body']}/{counts['new']['body']}；平均目标外文本占比 {counts['old']['noise']}%/{counts['new']['noise']}%；可回溯目标文本 {counts['old']['trace']}/{counts['new']['trace']}（应有 {expected} 个页面目标条目，静态/JS 会重复引用同一名言）。完整样本平均耗时 {counts['old']['seconds']}/{counts['new']['seconds']} 秒。

批量第一次在 JS 组出现 DNS_FAILED 后停止；第二次在 JS 第2页遇到 15 秒导航超时后停止，原始中止文件 `ab_attempt_*.jsonl` 保留。检查日志后把导航窗口调为 25 秒，进程树总时间/内存上限不变，只恢复未完成 URL。成功集合是对已完成配对的条件统计，不能掩盖前两次中断；本报告不将条件成功率当作无失败的运营成功率。所有 URL 实际执行结果/UTC 时间、预算字段 UNKNOWN、资源量与失败原因见 JSONL，未采样的 URL 不补数据。

## 5. JS 页面恢复效果

| 类型 | 完整配对数 | 有效正文旧/新 | 平均秒旧/新 |
|---|---|---|---|
{chr(10).join(groups)}

旧路径可能把只有标题/导航的 JS 壳页面标记为 PARSE_SUCCESS，但目标正文不存在；这是获取成功不等于提取成功的实测案例。新通道在原文存在 JS 数据标记、静态目标 DOM 为空的已诊断页面渲染，并按 CSS 提取真实 DOM。未执行滚动扩量、点击登录、验证码处理、隐藏浏览器指纹或反爬绕过。依赖外域 CDN 的 JS 仍会被阻断，不能推广本结果为所有 JS 站点恢复能力。

## 6. Evidence 质量与隔离入库

原始字节、HTML、原始可见文本、清洗正文分别存储；JS 增加渲染 HTML。metadata 保存原始/最终 URL、域名、采集时间、HTTP 状态对应 SourceRecord 字段、解析器版本、快照/正文哈希、许可和 Unicode 字符偏移基准。内容寻址路径避免覆盖旧版。

在**独立 `backend/data/bizpulse_t10_c1_validation.db`** 写入 {len(record['rows'])} 条真实沙盒 SourceRecord，全部 UNVERIFIED、无企业归属；同一条再次入库全部 SKIPPED_UNCHANGED。{sum(len(r['evidence_refs']) for r in record['rows'])} 条引用已核对 record_id、version=1、文本哈希及准确区间；见 `isolated_record_validation.json`。没有商业 Signal，因此不伪造正式 SignalEvidence：此处验证的是可回溯引用契约。

原文/清洗正文哈希与 DOM 复现失败会在入库前抛出 EVIDENCE_SNAPSHOT_MISMATCH。实际 Chromium 的中文编码测试发现响应未声明 UTF-8 时乱码，已修正桥接头；最终中文测试通过。短正文夹具曾被 SDK 自带反爬检测拒绝，改为正常长度夹具，保留检测，未绕过保护。

业务 EvidenceQualityGate、Source Reliability、主体归属与 Actionability 质量：**未验证商业正确性**，没有用名言页冒充采购证据。日期、预算、采购人、供应商、代理、截止时间在本批次都保持 UNKNOWN；严格格式校验仅由隔离测试夹具覆盖。

可用商业 Signal 数：0；Actionable Signal 数：0；生产自动批准：0。严重企业/采购方/中标方误归属数量：**未验证**（本批次未抽取商业主体）；没有观察到原文/Evidence 不一致的真实样本，但缺乏商务 Evidence 检验。私网请求的离线浏览器测试已验证阻断和停止，不能把此项当作所有协议的生产安全审计。

已准备 {len(selected)} 条人工复核记录：`human_review_queue.json`，全部 PENDING_HUMAN_REVIEW，没有冒充人工审核完成。

## 7. 原有功能回归与数据库保护

改动前：533 passed、5 warnings。最终全量：**{summary}**，失败 0；43 项新增测试覆盖配置/静态不启动浏览器/真 Chromium JS/私网请求停止、DNS 重绑定、重定向、robots、凭证注入拒绝、资源上限、PDF 拒绝、字段 UNKNOWN、快照一致性、CRLF响应字节保留、去重版本链与旧注册项兼容。测试使用 `tests/conftest.py` 设置的 `bizpulse_test.db`，结束释放连接后删除，与正式库路径不同。

初次适配器测试 35 passed；加入真实 Chromium 后出现短正文拒绝，再出现中文乱码（两次各1 failed/41 passed），修复后 42 passed。完整日志保留，不把中间失败隐藏为从未失败。4 条最终警告为原 FastAPI on_event 弃用；安装间接依赖 httpx2 后原 TestClient 警告不再出现。

正式库只读前/后快照的 8 张表哈希一致：experiments=2、experiment_targets=2、interactions=1、quotes=0、experiment_outcomes=0、companies=46、signals=185、opportunities=4。既有1条 Interaction 保留，本轮新增0。T09 与客户状态未改动，未发送消息。见 protected_before/after.json。

## 8. 资源与成本

完整配对下载字节旧/新：{counts['old']['bytes']:,}/{counts['new']['bytes']:,}，包括 robots 和允许的 JS/CSS 资源。Chromium 子进程树最高采样 RSS **{peak:.1f} MiB**。Python 进程 RSS 每25ms采样，记录于每条 old/new.python_peak_rss_bytes；为同一长期运行进程的绝对 RSS，存在热缓存和顺序效应，不是独立进程增量内存比较。浏览器树 RSS 每50ms监视，也不是操作系统硬配额。

域名间隔至少2秒并服从更严格 robots；单进程 HTTP 并发1、浏览器并发1；响应2MB、累计8MB、最多30请求；HTTP10秒、阶段60秒；浏览器导航25秒、进程树50秒/800MiB/CPU35秒。robots 使用安全通道强制逐跳检查，SDK `check_robots_txt=False` 是为防止额外独立联网，并非关闭本项目的 robots 检查。robots 404/410 按 RFC 9309 未配置处理，其他异常停止。

本次不调用 LLM，不消耗模型 token/API；未测电费、云成本或月度运营成本，不能给出虚构价格节省。JS 比静态昂贵，必须按诊断按需使用。浏览器/缓存磁盘与安装依赖开销为本地实际安装，不等同于每页运行成本。

## 9. 风险与未通过项

1. 技术沙盒具有真实访问与明确许可，但商务类型覆盖0；采购主体、日期、Signal 可用性、Actionability 和业务误报/漏报均未验证。
2. PDF 默认全部拒绝，没有占位正文；当前未实现明确策略下的页数受控解析（验收缺口），不把文件字节上限当页数验证。
3. 新安全通道 DNS 集变化即停止，可能拒绝合法 CDN 轮换；外域 JS/广告/字体阻断可能导致缺内容。脚本驱动跳转不接受，登录/付费/验证码绝不尝试绕过。
4. 原采集器的遗留安全缺口仍在，未通过本任务统一升级。新路径安全失败不能回退到旧 HTTP。
5. 本地锁仅保证单 FastAPI worker；多 worker/多主机全局限流和 OS 浏览器硬隔离未实现，不能上线扩量。站点许可依赖可信管理员核实，字段齐全不等于法律许可已自动判定。
6. 通道没有自动生成 Signal，代价是需要人工主体归属/字段/证据审核；这有意保留质量门，不以多抓正文替代质量提升。
7. A/B 有中断和恢复，样本及统计条件如实公开；未执行的内容和不能测的准确性不补造。框架测试通过不等于真实商业质量通过。
8. 遗留测试曾清理正式 raw 目录；本轮快照从报告副本完整恢复、最终测试不再触碰该目录，但历史快照是否曾丢失不能排除，是进入后续阶段前必须解决的证据存储风险。

## 10. 是否继续 T10-C2

**当前不建议进入扩量 T10-C2。** 可在人工验收后继续受控的小样本技术验证，先补齐真实采购/技术资料站点的条款与路径许可、20～30条业务类型对照、日期/角色人工真值、PDF字节/页数受控策略和商业 Evidence/Actionability 检验。仍不得启动100家扩量、自动批准生产信号或自动触达。

本轮完成后停止。默认开关仍为 false，正式许可文件没有创建。等待人工质检和下一阶段授权。
'''
    (OUT.parent/"T10-C1_CRAWL4AI_INTEGRATION_REPORT.md").write_text(report,encoding="utf-8")
    (OUT/"summary.json").write_text(json.dumps(dict(paired_urls=len(rows),static=len(static),js=len(js),counts=counts,expected=expected,protected_unchanged=True,commercial_samples=0,recommend_t10_c2=False),ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(dict(paired_urls=len(rows),counts=counts,report=str(OUT.parent/"T10-C1_CRAWL4AI_INTEGRATION_REPORT.md")),ensure_ascii=False))
