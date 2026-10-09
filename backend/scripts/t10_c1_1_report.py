"""由真实日志和逐条审计生成 P0 交付报告，不访问网络或修改业务库。"""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/reports/t10_c1_1'
def read(name):return json.loads((OUT/name).read_text(encoding='utf-8'))
def summary(name):
    text=(OUT/name).read_text(encoding='utf-8-sig')
    return next(line.strip('= ').strip() for line in reversed(text.splitlines()) if re.search(r'\d+ passed',line))
base=read('baseline.json');plan=read('repair_plan.json');changes=read('formal_changes.json')
post=read('post_repair_verification.json');hash_audit=read('formal_hash_audit.json');proof=read('offline_generation_proof.json')
for name in ('independent_final.txt','related_final.txt','related_reverse.txt','full_final.txt'):
    text=(OUT/name).read_text(encoding='utf-8-sig')
    assert 'FAILED ' not in text and 'ERROR ' not in text and 'passed' in text,name
offsets=[];snapshots=[]
for r in plan:
    def detailed(e=None):
        return dict(source_record_id=r['source_record_id'],signal_id=e['signal_id'] if e else [s['id'] for s in r['downstream_dependency']['signals']] or 'UNKNOWN',
            evidence_id=e['evidence_id'] if e else [v['evidence_id'] for v in r['evidences']] or 'UNKNOWN',
            source_url=r['source_url'],snapshot_reference=r['snapshot_reference'] or 'UNKNOWN',text_version=r['text_version'],
            content_hash=r['content_hash'],body_sha256=r['body_sha256'],
            stored_offset=e['stored_offset'] if e else [v['stored_offset'] for v in r['evidences']] or 'UNKNOWN',
            stored_excerpt=e['stored_excerpt'] if e else [v['stored_excerpt'] for v in r['evidences']] or 'UNKNOWN',
            actual_excerpt=e['actual_excerpt'] if e else [v['actual_excerpt'] for v in r['evidences']] or 'UNKNOWN',
            problem_type='INVALID_EVIDENCE' if e else 'MISSING_SOURCE_SNAPSHOT',downstream_dependency=r['downstream_dependency'],
            treatment='QUARANTINED; ORIGINAL_TEXT_AND_OFFSETS_UNCHANGED; HUMAN_REVIEW_REQUIRED',
            audit_log_ids=[c['audit_log_id'] for c in changes if c['id']==r['source_record_id'] or (e and c['id']==e['evidence_id'])])
    for e in r['evidences']:
        if not e['exact']:offsets.append(detailed(e))
    if 'MISSING_SOURCE_SNAPSHOT' in r['problem_type']:snapshots.append(detailed())
(OUT/'anomalies_detailed.json').write_text(json.dumps({'unique_source_records':len(plan),'offset_anomalies':offsets,'snapshot_anomalies':snapshots},ensure_ascii=False,indent=2),encoding='utf-8')
offset_table=['|SourceRecord / Evidence / Signal|偏移差异|处置|','|---|---|---|']
for r in plan:
    for e in r['evidences']:
        if e['exact']:continue
        delta='引用空白被归一化，无法在原文精确找到' if not e['exact_quote_positions'] else f"存储 {e['stored_offset']}，完整引用原文起点 {e['exact_quote_positions']}；原始快照缺失"
        offset_table.append(f"|{r['source_record_id']}<br>{e['evidence_id']}<br>{e['signal_id']}|{delta}|INVALID_EVIDENCE；保留原文与引用，隔离待审|")
snapshot_table=['|SourceRecord|原始 URL|快照情况与下游|','|---|---|---|']
for r in plan:
    if 'MISSING_SOURCE_SNAPSHOT' not in r['problem_type']:continue
    snapshot_table.append(f"|{r['source_record_id']}|{r['source_url']}|声明文件缺失；{len(r['downstream_dependency']['signals'])}条Signal、{len(r['downstream_dependency']['opportunities'])}条Opportunity依赖；MISSING_SOURCE_SNAPSHOT隔离|")
impact_table=['|Opportunity|历史审核状态|本次风险与门禁|','|---|---|---|']
for o in post['opportunities']:
    impact_table.append(f"|{o['id']}|{o['review_status_preserved']}（保留）|INVALID_EVIDENCE_REVIEW_REQUIRED；禁止新评分、批准、验证与目标推进|")
