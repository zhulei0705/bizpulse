# T05 机会判断引擎 · 总结报告

> 项目：BizPulse（商脉）本地商业情报与商业验证平台
> 任务：T05 机会判断引擎（Opportunity Candidates → 人工审核 → 正式 Opportunity）
> 状态：开发完成、真实数据验证通过、前端联调闭环验证通过（240 个后端测试全绿）

---

## 1. 任务目标

在 T03（数据采集）与 T04（信号/痛点/机会基座）之上，把"已批准的真实商业信号"自动加工为**可解释、可审核、反幻觉**的商业机会候选（OpportunityCandidate），由人工审核后转为正式 Opportunity，形成"信号 → 候选 → 机会 → 验证"的完整增长闭环。

## 2. 交付范围

- 数据模型：`opportunity_candidates`、`signal_bundles` 两张表（Alembic 迁移 `d15fe78e7edf`，已应用）+ `Opportunity` 表 T05 扩展字段（score_breakdown、grade_cap_reason、candidate_id 等）。
- 评分引擎：可配置权重 + 分数明细（score_breakdown）。
- 8 个分析器：pain / budget / intent / urgency / agent_fit / evidence / bundles / dedup。
- 生成编排：OpportunityGenerator（Company → Approved Signals → Bundles → 打分 → EvidenceGate → 候选落库）。
- API：单企业分析、批量分析 job、候选列表/详情、三向人工审核（approve / reject / need-more-evidence）。
- 前端联调：T05 API 客户端、类型定义、"AI 机会候选"审核区块与详情弹窗。
- 测试：240 个后端测试全部通过（T05 相关新增 24+ 项）。

## 3. 数据模型

- `opportunity_candidates`：候选完整快照（假设、分数明细、证据引用、风险、验证问题、状态机、fingerprint、analysis_input_hash）。
- `signal_bundles`：信号组合（组合类型、信号清单、时间窗计数、组合置信度），供候选解释"为什么把这些信号放在一起"。
- 状态机：`DETECTED / REVIEW / NEED_MORE_EVIDENCE`（活跃）→ `APPROVED / CONVERTED / REJECTED`（终态）。
- 循环 FK 决策：`Opportunity.candidate_id` 不建 DB 级 FK（避免与 `opportunity_candidates.opportunity_id` 成环，SQLite 不支持），改由应用层维护 + 双端索引。

## 4. 评分引擎 ScoreEngine

- 权重（可配置）：pain 0.25、budget 0.20、intent 0.20、urgency 0.10、agent_fit 0.10、evidence 0.10、reachability 0.05。
- 每次打分产出 `score_breakdown`（分项得分 + 加权值 + 理由），候选与正式机会都携带，前端直接展示。
- 总分/等级永远由代码计算，LLM 只产出解释性文本，不能改分数。

## 5. 八个分析器

| 分析器 | 输入 | 要点 |
| --- | --- | --- |
| pain | 信号组合 + 规则映射 | 17 类痛点分类（PROCUREMENT 等），输出置信度 + 推理摘要 |
| budget | 原文金额/资助线索 | 只认原文证据；无证据保持 UNKNOWN，不猜测金额 |
| intent | 采购/招标类信号 | 公开采购等直接购买行为加权 |
| urgency | 时间密度 + 截止日 | 7/30/90 天窗口计数，招标截止日加急 |
| agent_fit | 痛点分类 × 方案映射 | AI Agent 方案适配度 |
| evidence | SignalEvidence 原文 | 证据数量、来源等级、新鲜度、矛盾极性 |
| bundles | 组合规则 | 采购+招标+预算等组合 → 捆绑包解释 |
| dedup | fingerprint / input hash | 窗口内同指纹更新不新建；同输入跳过重复分析 |

## 6. Evidence Gate（反幻觉硬门槛）

- **证据数 = 0 的候选禁止转正式机会**：approve 时抛 `EvidenceGateError` → API 422，候选标记 `NEED_MORE_EVIDENCE`。
- 证据分 < 60：等级封顶 B。
- 单条弱证据（C/D 级来源）：等级封顶 C，候选直接进入 `NEED_MORE_EVIDENCE`。
- 生成端同门槛：Approved Signal ≥ 1 且 Evidence ≥ 1 才允许进入分析（配置化）。

## 7. 诚实性机制汇总

- Budget 无证据 → `UNKNOWN` + 风险备注"预算能力未知（Budget 不猜测）"。
- 矛盾证据：每条 -18 分计入 Evidence 分，并写入候选"矛盾证据"字段与风险备注。
- 假设文本强制带标注：`【SOLUTION_HYPOTHESIS】`、`【VALUE_HYPOTHESIS】`、"需人工验证"、"不承诺 ROI 数字"。
- 风险备注诚实列出负面因素（无预算证据、无直接购买信号、证据 ≤ 1、缺少触达渠道）。
- 审计留痕：分析、转换、封顶、拒绝全部写 audit log。

