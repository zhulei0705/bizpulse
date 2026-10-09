"""IntentAnalyzer —— 购买意图评分（T05）。

购买意图不能由一句话直接判断：由代码按配置权重计算
  直接购买信号 40% + 问题证据 20% + 近期变化 15% + 多信号支持 15% + 来源质量 10%。
每个分项给出真实依据（reasons），0-100。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.analyzers.opportunity.context import CompanyAnalysisContext
from app.core.config import settings
from app.core.constants import DIRECT_PURCHASE_SIGNAL_TYPES

# 直接购买信号的强度（TENDER 有截止期最紧急）
_DIRECT_STRENGTH = {"TENDER": 100, "PROCUREMENT": 85, "SUPPLIER_SEARCH": 78,
                    "CRM_DEMAND": 70, "ERP_DEMAND": 70, "AI_DEMAND": 70, "AUTOMATION_DEMAND": 70}

# 问题证据类信号（企业明确提出业务问题）
_PROBLEM_SIGNALS = {"CUSTOMER_COMPLAINT", "EFFICIENCY_PROBLEM", "MANUAL_WORK", "DATA_PROBLEM", "COST_PRESSURE"}


@dataclass
class AnalyzerResult:
    score: int
    reasons: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)


def compute_intent(ctx: CompanyAnalysisContext, *, now: datetime | None = None) -> AnalyzerResult:
    now = now or datetime.now(timezone.utc)
    w = settings.intent_score_weights
    reasons: list[str] = []
    types = ctx.signal_types

    # 1) 直接购买信号（40%）
    direct = [t for t in types if t in DIRECT_PURCHASE_SIGNAL_TYPES]
    if direct:
        direct_score = max(_DIRECT_STRENGTH.get(t, 60) for t in direct)
        reasons.append(f"存在直接购买信号：{'、'.join(direct)}")
    else:
        direct_score = 0
        reasons.append("未发现公开采购/招标/系统选型等直接购买信号")
    # T08.1：CONTRACT_AWARD 是"合同已授予"的既成事实，不是"正在寻找供应商"，
    # 绝不能因中标公告把购买意图抬成高意向（AWARDED ≠ active purchase intent）。
    if "CONTRACT_AWARD" in types:
        reasons.append("CONTRACT_AWARD 为已完成的中标事实，不计入购买意图（仅可作为供应商能力/历史采购证据）")

    # 2) 问题证据（20%）
    problems = [t for t in types if t in _PROBLEM_SIGNALS]
    problem_score = min(100, 45 + 20 * (len(problems) - 1)) if problems else 0
    if problems:
        reasons.append(f"存在问题类证据：{'、'.join(problems)}")
    else:
        reasons.append("未发现企业明确提出业务问题的信号")

    # 3) 近期变化（15%）：变化类信号或 30 天内的新信号
    change_signals = [s for s in ctx.signals if s.signal.change_type]
    recent = [s for s in ctx.signals if s.newest_evidence_at and (now - _ensure_utc(s.newest_evidence_at)).days <= 30]
    if change_signals:
        recent_score = 90
        reasons.append(f"检测到真实版本变化信号 {len(change_signals)} 条（{change_signals[0].signal.change_type} {change_signals[0].signal.change_value or ''}）")
    elif recent:
        recent_score = 70
        reasons.append(f"最近 30 天内新增 {len(recent)} 条已批准信号")
    else:
        recent_score = 25
        reasons.append("信号较旧（超过 30 天无新证据）")

    # 4) 多信号支持（15%）：不同类型信号数量
    type_count = len(types)
    multi_score = min(100, 30 + type_count * 18) if type_count >= 2 else (20 if type_count == 1 else 0)
    if type_count >= 2:
        reasons.append(f"共 {type_count} 类不同信号相互印证")
    else:
        reasons.append("仅单一类型信号支持")

    # 5) 来源质量（10%）
    grade_score = {"A": 100, "B": 80, "C": 60, "D": 40}.get(ctx.best_source_grade, 40)
    reasons.append(f"最高来源等级 {ctx.best_source_grade}")

    score = round(
        direct_score * w["direct_purchase"]
        + problem_score * w["problem_evidence"]
        + recent_score * w["recent_change"]
        + multi_score * w["multi_signal"]
        + grade_score * w["source_quality"]
    )
    return AnalyzerResult(score=max(0, min(score, 100)), reasons=reasons, extra={
        "direct_purchase": direct_score, "problem_evidence": problem_score,
        "recent_change": recent_score, "multi_signal": multi_score,
        "source_quality": grade_score,
    })


def _ensure_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
