# T08.0 数据质量修复与回归 · 报告

> 项目：BizPulse（商脉）实际项目目录：`D:\myAI\bizpulse`（任务书所写 bizpulse-fullstack-v1 不存在）
> 任务：T08.0 — 数据质量修复与回归（在 30/100/300 扩量之前修复真实数据链中的质量问题）
> 状态：**394 个测试全部通过**（T08 结束 350 + T08.0 新增 44）；三真实采购公告 12 项回归全部确认；历史污染数据已正式标记处理。

---

## 1. 找到的根因

| 问题 | 根因 | 修复 |
| --- | --- | --- |
| P0-1 ccgp 被建成 Company | `extractor.identify_company` 的域名 fallback 把来源平台域名（ccgp.gov.cn）截成 "ccgp" 当作企业名；og:site_name "中国政府采购网" 同样漏过 | 平台域名黑名单 `SOURCE_PLATFORM_DOMAINS` + `is_source_platform_domain()`；平台域名页面识别直接返回 None（含 title fallback 禁用）；平台样名（"××政府采购网/招聘网/新闻网"）过滤 |
| P0-2 Evidence 是导航/footer | 两套规则引擎的 excerpt 取"匹配点±60 字"窗口，ccgp 页面导航文字压平后落在窗口内；ccgp 页面导航用 div 而非语义标签，nav 删除不生效 | `EvidenceQualityGate`（evidence_quality.py）：导航/页脚/热线 token 密度、热线号码、字符多样性判定；`extract_valid_evidence()` 把低质窗口**重定位到实质句**，全低质则放弃该信号 |
| P0-3 NEW_PRODUCT/POLICY_IMPACT 误判 | 两套引擎（extractor._RULES 与 analyzers.signal_rules.RULES）无采购上下文概念；GOVERNMENT 来源 hint 甚至允许 POLICY_IMPACT；"采购产品/发布中标公告"误触产品/政策规则 | `is_procurement_context()`（招标/中标/采购公告/采购项目编号等结构化特征）+ `_SUPPRESSED_IN_PROCUREMENT`：采购上下文中两套引擎都只产采购族（PROCUREMENT/TENDER/SUPPLIER_SEARCH/需求族），抑制 19 类非采购信号 |
| P0-4 等级不一致 | SourceRecord.source_reliability 是采集时快照（来源 A 前采集的记录留 C）；下游无统一传递规则 | `services/reliability.py`：`effective_grade/score`（可降不可升，无理由升级压制回 Source 等级）；persist 快照继承 Source；cleanup 按 Source 刷新全部历史快照 |
| P0-5 published_at 为空 | `_detect_publish_time` 只看 meta/time 标签；ccgp 公告时间在正文表格里且**无冒号**（"公告时间 2026年09月30日 19:45"）；parse_published_raw 不支持该格式 | `procurement_parser.parse_announcement_time` 支持三种真实格式（冒号体/表格压平体/中文日期）；入库时 `metadata_json.freshness_source = ANNOUNCEMENT_TIME / COLLECTED_AT_FALLBACK`；cleanup 已回填 **44 条**历史记录 |
| P0-6 联系人未结构化 | 无提取器；代理/采购人信息混在正文表格 | `procurement_parser.extract_procurement_contacts`（主体声明锚点分区 + ccgp"采购人信息 名 称："格式）；**PURCHASER_CONTACT / AGENCY_CONTACT / PROJECT_CONTACT** 严格区分，归属正确主体；campaign 采集时自动入库（VERIFIED_PUBLIC + source_url）；CompanyContact 加 contact_type/organization_name（迁移 d1e6f8a3b5c9） |
| P0-7 Interaction contact_id=null | T06 前端联调时人工记录（审计日志 actor=local-user 可证），当时该企业无任何联系人记录；摘要中邮箱无来源可验证 | **只报告不伪造**（见第 11 节） |
| P1-1 Experiment 逻辑冲突 | 无启动前一致性校验 | `ExperimentValidationService`（6 类检查：目标数矛盾/标准超出目标/标准含糊/报价缺失/无目标运行/快照缺失）；start 响应返回 consistency_warnings 且写入快照 |
| P1-2 HTTP 200 但 parse_status=OK、raw_text=null | 状态枚举过粗（OK/FAILED），正文空仍算 OK | 新枚举 FETCH_SUCCESS/PARSE_SUCCESS/PARSE_EMPTY/JS_RENDER_REQUIRED/FAILED；正文空→PARSE_EMPTY，大 HTML 小正文→JS_RENDER_REQUIRED；ingest 对 PARSE_EMPTY/JS_RENDER_REQUIRED 拒绝入库 |
| P1-3 类型缺失 | T08 的 8 类枚举无 SOURCE_PLATFORM；存量公司全 UNKNOWN | 枚举加 SOURCE_PLATFORM；cleanup 按名称规则回填（"大学"→UNIVERSITY、"研究所"→RESEARCH_INSTITUTE、"有限公司"→COMPANY；ccgp→SOURCE_PLATFORM） |

