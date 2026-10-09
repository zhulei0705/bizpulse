# T06 商业验证与客户反馈系统 · 总结报告

> 项目：BizPulse（商脉）本地商业情报与商业验证后端 API
> 任务：T06 — 商业验证与客户反馈系统 V1
> 说明：任务书所写目录 `D:\myAI\bizpulse-fullstack-v1` 不存在，T03–T05 实际项目在 `D:\myAI\bizpulse`，本阶段继续在该项目开发。
> 状态：**289 个后端测试全部通过**（T06 新增 49）；浏览器端到端闭环验证通过。

---

## 1. 当前验证系统检查结果（开发前检查）

**已有能力（全部复用）**：`experiments`/`experiment_opportunities`/`interactions`/`company_contacts` 四张表；实验 list/create/get + 实验下记录互动；联系人 list/create；Opportunity 审核流（approve/ready→READY）；审计框架；前端路由与组件库。

**缺失能力**：experiment_targets/quotes/experiment_outcomes/opportunity_feedback 四张表；Interaction 缺 type/direction/contact_id/target_id 等核心字段；Experiment 缺报价/目标/成功标准；联系人无来源校验；漏斗按互动条数统计（错误）；无状态机保护；无 Feedback 闭环；实验前端为纯占位页。

**本次修改内容**：扩展 4 个模型 + 新增 4 张表（Alembic 迁移 `e7f3a91b2c4d`）；新增 `services/validation.py`（状态机 + 反伪造）；重写 `services/metrics.py`（按企业数漏斗/转化率/收入分离）；新增 interactions/quotes 全局 API 与实验 targets/funnel/metrics/complete API；机会 stage 校验 + add-to-experiment + confirm-budget + feedback；重写实验前端页；机会详情增加验证信息与加入实验入口。

## 2. 新增数据表

| 表 | 作用 |
| --- | --- |
| `experiment_targets` | 验证目标企业（实验×企业唯一）；`status` + `reached_stage`（到达过的最远阶段，漏斗依据）；priority/assigned_to/next_action |
| `quotes` | 真实报价：amount/currency/billing_type/scope/status（DRAFT→SENT→VIEWED→ACCEPTED/REJECTED/EXPIRED/WITHDRAWN）/sent_at/valid_until/response |
| `experiment_outcomes` | 目标终态快照：final_status/won/contract_amount/received_amount/reject_reason/pain_confirmed 等 |
| `opportunity_feedback` | 预测 vs 真实：predicted_score/grade + actual_reply/meeting/quote/pilot/win/revenue + reject_reason |

**现有表扩展**：experiments（value_proposition/offer_description/price_*/时间窗/target_*/success_criteria/failure_criteria/conclusion_notes）；interactions（target_id/contact_id/interaction_type/direction/occurred_at/subject/summary/result/sentiment/next_action*/created_by/evidence_attachment）；company_contacts（email/phone/public_profile_url/source_url/source_type/verification_status 枚举/is_decision_maker）；pain_points（confirmed_by_interaction_id/confirmed_at/confirmed_by）；opportunities（observed_intent/confirmed_budget/last_contacted_at/contact_count）。旧字段全部保留兼容。

## 3. 数据库 Migration

Alembic 迁移 `e7f3a91b2c4d`（down_revision `d15fe78e7edf`），已应用至真实库。interactions 的 FK 用 `batch_alter_table`（SQLite 限制）；downgrade 完整可回滚。测试库由 `Base.metadata.create_all` 按模型建表，与迁移保持一致。

## 4. Experiment 设计

- 必填：name + hypothesis（实验必须回答"验证什么"）；结构化：target_customer、value_proposition、offer_description、price_amount/currency、目标漏斗六项（target_contacts→target_wins）、success_criteria/failure_criteria。
- 状态机：DRAFT/READY→RUNNING（start，记录 started_at）→COMPLETED（complete，conclusion 必须是 KEEP/TEST_MORE/PAUSE/DROP 枚举，**V1 人工判定，AI 只能建议**）；PAUSED/CANCELLED 旁支。
- `actual_*` 不落库：真实值由 targets/interactions/quotes/outcomes 实时统计（避免双写不一致），API `GET /experiments/{id}` 内嵌 metrics。

