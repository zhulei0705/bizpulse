"""Signal Confidence —— 由代码计算的可解释置信度（T04）。

最终 confidence 不由 LLM 直接输出，而由代码加权：
  来源可信度 30% + Evidence 明确度 30% + 规则匹配度 15% + LLM 一致性 15% + 企业关联可信度 10%
权重写入配置（SIGNAL_CONFIDENCE_WEIGHTS），禁止散落硬编码。
每次计算返回 explanation（Signal 详情可回答「Confidence 为什么是这个分」）。
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings

# 来源等级 → 可信度分（配置化）
SOURCE_GRADE_SCORE = {"A": 100, "B": 80, "C": 60, "D": 40}

COMPANY_RESOLVE_SCORE = {"EXACT": 100, "HIGH_CONFIDENCE": 85, "USER_LINKED": 75, "POSSIBLE": 40, "UNKNOWN": 20, "UNRESOLVED": 20}


@dataclass(frozen=True)
class ConfidenceResult:
    score: int  # 0-100
    explanation: dict  # 各分项明细（可解释）


def _evidence_clarity(evidence_text: str | None, evidence_verified_in_source: bool) -> int:
    """Evidence 明确度：原文可寻 + 长度充分 + 含具体对象/数量词。"""
    if not evidence_text:
        return 20
    score = 55
    if len(evidence_text) >= 30:
        score += 10
    if len(evidence_text) >= 80:
        score += 5
    import re
    if re.search(r"\d+", evidence_text):  # 含数量/金额/日期
        score += 10
    if re.search(r"(招聘|融资|采购|招标|发布|扩张|合作|上线|中标)", evidence_text):
        score += 10
    if evidence_verified_in_source:
        score += 10
    return min(score, 100)


def compute_signal_confidence(
    *,
    source_grade: str | None,
    evidence_text: str | None,
    evidence_in_source: bool,
    rule_confidence: int,
    llm_confidence: int | None,
    company_resolve_status: str | None,
) -> ConfidenceResult:
    w = settings.signal_confidence_weights
    source_score = SOURCE_GRADE_SCORE.get(source_grade or "C", 50)
    clarity = _evidence_clarity(evidence_text, evidence_in_source)
    llm_score = llm_confidence if llm_confidence is not None else (55 if not settings.llm_api_key else 0)
    company_score = COMPANY_RESOLVE_SCORE.get(company_resolve_status or "UNRESOLVED", 30)

    score = round(
        source_score * w["source"] + clarity * w["evidence"] + rule_confidence * w["rule"]
        + llm_score * w["llm"] + company_score * w["company"]
    )
    score = max(0, min(score, 100))
    return ConfidenceResult(score=score, explanation={
        "weights": w,
        "source_score": source_score,
        "evidence_clarity": clarity,
        "rule_confidence": rule_confidence,
        "llm_score": llm_score,
        "company_score": company_score,
    })
