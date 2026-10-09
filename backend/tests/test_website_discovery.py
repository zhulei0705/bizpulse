"""T08.2 Website Discovery / 页面分类回归（任务书八/九）。"""
from app.services.company_discovery import SECTION_PATTERNS, classify_page_type, classify_link


def test_section_patterns_cover_task_keywords():
    """任务书八的关键词全部可命中对应维度。"""
    cases = [
        ("https://x.example.com/press", "媒体报道", "NEWS"),
        ("https://x.example.com/media", "媒体中心", "NEWS"),
        ("https://x.example.com/jobs", "JOBS", "CAREERS"),
        ("https://x.example.com/join-us", "加入我们", "CAREERS"),
        ("https://x.example.com/hr", "人才招聘", "CAREERS"),
        ("https://x.example.com/products", "产品中心", "PRODUCTS"),
        ("https://x.example.com/services", "解决方案", "SOLUTIONS"),
        ("https://x.example.com/contact-us", "Contact", "CONTACT"),
        ("https://x.example.com/about", "关于我们", "ABOUT"),
    ]
    for url, text, dim in cases:
        assert classify_link(url, text) == dim, (url, text)


def test_chinese_section_names():
    for url, text, dim in [
        ("https://x.example.com/xwzx", "新闻中心", "NEWS"),
        ("https://x.example.com/zp", "诚聘英才", "CAREERS"),
        ("https://x.example.com/cp", "产品与服务", "PRODUCTS"),
        ("https://x.example.com/fangan", "行业解决方案", "SOLUTIONS"),
        ("https://x.example.com/lxwm", "联系方式", "CONTACT"),
    ]:
        assert classify_link(url, text) == dim, (url, text)


def test_classify_page_type_basic():
    assert classify_page_type("https://x.example.com/", "首页") in {"OTHER", "HOME"}
    assert classify_page_type("https://x.example.com/news/20261001.html", "公司新闻") == "NEWS_INDEX"
    assert classify_page_type("https://x.example.com/news/2026/10/01/detail123.html", None) == "NEWS_ARTICLE"
    assert classify_page_type("https://x.example.com/job/detail.html", "职位详情") == "JOB_DETAIL"
    assert classify_page_type("https://x.example.com/contact", "联系我们") == "CONTACT"
    assert classify_page_type("https://x.example.com/solution/1", "解决方案") == "SOLUTION"
    assert classify_page_type("https://x.example.com/about", "公司简介") == "ABOUT"


def test_classify_page_type_job_list_by_text():
    """无栏目关键词但正文为岗位列表 → CAREERS。"""
    text = "\n".join(f"招聘岗位{i}：销售经理" for i in range(5))
    assert classify_page_type("https://x.example.com/list123", None, text) == "CAREERS"


def test_contact_dimension_priority():
    """联系页关键词优先于新闻词（URL 同时含两者时归 CONTACT）。"""
    assert classify_page_type("https://x.example.com/contact/news", "联系") == "CONTACT"
