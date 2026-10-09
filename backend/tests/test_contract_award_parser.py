"""T08.1 中标公告结构化解析回归（真实 ccgp 公告格式样例）。

覆盖任务书要求的全部真实变体：
1. 标准单供应商（万元）；2. 双包件（元）；3. 双供应商（万元）；
4. 仅折扣率/下浮率（无总价）；5. 金额数字夹空格。
解析不到 → None，禁止猜测。
"""
from app.services.procurement_parser import (
    extract_award_evidence_snippet,
    parse_announcement_time,
    parse_awarded_suppliers_with_amounts,
    parse_buyer_organization,
    parse_procurement_lifecycle,
    parse_procurement_method,
    parse_total_award_amount,
)

# 格式1：标准单供应商，金额万元（南京航空航天大学 激光增材平台中标公告真实格式）
NOTICE_SINGLE_WAN = """南京航空航天大学航空航天先进材料与结构多激光增材制造平台中标公告
公告信息： 采购项目名称 航空航天先进材料与结构多激光增材制造平台 采购单位 南京航空航天大学 行政区域 江苏省 公告时间 2026年09月30日 17:46
总中标金额 ￥990.000000 万元（人民币）
一、项目编号：NJDCX-202607031501 二、项目名称：航空航天先进材料与结构多激光增材制造平台
三、中标（成交）信息 供应商名称：广东汉邦激光科技有限公司 供应商地址：广东省中山市南头镇同福中路19号 中标（成交）金额：990.0000000（万元）
四、主要标的信息 1 广东汉邦激光科技有限公司 航空航天先进材料与结构多激光增材制造平台
1.采购人信息 名 称：南京航空航天大学"""

# 格式2：双包件，金额元（海关总署制式皮鞋真实格式）
NOTICE_TWO_PACKAGES = """海关总署2026年-2029年制式皮鞋加工服务采购项目中标公告
公告信息： 采购项目名称 海关总署2026年-2029年制式皮鞋加工服务采购项目 采购单位 海关总署物资装备采购中心 行政区域 北京市 公告时间 2026年09月30日 18:57
总中标金额 ￥1330.256500 万元（人民币）
三、中标信息 包件 1 供应商名称：上海新一名实业（集团）有限公司 供应商地址：上海市宝山区蕰川路3985号3号楼 中标金额：6,350,751.00元 评审总得分：93.50分 包件 2 供应商名称：德赛集团有限公司 供应商地址：浙江省温州市瓯海区 中标金额：6,951,814.00元 评审总得分：75.691分
1.采购人信息 名 称：海关总署 2.采购执行机构信息 名 称：海关总署物资装备采购中心"""

# 格式3：双供应商，金额万元（上海海关超低温冰箱真实格式）
NOTICE_TWO_SUPPLIERS = """上海海关全自动超低温保存冰箱采购项目（包件一、包件二）中标公告
公告信息： 采购项目名称 上海海关全自动超低温保存冰箱采购项目 采购单位 上海国际旅行卫生保健中心 行政区域 上海市 公告时间 2026年09月30日 17:38
三、中标（成交）信息 供应商名称：广东省帆泽国际贸易有限公司 供应商地址：广州市黄埔区开创大道2819号1栋460 中标（成交）金额：86.6000000（万元） 供应商名称：北京优尼赛斯科技有限公司 供应商地址：北京市朝阳区朝阳北路11号楼2单元511室 中标（成交）金额：47.5000000（万元）
1.采购人信息 名 称：上海国际旅行卫生保健中心"""

# 格式4：仅折扣率（广东海事局燃油供应真实格式；总中标金额为￥0）
NOTICE_DISCOUNT_ONLY = """广东海事局2026-2027年海巡船艇船用燃油供应服务统一采购项目中标公告
公告信息： 采购项目名称 广东海事局2026-2027年海巡船艇船用燃油供应服务统一采购项目 采购单位 中华人民共和国广东海事局本级 行政区域 广东省 公告时间 2026年09月30日 18:03
总中标金额 ￥0.000000 万元（人民币）
三、中标（成交）信息 供应商名称：中石化中海船舶燃料供应有限公司宁波分公司 供应商地址：浙江省宁波市鄞州区 包组或产品名称：燃油供应服务 折扣率(%)：95.7000000
八、其它补充事宜 招标公告发布日期：2026年9月2日 开标日期：2026年9月23日 定标日期：2026年9月30日"""

# 格式5：金额数字夹空格（公安部道研中心算力集群真实格式）
NOTICE_SPACED_AMOUNT = """2026年公安部道路交通安全研究中心算力集群设备采购项目Ⅱ中标公告
公告信息： 采购项目名称 算力集群设备采购项目 采购单位 公安部道路交通安全研究中心 行政区域 北京市 公告时间 2026年09月30日 17:35
三、中标（成交）信息 供应商名称：北京瑞源鑫达信息技术有限公司 供应商地址：北京市昌平区 中标（成交）金额： 4276000 .00元
1.采购人信息 名 称： 公安部道路交通安全研究中心"""

