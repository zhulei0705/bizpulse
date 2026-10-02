"""AgentFitAnalyzer —— 问题是否适合 AI/Agent 自动化（T05）。

由 Pain 分类 + 需求类信号推断；不因为项目是 AI 产品就全给高分。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.analyzers.opportunity.context import CompanyAnalysisContext

# Pain 分类 → 基础适配分（可解释的先验：重复性/数据化/标准化/频率/可衡量 ROI）
_CATEGORY_FIT = {
    "INVOICE_AUTOMATION": 90,   # 高度重复、标准化、输入输出明确
    "PROCESS_AUTOMATION": 85,
    "FINANCE_EFFICIENCY": 80,
    "DATA_MANAGEMENT": 80,
    "CUSTOMER_ACQUISITION": 75,
    "SALES_EFFICIENCY": 75,
    "LEAD_SHORTAGE": 72,
    "CUSTOMER_SERVICE": 70,
    "COST_REDUCTION": 65,
    "OVERSEAS_EXPANSION": 62,
    "AI_TRANSFORMATION": 60,
    "DIGITAL_TRANSFORMATION": 55,
    "SUPPLIER_MANAGEMENT": 45,
    "PROCUREMENT": 42,
    "RECRUITMENT": 40,
    "COMPLIANCE": 35,
    "OTHER": 40,
}

# 需求类信号 → 明确要买自动化/系统（+分）
_DEMAND_BONUS = {
    "AUTOMATION_DEMAND": 12,
    "AI_DEMAND": 10,
    "CRM_DEMAND": 10,
    "ERP_DEMAND": 10,
    "AI_TRANSFORMATION": 6,
    "DIGITAL_TRANSFORMATION": 4,
}
# 人工操作/效率问题证据 → 重复劳动特征（+分）
_MANUAL_EVIDENCE_BONUS = {"MANUAL_WORK": 8, "EFFICIENCY_PROBLEM": 6}


@dataclass
class AgentFitResult:
    score: int
    reasons: list[str] = field(default_factory=list)


def compute_agent_fit(ctx: CompanyAnalysisContext, pain_category: str | None) -> AgentFitResult:
    reasons: list[str] = []
    category = pain_category or "OTHER"
    score = _CATEGORY_FIT.get(category, 40)
    from app.core.constants import PAIN_CATEGORIES
    reasons.append(f"痛点分类 {PAIN_CATEGORIES.get(category, category)} 的自动化适配先验 {_CATEGORY_FIT.get(category, 40)}")

    types = ctx.signal_types
    for signal_type, bonus in _DEMAND_BONUS.items():
        if signal_type in types:
            score += bonus
            reasons.append(f"存在明确需求信号 {signal_type}（+{bonus}）")
    for signal_type, bonus in _MANUAL_EVIDENCE_BONUS.items():
        if signal_type in types:
            score += bonus
            reasons.append(f"存在重复人工/效率问题证据 {signal_type}（+{bonus}）")

    return AgentFitResult(score=max(0, min(score, 100)), reasons=reasons)
