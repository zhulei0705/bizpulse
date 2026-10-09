# 商脉 BizPulse 3.0 战略基线

> BIZ-V3-01（2026-10-09）：原文作为历史基线保留。当前商业定位、优先产品与首批样本口径以文末增补及[首批客户计划](BIZPULSE_FIRST_PAID_CUSTOMER_PLAN.md)为准；历史价格不作为本轮报价。

文档日期：2026-10-09。官网研究日期：2026-10-08。状态：产品定位与战略文档基线；后续执行等待人工确认，不授权业务开发、数据库修改或客户触达。

## 一、产品定位

产品名称：商脉 BizPulse。

长期定位：中国企业 AI 商业增长网络。

近期定位：基于真实需求与企业解决能力的高质量 B2B 商机发现和交付服务。

核心使命：让真实需求找到真正有能力解决它的企业。

近期交付单位是“经核验的需求与能力比较结果”，不是企业名单数量。长期网络成立的前提是双方授权、可持续交付、客户认可和付费；目前网络效应、获客效率、成交提升和付费意愿均未验证。

## 二、真实项目基线与门禁

项目目录存在。工作区已有大量未提交更改，本轮不覆盖、不提交、不重置。复用 FastAPI、SQLAlchemy、采集编排、SourceRecord、SignalEvidence、Signal、Opportunity、Experiment、人工审核及审计机制。

|能力|实际依据|当前边界|
|---|---|---|
|采集与来源管理|`backend/app/collectors/registry.py`，注册 HTTP 网页、RSS、手动 URL、可选 Crawl4AI|存在实现不等于真实业务来源全部验收；没有发现独立 API 来源适配器|
|来源版本与证据|`backend/app/models/source.py`、`signal.py`、`services/evidence_integrity.py`|P0 修复已加入阻断与隔离；商业场景完整性仍需复验|
|需求解析与可行动性|`services/procurement_parser.py`、`actionability.py`|已有规则；不能据此声称已具备跨行业技术匹配产品|
|参数比较研究|`backend/scripts/t10_a/product_match.py`|有证据、单位与同一配置比较的小型研究脚本；尚非生产通用引擎|
|销售实验与反馈记录|`models/experiment.py`、`opportunity.py`|存在目标、互动、报价、结果等结构；不等于已确认客户价值或续费|
|自动批准门禁|`core/config.py`、人工审核入口|NO_AUTO_APPROVAL 必须为 TRUE；历史 APPROVED 不代表本轮批准|

最新已找到的技术依据是 [T10-C1.1 P0 报告](../reports/T10-C1_1_P0_REMEDIATION_REPORT.md)：P0 修复 Gate 为 PASS，C1 整体验收仍待复验。未找到 T10-C1.2 通过报告，因此 T10-C2 保持 BLOCKED。报告中的全量 593 passed、4 warnings 是前轮历史结果，本轮文档任务没有重新运行 pytest。

[T10-A 报告](../reports/T10-A_MARKET_VALIDATION_REPORT.md)取得16个相关项目、3家供应商，确认可立即投标项目为0，客户认可和付费意愿未验证。旧沙盒20 URL 对照不能充当真实采购市场质量验证。汉邦激光历史证据隔离和历史客户状态保持；历史 READY_TO_CONTACT 不等于当前已联系就绪。

保持 REAL_DATA_ONLY、NO_FAKE_DATA、NO_FAKE_EVIDENCE、NO_UNVERIFIED_FACT、NO_AUTO_APPROVAL。T10-C1.2 未通过前，不启动 T10-C2、不大规模采集、不自动批准 Signal、不自动触达客户。通过后也须取得阶段任务授权，不能按日历自动推进。

## 三、竞品研究口径

FACT：官网或正式文档确实披露该能力或标价；仅证明厂商披露，不证明效果、全客户可用或本地适用性。INFERENCE：BizPulse 对产品方向的分析判断。UNKNOWN：公开证据不足，不能翻译成“竞品没有”。本轮没有登录试用或客户实测；不引用第三方评论推定功能缺陷。

### 1. 企业数据、需求信号与供需匹配

