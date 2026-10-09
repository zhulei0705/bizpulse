"""前后端共享语义的业务枚举。前端需保持相同取值与中文标签。"""

SIGNAL_TYPES: dict[str, str] = {
    "HIRING": "招聘扩张",
    "SALES_HIRING": "销售招聘",
    "CUSTOMER_SERVICE_HIRING": "客服招聘",
    "FINANCE_HIRING": "财务招聘",
    "AI_HIRING": "AI人才招聘",
    "TECH_HIRING": "技术招聘",
    "FUNDING": "融资事件",
    "EXPANSION": "业务扩张",
    "OVERSEAS_EXPANSION": "海外扩张",
    "NEW_FACTORY": "新建工厂",
    "NEW_OFFICE": "新办公室",
    "NEW_PRODUCT": "新产品发布",
    "NEW_SERVICE": "新服务上线",
    "NEW_MARKET": "新市场进入",
    "PROCUREMENT": "采购需求",
    "TENDER": "招标信息",
    "SUPPLIER_SEARCH": "供应商招募",
    "CRM_DEMAND": "CRM需求",
    "ERP_DEMAND": "ERP需求",
    "AI_DEMAND": "AI需求",
    "AUTOMATION_DEMAND": "自动化需求",
    "DIGITAL_TRANSFORMATION": "数字化转型",
    "AI_TRANSFORMATION": "AI转型",
    "CUSTOMER_COMPLAINT": "客户投诉",
    "COST_PRESSURE": "成本压力",
    "EFFICIENCY_PROBLEM": "效率问题",
    "MANUAL_WORK": "人工操作痛点",
    "DATA_PROBLEM": "数据问题",
    "PARTNERSHIP": "合作事件",
    "STRATEGIC_COOPERATION": "战略合作",
    "MANAGEMENT_CHANGE": "管理层变动",
    "POLICY_IMPACT": "政策影响",
    "CONTRACT_AWARD": "中标/合同授予",
    "OTHER": "其他商业事件",
}

OPPORTUNITY_STAGES: dict[str, str] = {
    "NEW": "新发现",
    "REVIEW": "待审核",
    "READY": "准备验证",
    "CONTACTED": "已联系",
    "REPLIED": "已回复",
    "MEETING": "已会议",
    "QUOTED": "已报价",
    "PILOT": "已试点",
    "WON": "已成交",
    "REJECTED": "已拒绝",
}

# 旧版本 stage 值 → 新枚举
LEGACY_STAGE_MAP: dict[str, str] = {
    "PENDING_REVIEW": "REVIEW",
}

OPPORTUNITY_REVIEW_ACTIONS: dict[str, str] = {
    "approve": "通过",
    "reject": "驳回",
    "edit": "修改",
    "ready": "加入验证",
}

REVIEW_STATUSES: dict[str, str] = {
    "PENDING": "待审核",
    "APPROVED": "已通过",
    "REJECTED": "已驳回",
    "EDITED": "已修改",
}

# 进入验证中阶段（不含 NEW/REVIEW/REJECTED/WON）
VALIDATING_STAGES = ("READY", "CONTACTED", "REPLIED", "MEETING", "QUOTED", "PILOT")

RELIABILITY_GRADES: dict[str, str] = {
    "A": "官方/权威来源",
    "B": "大型招聘平台/权威媒体",
    "C": "社区/论坛/公开社交平台",
    "D": "转载/无法完全确认",
}

# ---------------------------------------------------------------------------
# T05：机会判断引擎
# ---------------------------------------------------------------------------

# 机会阶段补齐（与现有前端状态兼容）
OPPORTUNITY_STAGES["STALE"] = "已过期"