## 5. Target 设计

- 加入门槛：企业可直加；**带机会加入时机会必须人工审核通过（review_status=APPROVED）且 stage≥READY**（关键测试 5）；同实验同企业唯一（409）。
- 状态机（`TARGET_FLOW`）：NEW→RESEARCHING→READY_TO_CONTACT→CONTACTED→REPLIED→QUALIFIED→MEETING→QUOTED→PILOT→WON，旁支 REJECTED/NO_RESPONSE/PAUSED。
- 保护规则：主流程前进 1 步/任意后退允许；**跳 2+ 步需 force=true + note（人工确认真实依据）**；WON 必须带 contract_amount>0（口头意向不算成交）；REJECTED 必须带统一拒绝原因；NO_RESPONSE 仅限已联系过的目标；终态重开需 force+note。
- `reached_stage` 只增不减：状态回退后漏斗仍按到达过的最远阶段统计（真实到达过即进入漏斗）。

## 6. Contact 真实性规则

- verification_status 枚举：VERIFIED_PUBLIC/USER_PROVIDED/UNVERIFIED/STALE/INVALID；只有前两者可作为正式联系渠道。
- **VERIFIED_PUBLIC 必须有真实公开来源（source_record_id 或 source_url），否则 422**（关键测试 6）；创建与修改双向校验；来源移除后降级 STALE/UNVERIFIED。
- 联系方式结构化（email/phone/public_profile_url），禁止拼凑猜测邮箱/生成假手机号；来源类型枚举（官网/公开资料/展会/人工录入）。

## 7. Interaction 设计

- 每一次真实商业动作一条记录：interaction_type（14 类）/channel（10 类）/direction（OUTBOUND/INBOUND/INTERNAL）/occurred_at/subject/summary/result/sentiment/next_action/evidence_attachment（只存附件路径，不写敏感内容进日志）。
- 方向真实性：REPLY/REJECTION 只能 INBOUND；OUTREACH/FOLLOW_UP/PROPOSAL/QUOTE 只能 OUTBOUND（客户回复不能伪造方向）。
- 收入规则：revenue 只能记在 CONTRACT/PAYMENT；**报价金额永远不是收入**（quote_amount 与 revenue 互斥校验）。
- 真实事件联动（服务层自动，force 内部放行因为互动本身是真实依据）：Target 状态推进 + Opportunity stage 推进 + observed_intent + contact_count/last_contacted_at。

## 8. Reject Reason

统一 12 类客户拒绝原因（NO_NEED/NO_BUDGET/WRONG_PERSON/BAD_TIMING/PRICE_HIGH/ALREADY_HAVE_SOLUTION/NO_TRUST/PRODUCT_NOT_FIT/NOT_REACHABLE/NO_RESPONSE/WEAK_VALUE_PROPOSITION/OTHER）。
真实性规则：只能记录在 REJECTION 互动/REJECTED 状态；**未到报价阶段不能归因 NO_BUDGET/PRICE_HIGH**（没有真实价格沟通）；没有客户反馈只能 NO_RESPONSE。

## 9. Quote

独立报价表与 API；状态枚举守卫；**未发送（sent_at 为空）不能记录 VIEWED**（不假设客户已查看）；报价创建联动 Target→QUOTED。报价金额从不进入 revenue 指标（关键测试 3）。

## 10. Pilot / Won

PILOT 记录在 Target 状态与互动；WON 必须提供真实 contract_amount，Outcome 固化 won/contract_amount/received_amount，机会阶段同步 WON。`contracted_revenue`（签约）与 `received_revenue`（真实收款 PAYMENT 互动）严格分开；预计收入不得混入实际收入。

## 11. Funnel