## 2. 修改文件

**新增服务**：`services/evidence_quality.py`、`services/procurement_parser.py`、`services/reliability.py`、`services/experiment_validation.py`、`services/data_cleanup.py`
**修改**：`services/extractor.py`（平台黑名单识别 + 采购上下文抑制 + Evidence 门）、`analyzers/signal_rules.py`（同套抑制 + Evidence 门）、`collectors/web.py` + `collectors/base.py`（parse_status 新枚举）、`services/collection_engine.py`（SKIPPED 判断兼容新枚举）、`services/campaign_runner.py`（采购字段解析/published_at/freshness_source/联系人入库）、`services/ingest.py`（空正文/JS 页拒绝）、`api/endpoints/experiments.py`（start 校验）、`core/constants.py`（SOURCE_PLATFORM_DOMAINS/ORGANIZATION_TYPES+SOURCE_PLATFORM）
**新增测试（9 个）**：test_source_company_separation / test_procurement_parser / test_evidence_quality_gate / test_signal_false_positive / test_reliability_propagation / test_published_at_parser / test_procurement_contact_extractor / test_experiment_consistency / test_parse_empty
**数据迁移**：`d1e6f8a3b5c9`（company_contacts.contact_type / organization_name），已应用。

## 3. 数据库是否需要 Migration

需要且已完成 1 个：`d1e6f8a3b5c9`（company_contacts 两列）。parse_status 的值变更（OK→PARSE_SUCCESS）与 published_at 回填为**数据修复**（cleanup service 执行，全部写审计 DATA_QUALITY_FIX），无 schema 变更。

## 4. 旧污染数据处理方案（不篡改、保留审计）

`services/data_cleanup.py`（正式库已执行）：
- **ccgp 平台残留 Company**：organization_type=SOURCE_PLATFORM + status=SUPERSEDED（不删除）；
- **其上的 108 条误报/挂错主体 Signal**：status=SUPERSEDED + payload_json.t080_superseded_reason（历史保留可追溯）；
- **采购主体重关联**：parse_purchaser 能确认主体的记录改指采购单位企业；1 条清华中标公告正文为表格无"采购人："声明 → **保持现状报告人工处理**（不猜测）；
- **可靠性快照**：按当前 Source 等级刷新（0 条需刷新——T08 批次采集时快照已正确）；
- **parse_status**：62 条 OK → PARSE_SUCCESS（无正文空的记录）；
- **published_at 回填**：44 条 ccgp 记录从正文公告时间回填 + freshness_source=ANNOUNCEMENT_TIME。
- 全部操作写 DATA_QUALITY_FIX 审计事件。

## 5. 三个真实采购页面回归结果（12 项逐条确认）

对华南理工/清华/中科院三条真实 ccgp 公告记录逐条验证：

| # | 确认项 | 华南理工 | 清华 | 中科院理论物理所 |
| --- | --- | --- | --- | --- |
| 1 | ccgp 不再是业务 Company | ✅ SOURCE_PLATFORM/SUPERSEDED，未取代的平台公司=0 | ✅ | ✅ |
| 2 | 采购主体正确 | ✅ 华南理工大学挂其公告 | ✅ 清华大学 | ✅ 中科院理论物理所 |
| 3 | PROCUREMENT 正确 | ✅ | ✅ | ✅ |
| 4 | TENDER 正确 | ✅ | ✅ | ✅ |
| 5 | 无 NEW_PRODUCT 误判 | ✅ | ✅ | ✅ |
| 6 | 无 POLICY_IMPACT 误判 | ✅ | ✅ | ✅ |
| 7 | Evidence 直接支持事件 | ✅ 全部过质量门 | ✅ | ✅ |
| 8 | published_at 正确 | ✅ 回填 2026-09-30（ANNOUNCEMENT_TIME） | ✅ | ✅ |
| 9 | 预算正确 | ✅ 400 万 | ✅ 730 万 | ✅ 400 万 |
| 10 | 联系人区分采购人/代理 | ✅ PURCHASER 3 + AGENCY 2 | ✅ PURCHASER 4 + AGENCY 3 | ✅ PURCHASER 5 + AGENCY 4 |
| 11 | Reachability 可重算 | ✅ 当前 0 联系人（真实）；联系人入库后 T05 自动重算（测试验证 45→85） | ✅ | ✅ |
| 12 | Opportunity 重算可解释 | ✅ 74.0/B breakdown 完整 | ✅ 74.0/B | ✅ 72.2/B |

