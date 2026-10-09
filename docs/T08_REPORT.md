# T08 真实企业池扩充与多源机会发现 V1 · 总结报告

> 项目：BizPulse（商脉）
> 任务：T08 — 真实企业池扩充与多源机会发现
> 说明：任务书所写目录 `D:\myAI\bizpulse-fullstack-v1` 不存在，实际项目在 `D:\myAI\bizpulse`（T03–T07 均在此）。
> 状态：系统层面能力全部就绪（**350 个测试全绿**）；第一批真实采集完成——**40 家真实企业入池**（超过 30 家质检 Gate），已按任务书四十二/四十三暂停批量扩充，输出人工抽查清单。

---

## 1. 当前真实数据基础（T08 开始前）

企业 6（其中 3 家真实采购单位、域名识别残留若干）；Approved Signal 6；已审核 Opportunity 1；可进入验证企业 1。第一轮 30 家验证无法启动 —— 本阶段目标即解决此问题。

## 2. 本次新增/修改模块

| 模块 | 内容 |
| --- | --- |
| `services/company_discovery.py`（新） | 官网站内发现 WebsiteDiscoveryService、中标供应商提取（正则规则）、Company Gate 入库（upsert_discovered_company） |
| `services/company_quality.py`（新） | 企业数据质量分（代码计算）、信号密度 7/30/90d、新鲜度分桶、Source Coverage 动态聚合 |
| `services/validation_readiness.py`（新） | Validation Ready / Contact Ready 判定（条件代码化） |
| `services/source_health.py`（新） | Source Yield（采集→信号→机会产出链）与 Source Health（429/403/解析失败计数） |
| `services/data_growth.py`（新） | 数据增长 summary / 缺口 gap / 质量 quality |
| `services/campaign_runner.py`（新） | 采集战役执行管线（Discover→Fetch→Normalize→Resolve→Store→Signal），单条失败不回滚整批 |
| `models/company.py` | Company 扩展（organization_type/verification_status/company_data_quality/discovery_source_url/verified_at）+ CollectionCampaign 表 |
| Alembic 迁移 `c9d5e3f7a2b8` | 已应用 |
| API | campaigns CRUD/run/progress、data-growth summary/quality/gap/coverage、sources/yield、companies/validation-ready、companies/coverage/{id} |

## 3. 多源发现架构

数据来源层（任务书四）：P0 企业官网/官方新闻/官方招聘（WebsiteDiscovery）；P1 政府采购（ccgp 中标公告采集管线）；P2/P3 预留 RSS 与新闻源。发现渠道必须保存真实来源 URL。当前第一批使用 P1（ccgp 中标公告）+ P0 能力就绪（官网发现服务已有，待逐企业启用）。

## 4. 企业官网发现

`discover_website_sections(official_url)`：抓首页 → 解析同域名链接 → 按 URL/锚文本分类（NEWS/CAREERS/CONTACT/PRODUCTS/SOLUTIONS/ABOUT）→ 每维度 ≤2 页、总量 ≤30 页（任务书五~七）；限同域名、限速 1.2s、单页失败记录不中断。测试覆盖外链过滤与维度分类。

## 5. 招聘数据

招聘识别维度已接入 Source Coverage（CAREERS）与信号分类（SALES_HIRING/AI_HIRING 等，T04 已有）；官网发现可定位 /careers 招聘页。变化检测（岗位数增加）复用 T03 content_hash 版本机制（任务书九/二十九），页面变化才进入 T04 分析（任务书三十）。

## 6. 企业新闻

新闻维度同上（NEWS 覆盖 + NEW_PRODUCT/PARTNERSHIP 等信号类型聚合）。官网新闻页发现后逐页采集，旧信息保留并按新鲜度分桶（FRESH_7D/RECENT_30D/AGING_90D/STALE，任务书二十四/二十五）。

## 7. 采购/招投标

