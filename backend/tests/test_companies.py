"""企业库 API 测试。测试数据只存在于独立测试库。"""


def _create_company(client, name: str, **extra) -> dict:
    resp = client.post("/api/v1/companies", json={"company_name": name, **extra})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def test_create_and_get_company(client):
    company = _create_company(client, "星河智造测试厂", industry="制造业", city="苏州", website="https://startest.example.com")
    assert company["company_name"] == "星河智造测试厂"
    assert company["normalized_name"] == "星河智造测试厂"

    detail = client.get(f"/api/v1/companies/{company['id']}")
    assert detail.status_code == 200
    data = detail.json()["data"]
    assert data["industry"] == "制造业"
    assert data["signal_count"] == 0
    assert data["opportunity_count"] == 0


def test_duplicate_normalized_name_rejected(client):
    _create_company(client, "重复名称企业A")
    resp = client.post("/api/v1/companies", json={"company_name": "重复名称企业A"})
    assert resp.status_code == 409


def test_company_404(client):
    assert client.get("/api/v1/companies/cmp_not_exists").status_code == 404


def test_list_companies_filters_and_pagination(client):
    _create_company(client, "筛选测试制造企业", industry="制造业", city="苏州")
    _create_company(client, "筛选测试贸易企业", industry="贸易", city="上海")

    resp = client.get("/api/v1/companies", params={"q": "筛选测试"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] >= 2
    assert {"items", "total", "page", "page_size"} <= set(data.keys())

    resp = client.get("/api/v1/companies", params={"q": "筛选测试", "industry": "贸易"})
    assert all(item["industry"] == "贸易" for item in resp.json()["data"]["items"])

    resp = client.get("/api/v1/companies", params={"q": "筛选测试", "city": "苏州"})
    assert all(item["city"] == "苏州" for item in resp.json()["data"]["items"])

    resp = client.get("/api/v1/companies", params={"q": "筛选测试", "page": 1, "page_size": 1})
    assert len(resp.json()["data"]["items"]) == 1


def test_list_companies_sort(client):
    _create_company(client, "排序测试甲企业")
    _create_company(client, "排序测试乙企业")
    resp = client.get("/api/v1/companies", params={"q": "排序测试", "sort": "company_name"})
    names = [item["company_name"] for item in resp.json()["data"]["items"]]
    assert names == sorted(names)