## 8. 去重与输入 Hash

- `fingerprint = sha256(company_id + pain_category + solution_category + 时间窗桶)`，带唯一约束：同窗口同主题只保留一条候选。
- `analysis_input_hash = sha256(company + signal_ids + signal_fingerprints + prompt_version)`：输入未变的重复分析自动跳过（`force=true` 可强制）。

## 9. LLM 集成

- Prompt（`OPPORTUNITY_GENERATOR_V1`）只做三件事：结构化解释、why_now、验证问题；分数与状态由代码决定。
- `insufficient_evidence=true` 时候选降级 `NEED_MORE_EVIDENCE`。
- 当前环境 `llm_configured=false`，全链路走规则路径——真实数据验证证明了"无 LLM 也能跑通"，LLM 配置后仅解释层增强。

## 10. Generator 编排

流程：Company → 加载已批准信号与证据 → 进入条件检查 → 输入 hash 跳过判断 → Bundles（无组合命中时单信号兜底）→ 七维打分 → LLM 解释（可选）→ 风险/验证问题装配 → fingerprint 查重 → 更新或新建候选 → 审计 + 提交。批量模式带 CollectionJob 记录、逐企业异常隔离、顺带执行 STALE 清扫。

## 11. API 层

- `POST /api/v1/companies/{id}/analyze-opportunities`（force 可选）
- `POST /api/v1/jobs/analyze-opportunities`（批量，输入 hash 未变自动跳过）
- `GET /api/v1/opportunity-candidates`（status/company_id/grade 过滤 + counts）
- `GET /api/v1/opportunity-candidates/{id}`（详情聚合：信号视图 + 来源等级 + URL 回溯）
- `POST /api/v1/opportunity-candidates/{id}/approve|reject|need-more-evidence`
- 响应包装 `{success, data, message}` 与全站一致；ORM `_json` 后缀字段手动映射为对外字段（`_serialize_candidate` / `_serialize_with_counts`）。

## 12. 测试覆盖

- 全量 240 个测试通过（本会话新增 13 个）。
- 关键测试：无信号跳过、弱新闻单证据封顶、采购+预算+A 级高于普通新闻、可解释字段齐备、approve 转换 + 零证据阻断（422）、批量 job + STALE、fingerprint 随窗口变化、同输入跳过、同指纹更新不新建、force 重分析跳过终态候选。
- 测试环境：pytest 不访问公网（HTTP 全 Mock），SQLite 独立测试库。

## 13. 真实数据验证：数据链

- 来源：ccgp.gov.cn（中国政府采购网，静态可解析的政府采购公告）。
- 三家真实采购单位入库并完成信号分析、信号人工批准：**中国科学院理论物理研究所、清华大学、华南理工大学**。
- 每家 2 条已批准信号（TENDER + PROCUREMENT），公告原文（招标编号、正文摘录）可作为证据引用回溯到原始 URL。
- 2 条误报信号已人工拒绝（清华 NEW_PRODUCT、华南理工 POLICY_IMPACT——招标公告被规则误读为新品/政策信号），验证了"AI 生成必须人工把关"的流程价值。

## 14. 真实数据验证：来源等级 C→A 的分数影响

手动 URL 来源默认 C 级（score 55），而 ccgp.gov.cn 是政府官网（A 级）。PATCH 修正后强制重分析：

| 指标 | 修正前（C） | 修正后（A） |
| --- | --- | --- |
| evidence_score | 71 | **81**（+10） |
| intent_score | 66 | **70**（+4） |
| total_score | 72.2 | **74.0**（+1.8） |
| 证据明细理由 | "最高来源等级 C" | "最高来源等级 A" |

分析器实时读取 `sources.reliability_grade`，等级修正立即影响下次分析；快照字段 `source_records.source_reliability` 只写不读，保留采集时历史。

## 15. 本会话修复 1：权威域名自动定级

- 新增 `ingest.ensure_authoritative_grade`：手动 URL 命中 `.gov.cn / .gov / .edu.cn / .edu` 时，手动来源自动升为 A 级（score ≥ 95），**只升不降**、幂等、写审计（`reason=authoritative_domain`）。
- 普通商业域名仍保持默认 C，人工可通过 `PATCH /sources/{id}` 随时调整（该端点实际可用，交接信息有误）。
- 新增 12 个测试（域名判定参数化 + gov URL 端到端升级 + 只升不降/幂等单元）。
- 现有数据已 PATCH 为 A/95。

## 16. 本会话修复 2：终态候选 fingerprint 冲突（真实 bug）