# PainPoint 分类（17 类，初期支持，可扩展）
PAIN_CATEGORIES: dict[str, str] = {
    "CUSTOMER_ACQUISITION": "客户获取",
    "SALES_EFFICIENCY": "销售效率",
    "LEAD_SHORTAGE": "线索不足",
    "OVERSEAS_EXPANSION": "海外拓展",
    "CUSTOMER_SERVICE": "客户服务",
    "RECRUITMENT": "招聘",
    "FINANCE_EFFICIENCY": "财务效率",
    "INVOICE_AUTOMATION": "发票自动化",
    "PROCUREMENT": "采购",
    "SUPPLIER_MANAGEMENT": "供应商管理",
    "DATA_MANAGEMENT": "数据管理",
    "AI_TRANSFORMATION": "AI转型",
    "DIGITAL_TRANSFORMATION": "数字化转型",
    "PROCESS_AUTOMATION": "流程自动化",
    "COMPLIANCE": "合规",
    "COST_REDUCTION": "降本",
    "OTHER": "其他",
}

# PainPoint 状态：CONFIRMED 只能来自人工/访谈/真实 Interaction，AI 不得自行升级
PAIN_POINT_STATUSES: dict[str, str] = {
    "INFERRED": "已推断",
    "REVIEWED": "已复核",
    "CONFIRMED": "已确认（人工）",
    "REJECTED": "已驳回",
}

# 机会候选状态机：DETECTED → NEED_MORE_EVIDENCE / REVIEW → APPROVED / REJECTED / CONVERTED
OPPORTUNITY_CANDIDATE_STATUSES: dict[str, str] = {
    "DETECTED": "已识别",
    "NEED_MORE_EVIDENCE": "证据不足",
    "REVIEW": "待人工审核",
    "APPROVED": "已通过",
    "REJECTED": "已驳回",
    "CONVERTED": "已转正式机会",
}

# 机会驳回原因（后续复盘最重要的数据）
OPPORTUNITY_REJECT_REASONS: dict[str, str] = {
    "NO_REAL_PROBLEM": "无真实问题",
    "WEAK_EVIDENCE": "证据不足",
    "WRONG_INTERPRETATION": "解读有误",
    "LOW_VALUE": "价值过低",
    "NO_BUDGET_SIGNAL": "无预算信号",
    "NOT_REACHABLE": "无法触达",
    "DUPLICATE": "重复机会",
    "BAD_TIMING": "时机不对",
    "OTHER": "其他",
}

# Evidence 极性：矛盾证据必须压低 Confidence / Evidence Score
EVIDENCE_POLARITY: dict[str, str] = {
    "SUPPORTING": "支持",
    "NEUTRAL": "中性",
    "CONTRADICTING": "矛盾",
}

# 推荐下一步动作（只能建议，不得自动外发）
NEXT_ACTIONS: dict[str, str] = {
    "RESEARCH": "继续研究",
    "FIND_CONTACT": "查找公开联系人",
    "MANUAL_REVIEW": "人工审核",
    "CUSTOMER_INTERVIEW": "客户访谈",
    "SEND_PROPOSAL": "发送方案",
    "EXPERIMENT": "进入实验",
}

# 直接购买信号类型（Intent 的强信号）
DIRECT_PURCHASE_SIGNAL_TYPES = {
    "PROCUREMENT", "TENDER", "SUPPLIER_SEARCH", "CRM_DEMAND", "ERP_DEMAND",
    "AI_DEMAND", "AUTOMATION_DEMAND",
}

# 信号组合类型
SIGNAL_BUNDLE_TYPES: dict[str, str] = {
    "OVERSEAS_GROWTH": "海外扩张组合",
    "AI_ADOPTION": "AI 采用组合",
    "PURCHASE_READY": "采购就绪组合",
    "SALES_SCALE_UP": "销售扩张组合",
    "SERVICE_STRAIN": "客服压力组合",
    "COST_OPTIMIZATION": "降本增效组合",
    "FINANCE_AUTOMATION": "财务自动化组合",
}

# 假设类型标记（Solution 永远是假设，不是既成需求）
HYPOTHESIS_KINDS: dict[str, str] = {
    "SOLUTION_HYPOTHESIS": "解决方案假设",
    "VALUE_HYPOTHESIS": "价值假设",
    "PAIN_INFERENCE": "痛点推断",
}

