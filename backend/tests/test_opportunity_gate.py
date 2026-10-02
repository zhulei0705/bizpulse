"""EvidenceGate 测试：Evidence Count=0 禁止生成正式机会；<60 封顶 B；单条弱证据封顶 C。"""
import pytest

from app.services.scoring import EvidenceGateError, evidence_gate


def test_zero_evidence_forbidden():
    """关键测试5：Evidence Count = 0 → 正式 Opportunity 生成必须失败。"""
    with pytest.raises(EvidenceGateError):
        evidence_gate(0, 90)


def test_weak_evidence_caps_at_b():
    cap, reason = evidence_gate(2, 45)
    assert cap == "B"
    assert reason == "LOW_EVIDENCE"


def test_boundary_59_caps_b_60_allows():
    cap, _ = evidence_gate(3, 59)
    assert cap == "B"
    cap, _ = evidence_gate(3, 60)
    assert cap == "S"


def test_strong_evidence_no_cap():
    cap, reason = evidence_gate(3, 85)
    assert cap == "S"
    assert reason is None