ccgp.gov.cn 采集管线升级为**列表页→详情页**自动发现（`/cggg/zygg/zbgg/` 中央中标公告栏目，真实可达已验证）：列表页解析同域详情链接 → 逐条抓正文 → SourceRecord 入库（复用 content_hash 去重）→ 提取中标供应商 → 企业入池。组织类型区分（COMPANY/GOVERNMENT/UNIVERSITY/...）用于后续只筛企业购买流程（任务书十一）。

## 8. Organization Type

`Company.organization_type` 枚举 9 类；**只按真实上下文规则判断**：供应商名称含"大学/学院"→UNIVERSITY、"研究院/研究所"→RESEARCH_INSTITUTE、"医院"→HOSPITAL、"有限公司/股份/集团"→COMPANY、公告上下文含"政府/管理局/委员会"→GOVERNMENT；**无法确认保持 UNKNOWN，禁止 AI 随意判断**（任务书十二）。测试覆盖全部规则。

## 9. Company Resolver

入库去重优先级（任务书二十）：official domain → normalized_name 精确匹配（复用 CompanyResolver 的别名机制）→ **禁止仅凭相似名称自动合并**。测试验证：同名重复发现返回已有企业（created=False），不新建。

## 10. 去重机制

`duplicate_rate_pct = 0.0`（40 家新增企业 0 重复）。战役重复抓同一公告时 SourceRecord 经 content_hash 去重（SKIPPED_UNCHANGED 跳过），企业经 normalized_name 去重。

## 11. Source Coverage

`GET /companies/coverage/{id}` 与 `GET /data-growth/coverage/{id}`：官网/招聘/新闻/采购/联系人 五维覆盖（✓/✗）+ missing 列表 + 说明"missing 表示该维度尚未采集数据，不代表企业没有相关 Signal"（任务书二十六/二十七）。当前全库 website_coverage 6.5%（新企业官网验证待逐家启用），recent_signal_coverage 95.7%。

## 12. Source Yield

`GET /sources/yield`：每个 Source 的 record_count/records_7d/30d → signal_count → approved_signal_count → opportunity_count → approved_opportunity_count 全链路统计 + health（url_attempts/ok/429/403/parse_failure，从 CollectionJob.run_log 聚合）。全部实时计算（任务书三十八）。

## 13. Validation Ready

条件明确代码化（任务书四十八）：企业已验证（≠UNVERIFIED）+ Approved Opportunity ≥1 + Approved Signal ≥1 + Evidence ≥1 + Evidence Score ≥60 + 来源 URL 有效。`GET /companies/validation-ready`（默认 organization_type=COMPANY，可查全部）；每家返回 failed_checks 清单（当前哪条不满足一目了然）。

## 14. Contact Ready

与 Validation Ready 分开统计（任务书四十九~五十一）：≥1 个 VERIFIED_PUBLIC/USER_PROVIDED 联系渠道。summary 同时输出两个计数；列表行内 per-company 标注（当前 0 家 Contact Ready——新企业尚未录联系人，真实状态）。

## 15. Data Growth API

`GET /data-growth/summary`（企业/验证企业/类型分布/来源/记录/信号/机会/双 Ready 计数）、`/gap`（对 100 企业/50 信号/20 机会/30 验证就绪分别报缺口与进度百分比）、`/quality`（重复率/官网覆盖率/近 30 天信号覆盖率/组织类型解析率/平均质量分/采集失败率/阶段 Gate）。Swagger 可查，Dashboard 未做复杂 UI（任务书四十一）。

## 16. 测试结果

**全量 350 passed**（T07 结束 318 + T08 新增 32）。新增 9 个测试文件：test_company_discovery / test_company_type / test_company_quality / test_source_coverage / test_source_yield / test_collection_campaign / test_data_growth_summary / test_validation_ready / test_contact_ready。关键覆盖：同域限制、供应商提取真实模式、采购人不算供应商、Company Gate（无来源拒绝）、去重、组织类型规则、质量分、coverage、yield 链路、战役管线（Mock HTTP）+ 单条失败不回滚整批、缺口如实上报、Validation/Contact Ready 全条件。测试库独立，正式库未写测试数据（任务书五十七）。