# ---------------------------------------------------------------------------
# T06：商业验证与客户反馈系统
# ---------------------------------------------------------------------------

# 实验状态（V1：人工管理实验生命周期）
EXPERIMENT_STATUSES: dict[str, str] = {
    "DRAFT": "草稿",
    "READY": "就绪",
    "RUNNING": "进行中",
    "PAUSED": "已暂停",
    "COMPLETED": "已完成",
    "CANCELLED": "已取消",
}

# 实验结论（V1 由人工最终判断；AI 只能给分析建议）
EXPERIMENT_CONCLUSIONS: dict[str, str] = {
    "KEEP": "继续推进",
    "TEST_MORE": "继续验证",
    "PAUSE": "暂停",
    "DROP": "放弃",
}

# 验证目标企业状态（真实状态，不由 AI 推测）
EXPERIMENT_TARGET_STATUSES: dict[str, str] = {
    "NEW": "新加入",
    "RESEARCHING": "研究中",
    "READY_TO_CONTACT": "准备联系",
    "CONTACTED": "已联系",
    "REPLIED": "已回复",
    "QUALIFIED": "已确认意向",
    "MEETING": "已会议",
    "QUOTED": "已报价",
    "PILOT": "已试点",
    "WON": "已成交",
    "REJECTED": "已拒绝",
    "NO_RESPONSE": "无回复",
    "PAUSED": "已暂停",
}

# Target 主流程顺序（漏斗与状态校验依据；REJECTED/NO_RESPONSE/PAUSED 为旁支）
TARGET_FLOW = [
    "NEW", "RESEARCHING", "READY_TO_CONTACT", "CONTACTED", "REPLIED",
    "QUALIFIED", "MEETING", "QUOTED", "PILOT", "WON",
]
TARGET_STATUS_RANK: dict[str, int] = {s: i for i, s in enumerate(TARGET_FLOW)}

# 互动类型（真实商业动作）
INTERACTION_TYPES: dict[str, str] = {
    "RESEARCH": "研究笔记",
    "OUTREACH": "首次触达",
    "FOLLOW_UP": "跟进",
    "REPLY": "客户回复",
    "MEETING": "会议",
    "DEMO": "演示",
    "PROPOSAL": "方案",
    "QUOTE": "报价",
    "NEGOTIATION": "谈判",
    "PILOT": "试点",
    "CONTRACT": "签约",
    "PAYMENT": "收款",
    "REJECTION": "客户拒绝",
    "NOTE": "备注",
}

# 触达渠道（仅记录真实发生的渠道）
INTERACTION_CHANNELS: dict[str, str] = {
    "EMAIL": "邮件",
    "PHONE": "电话",
    "WECHAT": "微信",
    "LINKEDIN": "LinkedIn",
    "FACEBOOK": "Facebook",
    "WHATSAPP": "WhatsApp",
    "WEBSITE_FORM": "官网表单",
    "OFFLINE": "线下",
    "MEETING": "会议",
    "OTHER": "其他",
}

# 互动方向：OUTBOUND=我方发出 / INBOUND=客户来讯 / INTERNAL=内部记录
INTERACTION_DIRECTIONS: dict[str, str] = {
    "OUTBOUND": "发出",
    "INBOUND": "收到",
    "INTERNAL": "内部",
}

# 回复分类（人工对真实回复的分类；没有回复就保持 NO_RESPONSE，不得推测）
REPLY_CATEGORIES: dict[str, str] = {
    "POSITIVE": "积极",
    "NEUTRAL": "中性",
    "NEGATIVE": "消极",
    "NEED_MORE_INFO": "需要更多信息",
    "NOT_NOW": "时机不合适",
    "WRONG_PERSON": "找错人",
    "NO_NEED": "无需求",
    "PRICE_CONCERN": "价格顾虑",
    "ALREADY_HAVE_SOLUTION": "已有解决方案",
}

