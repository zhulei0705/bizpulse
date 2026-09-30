"""SignalRuleEngine —— 规则优先的候选事件识别（T04）。

三层规则：
1. keyword/pattern 规则（继承 T02 _RULES 并扩展类型）；
2. 负面规则（NEGATION）：「不计划招聘/暂停招聘/未融资」等否定语境 → 不生成候选；
3. 来源类型规则（SOURCE_TYPE_HINT）：招聘来源优先 HIRING 族、政府来源优先 TENDER/PROCUREMENT。

规则输出 SignalCandidateDraft（含原文 offset），不是最终 Signal —— 关键词命中≠事实。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# 规则定义
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SignalRule:
    signal_type: str
    label: str
    patterns: tuple[str, ...]
    confidence: int
    #: 敏感/复杂类型：即使高分也建议人工审核
    review_always: bool = False


RULES: list[SignalRule] = [
    # ---- 招聘族 ----
    SignalRule("SALES_HIRING", "销售招聘", (r"(招聘|急聘|热招|诚聘)[^0-9]{0,10}(海外销售|销售人员?|销售(经理|总监|工程师|代表)|大客户经理|商务拓展|BD经理)", r"(海外销售|销售总监|销售经理|大客户经理|BD经理)[^0-9]{0,10}(招聘|急聘|热招|若干|\d+\s*(名|位|个))"), 78),
    SignalRule("AI_HIRING", "AI人才招聘", (r"(招聘|急聘|热招|诚聘)[^0-9]{0,8}(AI|人工智能|算法|大模型|机器学习|LLM|NLP)", r"(算法工程师|大模型工程师|AI工程师|机器学习工程师)[^0-9]{0,6}(招聘|急聘)"), 80),
    SignalRule("TECH_HIRING", "技术招聘", (r"(招聘|急聘|热招)[^0-9]{0,8}(软件|后端|前端|开发|架构师|测试|运维|程序员)", r"(后端|前端|全栈|架构师)工程师[^0-9]{0,6}(招聘|急聘)"), 72),
    SignalRule("CUSTOMER_SERVICE_HIRING", "客服招聘", (r"(招聘|急聘)[^0-9]{0,8}(客服|客户服务|客户成功|售后)", r"(客服专员|客户成功经理|售后服务)[^0-9]{0,6}(招聘|急聘)"), 72),
    SignalRule("FINANCE_HIRING", "财务招聘", (r"(招聘|急聘)[^0-9]{0,8}(财务|会计|审计|税务)", r"(财务经理|会计|审计员|税务专员)[^0-9]{0,6}(招聘|急聘)"), 70),
    SignalRule("HIRING", "招聘扩张", (r"(诚聘|急聘|热招|加入我们|join\s+us|we.?re\s+hiring|人才招聘|校园招聘|社会招聘)", r"招聘\d+名", r"新增\d+个?(销售|技术|研发|岗位|职位)"), 62),
    # ---- 融资 ----
    SignalRule("FUNDING", "融资事件", (r"完成.{0,10}(天使轮|Pre-[A-Z]\+?轮|[ABC]\+?轮|战略融资|股权融资)", r"(获得|宣布).{0,12}(融资|投资)", r"(亿元|万美元|千万).{0,4}(融资|投资)"), 85, review_always=True),
    # ---- 扩张族 ----
    SignalRule("OVERSEAS_EXPANSION", "海外扩张", (r"(设立|成立|开设|建立).{0,8}(海外|境外|国外)(公司|办公室|分公司|办事处|子公司|团队|业务)", r"(出海|海外(市场|业务|扩张|布局|团队)|进军(海外|国际|全球)|全球化战略)", r"海外(销售|业务)团队.{0,8}(扩(张|大)|增(加|至))"), 75),
    SignalRule("NEW_FACTORY", "新建工厂", (r"(新建|投建|动工|奠基).{0,8}(工厂|生产基地|产线|制造基地)", r"(工厂|基地|产线).{0,6}(扩建|扩产|投产)"), 78),
    SignalRule("NEW_OFFICE", "新办公室", (r"(新迁|搬迁至|启用新|设立新?).{0,6}(办公室|总部大楼|研发中心|办公区)", r"开设.{0,6}(分公司|办事处|分支机构)"), 66),
    SignalRule("EXPANSION", "业务扩张", (r"(扩(建|大)产能|产能扩张|规模扩大|增资扩产|业务(快速)?扩张|团队扩(张|编))",), 68),
    # ---- 产品/市场 ----
    SignalRule("NEW_PRODUCT", "新产品发布", (r"(发布(全新|新一代|最新)?(产品|版本|平台|系统|服务)|新品上市|product launch|全新上线)", r"(正式推出|重磅推出|首发)"), 74),
    SignalRule("NEW_SERVICE", "新服务上线", (r"(上线|推出).{0,8}(新?(服务|解决方案|SaaS|平台服务))", r"服务正式(上线|发布)"), 68),
    SignalRule("NEW_MARKET", "新市场进入", (r"(进军|切入|进入|开拓).{0,10}(市场|领域|行业|赛道)", r"新市场.{0,6}(开拓|拓展|进入)"), 66),
    # ---- 采购/招标族 ----
    SignalRule("TENDER", "招投标", (r"(招标|询价公告|竞标公告|中标公告|采购公告|招投标)", r"(招标编号|采购项目编号)", r"(中标|赢得招标|获得订单)"), 82),
    SignalRule("PROCUREMENT", "采购需求", (r"(采购(需求|计划|清单|公告)?[,，]?\s*(数量|金额|预算)?)", r"公开采购", r"拟?采购.{0,12}(服务|系统|设备|软件|平台)"), 74),
    SignalRule("SUPPLIER_SEARCH", "供应商招募", (r"(招募|寻找|遴选|征集).{0,8}(供应商|合作伙伴|服务商|渠道商)", r"供应商.{0,6}(招募|报名|入库)"), 70),
    # ---- 系统需求族 ----
    SignalRule("CRM_DEMAND", "CRM需求", (r"((客户管理|CRM|销售管理).{0,14}(系统|软件|平台|工具).{0,10}(需求|招标|采购|选型|建设)?)", r"(CRM系统|客户管理系统)"), 60),
    SignalRule("ERP_DEMAND", "ERP需求", (r"((ERP|进销存|供应链管理|生产管理).{0,10}(系统|软件|平台).{0,10}(需求|招标|采购|选型|建设)?)", r"(ERP系统|进销存系统)", r"ERP.{0,6}(上线|实施|升级)"), 62),
    SignalRule("AI_DEMAND", "AI需求", (r"(采购|选型|引入|招标).{0,12}(AI|人工智能|大模型|智能)(系统|平台|工具|服务|解决方案)", r"(部署|建设).{0,8}(AI|人工智能|智能化)(系统|平台|能力)"), 72),
    SignalRule("AUTOMATION_DEMAND", "自动化需求", (r"(流程自动化|RPA|自动化改造|智能(化)?升级|自动化系统).{0,10}(需求|建设|采购|招标|项目)?", r"(实施|部署|上线).{0,8}自动化"), 70),
    # ---- 转型 ----
    SignalRule("DIGITAL_TRANSFORMATION", "数字化转型", (r"(数字化(转型|升级|改造)|信息化建设|上云|智慧化建设)",), 72),
    SignalRule("AI_TRANSFORMATION", "AI转型", (r"(AI(赋能|转型|落地|升级)|人工智能(应用|落地|转型)|大模型(应用|落地)|成立.{0,6}(AI|人工智能)(部门|团队|实验室|研究院))",), 76),
    # ---- 痛点族 ----
    SignalRule("CUSTOMER_COMPLAINT", "客户投诉", (r"(客户(投诉|抱怨|不满)|投诉量|售后投诉|集中投诉)",), 68),
    SignalRule("COST_PRESSURE", "成本压力", (r"(成本(上涨|上升|压力|管控)|原材料涨价|人力成本(上涨|上升)|降本增效|利润(下滑|收窄))",), 70),
    SignalRule("EFFICIENCY_PROBLEM", "效率问题", (r"(效率(低|低下|不高)|处理耗时|重复劳动|手工操作|耗时.{0,6}小时)",), 68),
    SignalRule("MANUAL_WORK", "人工操作痛点", (r"(人工(审核|录入|填写|统计|核对|对账|排班)|纯手工|手动(录入|登记|统计))",), 66),
    SignalRule("DATA_PROBLEM", "数据问题", (r"(数据(孤岛|分散|不一致|缺失|混乱)|信息孤岛|数据无法(打通|互通))",), 66),
    # ---- 合作/管理 ----
    SignalRule("PARTNERSHIP", "战略合作", (r"(签署|达成|建立).{0,8}(战略合作|合作协议|伙伴关系|联合开发)", r"与.{2,20}(合作|结盟|共建)"), 74, review_always=True),
    SignalRule("STRATEGIC_COOPERATION", "战略合作", (r"(战略(合作|协同|联盟)|产业(协同|合作)|生态合作)",), 72, review_always=True),
    SignalRule("MANAGEMENT_CHANGE", "管理层变动", (r"(任命|聘任|出任).{0,8}(CEO|CTO|CFO|总裁|副总裁|总经理|董事|首席)", r"(高管|管理层).{0,6}(变动|调整|加入|离任)"), 76, review_always=True),
    SignalRule("POLICY_IMPACT", "政策影响", (r"(国家|省市?|部门)?(出台|发布|印发).{0,10}(政策|规划|条例|办法|补贴|扶持)", r"(政策|补贴|税收优惠).{0,6}(利好|支持|影响)"), 68, review_always=True),
]

# 负面语境：命中规则但同时命中否定 → 不生成候选（关键词命中≠事实）
NEGATION_PATTERNS: tuple[re.Pattern, ...] = tuple(re.compile(p, re.I) for p in (
    r"不(计划|打算|考虑|再)?(招聘|扩招|采购|投资|扩张|新建|合作)",
    r"(暂(停|不|缓))(招聘|采购|扩产|扩张|合作)",
    r"(没有|无|未|暂不|不再)[^。；;，,]{0,16}(计划|打算|意向|安排)",
    r"(没有|无|未)(任何)?(招聘|采购|融资|扩张|合作)?(计划|打算|意向|安排)",
    r"(停止|取消|终止|撤回)(招聘|采购|扩产|合作|融资)",
    r"(裁员|缩编|降薪|优化.{0,4}人员)",  # 裁员语境不产出扩张类
    r"(尚未|暂未|并未)(启动|开展|公布|完成).{0,10}(招聘|采购|融资|扩张|合作)",
))

# 行业泛指：主语非该企业（行业/市场/整体），不得生成为该企业 Signal
GENERIC_SUBJECT_PATTERNS: tuple[re.Pattern, ...] = tuple(re.compile(p, re.I) for p in (
    r"(行业|产业|市场|整体|普遍|趋势|全球|全国).{0,10}(普遍|整体|正在|预计|呈现)",
    r"(据|根据).{0,12}(报告|研究|统计|分析)(显示|表明|称)",
    r"(分析师|专家|机构)(预计|认为|预测)",
))

# 来源类型 → 优先信号类型（候选 confidence 加成）
SOURCE_TYPE_HINT: dict[str, tuple[str, ...]] = {
    "JOB": ("HIRING", "SALES_HIRING", "AI_HIRING", "TECH_HIRING", "CUSTOMER_SERVICE_HIRING", "FINANCE_HIRING"),
    "OFFICIAL_WEBSITE": ("OVERSEAS_EXPANSION", "NEW_PRODUCT", "EXPANSION", "FUNDING", "PARTNERSHIP", "NEW_FACTORY"),
    "OFFICIAL_NEWS": ("EXPANSION", "NEW_PRODUCT", "FUNDING", "PARTNERSHIP", "MANAGEMENT_CHANGE"),
    "GOVERNMENT": ("TENDER", "PROCUREMENT", "POLICY_IMPACT"),
    "PROCUREMENT": ("PROCUREMENT", "TENDER", "SUPPLIER_SEARCH"),
    "TENDER": ("TENDER", "PROCUREMENT"),
    "NEWS": ("FUNDING", "EXPANSION", "NEW_PRODUCT", "MANAGEMENT_CHANGE", "OVERSEAS_EXPANSION"),
    "RSS": ("FUNDING", "EXPANSION", "NEW_PRODUCT", "POLICY_IMPACT"),
    "INDUSTRY_ASSOCIATION": ("PARTNERSHIP", "STRATEGIC_COOPERATION", "POLICY_IMPACT"),
}

_EXCERPT_WINDOW = 60
# 泛化 HIRING 被更具体类型覆盖时不重复输出
_HIRING_FAMILY = {"SALES_HIRING", "AI_HIRING", "TECH_HIRING", "CUSTOMER_SERVICE_HIRING", "FINANCE_HIRING"}


@dataclass
class CandidateDraft:
    """规则产出的候选草稿（尚未入库）。"""

    candidate_type: str
    evidence_text: str
    start_offset: int
    end_offset: int
    rule_confidence: int
    review_always: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


def _is_negated(text: str, start: int, end: int) -> bool:
    """命中位置附近的否定语境检查（前后窗口）。"""
    window = text[max(0, start - 40):min(len(text), end + 40)]
    return any(p.search(window) for p in NEGATION_PATTERNS)


def _is_generic_subject(text: str, start: int) -> bool:
    """句首主语为行业/市场泛指（而非该企业）→ 不归属该企业。"""
    window = text[max(0, start - 50):start + 60]
    return any(p.search(window) for p in GENERIC_SUBJECT_PATTERNS)


def run_signal_rules(text: str, source_type: str | None = None, *, max_candidates: int = 10) -> list[CandidateDraft]:
    """对真实正文运行规则引擎 → 候选草稿（去负面/泛指/家族去重，带 offset）。"""
    if not text:
        return []
    haystack = text[:60_000]
    hints = SOURCE_TYPE_HINT.get(source_type or "", ())
    drafts: list[CandidateDraft] = []
    seen_types: set[str] = set()
    for rule in RULES:
        regex = re.compile("|".join(rule.patterns), re.I)
        match = regex.search(haystack)
        if not match:
            continue
        start, end = match.span()
        if _is_negated(haystack, start, end):
            continue  # 否定语境：不生成
        if _is_generic_subject(haystack, start):
            continue  # 行业泛指：不归属该企业
        confidence = rule.confidence + (6 if rule.signal_type in hints else 0)
        excerpt_start = max(0, start - _EXCERPT_WINDOW)
        excerpt_end = min(len(haystack), end + _EXCERPT_WINDOW)
        drafts.append(CandidateDraft(
            candidate_type=rule.signal_type,
            evidence_text=haystack[excerpt_start:excerpt_end].strip(),
            start_offset=excerpt_start,
            end_offset=excerpt_end,
            rule_confidence=min(confidence, 95),
            review_always=rule.review_always,
            extra={"label": rule.label, "review_always": rule.review_always},
        ))
        seen_types.add(rule.signal_type)
    if _HIRING_FAMILY & seen_types:
        drafts = [d for d in drafts if d.candidate_type != "HIRING"]
    return sorted(drafts, key=lambda d: -d.rule_confidence)[:max_candidates]
