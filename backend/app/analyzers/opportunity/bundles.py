"""SignalBundleAnalyzer —— 多信号组合（T05）。

规则表驱动、明确可解释：哪些已批准 Signal 类型在时间窗口内组合，
指向哪些 Pain 分类、组合置信度如何构成。组合只产生"候选机会"线索，
仍需 ScoreEngine + EvidenceGate + 人工审核 —— 不是最终结论。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.analyzers.opportunity.context import CompanyAnalysisContext
from app.core.config import settings
from app.core.constants import SIGNAL_BUNDLE_TYPES


def _is_current_signal(signal) -> bool:
    """T08.2 机会生成门（任务书二十六/二十三）：HISTORICAL_SIGNAL / NOT_ACTIONABLE
    的信号（如已中标 CONTRACT_AWARD）不得作为组合的核心或辅助触发；
    只能作为背景证据（证据分仍按真实证据计算）。"""
    from app.services.actionability import compute_actionability_by_rules

    status = compute_actionability_by_rules(signal)
    return status not in {"HISTORICAL_SIGNAL", "NOT_ACTIONABLE"}


@dataclass
class BundleDraft:
    bundle_type: str
    signal_ids: list[str] = field(default_factory=list)
    signal_types: list[str] = field(default_factory=list)
    pain_categories: list[str] = field(default_factory=list)
    confidence: int = 0
    explanation: dict = field(default_factory=dict)
    first_signal_at: object | None = None
    last_signal_at: object | None = None


# 组合规则表：bundle_type → (任一核心类型, 任一辅助类型, 指向 Pain 分类, 基础置信度, 组合加成)
# 核心类型决定组合是否成立（必须至少命中 1 个）；辅助类型命中越多置信度越高。
BUNDLE_RULES: dict[str, dict] = {
    "OVERSEAS_GROWTH": {
        "label": "海外扩张组合",
        "core": {"OVERSEAS_EXPANSION", "NEW_MARKET"},
        "support": {"SALES_HIRING", "HIRING", "FUNDING", "NEW_OFFICE", "EXPANSION"},
        "pains": ["OVERSEAS_EXPANSION", "CUSTOMER_ACQUISITION"],
        "base": 62,
        "support_bonus": 12,
        "rationale": "海外/新市场动作 + 销售资源投入，共同指向海外客户开发需求",
    },
    "AI_ADOPTION": {
        "label": "AI 采用组合",
        "core": {"AI_TRANSFORMATION", "AI_DEMAND", "AI_HIRING"},
        "support": {"DIGITAL_TRANSFORMATION", "AUTOMATION_DEMAND", "TECH_HIRING", "FUNDING"},
        "pains": ["AI_TRANSFORMATION", "PROCESS_AUTOMATION"],
        "base": 60,
        "support_bonus": 12,
        "rationale": "AI 转型动作与 AI 人才/需求信号互相印证，指向 AI 落地需求",
    },
    "PURCHASE_READY": {
        "label": "采购就绪组合",
        "core": {"PROCUREMENT", "TENDER", "SUPPLIER_SEARCH"},
        "support": {"CRM_DEMAND", "ERP_DEMAND", "AI_DEMAND", "AUTOMATION_DEMAND"},
        "pains": ["PROCUREMENT", "PROCESS_AUTOMATION"],
        "base": 80,
        "support_bonus": 8,
        "rationale": "公开采购/招标/寻源是直接购买信号，强购买意图",
    },
    "SALES_SCALE_UP": {
        "label": "销售扩张组合",
        "core": {"SALES_HIRING"},
        "support": {"FUNDING", "EXPANSION", "NEW_MARKET", "NEW_PRODUCT", "HIRING"},
        "pains": ["CUSTOMER_ACQUISITION", "SALES_EFFICIENCY"],
        "base": 55,
        "support_bonus": 13,
        "rationale": "销售团队扩张 + 业务增长动作，指向客户获取与销售效率压力",
    },
    "SERVICE_STRAIN": {
        "label": "客服压力组合",
        "core": {"CUSTOMER_COMPLAINT", "CUSTOMER_SERVICE_HIRING"},
        "support": {"EFFICIENCY_PROBLEM", "MANUAL_WORK", "EXPANSION"},
        "pains": ["CUSTOMER_SERVICE", "PROCESS_AUTOMATION"],
        "base": 58,
        "support_bonus": 13,
        "rationale": "投诉/客服扩编 + 效率问题，指向客服体系压力",
    },
    "COST_OPTIMIZATION": {
        "label": "降本增效组合",
        "core": {"COST_PRESSURE"},
        "support": {"EFFICIENCY_PROBLEM", "MANUAL_WORK", "DATA_PROBLEM"},
        "pains": ["COST_REDUCTION", "PROCESS_AUTOMATION"],
        "base": 60,
        "support_bonus": 14,
        "rationale": "成本压力 + 人工/效率问题，指向降本与自动化需求",
    },
    "FINANCE_AUTOMATION": {
        "label": "财务自动化组合",
        "core": {"FINANCE_HIRING"},
        "support": {"EFFICIENCY_PROBLEM", "MANUAL_WORK", "DIGITAL_TRANSFORMATION", "DATA_PROBLEM"},
        "pains": ["FINANCE_EFFICIENCY", "INVOICE_AUTOMATION", "PROCESS_AUTOMATION"],
        "base": 52,
        "support_bonus": 14,
        "rationale": "财务扩编 + 人工处理/效率问题，指向财务流程自动化空间",
    },
    "DATA_GOV": {
        "label": "数据治理组合",
        "core": {"DATA_PROBLEM"},
        "support": {"DIGITAL_TRANSFORMATION", "AI_TRANSFORMATION", "ERP_DEMAND", "TECH_HIRING"},
        "pains": ["DATA_MANAGEMENT", "DIGITAL_TRANSFORMATION"],
        "base": 58,
        "support_bonus": 14,
        "rationale": "数据问题 + 数字化动作，指向数据治理/系统集成需求",
    },
}

DENSITY_BONUS_7D = 8   # 7 天内多条信号：事件正在发生
DENSITY_BONUS_30D = 6  # 30 天窗口内信号较密
SINGLE_SIGNAL_FLOOR = 45  # 单信号无组合时的组合置信度下限


def build_signal_bundles(ctx: CompanyAnalysisContext, *, window_days: int | None = None) -> list[BundleDraft]:
    """从已批准 Signal 构建组合（含单信号候选：core 命中 1 个即成立）。"""
    window = window_days or settings.opportunity_dedup_window_days
    drafts: list[BundleDraft] = []

    for bundle_type, rule in BUNDLE_RULES.items():
        core_hits = [s for s in ctx.signals if s.signal.signal_type in rule["core"] and _is_current_signal(s.signal)]
        if not core_hits:
            continue
        support_hits = [s for s in ctx.signals if s.signal.signal_type in rule["support"] and _is_current_signal(s.signal)]
        members = core_hits + [s for s in support_hits if s not in core_hits]

        types = sorted({s.signal.signal_type for s in members})
        ids = [s.signal.id for s in members]
        times = [s.newest_evidence_at for s in members if s.newest_evidence_at]
        confidence = rule["base"] + min(len(support_hits), 3) * rule["support_bonus"]
        if ctx.signal_count_7d >= 2:
            confidence += DENSITY_BONUS_7D
        elif ctx.signal_count_30d >= 3:
            confidence += DENSITY_BONUS_30D
        confidence = min(confidence, 95)

        drafts.append(BundleDraft(
            bundle_type=bundle_type,
            signal_ids=ids,
            signal_types=types,
            pain_categories=list(rule["pains"]),
            confidence=confidence,
            explanation={
                "rule": rule["label"],
                "rationale": rule["rationale"],
                "core_types": sorted({s.signal.signal_type for s in core_hits}),
                "support_types": sorted({s.signal.signal_type for s in support_hits}),
                "support_count": len(support_hits),
                "signal_count_7d": ctx.signal_count_7d,
                "signal_count_30d": ctx.signal_count_30d,
                "signal_count_90d": ctx.signal_count_90d,
                "time_window_days": window,
                "base_confidence": rule["base"],
            },
            first_signal_at=min(times) if times else None,
            last_signal_at=max(times) if times else None,
        ))

    # 组合置信度排序；无任何组合命中时返回空（调用方可用单信号规则兜底）
    drafts.sort(key=lambda d: d.confidence, reverse=True)
    return drafts


def bundle_type_label(bundle_type: str) -> str:
    return SIGNAL_BUNDLE_TYPES.get(bundle_type, bundle_type)