# 客户拒绝原因（统一枚举；没有真实反馈只能记 NO_RESPONSE / NOT_REACHABLE）
EXPERIMENT_REJECT_REASONS: dict[str, str] = {
    "NO_NEED": "无需求",
    "NO_BUDGET": "无预算",
    "WRONG_PERSON": "接触对象不对",
    "BAD_TIMING": "时机不对",
    "PRICE_HIGH": "价格过高",
    "ALREADY_HAVE_SOLUTION": "已有解决方案",
    "NO_TRUST": "信任不足",
    "PRODUCT_NOT_FIT": "产品不匹配",
    "NOT_REACHABLE": "无法触达",
    "NO_RESPONSE": "无回复",
    "WEAK_VALUE_PROPOSITION": "价值主张不足",
    "OTHER": "其他",
}

# 联系人验证状态：只有 VERIFIED_PUBLIC / USER_PROVIDED 可作为正式联系渠道
CONTACT_VERIFICATION_STATUSES: dict[str, str] = {
    "VERIFIED_PUBLIC": "公开信息已核实",
    "USER_PROVIDED": "用户人工录入",
    "UNVERIFIED": "未核实",
    "STALE": "已过期",
    "INVALID": "无效",
}

# 联系人来源类型
CONTACT_SOURCE_TYPES: dict[str, str] = {
    "OFFICIAL_WEBSITE": "企业官网",
    "PUBLIC_PROFILE": "公开资料",
    "EXHIBITION": "展会",
    "USER_INPUT": "人工录入",
}

# T08.2 联系人业务类型（任务书十六；采购公告联系人 PURCHASER_CONTACT/AGENCY_CONTACT/PROJECT_CONTACT
# 为 T08.0 采购域取值，两套取值共存于 contact_type 字段）
CONTACT_BUSINESS_TYPES: dict[str, str] = {
    "GENERAL": "综合联系",
    "SALES": "销售",
    "BUSINESS": "商务合作",
    "PARTNERSHIP": "渠道/伙伴",
    "PROCUREMENT": "采购",
    "PROJECT": "项目",
    "HR": "人力资源",
    "PRESS": "媒体",
    "CUSTOMER_SERVICE": "客服",
    "EXECUTIVE": "高管",
    "AGENCY": "代理机构",
    "OTHER": "其他",
}

# T08.2 联系渠道（由字段推导，不新增列）：EMAIL / PHONE / WEBSITE_FORM
CONTACT_CHANNELS: dict[str, str] = {
    "EMAIL": "公开邮箱",
    "PHONE": "公开电话",
    "WEBSITE_FORM": "官方联系表单",
}

# 报价状态（VIEWED 只有真实获知才能记录，不假设）
QUOTE_STATUSES: dict[str, str] = {
    "DRAFT": "草稿",
    "SENT": "已发送",
    "VIEWED": "已查看",
    "ACCEPTED": "已接受",
    "REJECTED": "已拒绝",
    "EXPIRED": "已过期",
    "WITHDRAWN": "已撤回",
}

# 报价计费类型
QUOTE_BILLING_TYPES: dict[str, str] = {
    "PILOT": "试点",
    "SUBSCRIPTION": "订阅",
    "ONE_TIME": "一次性",
    "MILESTONE": "里程碑",
    "OTHER": "其他",
}

# observed_intent（真实观察到的购买意图，与预测 intent_score 严格区分）
OBSERVED_INTENTS: dict[str, str] = {
    "REPLIED": "回复了沟通",
    "MEETING_BOOKED": "预约了会议",
    "QUOTE_REQUESTED": "索要报价",
    "PILOT_STARTED": "开始试点",
    "NO_RESPONSE": "无回复",
    "DECLINED": "明确拒绝",
}

# PainPoint 确认来源（CONFIRMED 只能来自真实客户确认）
PAIN_CONFIRMATION_SOURCES: dict[str, str] = {
    "INTERACTION": "客户互动确认",
    "INTERVIEW": "客户访谈确认",
}

# ---------------------------------------------------------------------------
# T08：真实企业池扩充与多源机会发现
# ---------------------------------------------------------------------------

