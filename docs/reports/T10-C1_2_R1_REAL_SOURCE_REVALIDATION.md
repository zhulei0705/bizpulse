# T10-C1.2-R1：真实来源小批次复验

执行日期：2026-10-13（Asia/Shanghai）。**R1 BLOCKED / TECHNICAL_REVALIDATION_INCOMPLETE / HUMAN_REVIEW_PENDING**。未发现已证实影响当前可行动机会的 P0；没有声称整个 T10-C1.2 通过。T10-C1.2 保持 FAIL / 待复验，T10-C2 继续 BLOCKED，下一轮扩量未授权，本轮结束后停止。

本轮读完三份前报告及采集、规则、提取、日期、Evidence、Actionability、readiness、审核/隔离代码。只新增验收脚本与报告/证据目录，未开发产品功能、未修改现有业务实现。Git 起始已有大量未提交修改，全部保留。

## 真实来源与去重

新增 5 个不同真实业务 URL，均与原 3 个样本不重叠，合计 8 个独立版本。全部使用 SafeFetch → WebPageCollector → persist_collected → run_extractor，独立 acceptance.db 和原文目录；LLM disabled，REAL_DATA_ONLY / NO_FAKE_DATA / NO_AUTO_APPROVAL 均 true。HTTP 5/5 成功；RSS/Crawl4AI 真实采集 0，静态页无需 JS。robots、固定公网 IP/TLS、逐跳检查、限频、大小和超时保护未放宽。

