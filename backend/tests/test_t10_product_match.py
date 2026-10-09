"""Synthetic isolated rule fixtures; never business research samples."""
from datetime import datetime

from scripts.t10_a.product_match import match_product, compare
from app.services.procurement_parser import parse_deadline, parse_date_cn


def evidence():
    return dict(text='TEST FIXTURE 6 lasers', quote='6 lasers', start=13, end=21, url='https://example.com/test-fixture')


def req(op='eq', value=6, unit='count'):
    return dict(name='lasers', op=op, value=value, unit=unit, evidence=evidence())


def cap(value=6, unit='count'):
    return dict(value=value, unit=unit, evidence=evidence())


def test_missing_full_requirements_never_match_or_eligible():
    r = match_product([req()], {'lasers': cap()})
    assert r['status'] == 'PARTIAL' and r['eligibility'] == 'UNKNOWN'


def test_complete_technical_match_still_not_eligibility():
    r = match_product([req()], {'lasers': cap()}, requirements_complete=True)
    assert r['status'] == 'MATCH' and r['eligibility'] == 'UNKNOWN'


def test_explicit_failure_overrides_known_and_unknown():
    assert match_product([req(), {**req(), 'name': 'missing'}], {'lasers': cap(2)})['status'] == 'MISMATCH'


def test_absent_evidence_and_wrong_offsets_are_unknown():
    c = cap(); c['evidence']['start'] = 0
    assert compare(req(), c) == 'UNKNOWN'
    assert match_product([req()], {})['status'] == 'UNKNOWN'
    assert match_product([], {})['status'] == 'UNKNOWN'


def test_units_are_not_silently_mixed():
    assert compare(req('ge', 6, 'W'), cap(1000, 'mW')) == 'UNKNOWN'


def test_vector_checks_every_axis():
    assert compare(req('ge_vector', [265, 265, 325], 'mm'), cap([265, 170, 120], 'mm')) == 'UNSATISFIED'
    assert compare(req('ge_vector', [265, 265, 325], 'mm'), cap([350, 400, 400], 'mm')) == 'SATISFIED'


def test_explicit_category_mismatch():
    assert compare(req('eq', 'CERAMIC_SLA', 'category'), cap('METAL_SLM', 'category')) == 'UNSATISFIED'


def test_wavelength_membership_and_invalid_numbers():
    assert compare(req('contains', 1064, 'nm'), cap([1064, 532], 'nm')) == 'SATISFIED'
    assert compare(req('ge', 10, 'W'), cap(float('nan'), 'W')) == 'UNKNOWN'
    assert compare(req('gt', 10, 'W'), cap(10, 'W')) == 'UNSATISFIED'
    assert compare(req(value='UNKNOWN'), cap()) == 'UNKNOWN'


def test_chinese_deadline_and_seconds():
    assert parse_deadline('提交投标文件截止时间：2026年10月10日 09点30分（北京时间）') == datetime(2026, 10, 10, 9, 30)
    assert parse_deadline('谈判响应文件递交截止时间：2026年9月17日 10时00分') == datetime(2026, 9, 17, 10, 0)
    assert parse_date_cn('2026年10月10日 09点30分05秒') == datetime(2026, 10, 10, 9, 30, 5)
    assert parse_deadline('提交投标文件截止时间：2026年9月22日14:00') == datetime(2026, 9, 22, 14, 0)


def test_intention_window_is_not_bid_deadline():
    assert parse_deadline('采购意向公示时间：2026-09-04 ~ 2026-09-09') is None