`GET /experiments/{id}/funnel`：targets/researching/ready_to_contact/contacted/replied/qualified/meetings/quotes/pilots/wins/rejected/no_response/paused。**全部按目标企业数统计**（一个企业 5 次跟进仍是 1 家，关键测试 2），依据 reached_stage 到达序。正式库无真实互动时保持 0（不为验收造假）。

## 12. 转化指标

`GET /experiments/{id}/metrics`：contact_rate/reply_rate/meeting_rate/quote_rate/pilot_rate/close_rate（相邻漏斗阶段转化率）+ overall_close_rate；**分母为 0 统一返回 0**（不除零，关键测试 1）；contracted_revenue/received_revenue 分离；另附 interaction_stats（互动层参考，不计入转化率）。

## 13. Opportunity Feedback

Target 到达终态（WON/REJECTED/NO_RESPONSE）时自动写 Outcome + `opportunity_feedback`（预测分/等级 + actual_reply/meeting/quote/pilot/win/revenue + reject_reason）；`GET /opportunities/{id}/feedback` 查询。**只积累数据用于校准分析：不自动改权重、不在线训练、不让 LLM 改评分公式**（任务书四十四）。

## 14. Pain 确认机制

`POST /interactions/{id}/confirm-pain`：PainPoint 只能由**真实客户沟通（INBOUND 回复/会议）+ 客户原话依据（summary/note）** 从 INFERRED 升级 CONFIRMED，留痕 confirmed_by_interaction_id/confirmed_at；内部笔记不得确认。形成"AI 推断 → 客户确认"数据闭环。

## 15. Budget 确认机制

`POST /opportunities/{id}/confirm-budget`：保存客户明确说出的预算原文（confirmed_budget），**必须引用一条 INBOUND 互动作为依据**（interaction_id 必填）；客户没说就保持 UNKNOWN，禁止 AI 猜预算。

## 16. API

- 实验：GET/POST `/experiments`、GET/PATCH `/{id}`、POST `/{id}/start|complete`、GET `/{id}/funnel|metrics|interactions`
- 目标：GET/POST `/experiments/{id}/targets`、PATCH `/experiment-targets/{id}`
- 互动：GET/POST `/interactions`、GET/PATCH `/{id}`、POST `/{id}/confirm-pain`；兼容旧端点 `POST /experiments/{id}/interactions`
- 联系人：GET/POST `/companies/{id}/contacts`、GET/PATCH `/contacts/{id}`
- 报价：GET/POST `/quotes`、GET/PATCH `/{id}`
- 机会：PATCH `/{id}/stage`（状态机保护）、POST `/{id}/add-to-experiment`、GET `/{id}/feedback`、POST `/{id}/confirm-budget`

## 17. 审计机制

任务书六十节 11 类操作全部写 audit_logs：加入实验（ADD_TO_EXPERIMENT）、联系人创建/修改、Interaction 创建/修改、Opportunity 状态变化（STAGE_CHANGE）、PainPoint 确认（PAIN_CONFIRMED）、Budget 确认（BUDGET_CONFIRMED）、Quote 创建/修改、Target 状态流转（TARGET_STATUS_CHANGE）、Outcome（EXPERIMENT_OUTCOME）、Feedback（OPPORTUNITY_FEEDBACK）、实验开始/完成（EXPERIMENT_STARTED/COMPLETED）。审计记录 before/after 与真实依据。

## 18. 前端必要联调（不做视觉优化）

- `types/validation.ts` + `api/validation.ts`：完整 T06 类型与 API 客户端。
- ExperimentsPage 重写（原为纯占位）：实验列表/新建实验弹窗（假设必填 + 报价 + 六项目标 + 成功标准）/实验详情（定义、真实指标条、漏斗条、目标企业卡片与单步流转按钮、记录拒绝原因、记录互动表单）/开始与结束实验（结论枚举）。
- OpportunitiesPage：机会详情增加"真实验证进展"（联系次数/最后联系/observed_intent/confirmed_budget）与"加入验证实验"（仅审核通过后显示）；Kanban 状态拖动走后端校验（REJECTED/WON 引导走详情流程填写必要信息）。

## 19. 测试结果