- 现象：对中科院公司 `force` 重新分析返回 500，日志为 `UNIQUE constraint failed: opportunity_candidates.fingerprint`。
- 根因：`find_active_candidate` 只匹配活跃状态（DETECTED/NEED_MORE_EVIDENCE/REVIEW）；候选已 CONVERTED 后重分析走 INSERT 分支，撞唯一约束。
- 修复：新增 `dedup.find_finalized_candidate`（CONVERTED/APPROVED/REJECTED）；同指纹终态候选存在时**跳过重建**（尊重人工决策），计数进审计事件；全部被跳过时 `reason=candidates_finalized(n)`。
- 回归测试：`test_force_reanalysis_after_convert_skips_finalized`。

## 17. 前端联调：T05 接入

- `src/types/index.ts`：`OpportunityCandidate`、`CandidateEvidenceRef`、状态标签、拒绝原因常量（与后端一致）。
- `src/api/bizpulse.ts`：候选列表/详情、approve / reject / need-more-evidence、单企业分析、批量分析 job。
- `src/pages/OpportunitiesPage.tsx`：新增"AI 机会候选"区块（分数环、等级、状态徽章、pain 分类、证据数、生成方式、why_now、风险提示）；候选详情弹窗（七维分数、假设标注、风险、验证问题、A 级证据外链、矛盾证据）；三向审核 + 拒绝原因选择 + 重新分析 + 批量分析。
- 终态候选只读展示（"人工已处理"），不提供重复操作。
- TypeScript 编译（`tsc --noEmit`）通过。

## 18. 联调发现与修复：CORS 配置

- 现象：前端经 `http://127.0.0.1:5173` 访问时全部请求失败（页面报"无法连接后端服务"），而 `localhost:5173` 正常。
- 根因：`config.cors_origins` 默认只有 `http://localhost:5173`，CORS 预检（OPTIONS）对 `127.0.0.1` origin 返回 400。
- 修复：默认值改为 `http://localhost:5173,http://127.0.0.1:5173`；预检验证通过（200 + 正确 allow-origin）。

## 19. 端到端闭环验证（浏览器实测）

1. 打开 `/opportunities`：候选区块正确渲染 3 个候选（2 个待审核、1 个已转机会只读）。
2. 打开清华候选详情：分数、假设标注、风险、验证问题、2 条 A 级 ccgp.gov.cn 证据外链全部正确。
3. 填写审核备注 → 点击"通过转正式"：候选状态 `REVIEW → CONVERTED`，正式 Opportunity 创建（74.0 / B / stage=REVIEW），页面统计与列表即时刷新。
4. 数据库复核：opportunities 2 条（中科院 72.2、清华 74.0），候选 CONVERTED×2 + REVIEW×1。
- （中科院候选保留其转换时的历史分数 72.2，属预期行为：终态候选不重算。）

## 20. 真实数据当前状态快照

- 来源：1 个（手动URL分析，A/95，notes 已注明自动定级规则）。
- 信号：APPROVED 6（3 家 × TENDER+PROCUREMENT）、REJECTED 2（误报）、VALID 7（早期规则产物，关联自动识别的 "ccgp" 公司，**不参与分析**——分析只读 APPROVED/REVIEW）。
- 候选：CONVERTED 2、REVIEW 1（华南理工，74.0/B，待人工审核）。
- 正式机会：2（REVIEW/PENDING）。

## 21. 已知限制与风险

- LLM 未配置：解释层为模板文本（已验证不阻塞主流程）；配置后需重跑 prompt 版本对比。
- 采集覆盖：多数企业官网 JS 渲染无法采集；当前可稳定采集的是 ccgp.gov.cn 静态页。
- VALID 残留信号：7 条早期信号关联到域名识别的 "ccgp" 公司，建议后续提供"公司合并/重新关联"工具，或按保留期清理。
- `Opportunity.candidate_id` 无 DB 级 FK（SQLite 限制），依赖应用层维护。
- `main.py` 使用 `on_event`（FastAPI 已建议迁移 lifespan），当前仅产生 Deprecation 警告。

## 22. 遗留事项与建议

- 华南理工候选（74.0/B）待人工审核，可由用户在 UI 完成或保持待审。
- 候选转正式后，新信号如何回流更新**正式机会**（而非已终态的候选）——建议 T06 设计"Opportunity 级增量刷新"。
- CompanyDetailPage 可补一个"分析机会"快捷按钮（当前可通过机会页"批量分析"覆盖）。
- 验证脚本已系统化于 `backend/scripts/t05_validation/`（step1–4，含 README），可重复执行真实数据验收。
- 拒绝原因（9 类）已落库，建议后续做拒绝原因复盘报表。

## 23. T05 结论

T05 交付了完整的"信号 → 候选 → 人工审核 → 正式机会"引擎：分数可解释、证据可回溯、无证据不生成、人工决策优先。真实数据（ccgp.gov.cn 三家真实采购单位）完成了从采集到候选到转正式的全链路验收；本会话额外修复了来源等级误判、终态候选重建崩溃两个真实 bug，并补齐了前端审核闭环与 CORS 配置。240 个测试全绿。**T05 验收通过**，系统具备进入 T06（验证实验/增长闭环深化）的条件。