DOE 许可：[官方 Web Policies](https://www.energy.gov/web-policies) 的政府信息公开复制条款；保留政策快照及 SHA256，署名本地事实研究，排除第三方版权材料。正文不是普通宣传首页，分别包含资助申请、制造合作申请、RFP/RFI 与具体截止历史条目。资助金额不是采购预算，资助方不是企业买方。

|真实 ID / URL|业务类型|系统语义|标准发布时间（UTC）|日期检查|
|---|---|---|---|---|
|[rec_3cb665d1174a4656a2ea0e1a](https://www.energy.gov/articles/energy-department-announces-293-million-funding-support-genesis-mission-national-science)|FUNDING_CALL|TERM_MENTION/D0|2026-02-25 14:16:37|CONFLICT_REQUIRES_HUMAN_REVIEW|
|[rec_51c2ba9e67b34ed7b4227eb7](https://www.energy.gov/articles/energy-department-announces-500-million-strengthen-domestic-critical-materials-processing)|FUNDING_CALL|DEMAND_INFERRED/D1|2026-02-25 14:16:37|CONFLICT_REQUIRES_HUMAN_REVIEW|
|[rec_9dad27a890434fe4a5fdaf2d](https://www.energy.gov/cmei/articles/energy-department-solicits-applications-program-strengthen-us-manufacturing-sector)|APPLICATION_SOLICITATION|UNKNOWN/D0|2026-10-01 02:08:24|CONFLICT_REQUIRES_HUMAN_REVIEW|
|[rec_36c085ce25ef48d49bc457fb](https://www.energy.gov/oe/funding-opportunities-and-requests-information)|REQUESTS_FOR_INFORMATION|DEMAND_INFERRED/D1|2022-05-31 13:06:55|EXTRACTED_UNVERIFIED_DOCUMENT_DATE|
|[rec_eec050a982184ace8dd66b69](https://www.energy.gov/indianenergy/current-funding-and-technical-assistance-opportunities)|FUNDING_CALL|UNKNOWN/D0|2023-02-24 20:08:41|EXTRACTED_UNVERIFIED_DOCUMENT_DATE|

逐条来源类型、发布方、许可及版本、原始 HTML/清洗正文、采集/发布时间、哈希、准确引用、主体角色 UNKNOWN 和真实输出见 [collection.json](D:/myAI/bizpulse/docs/reports/t10_c1_2_r1/collection.json) 与 [verification.json](D:/myAI/bizpulse/docs/reports/t10_c1_2_r1/verification.json)。

**覆盖缺口**：新增中至少 2 条明确资助/合作申请征集（不是企业采购）；直接企业采购 0。企业产品/服务能力来源 0/2；不能把政府资助页计为企业供给。NIST policy/news 与 GitHub/raw GitHub 独立文档许可证 SafeFetch 网络失败；Microsoft Learn 通用许可有非商业限制，未准入其产品文档。额外 DOE 技术商业化路径 404 未计数。没有绕过拒绝，未用模拟页面凑数。DOE/电力、材料、制造、部落能源覆盖不等于充分跨行业验证。若下一任务完成许可核验，应优先补齐 2 条企业能力来源，仍需另行受控授权。

## 语义与主体角色

新增分类：{'TERM_MENTION': 1, 'DEMAND_INFERRED': 2, 'UNKNOWN': 2}；全部 D0/D1，DEMAND_EXPLICIT 0。5 页均正式 Signal 0、候选 0、Opportunity 0、自动批准 0。原 3 个历史快照本轮独立离线重放规则及 legacy extraction；counterpart 未再触发 AUTOMATION_DEMAND；4 处旧引用准确。独立 RPA/ERP/CRM、英文子串、供给/招聘/历史中标、角色及未知日期用本轮 232 项专项测试覆盖，测试夹具不计真实商业来源或人工审核。真实供给/招聘场景尚缺，不能宣称真实覆盖完成。

发布方 DOE/NIST 与业务主体分离：系统网站标签不作为买方确认。OE 混合页“Request for Proposals”只得到 D1 推断，没有高价值购买事实；关键主体、采购意图、业务角色待人工核实。

## 日期端到端与新发现

5/5 CollectedItem → SourceRecord 按选中明确元数据正确转换 UTC；没有使用采集时间补原发布日期。原时区与字面值存元数据，原始发布时间和正文显示日期同时保留在 verification.json。没有真实 Signal/Opportunity，因此这两层日期链真实验收 **BLOCKED / NOT_EXERCISED**，单元测试通过不冒充端到端真实验证。

发现 **P1 日期来源冲突**：Genesis、Critical Materials 的 META / JSONLD 为 2026-02-25，但文章 display-date 分别 March 17, 2026 / March 13, 2026；制造业申请公告 META 日期 September 30, 2026，与 display-date October 2, 2026 不同。现行解析首个有效元数据后返回，未暴露后续冲突。未认定哪一方为真、未修改历史或业务代码，审计标为 CONFLICT_REQUIRES_HUMAN_REVIEW，不能声称发布时间准确通过。三者不是因时区差产生的日历差异。

OE 页面 DOCUMENT 创建日期 2022-05-31，列表内事件日期单独存在，如 7/9/2026 公布、9/7/2026 截止；不能把文档创建或采集时间当该事件日期。Indian Energy 文档创建日期 2023-02-24，不代表所有资助仍有效。事件时间、逐项目截止和当前状态 UNKNOWN / 待核；没有产生 ACTIONABLE_NOW。原 3 条只做留存快照重放，原 acceptance.db 的 UNKNOWN 发布时间未回写修复。

## Evidence 与历史影响

8 个版本均保留原始 HTML、同版本正文、版本和原文/正文 SHA256；5 个新正文由同版本 HTML 重解析逐字相等。引用 18/18 精确，Unicode [start,end) 切片相等，100%。正式 SignalEvidence 0；审核摘录和旧候选引用不能包装成正式 Evidence。116 条历史记录证据问题另列，不混入新样本 100% 指标。缺失历史快照未用在线页面替代。

116 条审计：CONFIRMED_ERROR 2（已隔离偏移不匹配）、INSUFFICIENT_EVIDENCE 114；P0=0、P1=6、P2=110、UNKNOWN=0。3 个关联机会被 INVALID_EVIDENCE 门禁阻断；没有可确认独立有效购买证据。完整逐条审计见 [116 风险审计](D:/myAI/bizpulse/docs/reports/T10-C1_2_R1_116_RISK_AUDIT.md)。

## 真人审核

真实审核完成 0；全部 8 条 PENDING_HUMAN_REVIEW。已准备原 3 + 新 5 条完整材料，推荐 5 条不同关注点优先审查。[真人审核包](D:/myAI/bizpulse/docs/reports/T10-C1_2_R1_HUMAN_REVIEW_PACKET.md) 内有审核人、时间、依据、判断、意见、签字栏；没有代填结果、没有正式 APPROVE。

## 本轮实际测试与保护

|执行|结果|日志|
|---|---|---|
|语义、缩写、角色、日期生命周期、Evidence、审核、采集安全专项 pytest|232 passed in 41.46s|related_pytest.txt|
|全量 pytest|743 passed in 187.35s (0:03:07)|full_pytest.txt|
|8 版本 / 精确引用验证|8 版本；18 引用准确；3 日期冲突|verification.json|
|历史门禁回归|6 SourceRecord / 9 Evidence / 16 Signal / 4 Opportunity；7 gate_checks 全 true|history_gate.txt|
|前端构建|N/A：未改前端、无新增 UI 行为|没有借用旧结果|

正式库 29 张表排序行哈希与 91 份历史原文文件哈希前后全等，integrity_check ok / foreign_key_check 空；T09、Interaction、审核状态包含在核对中。原 C1.2/P0A 归档逐文件全等，执行前所有既有文件哈希一致，除本轮新脚本开发变化外无既有文件变化。无 reset/clean/提交/推送、客户邮件、Interaction 创建、生产写入或隔离解除。[保护核对](D:/myAI/bizpulse/docs/reports/t10_c1_2_r1/protection_result.json)；baseline/git/文件与归档清单均存本轮目录。

工具过程错误如实保留：初次 audit 导入 OpportunityCandidate 路径错误，未执行生产写入，修正后再运行；一次终端正文查看因 GBK UnicodeEncodeError 失败，不影响原文。搜索工具 429/验证码页面未绕过，改用已有 SafeFetch 有界公开路径调查。多次 discovery 最初复用了临时编号，后一次 404 覆盖了 Microsoft 通用政策临时快照；该来源未准入、未计样本、未作许可依据。DOE 已使用的政策 discovery_1.html 哈希复核一致；后续不再写入临时调查文件。

## 验收判定与停止范围

|条件|状态|
|---|---|
|116 条逐项分类及下游风险|PASS（真实性恢复未完成）|
|至少 5 条新增合法真实业务 URL|PASS，5，与旧 3 无重叠|
|缩写误报回归|PASS（历史真实反例 + 专项）|
|真实企业供给不误认采购|BLOCKED，企业能力来源 0/2|
|严重角色误判为零|未发现自动高价值错误，但真人角色核实 BLOCKED|
|原发布时间准确及完整真实下游传递|BLOCKED，3 冲突；正式下游真实链未生成|
|所有被引用新旧复验 Evidence 精确|PASS，审核/候选引用；正式 Evidence 0|
|历史隔离与安全回归|PASS|
|全量 pytest 零失败|PASS，本轮 743 passed|
|正式库/原文/既有修改保护|PASS|
|独立真人审核|BLOCKED，0/8|

**不放行 TECHNICAL_PASS，也不宣布 T10-C1.2 PASS。** 下轮只可在另行授权后处理日期冲突门禁、补齐 2 个合法企业能力样本、逐事件日期证据和 3–5 条真实审核；不自动进入扩量或 T10-C2。确认当前可行动 P0 时应立即停止并另行授权历史修复；本轮未触发该条件。新增采集已停止。