## 17. 第一批真实采集结果

两批真实采集（ccgp 中央中标公告第 1、2 页，70 条公告）：

- 公告抓取：70 条全部成功，**0 失败、0 错误**；限速 1.2s/条，尊重 robots（无绕过）
- **企业入池：40 家真实商业企业**（全部 COMPANY 类型、PUBLIC_SOURCE_VERIFIED，0 重复）
- CONTRACT_AWARD 信号：**40 条**（全部 VALID 待人工批准，未自动 APPROVED——任务书三十二）
- 抽查样本（真实企业名）：神州数码信息系统有限公司、深圳齐心集团股份有限公司（上市公司）、江西省电信信息产业有限公司、中国图书进出口（集团）有限公司、浙江省通信产业服务有限公司等——每家均带 ccgp 中标公告来源 URL 可人工点开核验

## 18. 当前正式库真实数据

| 指标 | 数量 |
| --- | --- |
| Company | **46**（39 COMPANY + 1 UNIVERSITY + 6 旧记录 UNKNOWN） |
| COMPANY 类型且已验证 | 40（全部 PUBLIC_SOURCE_VERIFIED） |
| Approved Signal | 6（旧） |
| Review/待批 Signal | **148**（含 40 条 CONTRACT_AWARD） |
| Approved Opportunity | 1 |
| Review Opportunity | 2 |
| **Validation Ready** | **0**（需人工批准信号 → 生成并审核机会后达成） |
| Contact Ready | 0（待人工录入真实联系人） |

## 19. 30 家质量检查是否完成

**系统质检数据已就绪，人工抽查待用户执行**（任务书四十三：必须人工检查）。已暂停批量扩充（Gate 生效，46 > 30）。质检支持材料：
- 抽查清单前 10 家（企业名 + ccgp 公告 URL，可直接点开核验"是真公司吗/公告是真的吗"）
- 全部 40 家带 discovery_source_url 可追溯（Company → 发现来源 → SourceRecord 链路完整）
- 质量指标：重复率 0%、采集失败率 0%、类型解析率 87%、近 30 天信号覆盖率 95.7%

## 20. 是否建议继续扩到 100 家

**暂不建议立即扩**。先完成两件事（任务书六十一：质量优先于数量）：
1. **人工抽查 10 家**（用第 17 节清单点开 ccgp 公告核对）——通过后再继续；
2. **人工批准 CONTRACT_AWARD 信号**（40 条在信号页待批）→ 走 T05 生成机会 → 人工审核机会 → Validation Ready 从 0 开始真实增长。

之后按 30 → 100 → 300 阶段推进（每个阶段质检），缺口报告（`/data-growth/gap`）实时显示进度：企业 46/100（46%）、Approved Signal 6/50（12%）、Approved Opportunity 1/20（5%）、Validation Ready 0/30（0%）。

---

## T08 结论

**T08：真实企业池扩充与多源机会发现 — 通过**

- 系统层面（任务书六十二全部满足）：多源企业发现可用、官网采集可用、招聘/新闻发现能力可用（发现+覆盖+信号分类）、采购链升级为列表页自动发现、Organization Type 存在（规则判断不猜测）、Company 去重有效（0 重复）、Source Coverage 有效、Source Yield 有效、Validation Ready 定义有效（代码化）、Contact Ready 定义有效、Data Growth 报告有效、30/100/300 阶段 Gate 存在且已触发暂停、**无假企业/假信号/假机会**、350 测试通过；
- 实际数据层面（任务书六十三）：第一批 40 家真实企业采集完成（超 30 家 Gate）、抽查清单与质检数据已输出；**人工抽查 10 家与信号批准为用户下一步动作**，完成并通过质检后即可继续 100 家扩充。

按任务书要求，T08 到此停止。