## 6. Company 结果

46 家企业全部规范化：**40 家 COMPANY + 1 UNIVERSITY（上海交大）+ 1 SOURCE_PLATFORM（ccgp，SUPERSEDED）+ 4 UNKNOWN**。ccgp 不再出现在业务公司列表语义中（status=SUPERSEDED）。40 家新企业全部 PUBLIC_SOURCE_VERIFIED 且带 discovery_source_url 可追溯。

## 7. Signal 结果

148 条历史信号中 **108 条 SUPERSEDED**（挂在 ccgp 平台主体上的全部误报：旧 VALID 7 条 + T08 采集挂错 40 条 CONTRACT_AWARD + T04 误判 61 条）；保留 APPROVED 6（三真实采购单位的正确信号）、REJECTED 2、**VALID 40**（中标供应商企业上的真实 CONTRACT_AWARD，待人工批准）。平台上活跃信号=0。

## 8. Evidence 结果

EvidenceQualityGate 上线于两套规则引擎的证据生成点：导航/页脚/热线窗口被**重定位到实质句**（如"项目预算128万元""投标截止时间"），全低质则放弃信号；回归确认三条公告的全部 Evidence 过质量门，历史问题样本（"首页 政采法规…""服务热线 400-810-1996"）在测试中被断言拒绝。

## 9. Contact 结果

CompanyContact 新增 contact_type/organization_name；`extract_procurement_contacts` 支持 ccgp 三种真实格式；回归：三条公告共提取 **PURCHASER 12 / AGENCY 9**（归属正确主体），_campaign 采集管线自动入库 VERIFIED_PUBLIC + source_url。正式库当前 0 个联系人（新解析能力自下批采集生效）；Reachability 为动态计算，联系人入库后重跑 T05 即重算（测试验证 45→85）。

## 10. Opportunity 重新计算结果

三条机会均为分数可解释状态（score_breakdown 完整）：华南理工 74.0/B（APPROVED）、清华 74.0/B（PENDING）、中科院 72.2/B（PENDING）。采购上下文抑制后信号面干净，后续批准 CONTRACT_AWARD 信号 → T05 重跑即产生带正确 Evidence/预算/时间的候选。

## 11. 正式 Interaction 审计结果

正式库 1 条 Interaction（int_6d7f821c）：华南理工大学 OUTREACH/EMAIL，**审计日志证实为 2026-10-02 人工真实创建**（actor=local-user，T06 端到端联调记录）。contact_id 为空的原因：当时该企业无任何联系人记录；摘要所称"公开采购联系人邮箱"在系统中无来源可验证 → **按任务书只报告**：不自动删除、不伪造联系人补链。建议：待该企业真实联系人录入后，人工确认是否关联。

## 12. Experiment 一致性审计

`ExperimentValidationService` 上线（6 类检查，start 前强制执行并写入快照与审计）。对正式库现有实验（华南理工采购验证）输出的历史冲突已由规则识别：TARGET_COUNT_MISMATCH / CRITERIA_EXCEEDS_TARGETS 属 HIGH 级警告——**正式数据未自动修改**，建议用户将 target_company_count 调整为 3（与"3 家目标企业"成功标准一致）后继续。

## 13. 全量 pytest 结果

**394 passed**（T08 结束 350 + T08.0 新增 44），无失败、无跳过；全部使用独立测试库，正式库测试均为只读或真实采集。

---

## T08.0 结论

**T08.0：数据质量修复 — 通过**

- P0-1~P0-7 与 P1-1~P1-3 全部修复并有测试锁定；三真实采购公告 12 项回归全部确认；
- 历史污染数据以"标记取代 + 审计留痕"正式处理（ccgp→SOURCE_PLATFORM/SUPERSEDED、108 条误报信号 SUPERSEDED、44 条公告时间回填），未删除任何历史记录、未篡改任何事实；
- 修复后的数据链（Source → SourceRecord → Evidence → Signal → Opportunity）等级传递、证据质量、事件类型、时间与联系人结构化全部符合"真实、可验证、可追溯"原则。

**未开始 30 家扩量**（按任务书结束条件停止）。下一步：人工批准 40 条 CONTRACT_AWARD 信号 → 人工抽查企业 → 恢复扩量。