# 组织类型：通过真实来源判断；无法确认保持 UNKNOWN（禁止 AI 随意判断）
ORGANIZATION_TYPES: dict[str, str] = {
    "COMPANY": "商业企业",
    "GOVERNMENT": "政府机关",
    "UNIVERSITY": "高校",
    "RESEARCH_INSTITUTE": "科研院所",
    "HOSPITAL": "医院",
    "NON_PROFIT": "非营利组织",
    "ASSOCIATION": "行业协会",
    "SOURCE_PLATFORM": "数据来源平台（招聘/采购/媒体/新闻网站）",
    "OTHER": "其他",
    "UNKNOWN": "未确认",
}

# T08.0 P0-1：Source Publisher ≠ Business Subject Company
# 这些域名是数据来源平台（采购/招聘/媒体/新闻），禁止因域名自动创建为被分析 Company。
SOURCE_PLATFORM_DOMAINS: frozenset[str] = frozenset({
    "ccgp.gov.cn",
    "ccgp.cn",
    "zhaopin.com",
    "51job.com",
    "liepin.com",
    "bosszhipin.com",
    "lagou.com",
    "chinahr.com",
    "gov.cn",
    "gov.uk",
    "gov",
    "samr.gov.cn",
    "sina.com.cn",
    "sohu.com",
    "163.com",
    "qq.com",
    "baidu.com",
    "36kr.com",
    "tmtpost.com",
    "jiemian.com",
    "caixin.com",
    "thepaper.cn",
    "stcn.com",
    "cninfo.com.cn",
    "sse.com.cn",
    "szse.cn",
})


def is_source_platform_domain(host: str | None) -> bool:
    """判断域名是否为数据来源平台（Publisher），不得作为被分析业务主体。"""
    if not host:
        return False
    host = host.lower().rstrip(".")
    parts = host.split(".")
    # 逐级后缀匹配：ccgp.gov.cn / gov.cn / zhaopin.com 均命中
    for i in range(len(parts) - 1):
        suffix = ".".join(parts[i:])
        if suffix in SOURCE_PLATFORM_DOMAINS:
            return True
    return host in SOURCE_PLATFORM_DOMAINS

# 企业验证状态（Company Gate，任务书十九）
COMPANY_VERIFICATION_STATUSES: dict[str, str] = {
    "UNVERIFIED": "仅有名称，未验证",
    "PUBLIC_SOURCE_VERIFIED": "可信官方公开来源已核实（如中标公告）",
    "WEBSITE_VERIFIED": "官网已验证",
}

# 采集战役状态
CAMPAIGN_STATUSES: dict[str, str] = {
    "DRAFT": "草稿",
    "RUNNING": "进行中",
    "PAUSED": "已暂停",
    "COMPLETED": "已完成",
    "CANCELLED": "已取消",
}

# 信号新鲜度分桶（任务书二十四；不能把3年前新闻当"最新机会"）
SIGNAL_FRESHNESS_BUCKETS: dict[str, str] = {
    "FRESH_7D": "0-7天",
    "RECENT_30D": "8-30天",
    "AGING_90D": "31-90天",
    "STALE": "90天以上",
}

# Source Coverage 维度（每家企业覆盖情况，动态聚合回答"数据不足还是确实没Signal"）
SOURCE_COVERAGE_DIMENSIONS: dict[str, str] = {
    "WEBSITE": "官网",
    "CAREERS": "招聘",
    "NEWS": "新闻",
    "PROCUREMENT": "采购/招投标",
    "CONTACT": "联系页/联系人",
}

# T08 阶段质检 Gate：30/100/300 分阶段，每阶段人工质检后才继续（任务书四十二~四十六）
DATA_EXPANSION_STAGES = [30, 100, 300]

# 第一轮数据目标（任务书二）
DATA_GROWTH_TARGETS = {
    "companies": 100,
    "approved_signals": 50,
    "approved_opportunities": 20,
    "validation_ready": 30,
}