- **全量 289 passed**（T05 结束时 240 + T06 新增 49）。
- 新增 10 个测试文件：test_experiments / test_experiment_targets / test_interactions / test_contacts / test_quotes / test_funnel / test_experiment_metrics / test_opportunity_feedback / test_reject_reasons / test_validation_state_machine（+ helpers_t06）。
- 6 个关键测试全部覆盖：除零（funnel/metrics 0 联系返回 0）、5 次跟进算 1 家企业、只有报价不算收入、无回复不能记 NO_BUDGET（且未报价阶段不能归因价格）、未审核机会禁止加入实验、无来源联系人不能 VERIFIED_PUBLIC。
- 1 处有意的行为变更：旧测试 `test_stage_update_and_legacy_mapping` 更新为 T06 规则（未审核机会 PATCH 到验证阶段 422，审核通过后可流转）。

## 20. 当前真实数据情况

- 正式库：1 个实验「华南理工科研仪器采购验证」（RUNNING，试点价 ¥9800，成功标准"3 家中至少 1 家进入会议"）；1 个验证目标（华南理工大学，CONTACTED）；1 条真实人工触达互动记录（OUTREACH/EMAIL）；漏斗 targets=1、contacted=1、contact_rate=100%、reply_rate=0；contracted/received revenue 均为 0（真实未发生）。
- 机会侧：华南理工机会（74.0/B）review_status=APPROVED、stage=CONTACTED、contact_count=1；清华大学机会 REVIEW/PENDING 待人工审核；中科院机会 REVIEW。
- 反馈表：暂无终态目标，opportunity_feedback 为空（真实未发生，保持 0）。
- 以上全部为验证闭环的真实操作产生，无一条假互动/假回复/假收入。

## 21. 当前已知问题

- 前端 Contact/Quote 管理界面尚未做（API 已全，任务书七十八未硬性要求 UI）；记录报价/联系人当前走 API。
- Target 状态单步流转按钮在目标较多时操作较长，可后续做快捷"下一步"。
- `experiment_metrics` 未做按 signal 类型 / pain 分类 / 行业的交叉分析（任务书四十五，属后续分析能力）。
- 收款依赖人工把 PAYMENT 互动录入；未来可接真实支付/合同附件校验。
- 非阻塞遗留：`main.py` on_event deprecation 警告；VALID 残留信号清理工具（T05 报告已列）。

## 22. 下一阶段建议

- 前端补齐联系人/报价管理界面与"验证实验"深度看板（拒绝原因分布、Score 分桶表现）。
- 积累真实样本后（任务书四十五）：A 类机会真实回复率、PROCUREMENT vs 招聘信号质量、行业付费意愿等交叉分析。
- Score Calibration：样本足够后用 opportunity_feedback 分析各分数段/等级的真实转化差异，为 T07 权重校准提供依据（仍由人工决策）。
- 实验报告导出（目标/漏斗/拒绝分布/收入/Score 分布）与 AI 总结（标注"AI 分析"、底层数字来自数据库）。

---

## T06 结论

**T06：商业验证与客户反馈系统 — 通过**

- Experiment/Target/Contact/Interaction/Quote/Outcome/RejectReason/Feedback 全部对象落地，状态机与真实性约束在 Service 层强制执行；
- 反幻觉原则贯穿：无假联系人、无假回复、无假收入、报价≠收入、无回复≠无预算、未发送≠已查看、无真实互动全部指标为 0；
- 漏斗与转化率按企业数统计、除零安全、收入双轨分离；
- 预测（Opportunity Score / intent_score）与真实（Outcome / observed_intent / confirmed_budget）严格区分并形成反馈闭环（不自动训练）；
- Alembic 迁移通过并已应用；pytest 289 全部通过；浏览器端到端闭环（创建实验→审核机会→加入实验→开始实验→记录真实触达→漏斗/指标更新）验证通过；
- 无自动群发、无自动加好友、无自动触达——系统定位为"商业验证操作系统"。

按任务书八十节要求，T06 完成，**立即停止，不进入 T07**。