# 格式6：下浮率（中南大学食用油配送真实格式；总中标金额为￥0）
NOTICE_XIAFU = """中南大学后勤保障部饮食服务中心食用油配送服务项目中标公告
公告信息： 采购项目名称 食用油配送服务项目 采购单位 中南大学 行政区域 湖南省 公告时间 2026年09月30日 18:59
总中标金额 ￥0.000000 万元（人民币）
三、中标（成交）信息 供应商名称：湖南京升缘供应链有限公司 供应商地址：湖南省长沙市 包组或产品名称：食用油配送服务 下浮率(%)：3.0000000"""


def test_single_supplier_amount_in_wan():
    suppliers = parse_awarded_suppliers_with_amounts(NOTICE_SINGLE_WAN)
    assert len(suppliers) == 1
    assert suppliers[0]["supplier_name"] == "广东汉邦激光科技有限公司"
    assert suppliers[0]["award_amount"] == 9900000.0
    assert suppliers[0]["currency"] == "CNY"


def test_two_packages_amounts_in_yuan():
    suppliers = parse_awarded_suppliers_with_amounts(NOTICE_TWO_PACKAGES)
    names = [s["supplier_name"] for s in suppliers]
    amounts = [s["award_amount"] for s in suppliers]
    assert names == ["上海新一名实业（集团）有限公司", "德赛集团有限公司"]
    assert amounts == [6350751.0, 6951814.0]


def test_two_suppliers_amounts_in_wan():
    suppliers = parse_awarded_suppliers_with_amounts(NOTICE_TWO_SUPPLIERS)
    assert [(s["supplier_name"], s["award_amount"]) for s in suppliers] == [
        ("广东省帆泽国际贸易有限公司", 866000.0),
        ("北京优尼赛斯科技有限公司", 475000.0),
    ]


def test_discount_only_notice_amount_stays_none():
    """仅折扣率（总价￥0）→ 金额必须 None，禁止编造；折扣率如实记录。"""
    suppliers = parse_awarded_suppliers_with_amounts(NOTICE_DISCOUNT_ONLY)
    assert len(suppliers) == 1
    assert suppliers[0]["award_amount"] is None
    assert suppliers[0]["discount_rate"] == 95.7
    assert suppliers[0]["amount_source"] == "DISCOUNT_RATE_ONLY"
    assert parse_total_award_amount(NOTICE_DISCOUNT_ONLY) is None


def test_xiafu_rate_recognized():
    suppliers = parse_awarded_suppliers_with_amounts(NOTICE_XIAFU)
    assert suppliers[0]["award_amount"] is None
    assert suppliers[0]["discount_rate"] == 3.0


def test_spaced_amount_parsed():
    """真实公告存在"4276000 .00元"式空格数字，必须解析成功。"""
    suppliers = parse_awarded_suppliers_with_amounts(NOTICE_SPACED_AMOUNT)
    assert suppliers[0]["award_amount"] == 4276000.0


def test_no_amount_text_returns_none_not_guess():
    suppliers = parse_awarded_suppliers_with_amounts("供应商名称：某某科技有限公司 供应商地址：某地")
    assert suppliers[0]["award_amount"] is None
    assert suppliers[0]["currency"] is None


def test_buyer_vs_executing_agency_separated():
    """采购人（法人）与采购执行机构不得混同。"""
    buyer = parse_buyer_organization(NOTICE_TWO_PACKAGES)
    assert buyer["buyer"] == "海关总署"
    assert buyer["executing_agency"] == "海关总署物资装备采购中心"
    buyer_single = parse_buyer_organization(NOTICE_SINGLE_WAN)
    assert buyer_single["buyer"] == "南京航空航天大学"


def test_announcement_time_not_confused_with_bid_dates():
    """招标公告发布日期/开标/定标日期 ≠ 公告发布时间。"""
    assert parse_announcement_time(NOTICE_DISCOUNT_ONLY).isoformat() == "2026-09-30T18:03:00"


def test_procurement_method_none_without_explicit_field():
    """评审专家名单里的"单一来源采购人员"是 ccgp 固定模板，不得判定为单一来源采购方式。"""
    assert parse_procurement_method(NOTICE_SINGLE_WAN) is None
    assert parse_procurement_method("采购方式：竞争性磋商") == "竞争性磋商"


def test_lifecycle_awarded_for_result_notices():
    assert parse_procurement_lifecycle(NOTICE_SINGLE_WAN) == "AWARDED"
    assert parse_procurement_lifecycle(NOTICE_DISCOUNT_ONLY) == "AWARDED"


def test_evidence_snippet_is_exact_substring():
    for text, subject in [
        (NOTICE_SINGLE_WAN, "广东汉邦激光科技有限公司"),
        (NOTICE_TWO_PACKAGES, "德赛集团有限公司"),
        (NOTICE_DISCOUNT_ONLY, "中石化中海船舶燃料供应有限公司宁波分公司"),
    ]:
        snippet = extract_award_evidence_snippet(text, subject)
        assert snippet is not None
        assert snippet in text  # 原文精确子串
        assert subject in snippet


def test_total_award_amount_converted_to_yuan():
    assert parse_total_award_amount(NOTICE_SINGLE_WAN) == 9900000.0
    assert parse_total_award_amount(NOTICE_TWO_PACKAGES) == 13302565.0
    assert parse_total_award_amount("没有金额字段") is None
