"""T08.0 P0-5 published_at 测试：公告时间解析 + freshness_source 标记。"""
from app.services.procurement_parser import parse_announcement_time, parse_date_cn


def test_chinese_datetime_format():
    """任务书样例：公告时间：2026年09月30日 19:46。"""
    parsed = parse_announcement_time("公告时间：2026年09月30日 19:46")
    assert parsed is not None
    assert (parsed.year, parsed.month, parsed.day, parsed.hour, parsed.minute) == (2026, 9, 30, 19, 46)


def test_dash_and_slash_formats():
    assert parse_announcement_time("发布时间：2026-09-30 19:46") is not None
    assert parse_announcement_time("公告日期：2026/09/30") is not None
    assert parse_date_cn("2026-09-30") is not None


def test_missing_time_returns_none():
    assert parse_announcement_time("正文里没有时间结构字段") is None
    assert parse_announcement_time(None) is None


def test_campaign_marks_freshness_source(client, monkeypatch):
    """端到端：公告时间缺失时 SourceRecord.metadata_json 标记 COLLECTED_AT_FALLBACK。"""
    list_page = """
    <html><body>
      <a href="/cggg/zygg/zbgg/202609/t20261001_333001.htm">中标公告无时间</a>
    </body></html>
    """
    notice_html = """
    <html><head><title>中标公告</title></head><body>
    <p>中标供应商名称：时标测试科技有限公司</p>
    <p>（正文故意不含"公告时间："结构字段）</p>
    </body></html>
    """
    from app.services import extractor
    from app.services.extractor import parse_html

    pages = {
        "http://www.ccgp.gov.cn/cggg/zygg/zbgg/index.htm": list_page,
        "http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20261001_333001.htm": notice_html,
    }
    monkeypatch.setattr(extractor, "fetch_public_page", lambda url: parse_html(
        url, url, 200, "text/html; charset=utf-8", pages.get(url, "<html></html>")) if url in pages else (_ for _ in ()).throw(RuntimeError("404")))

    created = client.post("/api/v1/collection-campaigns", json={
        "name": "时标战役", "seed_urls": ["http://www.ccgp.gov.cn/cggg/zygg/zbgg/index.htm"],
        "target_company_count": 5,
    }).json()["data"]
    run = client.post(f"/api/v1/collection-campaigns/{created['id']}/run", json={"max_notices": 3})
    assert run.status_code == 200
    assert run.json()["data"]["companies_created"] >= 1

    records = client.get("/api/v1/source-records", params={"page_size": 50}).json()["data"]["items"]
    target = next(r for r in records if r["url"].endswith("333001.htm"))
    assert target["metadata_json"].get("freshness_source") == "COLLECTED_AT_FALLBACK"


def test_campaign_uses_announcement_time(client, monkeypatch):
    """公告正文含"公告时间："时 published_at 来自公告时间（非采集时间）。"""
    list_page = """
    <html><body>
      <a href="/cggg/zygg/zbgg/202609/t20261001_444001.htm">中标公告有时间</a>
    </body></html>
    """
    notice_html = """
    <html><head><title>中标公告</title></head><body>
    <p>中标供应商名称：公告时间验证科技有限公司</p>
    <p>公告时间：2026年09月15日 10:30</p>
    </body></html>
    """
    from app.services import extractor
    from app.services.extractor import parse_html

    pages = {
        "http://www.ccgp.gov.cn/cggg/zygg/zbgg/index.htm": list_page,
        "http://www.ccgp.gov.cn/cggg/zygg/zbgg/202609/t20261001_444001.htm": notice_html,
    }
    monkeypatch.setattr(extractor, "fetch_public_page", lambda url: parse_html(
        url, url, 200, "text/html; charset=utf-8", pages[url]) if url in pages else (_ for _ in ()).throw(RuntimeError("404")))

    created = client.post("/api/v1/collection-campaigns", json={
        "name": "公告时间战役", "seed_urls": ["http://www.ccgp.gov.cn/cggg/zygg/zbgg/index.htm"],
        "target_company_count": 5,
    }).json()["data"]
    client.post(f"/api/v1/collection-campaigns/{created['id']}/run", json={"max_notices": 3})

    records = client.get("/api/v1/source-records", params={"page_size": 50}).json()["data"]["items"]
    target = next(r for r in records if r["url"].endswith("444001.htm"))
    assert target["published_at"] and target["published_at"].startswith("2026-09-15")
    assert target["metadata_json"].get("freshness_source") == "ANNOUNCEMENT_TIME"
