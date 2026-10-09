"""T08.2 Enrichment Priority 回归（任务书六）：代码权重计算，不用 LLM；权重合计=1。"""
from app.services.company_coverage import WEIGHTS, enrichment_priority


def test_weights_match_task_spec():
    """权重 = Opportunity Potential 30% / Recent Signal 20% / Coverage Gap 20%
    / Commercial 10% / Website Verified 10% / Reachability 10%。"""
    assert WEIGHTS == {
        "opportunity_potential": 0.30,
        "recent_signal_presence": 0.20,
        "source_coverage_gap": 0.20,
        "commercial_company": 0.10,
        "website_verified": 0.10,
        "current_reachability": 0.10,
    }
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_priority_is_deterministic_code_computed(db_session=None):
    """同样输入 → 同样分数（代码计算，非 LLM 打分）。"""
    audit = {
        "company_id": "cmp_x", "company_name": "优先级测试公司",
        "organization_type": "COMPANY", "website_verified": True,
        "opportunity_count": 1, "actionable_signal_count": 2,
        "coverage_gap": ["contact_covered", "careers_covered"],
        "official_website": "https://p.example.com",
    }

    class _FakeCompany:
        id = "cmp_x"
        company_name = "优先级测试公司"
        verification_status = "WEBSITE_VERIFIED"
        organization_type = "COMPANY"
        website = "https://p.example.com"
        domain = "p.example.com"
        discovery_source_url = "https://p.example.com"
        status = "ACTIVE"

    class _Result:
        def all(self):
            return []

    class _FakeDB:
        """最小桩：recent 信号为 0，channels 为 1（分数由确定性公式决定）。"""

        def scalar(self, *a, **k):
            return 0

        def get(self, *a, **k):
            return _FakeCompany()

        def scalars(self, *a, **k):
            return _Result()

    r1 = enrichment_priority(_FakeDB(), audit)
    r2 = enrichment_priority(_FakeDB(), audit)
    assert r1["priority_score"] == r2["priority_score"]
    # 分项核对（fake：recent=0，channels=0 → reachability=40）
    assert r1["factors"]["opportunity_potential"] == 100
    assert r1["factors"]["source_coverage_gap"] == 50
    assert r1["factors"]["current_reachability"] == 40
    # 权重合成自洽：score = Σ(factor × weight)
    expected = round(sum(r1["factors"][k] * WEIGHTS[k] for k in WEIGHTS))
    assert r1["priority_score"] == expected


def test_more_gap_higher_priority():
    """其他条件相同，缺口多的公司补全优先级更高。"""
    base = {
        "company_id": "cmp_y", "company_name": "缺口对比公司",
        "organization_type": "COMPANY", "website_verified": True,
        "opportunity_count": 0, "actionable_signal_count": 0,
        "coverage_gap": [], "official_website": "https://q.example.com",
    }

    class _FakeCompany:
        id = "cmp_y"
        company_name = "缺口对比公司"
        verification_status = "WEBSITE_VERIFIED"
        organization_type = "COMPANY"
        website = "https://q.example.com"
        domain = "q.example.com"
        discovery_source_url = "https://q.example.com"
        status = "ACTIVE"

    class _Result:
        def all(self):
            return []

    class _FakeDB:
        def scalar(self, *a, **k):
            return 0

        def get(self, *a, **k):
            return _FakeCompany()

        def scalars(self, *a, **k):
            return _Result()

    few = dict(base, coverage_gap=["contact_covered"])
    many = dict(base, coverage_gap=["contact_covered", "careers_covered", "news_covered"])
    assert enrichment_priority(_FakeDB(), many)["priority_score"] > enrichment_priority(_FakeDB(), few)["priority_score"]
