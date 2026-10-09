# T07 第一轮真实市场验证 · 准备阶段报告

> 项目：BizPulse（商脉）
> 任务：T07 — 第一轮真实市场验证（开发仅为验证准备，重点是用系统跑业务）
> 说明：任务书所写目录 `D:\myAI\bizpulse-fullstack-v1` 不存在，实际项目在 `D:\myAI\bizpulse`（T03–T06 均在此）。
> 状态：能力全部就绪（318 个测试全绿）；正式库真实数据不足 30 家，**按任务书六十三/六十四节输出缺口并停止，不硬凑、不造假**。

---

## 1. T07 当前实现情况

本阶段开发被严格限制在"阻塞真实验证的最小集合"（任务书三）：

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| 真实市场候选排序 | ✅ | `GET /markets/validation-candidates`，实时聚合不落库 |
| Experiment 可创建 | ✅ | T06 已有，本次补充快照 |
| Target 可筛选 | ✅ | `POST /experiments/{id}/targets/select` |
| Selection Reason | ✅ | 每家记录枚举+数值理由 |
| Validation Brief | ✅ | `GET /experiment-targets/{id}/brief`，事实/AI推断/待验证三分 |
| Contact 来源真实 | ✅ | T06 规则沿用（VERIFIED_PUBLIC 必须有来源） |
| Outreach Draft 只是草稿 | ✅ | 规则模板生成，`is_draft_only=true`，不自动发送 |
| Interaction 真实记录 | ✅ | T06 已有（方向/收入/拒绝原因反伪造） |
| Metrics 真实计算 | ✅ | 补充 reachable_rate / positive_reply_rate |
| Report 真实生成 | ✅ | `GET /experiments/{id}/report`，真实结果与系统分析分离 |
| CSV 导出 | ✅ | `GET /experiments/{id}/export.csv` |
| Experiment Snapshot | ✅ | start 时冻结假设/模型版本/报价假设/筛选规则 |
| 正式库无假 Interaction | ✅ | 正式库仅含 T06 真实触达 1 条 |

## 2. 新增/修改模块

- `app/services/market_validation.py`（新）：市场候选聚合排序 + 数据充足性评估。
- `app/services/brief.py`（新）：Validation Brief / Outreach Draft / 实验报告 / CSV 导出。
- `app/services/metrics.py`：补 `reachable_count/reachable_rate`（有真实可用联系人的企业占比）与 `positive_reply_rate`（POSITIVE 回复企业/回复企业）。
- `app/api/v1/endpoints/markets.py`：+`validation-candidates`。
- `app/api/v1/endpoints/experiments.py`：+`targets/select`、`{id}/report`、`{id}/export.csv`；start 时写快照。
- `app/api/v1/endpoints/opportunities.py` 创建 schema 补 `why_now/risk_notes/validation_questions` 字段。
- 模型：`experiment_targets.selection_reason`（JSON）、`experiments.snapshot_json`（JSON），Alembic 迁移 `b8c4d2e6f1a9` 已应用。

## 3. API（任务书五十八核对）

| 要求 | 实现 |
| --- | --- |
| GET /api/v1/markets/validation-candidates | ✅ 新增（min_companies 可调） |
| POST /api/v1/experiments | ✅ 已有 |
| GET /api/v1/experiments/{id} | ✅ 已有 |
| POST /api/v1/experiments/{id}/targets/select | ✅ 新增 |
| GET /api/v1/experiment-targets/{id}/brief | ✅ 新增 |
| POST /api/v1/interactions | ✅ 已有（T06） |
| GET /api/v1/experiments/{id}/metrics | ✅ 增强 |
| GET /api/v1/experiments/{id}/report | ✅ 新增 |
| （补充）GET /api/v1/experiments/{id}/export.csv | ✅ 新增 |

## 4. 市场候选排序逻辑

- **场景轴**：已审核机会关联 PainPoint 的 category（细分到"什么企业+什么问题"，非大行业，任务书五）。
- **统计口径**（全部来自真实数据）：company_count / signal_count（企业级 APPROVED）/ opportunity_count / avg_opportunity_score / avg_evidence_score / avg_intent_score / reachable_company_count（有 VERIFIED_PUBLIC 或 USER_PROVIDED 联系人）/ fresh_signal_count_30d / replied_company_count。
- **排序规则（透明可解释）**：机会数量 > 平均机会分 > 30 天新鲜信号 > 可触达企业；每个候选输出 `recommendation_basis` 文本依据。
- **人工决定**：系统只输出推荐候选与依据，不自动创建实验、不自动选定市场（任务书七）。

## 5. Target 选择逻辑

- 输入：`opportunity_ids` 或 `company_ids`（企业模式自动选其最高分已审核机会）；`max_count` 默认 30。
- 门槛（任务书十四）：机会已人工审核（APPROVED）、有至少 1 条证据、企业真实存在；不满足记入 `skipped`（含原因）。
- 每家记录 `selection_reason`：HIGH_SCORE/HIGH_INTENT/HIGH_EVIDENCE/HIGH_URGENCY/FRESH_SIGNAL/REACHABLE（均带具体数值），兜底 MANUAL_PICK(人工指定)——杜绝只写"AI推荐"。
- 重复企业自动跳过（already_in_experiment），审计留痕 `via=targets/select`。

## 6. Validation Brief

`GET /experiment-targets/{id}/brief` 输出三段式看板 `statement_board`：
- **【事实】**：只来自真实来源（证据原文 + 来源 URL）；
- **【AI推断】**：问题假设（AI 推断）/ why_now / 风险提示，明确标注"AI推断"；
- **【待验证】**：Pain 假设留待客户确认。
另含 company 简报、evidences（信号类型+URL）、contacts（仅真实可用联系人）、validation_questions（T05 生成 3~5 问）、risk_notes。

