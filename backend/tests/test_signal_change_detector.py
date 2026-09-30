"""SignalChangeDetector 测试：版本变化 → 变化类候选（数量变化/新增内容）。"""
import uuid

from app.analyzers.change_detector import detect_changes


class FakeRecord:
    def __init__(self, raw_text: str, version: int):
        self.raw_text = raw_text
        self.version_number = version
        self.id = f"rec_fake_{uuid.uuid4().hex[:8]}"


def test_hiring_increase_detected():
    old = FakeRecord("公司介绍。目前招聘海外销售人员5名，办公地点在上海。", 1)
    new = FakeRecord("公司介绍。目前招聘海外销售人员15名，办公地点在上海。", 2)
    changes = detect_changes(old, new)
    assert changes
    inc = next(c for c in changes if c.change_type == "INCREASE")
    assert inc.candidate_type == "SALES_HIRING"
    assert inc.change_value == "5 → 15"  # 来自真实版本文本
    assert "15" in inc.evidence_text


def test_decrease_detected():
    old = FakeRecord("因业务调整，招聘算法工程师20名。", 1)
    new = FakeRecord("因业务调整，招聘算法工程师8名。", 2)
    changes = detect_changes(old, new)
    dec = next((c for c in changes if c.change_type == "DECREASE"), None)
    assert dec is not None
    assert dec.change_value == "20 → 8"


def test_no_change_no_candidates():
    text = "公司简介与业务说明保持不变。招聘海外销售人员5名。"
    changes = detect_changes(FakeRecord(text, 1), FakeRecord(text + " ", 2))
    quantity_changes = [c for c in changes if c.change_type in {"INCREASE", "DECREASE"}]
    assert quantity_changes == []


def test_new_quantity_sentence_generates_new():
    old = FakeRecord("公司主页：介绍产品与服务。", 1)
    new = FakeRecord("公司主页：介绍产品与服务。现为海外扩张，新增销售岗位10个。", 2)
    changes = detect_changes(old, new)
    new_ones = [c for c in changes if c.change_type == "NEW"]
    assert new_ones
    assert any(c.candidate_type in {"SALES_HIRING", "HIRING"} for c in new_ones)


def test_empty_text_returns_empty():
    assert detect_changes(FakeRecord("", 1), FakeRecord("有内容", 2)) == []


def test_change_value_never_invented():
    """change_value 必须来自两个版本的数字差异，不得凭空出现。"""
    old = FakeRecord("招聘销售人员5名。", 1)
    new = FakeRecord("招聘销售人员7名。", 2)
    changes = detect_changes(old, new)
    for c in changes:
        if c.change_type in {"INCREASE", "DECREASE"}:
            assert c.change_value in {"5 → 7"}
            assert c.extra.get("old_value") == 5 and c.extra.get("new_value") == 7
