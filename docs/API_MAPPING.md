# BizPulse 前后端 API 映射（T02）

> Base URL：`http://localhost:8000/api/v1`（前端统一走 `frontend/src/api/client.ts`，禁止页面内硬编码地址）
>
> 统一响应包装：`{"success": bool, "data": T | null, "message": string | null}`
>
> 统一分页参数：`page`（≥1）、`page_size`（1–100）；统一分页响应：`{"items": [], "page": 1, "page_size": 20, "total": 0}`

## 页面 ↔ API 对照

| 前端页面 | 路由 | 对应 API | 请求方式 | 响应类型 | 是否已联调 |
|---|---|---|---|---|---|
| 首页 | `/` | `/dashboard` | GET | DashboardSummary（真实统计，无数据为 0） | ✅ 已联调 |
| 首页（系统状态） | `/` | `/health`、`/system/info` | GET | HealthStatus / SystemInfo | ✅ 已联调 |
| 机会雷达 | `/radar` | `/radar/summary`、`/opportunities` | GET | RadarSummary / 分页机会列表 | ✅ 已联调 |
| 市场机会 | `/markets` | `/markets` | GET | 分页市场列表 | ⏳ 待联调（V1 无真实市场数据，显示空状态） |
| 企业库 | `/companies` | `/companies` | GET（q/industry/country/province/city/sort/分页） | 分页企业列表 | ✅ 已联调 |
| 企业详情 | `/companies/:id` | `/companies/{id}/overview` | GET | 企业+信号+AI推断痛点+机会+原始证据聚合 | ✅ 已联调（T02 新增页面） |
| 企业详情（新增信号） | `/companies/:id` | `/signals` | POST | Signal | ✅ 已联调 |
| 企业详情（新增机会） | `/companies/:id` | `/opportunities` | POST | Opportunity | ✅ 已联调 |
| 商业信号 | `/signals` | `/signals` | GET（signal_type/company_id/status/fact_or_inference/min_confidence/分页） | 分页信号列表（含 evidence） | ✅ 已联调 |
| 客户机会 | `/opportunities` | `/opportunities` | GET（stage/grade/status/company_id/min_score/分页） | 分页机会列表（含 counts） | ✅ 已联调 |
| 客户机会（人工审核） | `/opportunities` | `/opportunities/{id}/review` | POST | Opportunity（T02 新增） | ✅ 已联调 |
| 客户机会（阶段流转） | `/opportunities` | `/opportunities/{id}/stage` | PATCH | Opportunity | ✅ 已联调 |
| 验证实验 | `/experiments` | `/experiments` | GET | 分页实验列表 | ⏳ 待联调（V1 显示空状态） |
| 数据源 | `/sources` | `/sources` | GET/POST/PATCH | 分页数据源列表 | ✅ 已联调 |
| 数据源（分析网页） | `/sources` | `/ingest/url` | POST | IngestResult（T02 新增） | ✅ 已联调 |
| 采集任务 | `/jobs` | `/jobs` | GET/POST | 分页任务列表 | ⏳ 待联调 |
| 分析日志 | `/logs` | `/logs/audit`、`/logs/llm-runs` | GET | 分页日志 | ✅ 已联调（审计日志） |
| 系统设置 | `/settings` | `/system/info` | GET | SystemInfo | ✅ 已联调（只读） |

## T02 核心 API 明细

### POST /ingest/url（手动 URL 分析）
```json
请求: {"url": "https://...", "note": "可选备注"}
响应: {"success": true, "data": {"source_id", "source_record_id", "company_id", "signal_ids": [], "pain_point_ids": [], "opportunity_ids": [], "llm_configured": false, "duplicate": false}, "message": "ingested|duplicate_record_reused|llm_enriched"}
```
- URL 安全：仅 http/https；拒绝 localhost/内网/保留 IP（含 DNS 解析结果）；超时/重定向/大小受限；不绕过登录验证码。
- 识别不了企业时 `company_id = null`，不猜测。
- LLM 未配置时 `llm_configured=false`，不阻塞采集（规则引擎照常提取事实信号）。