file_list='\n'.join('- '+p.replace('\\','/') for p in post['modified_files'])
report=f'''# T10-C1.1 可信证据链与安全门禁 P0 修复报告

日期：2026-10-08。项目：D:\\myAI\\bizpulse。**T10-C1.1 = PASS（P0 修复 Gate）**。T10-C1 整体验收仍等待人工复验，T10-C2 继续 BLOCKED。本轮没有开始真实批量采集、扩量、客户触达或 C2 开发。

## 1. Git 基线与备份

项目目录真实存在。已阅读原验收报告、evidence_audit.json、offline_probes.json、collection_tests.txt、full_pytest.txt。原基线为相关测试158通过/1失败、全量576通过；不能只凭原全量结果忽略独立相关失败。

原工作区已有大量未提交修改，完整基线见 [git_before.txt](t10_c1_1/git_before.txt)，结束状态见 [git_after.txt](t10_c1_1/git_after.txt)。本轮没有 reset、clean、提交或覆盖无关工作，也没有修改前端、创建新数据库架构或新服务。

修复前使用 SQLite 只读连接与 backup API 得到一致性备份；原文逐文件复制并核对 SHA256。备份位置：`{base['backup_path']}`，文件具有 Windows ReadOnly 属性，位于 Git 项目目录之外，未纳入 Git。备份 manifest.json 保存数据库 SHA256、29张表的行数/内容哈希和91个原文文件哈希；项目内 baseline.json 保存清单，不保存完整数据库。

测试使用 backend/data/bizpulse_test.db，与正式库 backend/data/bizpulse.db 分离。测试结束回收连接并删除测试库；临时生成计量使用独立 TemporaryDirectory 数据库。正式库写入发生在代码与隔离测试通过后，并逐条检查基线未变、备份有效和影响范围；后续门禁补查再次回归。

## 2. 受影响代码与复用范围

复用现有 SourceRecord 版本、metadata、SignalEvidence 偏移、验证状态、Opportunity risk_notes、AuditLog、采集/分析与人工审核 API。不新增表或迁移，不改写原文，不重新设计业务架构。新增小型 evidence_integrity / url_safety 公共校验，供现有入口调用；保持成功接口的请求/响应主体兼容。

修复前后 Python 文件 SHA256 实际差异清单如下；另新增本报告及验收日志。清单中的既有脏文件只改动本轮涉及的函数：

{file_list}

## 3. 四条偏移异常逐条处理

138条SourceRecord、52条Evidence的基线仍保留。4条偏移异常与5个缺失快照有3条SourceRecord重叠，合并后涉及 **6条SourceRecord**，不能简单相加成9条不同来源问题。

{chr(10).join(offset_table)}

三个政府公告引用虽然可在存储正文找到完整位置，但相应原快照已经缺失；不能仅修偏移后就宣称已恢复可信源。汉邦激光引用的空格与原文不换行空格不同，当前没有完整引用的精确匹配，也没有可用原HTML版本。本轮都采用隔离，未反向补造正文，未修改引用或偏移迎合检查。

逐条 source_record_id、signal_id、evidence_id、source_url、snapshot_reference、text_version、content_hash、stored_offset、stored_excerpt、actual_excerpt、problem_type、downstream_dependency 和对应审计ID全部输出在 [anomalies_detailed.json](t10_c1_1/anomalies_detailed.json)。该文件保留精确空白，正文和引用差异不要用 Markdown 渲染后的外观判断。

## 4. 五个缺失快照逐条处理

已搜索项目原文、报告归档及现有备份中的对应文件名，未找到可证明为原版本的恢复文件；本轮新建备份也不能恢复此前已缺失的文件。

{chr(10).join(snapshot_table)}

缺失条目的完整路径、版本、存储正文哈希、关联Evidence及实际摘录见上述逐条JSON与 [repair_plan.json](t10_c1_1/repair_plan.json)。海底捞/比亚迪条目没有Signal/Evidence依赖，相应证据字段明确为UNKNOWN。原始快照缺失保留为事实，不生成HTML占位文件，不删除历史记录。

## 5. 下游影响与正式隔离

共隔离6条SourceRecord、9条相关Evidence、16条直接或证据依赖Signal；4条Opportunity追加风险标志。16条包括历史APPROVED/REJECTED/SUPERSEDED记录；保留原status及历史结论，仅追加 evidence_integrity 风险和 REVIEW_REQUIRED 验证状态。原有50条APPROVED未批量撤销或重新批准。

{chr(10).join(impact_table)}

SourceRecord元数据与verification_status隔离，Evidence标为INVALID_EVIDENCE或MISSING_SOURCE_SNAPSHOT；Signal payload标记需要人工重新审核；Opportunity风险标为INVALID_EVIDENCE_REVIEW_REQUIRED。审计actor为 `system:T10-C1.1-remediation`，明确表示维护程序隔离，不冒充客户/人工审核人。

修复后只读实际复核：16条依赖Signal均返回INVALID_EVIDENCE，机会分析上下文排除它们，4条Opportunity被门禁阻断，相关5家企业的validation_ready/contact_ready均为false。市场验证排序及目标选择也排除失效依赖。人工创建新机会、重新评分、批准/ready、强制阶段推进均不能绕过隔离。

T09 Experiment、ExperimentTarget、Interaction、客户状态等非目标表内容哈希一致。汉邦激光历史READY_TO_CONTACT状态仍保留；它不代表隔离后仍实际联系就绪。风险未人工复核通过前不能继续作为有效新商机使用，本次没有新建Interaction或联系客户。

## 6. Evidence版本和偏移语义

|字段|统一含义|
|---|---|
|SourceRecord.raw_text|已存引用正文；Crawl4AI路径为清洗DOM正文，保持既有字段兼容|
|原始HTML/响应字节/原始可见文本|分别保存快照；不借用清洗正文偏移|
|clean_text|Crawl4AI的cleaned_text_path对应文本；与该记录raw_text完全一致|
|text_version|SourceRecord.version_number，加上固定source_record_id引用不可混用新旧版本|
|content_hash|既有采集去重指纹；不能误认为单纯正文哈希|
|body_sha256|新增metadata evidence_text_contract中的实际引用文本SHA256|
|start_offset/end_offset|Python Unicode字符索引，左闭右开，不是UTF-8字节索引|

精确校验固定为 `referenced_text[start:end] == evidence_excerpt`。规则窗口保留换行/NBSP等原文字面值；LLM改写、空白归一化或无法完整定位的片段不获得有效证据偏移，也不能批准。全文完整定位后重新计算候选偏移，避免沿用与LLM替换前草稿对应的旧位置。

新增采集记录存储文本basis/版本/正文哈希合同；人工候选批准校验版本与快照并记录合同。多来源证据合并也精确校验，必须经人工操作才能更新已批准信号。Crawl4AI解析器由css-v1升级css-v2，旧快照按旧版本复核，未重写历史快照。

离线隔离库实际生成Evidence **{proof['new_evidence_count']}条，精确偏移通过{proof['exact_pass_count']}条（100%）**；自动批准0，网络请求0，正式写入0，明确是测试夹具，不计真实商业样本。[计量记录](t10_c1_1/offline_generation_proof.json)。原20条真实沙盒归档/200个引用的位置仍可离线复核，不作为本轮新采集。

## 7. CSS清洗修复

默认/CSS/JS都使用明确的DOM正文清洗。CSS路径在保存原始可见文本之后，对清洗副本移除nav/footer/aside/form/svg/iframe和aria-hidden内容；有效article段落保留。未经清洗的快照和原始文本保留导航页脚。本轮同时测试HTTP与模拟JS渲染的article/nav/footer夹具、Evidence快照一致性及正文保留。

## 8. 发布时间与Actionability修复

显式配置节点的发布时间经严格日期校验后进入 `CollectedItem.published_at → SourceRecord.published_at → Signal.published_at`，不再只在metadata里出现。无时区日期保存为naive/UNKNOWN时区，不猜UTC。网页发布时间、显式事件时间、collected_at、deadline分别处理，截止日期不回填发布时间。

新鲜度不再以collected_at兜底。2020新品页返回WATCH；无日期新闻/招聘不能仅凭最近采集成为ACTIONABLE_NOW；显式近期招聘日期可进入规则窗口；缺失标准日期但已有明确metadata历史日期的旧记录，也不能被缓存近期状态覆盖。CONTRACT_AWARD始终按历史/不可行动处理，过期、取消等既有采购生命周期规则保留。

实际保存的汉邦招聘Signal日期为2026-04-30，SourceRecord标准日期缺失且引用不一致，现已隔离；不能宣称这是已核实的近期招聘。近期招聘规则正例使用明确标记的离线日期夹具，**本轮未取得新的经核实近期真实招聘公告样本**，不编造其真实性。

## 9. 全局人工审批门禁

Settings补齐REAL_DATA_ONLY/NO_FAKE_DATA/NO_FAKE_EVIDENCE/NO_UNVERIFIED_FACT/NO_AUTO_APPROVAL。NO_AUTO_APPROVAL在本阶段固定True，错误配置关闭会失败，不能因等级/阈值关闭门禁。

检查HTTP/Crawl4AI/RSS、CSV导入、手动URL、规则/LLM分析、批处理、重分析与版本变化入口：采集衍生Signal为REVIEW，分析候选为REVIEW_REQUIRED。Crawl4AI继续不直接创建Signal或Opportunity。source=A、confidence达标或LLM建议不批准信号，不自动向既有APPROVED追加新的有效证据。

人工批准必须走明确审核操作，校验actor、证据和隔离状态，记录审核时间、动作及AuditLog。单机现有API默认actor为local-user，测试actor仅用于隔离测试库；正式修复没有用测试人名审批。多人部署仍需独立身份认证，不把当前单机actor当作多人认证能力。

## 10. 来源可靠性隔离

根因是共享MANUAL_URL Source经政府URL升级为A后，普通商业URL继承同一Source。修复为按实际来源origin隔离手动Source；政府域名规则仅能作用于同域且未混入跨域记录的来源，共享入口不能升级。来源创建/等级变化写AuditLog。普通企业记录仍C、政府记录A且source_id不同；SourceRecord保留采集时等级快照，不依靠测试先后顺序污染其他来源。

来源平台等级、单条记录等级和单条Evidence质量分别处理。新增测试检查共享入口不升级、跨域升级拒绝、同域幂等、审计记录和记录快照；没有把原失败断言改为接受“所有来源都是A”。

## 11. URL安全与PDF边界

先规范化/解码参数名，再识别凭证键；覆盖百分号/双重编码、大小写、重复键、用户名密码和嵌套redirect URL。危险请求拒绝，合法page/q/tokenizer等参数仍允许；日志移除用户信息/query/fragment，离线测试凭证值不输出到采集日志。

普通HTTP复用已有SafeFetch固定公网IP传输及robots，重定向逐跳在请求前校验，避免HTTP库重新DNS解析形成重绑定窗口；不导入SDK或无条件启动Chromium。Crawl4AI保留站点许可、robots、DNS变化停止、固定公网IP、TLS域名校验、域名限频、并发/超时/资源上限及访问控制停止。

兼容边界：普通HTTP现在使用SafeFetch保守上限（2MiB正文、15秒单次超时、至少2秒间隔、拒绝非identity压缩响应）；超过边界明确失败，不返回伪正文。相比旧设置上限更保守，真实大页面/压缩站点兼容性需后续独立验证，不能由离线回归推断所有公网来源可用。

PDF继续拒绝：Crawl4AI为PDF_STRATEGY_NOT_CONFIGURED（等价不支持），普通HTTP明确PDF_UNSUPPORTED。不新增复杂PDF解析器，不把占位文本或错误页当正文。

## 12. 独立、相关与全量测试

执行命令均为项目虚拟环境 `.venv/Scripts/python.exe -m pytest`，没有全局安装或正式测试库混用。

|执行|真实结果|日志|
|---|---|---|
|先运行失败文件test_evidence_chain.py|{summary('independent_initial.txt')}|independent_initial.txt|
|最终独立文件|{summary('independent_final.txt')}|independent_final.txt|
|相关集合正序|{summary('related_final.txt')}|related_final.txt|
|相同相关集合反序|{summary('related_reverse.txt')}|related_reverse.txt|
|最终全量pytest|{summary('full_final.txt')}|full_final.txt|

4条警告为既有FastAPI on_event弃用提示。相关集合覆盖适配器、HTTP/RSS、URL安全、证据、可靠性、归属/生命周期相关既有模块、人工审批、机会生成、Validation/Contact Ready、市场候选和目标选择。

没有隐藏中间失败：related_initial曾6失败/104通过；full_initial曾25失败/564通过；related_second曾1失败/79通过且Windows清理1错误；full_second曾1失败/588通过。主要来自被本次明确安全规则替代的旧假设、离线夹具原文与Evidence不自洽，以及无日期招聘夹具。修复测试夹具与程序后重跑；测试退出时gc回收再dispose连接池，解决Windows测试库句柄占用。初始备份计划曾查询不存在字段、一次临时shell只读查询引号错误，均在正式写入前停止并修正，未造成业务变更。

测试更新有业务依据：无日期不再当近期；新来源须人工审核后合并；离线夹具显式包含自身引用原文和日期。没有修改正式原文或把可靠性断言统一改A来通过测试。

## 13. 正式库变更、审计与可逆性

正式库仅改变source_records、signal_evidences、signals、opportunities及audit_logs。新增AuditLog35条；其他24张表内容SHA256完全一致。目标表中的非目标行也逐条比对完全一致。业务记录新增0/删除0；91个原文文件前后哈希全部一致。完整哈希审计见 [formal_hash_audit.json](t10_c1_1/formal_hash_audit.json)。

每条修改的表、主键、原因、before/after精确值、AuditLog ID保存于 [formal_changes.json](t10_c1_1/formal_changes.json)，同时写入正式AuditLog。对隔离状态的恢复须人工确认后逐条比较当前值等于本次after，再恢复允许字段并追加回退审计；不得删审计日志或自动恢复为有效机会。本轮不自动回退。

只读复核结果见 [post_repair_verification.json](t10_c1_1/post_repair_verification.json)：历史精确偏移48条仍保留；4条不一致全部隔离，未隔离偏移异常0；5个缺失快照全部隔离。这里不是宣称缺失文件已恢复或52条都可信。

## 14. P0 Gate与结论

|Gate|结果与依据|
|---|---|
|1 异常证据修复或隔离|PASS：6个来源、9个关联Evidence风险隔离，完整逐条计划/审计|
|2 新Evidence精确偏移|PASS：离线实际4/4，Unicode/版本回归通过；真实新增样本0|
|3 无失效依赖驱动新商机|PASS：16条Signal/4条Opportunity阻断，评分/审批/市场排序/目标推进有门禁|
|4 发布时间标准链|PASS：HTTP/Crawl4AI显式日期进入标准字段，未知时区保留|
|5 历史不因近期采集变新|PASS：历史/无日期/缓存状态/截止日期分别验证|
|6 不自动批准|PASS：自动批准0，候选待审，人工动作与审计可追溯|
|7 来源不共享错误升级|PASS：同域隔离及跨域拒绝；正反顺序一致|
|8 CSS清洗|PASS：HTTP/JS夹具清洗副本过滤，原始快照完整|
|9 凭证绕过阻断|PASS：编码/重复/嵌套/重定向离线测试与合法参数测试通过|
|10 独立/组合/全量零失败|PASS：最终三类测试均0失败|
|11 正式变更可审计|PASS：35条审计、非目标表/行及原文哈希一致|

**T10-C1.1 = PASS。** 该结论限定于此次P0安全修复，不代表真实业务采集质量已通过T10-C1整体验收。

## 15. 尚未解决的风险与停止状态

原5个缺失快照及4条历史偏移异常未进行可信恢复，已隔离等待人工处理；汉邦激光现有机会需重新复核。历史主体结论、客户状态及T09实验未被本轮重写。近期真实招聘正例、采购/产品参数业务来源对照、PDF解析、真实大页面兼容性仍未验证；不能用测试夹具补足真实样本。

没有自动触达、创建互动或成交，也没有启动100家扩量。Crawl4AI版本仍固定0.9.4；原有许可/浏览器资源上限保留。T10-C1整体待人工复验，**T10-C2仍BLOCKED**。本轮工作停止，等待人工复验；不自动开始真实批量采集。
'''
report=report.replace('](t10_c1_1/',']('+OUT.as_posix()+'/')
(ROOT/'docs/reports/T10-C1_1_P0_REMEDIATION_REPORT.md').write_text(report,encoding='utf-8')
print('report_created')
