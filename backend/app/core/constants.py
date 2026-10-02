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
