"""T06 联系人测试：真实来源规则（关键测试 6：无来源不能 VERIFIED_PUBLIC）。"""
from tests.helpers_t06 import make_company, make_contact, uniq


def test_contact_verified_public_requires_source(client):
    company = make_company(client)
    bad = client.post(f"/api/v1/companies/{company['id']}/contacts", json={
        "name": "王总", "email": "wang@t06.example.com", "verification_status": "VERIFIED_PUBLIC",
    })
    assert bad.status_code == 422
    assert "来源" in bad.json()["detail"]


def test_contact_verified_public_with_url_ok(client):
    company = make_company(client)
    ok = client.post(f"/api/v1/companies/{company['id']}/contacts", json={
        "name": "李经理", "email": "li@t06.example.com",
        "verification_status": "VERIFIED_PUBLIC",
        "source_url": "https://t06.example.com/team/li",
    })
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    assert data["verification_status"] == "VERIFIED_PUBLIC"
    assert data["verified_public"] is True


def test_contact_user_provided_ok(client):
    company = make_company(client)
    ok = client.post(f"/api/v1/companies/{company['id']}/contacts", json={
        "name": "用户录入联系人", "phone": "13800000000",
        "verification_status": "USER_PROVIDED", "source_type": "USER_INPUT",
    })
    assert ok.status_code == 200
    assert ok.json()["data"]["verification_status"] == "USER_PROVIDED"


def test_contact_default_unverified(client):
    company = make_company(client)
    ok = client.post(f"/api/v1/companies/{company['id']}/contacts", json={"name": f"未核实{uniq()}"})
    assert ok.status_code == 200
    assert ok.json()["data"]["verification_status"] == "UNVERIFIED"
    assert ok.json()["data"]["verified_public"] is False


def test_contact_patch_and_verification_downgrade(client):
    company = make_company(client)
    contact = make_contact(client, company["id"], verified=True)
    # 移除来源时不能保持 VERIFIED_PUBLIC
    resp = client.patch(f"/api/v1/contacts/{contact['id']}", json={"verification_status": "STALE"})
    assert resp.status_code == 200
    assert resp.json()["data"]["verification_status"] == "STALE"
    assert resp.json()["data"]["verified_public"] is False

    # 来源已被移除（source_url=None）时改回 VERIFIED_PUBLIC → 422
    invalid = client.patch(f"/api/v1/contacts/{contact['id']}", json={
        "verification_status": "VERIFIED_PUBLIC", "source_url": None,
    })
    assert invalid.status_code == 422

    # 补回真实来源 → 允许
    ok = client.patch(f"/api/v1/contacts/{contact['id']}", json={
        "verification_status": "VERIFIED_PUBLIC", "source_url": "https://t06.example.com/about/team",
    })
    assert ok.status_code == 200
    assert ok.json()["data"]["verified_public"] is True


def test_contact_legacy_verified_flag_maps(client):
    company = make_company(client)
    resp = client.post(f"/api/v1/companies/{company['id']}/contacts", json={
        "name": "旧字段联系人", "verified_public": True,
        "source_url": "https://t06.example.com/about",
    })
    assert resp.status_code == 200
    assert resp.json()["data"]["verification_status"] == "VERIFIED_PUBLIC"
