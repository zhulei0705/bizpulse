"""SignalChangeDetector —— 基于 T03 版本系统的变化检测（T04）。

比较同一 canonical_url 相邻两个 SourceRecord 版本：
- 句子级 diff（新增/删除内容）→ 产出变化类候选（NEW_* / REMOVED）；
- 数量正则提取比较（如招聘人数 5→15）→ change_type=INCREASE/DECREASE，
  change_value 必须来自两个真实版本的文本差异，禁止推测。

BizPulse 的核心价值：不是「网页上有什么」，而是「最近发生了什么变化」。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models.source import SourceRecord

# 数量提取：句子中的「招聘 N 名/新增 N 个/N 人」（间隔段排除数字，避免回溯吞位）
_QUANTITY_PATTERNS = (
    re.compile(r"招聘[^0-9]{0,6}(\d+)\s*(名|位|个|人)"),
    re.compile(r"新增[^0-9]{0,6}(\d+)\s*(名|位|个|人|岗位|职位)"),
    re.compile(r"(\d+)\s*(名|位|个|人)[^0-9]{0,6}(岗位|职位|员工)"),
    re.compile(r"扩(招|增)至?\s*(\d+)\s*(人|名)"),
)

# 变化敏感类型：数量变化有商业意义的规则族
_QUANTITY_SENSITIVE_TYPES = {"HIRING", "SALES_HIRING", "AI_HIRING", "TECH_HIRING", "CUSTOMER_SERVICE_HIRING", "FINANCE_HIRING", "PROCUREMENT", "TENDER"}


@dataclass
class ChangeCandidate:
    candidate_type: str
    change_type: str  # NEW / INCREASE / DECREASE / REMOVED
    change_value: str
    evidence_text: str
    start_offset: int
    end_offset: int
    rule_confidence: int
    extra: dict = field(default_factory=dict)


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？；.!?;])\s*|\n+", text or "")
    return [p.strip() for p in parts if len(p.strip()) >= 8]


def _extract_quantities(text: str) -> dict[str, int]:
    """句子 → 数量（每句取首个数量表达）。返回 sentence→number。"""
    result = {}
    for sentence in _split_sentences(text):
        for pattern in _QUANTITY_PATTERNS:
            m = pattern.search(sentence)
            if m:
                digits = next((g for g in m.groups() if g and g.isdigit()), None)
                if digits:
                    result[sentence] = int(digits)
                    break
    return result


def detect_changes(old_record: SourceRecord, new_record: SourceRecord, *, signal_types_in_old: set[str] | None = None) -> list[ChangeCandidate]:
    """比较相邻版本 → 变化候选（NEW/REMOVED/INCREASE/DECREASE）。

    old/new 必须是同一 canonical_url 的相邻版本（version_number 连续），由调用方保证。
    """
    old_text = old_record.raw_text or ""
    new_text = new_record.raw_text or ""
    if not old_text or not new_text:
        return []

    old_sentences = set(_split_sentences(old_text))
    new_sentences = set(_split_sentences(new_text))
    added = [s for s in new_sentences - old_sentences if len(s) >= 10]
    removed = [s for s in old_sentences - new_sentences if len(s) >= 10]

    candidates: list[ChangeCandidate] = []

    # 数量变化：同一敏感规则族的句子在新旧版本数量不同
    old_q = _extract_quantities(old_text)
    new_q = _extract_quantities(new_text)
    matched_old: set[str] = set()
    for new_sentence, new_num in new_q.items():
        best_old_sentence, best_old_num = None, None
        best_sim = 0.0
        for old_sentence, old_num in old_q.items():
            if old_sentence in matched_old or old_num == new_num:
                continue
            sim = _similarity(old_sentence, new_sentence)
            if sim > best_sim:
                best_sim, best_old_sentence, best_old_num = sim, old_sentence, old_num
        if best_old_sentence is not None and best_sim >= 0.55 and best_old_num is not None and new_num != best_old_num:
            matched_old.add(best_old_sentence)
            direction = "INCREASE" if new_num > best_old_num else "DECREASE"
            offset = new_text.find(new_sentence)
            candidates.append(ChangeCandidate(
                candidate_type=_classify_quantity_sentence(new_sentence),
                change_type=direction,
                change_value=f"{best_old_num} → {new_num}",
                evidence_text=new_sentence[:400],
                start_offset=max(offset, 0),
                end_offset=max(offset, 0) + len(new_sentence),
                rule_confidence=82 if direction == "INCREASE" else 70,
                extra={"old_sentence": best_old_sentence[:200], "old_value": best_old_num, "new_value": new_num},
            ))

    # 新增内容 → NEW 类候选（数量敏感类型优先；否则通用 NEW_CONTENT→EXPANSION 保守不计）
    for sentence in added[:5]:
        qtype = _classify_quantity_sentence(sentence)
        if not qtype:
            continue  # 非数量敏感新增句交给常规规则在最新版本上运行
        if any(c.evidence_text[:60] == sentence[:60] for c in candidates):
            continue
        offset = new_text.find(sentence)
        candidates.append(ChangeCandidate(
            candidate_type=qtype,
            change_type="NEW",
            change_value="新增内容",
            evidence_text=sentence[:400],
            start_offset=max(offset, 0),
            end_offset=max(offset, 0) + len(sentence),
            rule_confidence=70,
            extra={},
        ))

    return candidates[:6]


def _classify_quantity_sentence(sentence: str) -> str | None:
    """数量句 → 敏感信号类型（用于变化归类）。"""
    checks = {
        "SALES_HIRING": (r"(海外)?销售|大客户|BD"),
        "AI_HIRING": (r"算法|大模型|AI|人工智能|机器学习"),
        "TECH_HIRING": (r"工程师|开发|架构|测试|运维"),
        "CUSTOMER_SERVICE_HIRING": (r"客服|客户服务|客户成功"),
        "FINANCE_HIRING": (r"财务|会计|审计"),
        "HIRING": (r"招聘|岗位|职位|员工"),
        "PROCUREMENT": (r"采购"),
        "TENDER": (r"招标|中标"),
    }
    for signal_type, pattern in checks.items():
        if re.search(pattern, sentence):
            return signal_type
    return None


def _similarity(a: str, b: str) -> float:
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a[:120], b[:120]).ratio()
