"""T08.0 P0-2 EvidenceQualityGate 测试：导航/footer/热线不得成为 Evidence。"""
from app.services.evidence_quality import evaluate_evidence, extract_valid_evidence, is_platform_boilerplate

# T08 真实采集发现的问题 Evidence（ccgp 页面导航 + 平台介绍 + 热线）
BAD_NAV = "9289 首页 政采法规 购买服务 监督检查 信息公告 国际专栏 当前位置： 首页 » 政采公告 » 中央公告 » 公开"
BAD_INTRO = "财政部唯一指定政府采购信息网络发布媒体 国家级政府采购专业网站 服务热线：400-810-1996 | 服务投诉：010-638192"
GOOD_EVIDENCE = "清华大学67GHz矢量信号发生器采购项目，预算金额128万元，投标截止时间2026年9月20日。"


def test_navigation_evidence_rejected():
    ok, reasons = evaluate_evidence(BAD_NAV)
    assert ok is False
    assert any("导航" in r for r in reasons)


def test_platform_intro_and_hotline_rejected():
    ok, reasons = evaluate_evidence(BAD_INTRO)
    assert ok is False
    assert reasons  # 平台介绍/热线被拒


def test_substantive_evidence_accepted():
    ok, reasons = evaluate_evidence(GOOD_EVIDENCE)
    assert ok is True, reasons


def test_empty_evidence_rejected():
    assert evaluate_evidence(None)[0] is False
    assert evaluate_evidence("   ")[0] is False


def test_extract_valid_evidence_relocates_from_nav():
    """匹配落在导航区时，Evidence 必须被重定位到实质句（原文中真实采购内容）。"""
    text = (
        "9289 首页 政采法规 购买服务 监督检查 信息公告 国际专栏\n"
        "当前位置： 首页 » 政采公告 » 中央公告 » 公开\n"
        "清华大学67GHz矢量信号发生器采购项目公开招标公告，项目预算128万元。\n"
        "财政部唯一指定政府采购信息网络发布媒体 服务热线：400-810-1996\n"
    )
    match_start = text.index("采购")  # 第一个"采购"出现在导航区
    evidence = extract_valid_evidence(text, match_start, match_start + 2)
    assert evidence is not None
    assert "首页 »" not in evidence
    assert "服务热线" not in evidence
    assert "67GHz" in evidence or "预算" in evidence


def test_extract_valid_evidence_none_when_all_noise():
    noise = "首页 信息公告 服务热线 400-810-1996 版权所有 备案号 ICP备"
    assert extract_valid_evidence(noise, 0, 4) is None


def test_platform_boilerplate_shortcut():
    assert is_platform_boilerplate(BAD_NAV) is True
    assert is_platform_boilerplate(GOOD_EVIDENCE) is False