## 7. Outreach Package

六要素齐备：Company Brief + Evidence + Contact + Message Draft + Validation Questions + Suggested 状态。
草稿规则（任务书二十五/二十六）：只引用真实事实条目与企业名；话术结构 = 真实 Signal + 客户价值 + 15~30 分钟低门槛下一步 + "不推销平台"声明；**禁止虚构个性化**（无依据的"营收增长/融资"等不得出现，测试有禁用词断言）；`is_draft_only=true`，人工复制修改后自行发送。

## 8. Experiment Snapshot

`POST /experiments/{id}/start` 时冻结 `snapshot_json`：market_hypothesis / target_customer / value_proposition / offer（含 price_amount 与 pricing_hypothesis）/ success_criteria / failure_criteria / score_model_version（SCORE_ENGINE_V1_T05）/ prompt_version / target_selection_rule / llm_configured / targets_at_start。中途 PAUSE 保留实验、新建新实验，历史快照不可改（任务书五十二）。

## 9. Metrics

在 T06 基础上补充（任务书四十八）：`reachable_rate`（可触达率=有真实可用联系人的目标企业占比）、`positive_reply_rate`（POSITIVE 回复企业/回复企业，0 回复时为 0）。既有指标：按企业数漏斗、相邻转化率（除零返回 0）、contracted/received revenue 分离。

## 10. Report

`GET /experiments/{id}/report`：
- **real_results**（全部来自数据库）：metrics、funnel、reject_reason_distribution、reply_category_distribution、opportunity_score_buckets（分数桶 × 真实回复/会议，任务书四十九的 High Score Reply Rate 雏形）、snapshot；
- **system_analysis**（明确标注"只读统计描述，不修改任何真实结果"）：样本量 <10 不建议改评分模型（任务书四十六）。
- CSV 导出含任务书五十七全部列（company/score/signals/evidence/contact_status/reply/meeting/quote/outcome/reject_reason/selection_reason）。

## 11. 测试结果

- **全量 318 passed**（T06 结束 289 + T07 新增 29）。
- 新增 7 个测试文件：test_market_validation_candidates / test_target_selection / test_validation_brief / test_outreach_package / test_experiment_snapshot / test_validation_metrics / test_validation_report。
- 关键断言：候选按细分场景聚合（非大行业）；未审核机会不进候选；缺口如实上报；selection_reason 可解释（含 HIGH_INTENT(意图分90) 等）；Brief 三分看板 + 事实带来源 URL；草稿禁用词断言（不得出现"营收增长/最近融资"）；快照冻结报价假设；报告真实结果与系统分析分离；CSV 列完整。
- 测试库（pytest）隔离；正式库未写入任何测试数据。

## 12. 正式数据库当前真实数据

| 指标 | 数量 |
| --- | --- |
| Company 总数 | 6（3 家真实采购单位 + 域名识别残留 "ccgp" 及辅助记录） |
| Approved Signal | 6（3 家 × TENDER+PROCUREMENT，来源 ccgp.gov.cn，A 级） |
| 已审核 Opportunity | **1**（华南理工大学 74.0/B，PROCUREMENT 场景；清华、中科院机会 review_status 仍为 PENDING 待人工审核） |
| 满足筛选条件的企业 | **1**（有已审核机会的真实企业） |
| 真实 Interaction | 1 条（华南理工 OUTREACH/EMAIL，T06 闭环验证产生） |

## 13. 是否具备第一轮 30 家验证条件

**不具备。** 充足性评估输出：

- 满足筛选条件企业：**1 家**；第一轮目标：**30 家**；**缺口：29 家**。
- 系统消息（真实输出，非人工编写）："真实数据不足：满足筛选条件的企业 1 家，第一轮目标 30 家，缺口 29 家。建议先继续真实数据采集，不要硬凑。"
- 现有市场候选仅 1 个：**#1 采购场景（PROCUREMENT）**——华南理工大学，机会 1 个（均分 74.0、意图 70、证据 81），APPROVED 信号 2 条（均在 30 天内），可触达 0/1（该企业尚无录入的真实联系人）。

### 建议的补数据路径（不造假的前提下）

1. **先人工审核**清华、中科院两个已转换机会（各带 2 条 APPROVED 信号），满足筛选条件企业 1 → 3；
2. **继续真实采集**：ccgp.gov.cn 政府采购公告可稳定解析，按行业关键词（如高校/科研院所仪器采购）批量采集可自然扩大 PROCUREMENT 场景企业与机会池；
3. **为企业录入真实公开联系人**（官网/公告中的采购联系人，附 source_url），提升 reachable_rate；
4. 达到 30 家后：用 `targets/select` 批量选入（自动带 selection_reason）→ 人工复核 P1/P2/P3 → 用 brief 的 Outreach Package 逐家人工触达。

---

## T07 结论

**T07：第一轮真实市场验证准备 — 通过**

- 任务书六十五节 13 项通过标准全部满足：市场候选排序、实验创建、目标筛选（可解释理由）、Validation Brief、真实 Contact 规则、草稿不发送、真实 Interaction、真实 Metrics、真实 Report、Experiment Snapshot、正式库无假 Interaction、318 测试通过；
- 按任务书六十二节完成正式库真实筛选并输出候选；按六十三/六十四节确认**真实数据不足（1/30，缺口 29）**，未硬凑、未生成假企业/假信号/假互动；
- **第一轮验证的启动动作已明确**：人工审核 2 个待审机会 → 继续采集采购公告扩大企业池 → 录入真实联系人 → 达标后创建正式 Experiment。

按任务书要求，T07 到此停止。