|产品|企业数据|需求信号|供需匹配|官方依据|
|---|---|---|---|---|
|探迹|企业及产业等数据检索|招投标、商业动态及机会发现|目标画像推荐、产品关系和 AI 商机匹配；参数级判定细节 UNKNOWN|[产品官网](https://www.tungee.com/)|
|百炼智能|企业、行业知识与上下游数据|标讯、项目及企业动态|商机大师与企业画像推荐；逐条硬参数计算 UNKNOWN|[官网](https://www.bailian-ai.com/)、[公司与产品说明](https://www.bailian-ai.com/about)|
|剑鱼标讯|企业与采购单位画像|招标、结果、采购意向等，权益依套餐|组合筛选、大模型匹配；不能归为只有关键词的产品|[超级订阅](https://www.jianyu360.cn/front/subscribe.html)、[会员说明](https://www.jianyu360.cn/big/pc/page/index)|
|6sense|企业、联系人与技术属性|第一方及第三方意图、网站访问等|账户适配、阶段与意图评分；采购参数比较 UNKNOWN|[销售方案](https://6sense.com/platform/sales/pricing/)、[意图数据](https://6sense.com/platform/intent-data/)|
|Clay|多供应商数据补全及网页研究|职位变化、网站意图等，依套餐|客户可编排条件、补全与 AI 研究；领域参数模板完整性 UNKNOWN|[套餐](https://www.clay.com/pricing)、[条件工作流文档](https://university.clay.com/docs/enrichment-in-workflows)|
|HubSpot|CRM 企业/联系人与数据管理|Buyer Intent、客户行为及自定义信号|目标市场和意图筛选；设备参数判定 UNKNOWN|[Buyer Intent](https://knowledge.hubspot.com/reports/use-buyer-intent)、[自定义信号](https://knowledge.hubspot.com/data-management/create-custom-signals)|
|纷享销客|CRM 客户、产品及业务数据|客户行为、采购意向和商机变化|客户洞察、商机风险与策略；逐项采购参数比较 UNKNOWN|[官网业务能力](https://www.fxiaoke.com/)|

### 2. 证据可信度、销售行动、客户反馈与数据集成

|产品|证据可信度：已披露与未知|销售行动|客户反馈|数据集成|官方依据|
|---|---|---|---|---|---|
|探迹|有企业信息与业务记录；原文版本及字符级核验 UNKNOWN|客户分级、沟通、销售管理|交易画像用于推荐；卡片级客户价值归因 UNKNOWN|对外接口范围、授权与费用 UNKNOWN|[移动产品](https://www.tungee.com/product/app/)、[客户分级](https://www.tungee.com/solution/grade/)|
|百炼智能|行业知识与数据产品披露；逐项原文版本核验 UNKNOWN|找项目、推荐与标书辅助|商机结果回流协议 UNKNOWN|招投标数据开放平台披露；接口权益需核实|[官方产品与平台](https://www.bailian-ai.com/)|
|剑鱼标讯|明确提供公告原文链接、附件与进度监控；字符级版本核验 UNKNOWN|订阅推送与团队协作|客服服务已披露；逐卡真实商业结果反馈 UNKNOWN|开放平台/API 已披露；许可范围需另核实|[订阅权益](https://www.jianyu360.cn/front/subscribe.html)、[服务体系](https://www.jianyu360.cn/product/index?serviceType=1)、[开放平台介绍](https://www.jianyu360.cn/jyapp/free/swordfish/about)|
|6sense|多源数据与预测评分；官网 Contextual Intelligence 标为 Coming Soon，不能视为已上线证据证明书|账户优先级、提醒、销售工作流|CRM/MAP 数据用于模型；不等于因果成交证明|正式文档列出 CRM/MAP 等集成|[平台状态](https://6sense.com/platform/)、[集成支持](https://support.6sense.com/docs/supported-versions-of-integrations)、[输入对象要求](https://support.6sense.com/docs/minimum-object-requirements-for-crm-and-map-integrations-for-abm-customers)|
|Clay|网页研究、连接与执行管理；不可变原文字符证据保证 UNKNOWN|编排、邮件及 CRM 工作流|可接业务数据；价值反馈闭环效果 UNKNOWN|HTTP、Webhook、CRM、企业 API 等依套餐|[研究说明](https://university.clay.com/lessons/enriching-with-claygent)、[连接文档](https://university.clay.com/docs/connections)、[套餐](https://www.clay.com/pricing)|
|HubSpot|集中业务记录；采购原文不可变快照保证 UNKNOWN|销售流程与营销/服务工具|CRM 关联满意度调查和客户成功能力|官方 CRM 等 API|[产品](https://www.hubspot.com/products)、[反馈文档](https://knowledge.hubspot.com/customer-feedback/create-and-send-customer-satisfaction-surveys)、[API](https://developers.hubspot.com/docs/api-reference/latest/overview)|
|纷享销客|业务主数据及过程管理；公告字符级证据保证 UNKNOWN|线索到现金、销售与服务协同|客户声音汇总、商机复盘与服务管理|开放平台，钉钉/企微等生态产品|[产品官网](https://www.fxiaoke.com/)、[平台及套餐页](https://www.fxiaoke.com/ap/market-price)|

### 3. 收费方式

|产品|官网可确认的收费方式|未知项与注意事项|
|---|---|---|
|探迹|官网引导咨询/演示；本轮未核实统一公开价|套餐、座席、数据配额和合同价 UNKNOWN；不能断言没有公开价|
|百炼智能|多产品服务；本轮未核实统一公开价|商机大师、数据 API 等实际计费 UNKNOWN|
|剑鱼标讯|官网列超级订阅29元/省/月、680元/全国/年；大会员2999、7999、19999元/全国/年|标价不等于成交价；地区、权益与促销需成交时复核。见[服务价格](https://www.jianyu360.cn/product/index?serviceType=1)|
|6sense|销售方案结合 Data Credits 与 Predictive AI，需咨询|本轮未核实统一金额；见[官方销售价格页](https://6sense.com/platform/sales/pricing/)|
|Clay|Free/Launch/Growth/Enterprise，Data Credits 与 Actions 计量，企业询价|周期、配额影响金额；不把不同月/年付显示混为一价。见[价格及 FAQ](https://www.clay.com/pricing)|
|HubSpot|免费及付费分层，按 Hub、套餐与座席等购买|附加配额和合同条款另核实；见[Sales Hub 价格](https://www.hubspot.com/pricing/sales)|
|纷享销客|专业版119元/人/月、旗舰版220元/人/月，官网列12个月起购；按账号/功能综合计费|实施和附加模块费需询价；见[官方报价](https://www.fxiaoke.com/ap/market-price)|

以上竞品标价是截至研究日的官网披露，不是 BizPulse 价格验证结果。覆盖率、准确率、客户数量和营收效果宣传均未在本轮独立核验。

## 四、选择性复用与差异化假设

|方向|BizPulse 已有|计划引入：须门禁与验证|本阶段不复制|
|---|---|---|---|
|需求发现|采集、来源质量、Signal、采购解析|借鉴多源监控与生命周期，但先证明主体、日期和原文准确|全网大规模数据库、未经授权意图追踪|
|企业能力|Company 与研究级产品比较|客户授权能力护照、产品配置/资质/地区证据|无限联系人数据库与完整工商数据库自建|
|解释与交付|Evidence、风险项、人工审核、Opportunity|逐条双边证据和版本化证明书|仅凭评分自动声称可投标或必成交|
|客户工作流|Experiment、互动及结果结构|人工反馈原因、授权 CRM 单向试接|完整 CRM、群发平台、广告系统、标书大套件|

INFERENCE：可检验的优势假设是“同一真实需求、同一供应商配置，硬条件与证据同时可复核，减少无效筛选并进入客户工作流”。不能宣称唯一、竞品不具备或已经提高成交率。可被复制的模块名称和页面不是壁垒。

## 五、市场切入与扩行业机制

优先邀请有明确产品资料、人工筛选负担和可核验交付约束的企业参与研究。激光/增材及科研设备可作为首个验证场景，沿用已有研究；不全局硬编码为唯一行业，不默认汉邦激光是有效试点客户。

行业只是选择规则包和数据词典的维度。每个新行业需要需求来源许可、能力资料、硬约束词典、人工审阅基准、真实客户和成本核验；六道硬门槛通过后才能排序，详见 [PRD](BIZPULSE_PRODUCT_PRD_V3.md)。第二行业先做人工模板复核，只有真实付费和 Gate 通过后才安排自动化。

网络路线：先做一侧供应商的可信交付服务，再验证买方授权需求与供应方反馈，最后检验跨客户推荐是否产生增量价值。没有双侧授权、足够有效需求和重复交易前，不开发交易撮合、竞价或佣金系统。

## 六、决策与退出条件

立即可验证：竞品演示清单、用户筛选成本访谈、授权能力模板、证明书可读性、手工成本表与价格访谈。当前任务只准备这些材料，实际访谈和报价需人工安排。

必须等待技术 Gate：真实业务来源复验、受控采集、生产证据链与生命周期复验、T10-C2 详细技术任务及实现。必须等待实际付费及单独授权：专属集成、复杂租户、跨行业自动规则包、双侧网络功能。

严重主体错误、证据不一致、越权访问立即停止相应批次；无法取得资料或客户认为只是重复已有订阅时，记录失败并缩小场景。商业验证不通过不以扩大采集量掩盖。

配套：[商业模型](BIZPULSE_BUSINESS_MODEL_V3.md)、[产品 PRD](BIZPULSE_PRODUCT_PRD_V3.md)、[壁垒路线](BIZPULSE_MOAT_ROADMAP.md)、[90天验证](BIZPULSE_90_DAY_VALIDATION.md)。

## 七、本轮交付核验

实际新增上述五份中文文档，引用27个不同官方网页/文档地址；本地文档链接检查无缺失。对后端应用、测试、脚本、前端源码及 backend/data 中449个文件的开始/结束 SHA256 清单比对，无新增、删除或内容改变，包含正式数据库及原文文件。该文件级核验不替代后续技术 Gate。本轮未运行 pytest、创建 Interaction、发送消息或修改业务数据。

## 八、BIZ-V3-01 商业定义冻结与审计增补

产品：商脉 BizPulse。长期定位：中国企业AI商业增长网络。**现行近期商业定位：客户专属精准商机发现与验证服务。**核心价值：让真实需求找到真正有能力解决它的企业。商业目标：帮助付费客户找到值得跟进的潜在客户，降低无效获客成本，提高有效销售机会数量；这些效果是验证目标，尚未证明。

不限定行业，优先选择可以核实需求、能力及销售价值的问题。首批目标3–5家愿交流的真实 B2B 企业；原90天10家访谈为后续扩展目标，不是本轮必须凑满的门槛。激光设备研究只作为方法经验，不能默认已有供应商愿付费或恢复汉邦失效证据。

第一款收费产品建议：14天1999元的“客户专属商机核验试点”，为实验假设，报价区间999–2999元、周期14–30天；后续月度服务2000–5000元/月，团队 SaaS 暂缓。交付能力护照、真实证据证明书和复盘，允许不推荐或零有效机会报告。此定义替代本轮执行中的旧低价订阅假设，旧测算保留研究历史。

三个最值得先问的客户问题（均为假设）：①筛选大量不适合的线索，人工与获客成本高；②不知道需求是否真实、有效、能由自己交付；③新机会是否超出已知信息、值得销售投入难以判断。必须用客户具体案例、工时、原话和实际评审确认，不能把这三项写成已确认需求。

审计补充：Company 基本资料、SourceRecord 版本、SignalEvidence、人工审核和 Experiment/Interaction/Quote/Outcome 基础已存在；`services/metrics.py`区分合同与收款。没有把能力护照、D0–D3、证明书或首批收费方案实现为已上线产品。现有招聘规则可输出 ACTIONABLE_NOW，但不能直接映射为 D3 或购买意图；BIZ-V3-01 人工商业规则须独立复核，禁止修改正式规则/评分。后台某些空分母比率返回0，商业报告要附真实分母并显示未验证，本轮不改代码。

技术门禁：T10-C1.1=PASS（P0）；T10-C1.2=尚待真实业务来源验收；T10-C2=BLOCKED。README 保留旧目录启动示例和早期5测试结果，不用其证明当前状态，也不在本任务修改 README。现有全量593通过是历史报告，本任务只检查文档。

差异化仍是可验证假设：以客户授权能力及排除条件决定是否推荐，D0–D3分层，双边证据与拒绝推荐，按真实客户评审改进。成熟产品已有推荐、公告回链、CRM 等能力，不宣称它们没有这些功能。本轮复核[探迹](https://www.tungee.com/)、[剑鱼](https://www.jianyu360.cn/front/subscribe.html)、[HubSpot](https://www.hubspot.com/products)及[百炼公司说明](https://www.bailian-ai.com/about)；百炼首页本轮访问失败，不将旧官网研究日期改成新实测。

新增执行资料：[客户能力模板](BIZPULSE_CUSTOMER_CAPABILITY_TEMPLATE.md)、[商机证明书](BIZPULSE_OPPORTUNITY_PROOF_TEMPLATE.md)、[收费实验](BIZPULSE_PRICING_EXPERIMENT.md)、[首批客户与30天计划](BIZPULSE_FIRST_PAID_CUSTOMER_PLAN.md)。本任务仅准备材料，新增访谈、报价、付款、外发及正式业务记录均为0，不能由文档目标推定已经验证。
