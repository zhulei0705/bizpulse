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