### POST /opportunities/{id}/review（人工审核）
```json
请求: {"action": "approve|reject|edit|ready", "note": "备注", "updates": {"title?": "...", "*_score?": 0-100}}
响应: Opportunity（含 review_status/reviewed_at/review_note/reviewed_by）
```
- approve → 通过（stage=READY）；reject → 驳回（stage=REJECTED）；ready → 加入验证；edit → 修改（分数变更由后端重新计算总分）。
- 每次审核写入 `audit_logs`（action=REVIEW）。

### POST /signals（人工创建信号）
- 必须提供 `source_record_id` 或 `evidence_url` 之一（保证证据可追溯）。
- `evidence_url` 会自动创建 SourceRecord（来源：人工录入证据，B 级）。
- `signal_type` 必须在统一枚举内（22 种，与前端 `SIGNAL_TYPE_LABELS` 共享语义）。

### 证据验证机制（真实数据强制规范）
- `source_records` 与 `signals` 均含 `verification_status`（UNVERIFIED/VERIFIED）；`source_records` 另含 `source_reliability`（采集时来源等级快照 A/B/C/D）与 `last_verified_at`。
- Opportunity **人工审核通过**（approve/ready）时，其关联证据自动标记 VERIFIED 并记录验证时间。
- **创建 Opportunity 必须至少关联 1 条 Signal**（后端自动挂接 Evidence）；`evidence_count=0` 时返回 422 —— 无证据只能作为待验证线索，不能生成正式机会。
- **D 级来源联动**：主信号来源等级为 D 时，`evidence_score` 强制钳制 ≤59（证据门槛生效，等级最高 B）。
- 采集入库前执行内容非空检查：正文与标题均为空的页面返回 422 拒绝入库。
- 审核审计（audit_logs，action=REVIEW）记录 `before` / `after`（修改前后字段值对照）。

### GET /signals 筛选参数（全量）
`signal_type` / `company_id` / `status` / `fact_or_inference` / `min_confidence` / `collected_from` / `collected_to`（ISO 时间）/ `page` / `page_size`

## Signal Type 枚举（前后端共享）

HIRING / SALES_HIRING / CUSTOMER_SERVICE_HIRING / FINANCE_HIRING / AI_HIRING / FUNDING / EXPANSION / OVERSEAS_EXPANSION / NEW_PRODUCT / NEW_MARKET / PROCUREMENT / TENDER / CRM_DEMAND / ERP_DEMAND / CUSTOMER_COMPLAINT / COST_PRESSURE / EFFICIENCY_PROBLEM / DIGITAL_TRANSFORMATION / AI_TRANSFORMATION / MANUAL_WORK / DATA_PROBLEM

## Opportunity 阶段枚举（前后端共享）

NEW 新发现 / REVIEW 待审核 / READY 准备验证 / CONTACTED 已联系 / REPLIED 已回复 / MEETING 已会议 / QUOTED 已报价 / PILOT 已试点 / WON 已成交 / REJECTED 已拒绝

（旧值 `PENDING_REVIEW` 后端自动映射为 `REVIEW`。）

## 证据来源等级（EvidencePanel）

- **A** 官方网站 / 官方公告 / 政府 / 交易所 / 官方采购
- **B** 大型招聘平台 / 权威媒体 / 行业协会 / 人工录入证据
- **C** 社区 / 论坛 / 公开社交平台 / 手动URL分析
- **D** 转载 / 无法完全确认

## 未联调 / 已知边界

- `/markets`、`/experiments`、`/jobs` 页面尚未接真实数据（端点已存在），页面显示"暂无真实数据"。
- LLM Adapter（`backend/app/llm/adapter.py`）已实现 extract_signal / infer_pain_point / generate_opportunity，配置 `LLM_API_KEY`/`LLM_BASE_URL`/`LLM_MODEL` 后生效；未配置时 ingest 正常返回 `llm_configured=false`。
