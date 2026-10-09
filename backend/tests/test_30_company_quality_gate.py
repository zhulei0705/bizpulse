"""T08.1 30家企业扩量质量 Gate 回归（任务书十四/十八/二十四/二十九）。"""
import uuid

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.company import Company
from app.services.expansion_gate import expansion_quality_gate


def _isolate_pool():
    """测试库跨用例共享：把既有企业移出 ACTIVE 池，保证 Gate 断言只看本用例夹具。"""
    with SessionLocal() as db:
        for c in db.scalars(select(Company)).all():
            c.status = "ARCHIVED"
        db.commit()


def _add_company(db, *, name_suffix: str, org_type: str = "COMPANY",
                 verification: str = "PUBLIC_SOURCE_VERIFIED", status: str = "ACTIVE") -> Company:
    c = Company(
        company_name=f"Gate测试企业{name_suffix}{uuid.uuid4().hex[:4]}",
        normalized_name=f"gate测试企业{name_suffix}{uuid.uuid4().hex[:4]}".lower(),
        organization_type=org_type,
        verification_status=verification,
        status=status,
        website=f"https://{name_suffix}.example.com" if verification == "WEBSITE_VERIFIED" else None,
        domain=f"{name_suffix}.example.com" if verification == "WEBSITE_VERIFIED" else None,
    )
    db.add(c)
    return c


def test_gate_fails_when_pool_below_target():
    """真实主体不足目标数 → Gate 不通过。"""
    _isolate_pool()
    with SessionLocal() as db:
        _add_company(db, name_suffix="few")
        db.commit()
        report = expansion_quality_gate(db, target_count=30)
    assert report["gates"]["real_entities_at_least_target"] is False
    assert report["passed"] is False


def test_gate_fails_when_commercial_ratio_below_70pct():
    """商业企业占比 <70%（政府/高校凑数）→ Gate 不通过。"""
    _isolate_pool()
    with SessionLocal() as db:
        _add_company(db, name_suffix="c1", org_type="COMPANY")
        _add_company(db, name_suffix="g1", org_type="GOVERNMENT")
        _add_company(db, name_suffix="u1", org_type="UNIVERSITY")
        db.commit()
        report = expansion_quality_gate(db, target_count=1)
    assert report["real_entity_count"] == 3
    assert report["commercial_company_count"] == 1
    assert abs(report["commercial_ratio"] - 1 / 3) < 0.001
    assert report["gates"]["commercial_ratio_at_least_70pct"] is False


def test_gate_counts_only_verified_entities():
    """UNVERIFIED（仅名称/遗留）不计入真实主体；SOURCE_PLATFORM 不计入业务池。"""
    _isolate_pool()
    with SessionLocal() as db:
        _add_company(db, name_suffix="real1", verification="PUBLIC_SOURCE_VERIFIED")
        _add_company(db, name_suffix="web1", verification="WEBSITE_VERIFIED")
        _add_company(db, name_suffix="ghost", verification="UNVERIFIED")
        _add_company(db, name_suffix="platform", org_type="SOURCE_PLATFORM", verification="UNVERIFIED")
        db.commit()
        report = expansion_quality_gate(db, target_count=1)
    assert report["real_entity_count"] == 2
    assert report["company_count"] == 4
    assert report["source_platform_company_count"] == 1


def test_gate_fails_with_single_source_type():
    """真实主体只挂 1 类来源 → 不满足多样性要求（≥3 类）。

    注意：不用 MANUAL_ENTRY（那会占用 test_signals 依赖的"人工录入证据"自动来源），
    用行业目录类型模拟单来源池；记录必须挂接到真实主体（Gate 只统计真实主体的来源）。
    """
    _isolate_pool()
    with SessionLocal() as db:
        from app.models.source import Source, SourceRecord

        c = _add_company(db, name_suffix="only1")
        src = Source(name="唯一来源", source_type="INDUSTRY_DIRECTORY", reliability_grade="A", reliability_score=95)
        db.add(src)
        db.flush()
        db.add(SourceRecord(source_id=src.id, company_id=c.id, url="https://only.example.com/1",
                            title="t", raw_text="r", content_hash=f"h-{uuid.uuid4().hex[:8]}", http_status=200))
        db.commit()
        report = expansion_quality_gate(db, target_count=1, min_source_types=3)
    assert report["source_type_count"] == 1
    assert report["gates"]["source_types_at_least_3"] is False


def test_gate_passes_with_quality_pool():
    """达标池：30家真实主体、≥70% COMPANY、≥3类来源、无平台主体 → Gate 通过。"""
    _isolate_pool()
    with SessionLocal() as db:
        # 21 家 COMPANY + 5 家 UNIVERSITY + 4 家 RESEARCH_INSTITUTE = 30（70% COMPANY）
        for i in range(21):
            _add_company(db, name_suffix=f"p{i}", org_type="COMPANY")
        for i in range(5):
            _add_company(db, name_suffix=f"u{i}", org_type="UNIVERSITY")
        for i in range(4):
            _add_company(db, name_suffix=f"r{i}", org_type="RESEARCH_INSTITUTE")
        # 三类真实来源（各带 1 条 200 记录，挂接到真实主体）
        from app.models.source import Source, SourceRecord

        db.flush()  # SessionLocal autoflush=False，先落盘再查询
        pool_companies = db.scalars(select(Company).where(Company.status == "ACTIVE")).all()
        for idx, st in enumerate(("GOVERNMENT_PROCUREMENT", "OFFICIAL_WEBSITE", "OFFICIAL_CAREERS")):
            src = Source(name=f"达标源{st}{uuid.uuid4().hex[:4]}", source_type=st,
                         reliability_grade="A", reliability_score=95)
            db.add(src)
            db.flush()
            db.add(SourceRecord(source_id=src.id,
                                company_id=pool_companies[idx % len(pool_companies)].id,
                                url=f"https://{st.lower()}.example.com/1",
                                title="t", raw_text="r", content_hash=f"h-{st}-{uuid.uuid4().hex[:8]}",
                                http_status=200))
        db.commit()
        report = expansion_quality_gate(db, target_count=30)
    assert report["real_entity_count"] == 30
    assert report["commercial_ratio"] == 0.7
    assert report["source_type_count"] >= 3
    assert report["gates"]["real_entities_at_least_target"] is True
    assert report["gates"]["commercial_ratio_at_least_70pct"] is True
    assert report["gates"]["source_types_at_least_3"] is True
    assert report["gates"]["no_source_platform_company_active"] is True
    assert report["gates"]["no_severe_signal_misjudgement"] is True
    assert report["gates"]["evidence_pass_rate_at_least_95pct"] is True  # 无证据信号时按 1.0 计
    assert report["passed"] is True


def test_gate_metrics_include_report_fields():
    """报告字段齐全（任务书二十九要求的指标）。"""
    _isolate_pool()
    with SessionLocal() as db:
        _add_company(db, name_suffix="m1")
        db.commit()
        report = expansion_quality_gate(db, target_count=30)
    for key in (
        "company_count", "real_entity_count", "commercial_company_count", "commercial_ratio",
        "organization_type_distribution", "source_type_distribution", "source_type_count",
        "official_website_coverage", "signal_coverage", "approved_signal_count", "review_signal_count",
        "opportunity_count", "approved_opportunity_count", "validation_ready_count", "contact_ready_count",
        "duplicate_rate", "parse_failure_rate", "evidence_pass_rate", "source_url_valid_rate",
    ):
        assert key in report, key
