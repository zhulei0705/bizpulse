"""T08.2 Contact 抽取器回归（任务书十五~十八）：原文公开才收、角色规则、禁猜邮箱。"""
from app.services.contact_extractor import (
    classify_contact_page,
    contact_channel,
    extract_contacts,
    site_domain_of,
)

CONTACT_PAGE_TEXT = """联系我们
销售咨询：sales@hanbang-test.com 400-800-1234
人力资源部：hr@hanbang-test.com 联系人：张工
商务合作：bd@hanbang-test.com
地址：广东省中山市xxx"""


def test_extract_emails_with_roles():
    drafts = extract_contacts(CONTACT_PAGE_TEXT, page_url="https://hanbang-test.com/contact.html",
                              company_domain="hanbang-test.com", page_is_contact=True)
    emails = {d.email: d.contact_type for d in drafts if d.channel == "EMAIL"}
    assert emails["sales@hanbang-test.com"] == "SALES"
    assert emails["hr@hanbang-test.com"] == "HR"
    assert emails["bd@hanbang-test.com"] == "BUSINESS"


def test_extract_phone():
    drafts = extract_contacts(CONTACT_PAGE_TEXT, page_url="https://hanbang-test.com/contact.html",
                              company_domain="hanbang-test.com")
    phones = [_norm_digits(d.phone) for d in drafts if d.channel == "PHONE"]
    assert "4008001234" in phones


def _norm_digits(s):
    return "".join(ch for ch in (s or "") if ch.isdigit())


def test_no_email_no_guess():
    """原文只有姓名和域名 → 不得生成邮箱（任务书十八：禁止 姓名+域名 推断）。"""
    text = "联系人：张三 技术支持由本站提供 域名 example-test-company.com"
    drafts = extract_contacts(text, page_url="https://example-test-company.com/about",
                              company_domain="example-test-company.com")
    assert all(d.channel != "EMAIL" for d in drafts)


def test_third_party_email_rejected():
    """第三方服务/平台域邮箱不得采集。"""
    text = "技术支持 support@sentry.io 销售 sales@hanbang-test.com"
    drafts = extract_contacts(text, page_url="https://hanbang-test.com/contact",
                              company_domain="hanbang-test.com")
    emails = {d.email for d in drafts if d.channel == "EMAIL"}
    assert "support@sentry.io" not in emails
    assert "sales@hanbang-test.com" in emails


def test_company_domain_email_kept_subdomain():
    """子域邮箱（mail.company.com）属于本企业域名 → 保留。"""
    text = "联系：service@mail.hanbang-test.com"
    drafts = extract_contacts(text, page_url="https://hanbang-test.com/contact",
                              company_domain="www.hanbang-test.com")
    assert any(d.email == "service@mail.hanbang-test.com" for d in drafts)


def test_context_role_beats_default():
    """上下文标签（招聘邮箱）优先于账号前缀缺失时的默认值。"""
    text = "招聘邮箱：zhaopin@hanbang-test.com"
    drafts = extract_contacts(text, page_url="https://hanbang-test.com/careers",
                              company_domain="hanbang-test.com")
    assert drafts[0].contact_type == "HR"


def test_form_channel_only_on_contact_page():
    """联系页出现在线留言/表单关键词且无邮箱 → WEBSITE_FORM 渠道。"""
    text = "在线留言 您的需求我们将尽快回复"
    drafts = extract_contacts(text, page_url="https://hanbang-test.com/message.html",
                              company_domain="hanbang-test.com", page_is_contact=True)
    assert any(d.channel == "WEBSITE_FORM" for d in drafts)
    assert drafts[0].form_url == "https://hanbang-test.com/message.html"


def test_form_channel_not_on_regular_page():
    """普通页面导航里的"在线留言"不构成 WEBSITE_FORM（任务书十九）。"""
    text = "首页 产品 新闻 在线留言 联系我们"
    drafts = extract_contacts(text, page_url="https://hanbang-test.com/product/1",
                              company_domain="hanbang-test.com", page_is_contact=False)
    assert all(d.channel != "WEBSITE_FORM" for d in drafts)


def test_no_duplicate_emails():
    text = "联系 info@hanbang-test.com\n再次联系 info@hanbang-test.com"
    drafts = extract_contacts(text, page_url="https://hanbang-test.com/contact",
                              company_domain="hanbang-test.com")
    emails = [d.email for d in drafts if d.channel == "EMAIL"]
    assert len(emails) == 1


def test_contact_channel_helper():
    """渠道由字段推导：EMAIL > PHONE > WEBSITE_FORM（不新增列）。"""
    class Row:
        def __init__(self, email=None, phone=None, form=None):
            self.email, self.phone, self.public_profile_url = email, phone, form

    assert contact_channel(Row(email="a@b.com")) == "EMAIL"
    assert contact_channel(Row(phone="010-123")) == "PHONE"
    assert contact_channel(Row(form="https://x.com/form")) == "WEBSITE_FORM"
    assert contact_channel(Row()) is None


def test_classify_contact_page():
    assert classify_contact_page("https://x.com/contact.html", "联系我们") is True
    assert classify_contact_page("https://x.com/product/1", "产品") is False


def test_site_domain_of():
    assert site_domain_of("https://www.x.com/a") == "www.x.com"
    assert site_domain_of(None) is None
