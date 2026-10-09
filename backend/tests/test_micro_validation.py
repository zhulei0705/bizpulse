"""T09 微型验证 Sprint 服务回归（任务书四/十/十三/十六）。"""
import uuid
from datetime import datetime, timedelta, timezone

from app.db.session import SessionLocal
from app.models.company import Company, CompanyContact
from app.services.micro_validation import (
    RANKING_WEIGHTS,
    contact_role_fit,
    factcheck_claims,
    rank_micro_candidates,
    score_offer,
    screen_candidates,
)


class _C:
    """最小联系人桩（字段与 CompanyContact 对齐）。"""

    def __init__(self, *, contact_type="GENERAL", email=None, phone=None, form=None, name=None):
        self.contact_type = contact_type
        self.email = email
        self.phone = phone
        self.public_profile_url = form
        self.name = name


def test_ranking_weights_match_task_spec():
    """任务书四权重：Actionability30 / Pain20 / Intent15 / Evidence15 / Reach10 / Fit10。"""
    assert RANKING_WEIGHTS == {
        "actionability": 0.30, "pain_strength": 0.20, "intent": 0.15,
        "evidence": 0.15, "reachability": 0.10, "solution_fit": 0.10,
    }
    assert abs(sum(RANKING_WEIGHTS.values()) - 1.0) < 1e-9


def test_ranking_orders_and_is_deterministic():
    cands = [
        {"company_name": "甲", "subs": {"actionability": 100, "pain_strength": 80, "intent": 40,
                                         "evidence": 80, "reachability": 90, "solution_fit": 42}},
        {"company_name": "乙", "subs": {"actionability": 100, "pain_strength": 60, "intent": 0,
                                         "evidence": 70, "reachability": 85, "solution_fit": 42}},
    ]
    ranked = rank_micro_candidates(None, cands)
    assert [r["company_name"] for r in ranked] == ["甲", "乙"]
    assert ranked[0]["rank"] == 1
    assert ranked[0]["ranking_score"] > ranked[1]["ranking_score"]
    assert rank_micro_candidates(None, cands)[0]["ranking_score"] == ranked[0]["ranking_score"]


def test_role_fit_rules():
    """HIGH=具名商务；MEDIUM=商务功能邮箱/有标注；LOW=HR/客服/总机；UNKNOWN=表单/无依据。"""
    assert contact_role_fit(_C(contact_type="SALES", email="zhang@x.com",
                               name="张三")) == "HIGH"
    assert contact_role_fit(_C(contact_type="SALES", email="sales@x.com")) == "MEDIUM"
    assert contact_role_fit(_C(email="bd@x.com")) == "MEDIUM"
    # 来源页功能标注仅提升邮箱（任务书十三：依据公开标注）
    assert contact_role_fit(_C(email="hb3d@hb3dp.com"),
                            label_basis="官网页脚：国内业务邮箱 hb3d@hb3dp.com") == "MEDIUM"
    assert contact_role_fit(_C(phone="400-088-8585"),
                            label_basis="官网页脚：国内业务邮箱") == "LOW"  # 标注不得提升电话
    assert contact_role_fit(_C(contact_type="HR", email="hr@x.com")) == "LOW"
    assert contact_role_fit(_C(email="service@x.com")) == "LOW"
    assert contact_role_fit(_C(form="https://x.com/form")) == "UNKNOWN"
    assert contact_role_fit(_C()) == "UNKNOWN"


def _mk_offer(**over):
    base = {
        "offer_name": "测试Offer", "success_metric": "≥3条被客户确认",
        "pilot_duration_days": 14, "buyer_clarity": "MEDIUM",
        "price_hypothesis": "试点0元；转正假设1500元/月", "value_type": "增加收入",
        "pain_match_score": 85, "urgency_score": 55, "delivery_feasibility_score": 85,
    }
    base.update(over)
    return base


def test_offer_score_dims_and_bounds():
    result = score_offer(_mk_offer())
    assert set(result["dims"].keys()) == {"pain_match", "urgency", "measurability", "delivery_feasibility",
                                           "time_to_value", "buyer_clarity", "revenue_likelihood"}
    assert 0 <= result["total"] <= 100
    # 可衡量性：无 success_metric → 明显降低
    assert score_offer(_mk_offer(success_metric=None))["dims"]["measurability"] < 50
    # 试点时长拉长 → time_to_value 降低
    assert score_offer(_mk_offer(pilot_duration_days=90))["dims"]["time_to_value"] < 50
    # buyer_clarity 映射
    assert score_offer(_mk_offer(buyer_clarity="UNKNOWN"))["dims"]["buyer_clarity"] == 25
    assert score_offer(_mk_offer(buyer_clarity="HIGH"))["dims"]["buyer_clarity"] == 90
    # 价值不在四类之内 → 收费可能性低
    assert score_offer(_mk_offer(value_type="更加智能"))["dims"]["revenue_likelihood"] == 30


def test_factcheck_pass_and_fail():
    """草稿事实性陈述必须映射原文精确子串（空白差异容忍）。"""
    class _Rec:
        pass

    class _DB:
        def get(self, *a, **k):
            r = _Rec()
            r.raw_text = "公告全文：五一职等你来！汉邦激光诚邀英才，共拓金属 3D 打印新征程！ 30 2026 / 04"
            return r

    ok = factcheck_claims(_DB(), [{
        "claim": "官网发布招聘计划",
        "quote": "五一职等你来！汉邦激光诚邀英才，共拓金属 3D 打印新征程",
        "source_record_id": "rec_x",
    }])
    assert ok[0]["pass"] is True
    bad = factcheck_claims(_DB(), [{
        "claim": "贵司上月获得1亿元融资（编造）",
        "quote": "完成1亿元融资",
        "source_record_id": "rec_x",
    }])
    assert bad[0]["pass"] is False


def test_screen_excludes_undated_one_off_events():
    """无日期的一次性事件（如'设立子公司'）不通过新鲜度筛选（任务书三）。"""
    from app.models.signal import Signal
    from app.models.source import Source, SourceRecord

    suffix = uuid.uuid4().hex[:6]
    with SessionLocal() as db:
        c = Company(company_name=f"筛选测试{suffix}", normalized_name=f"筛选测试{suffix}".lower(),
                    organization_type="COMPANY", verification_status="PUBLIC_SOURCE_VERIFIED")
        db.add(c)
        db.flush()
        src = Source(name=f"筛选源{suffix}", source_type="OFFICIAL_WEBSITE",
                     reliability_grade="B", reliability_score=75)
        db.add(src)
        db.flush()
        rec = SourceRecord(source_id=src.id, company_id=c.id,
                           url=f"https://screen{suffix}.example.com/about",
                           title="关于我们", raw_text="公司在某地设立子公司",
                           content_hash=f"h-{suffix}", http_status=200)
        db.add(rec)
        db.flush()
        db.add(Signal(company_id=c.id, source_record_id=rec.id, signal_type="NEW_OFFICE",
                      title="设立子公司", confidence=72, status="APPROVED",
                      published_at=None,
                      payload_json={"actionability": {"status": "ACTIONABLE_NOW"}}))
        db.commit()
        cid = c.id

    with SessionLocal() as db2:
        passed, excluded = screen_candidates(db2)
    ids = {p["company_id"] for p in passed}
    assert cid not in ids
    assert any(e["company"] == f"筛选测试{suffix}" for e in excluded)
