"""Small research rule evaluator. Evidence-backed curation is not customer validation.

Comparisons apply to one documented product configuration, never a whole supplier.
No database access, outreach, or inferred eligibility.
"""
from __future__ import annotations

import math


def valid_evidence(evidence: dict | None) -> bool:
    if not evidence:
        return False
    text, quote = evidence.get('text', ''), evidence.get('quote', '')
    start, end = evidence.get('start'), evidence.get('end')
    return bool(quote and isinstance(start, int) and isinstance(end, int)
                and 0 <= start < end <= len(text) and text[start:end] == quote
                and evidence.get('url'))


def compare(requirement: dict, capability: dict | None) -> str:
    if not valid_evidence(requirement.get('evidence')):
        return 'UNKNOWN'
    if not capability or not valid_evidence(capability.get('evidence')):
        return 'UNKNOWN'
    if requirement.get('unit') != capability.get('unit'):
        return 'UNKNOWN'  # no silent unit conversion
    actual, target, op = capability.get('value'), requirement.get('value'), requirement.get('op')
    if actual is None or target is None or actual == 'UNKNOWN' or target == 'UNKNOWN':
        return 'UNKNOWN'
    try:
        if op == 'eq':
            return 'SATISFIED' if actual == target else 'UNSATISFIED'
        if op == 'contains':
            if not isinstance(actual, (list, tuple, set)):
                return 'UNKNOWN'
            return 'SATISFIED' if target in actual else 'UNSATISFIED'
        if op == 'ge_vector':
            if len(actual) != len(target) or not all(math.isfinite(float(v)) for v in [*actual, *target]):
                return 'UNKNOWN'
            return 'SATISFIED' if all(a >= b for a, b in zip(actual, target)) else 'UNSATISFIED'
        if op in {'ge', 'gt'}:
            if not all(math.isfinite(float(v)) for v in [actual, target]):
                return 'UNKNOWN'
            ok = actual >= target if op == 'ge' else actual > target
            return 'SATISFIED' if ok else 'UNSATISFIED'
    except (TypeError, ValueError, OverflowError):
        pass
    return 'UNKNOWN'


def match_product(requirements: list[dict], capabilities: dict, *, requirements_complete=False) -> dict:
    checks = [{**r, 'result': compare(r, capabilities.get(r['name'])),
               'capability': capabilities.get(r['name'])} for r in requirements]
    states = [c['result'] for c in checks]
    if 'UNSATISFIED' in states:
        status = 'MISMATCH'
    elif states and all(s == 'SATISFIED' for s in states) and requirements_complete:
        status = 'MATCH'
    elif 'SATISFIED' in states:
        status = 'PARTIAL'
    else:
        status = 'UNKNOWN'
    return dict(status=status, checks=checks, requirements_complete=requirements_complete,
                eligibility='UNKNOWN', review_status='HUMAN_REVIEW_PENDING')
