"""Rebuild the T10-A offline review package from captured official pages.

Curated interpretations are REVIEW_PENDING. No customer behavior or writable DB.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.services import procurement_parser as pp
from scripts.t10_a.product_match import match_product

OUT = ROOT.parent / 'docs/reports/t10_a'
AS_OF = datetime(2026, 10, 8, 11, 30)  # Beijing time, explicit research cutoff
captures = {}
for filename in ['capture_seed.json', 'capture_details.json', 'capture_final.json']:
    for row in json.loads((OUT / filename).read_text(encoding='utf-8')):
        if row['status'] == 'CAPTURED':
            key = row['text_path'].split('/')[-1].split('.')[0]
            row['full_text_path'] = f'raw/{key}.full.txt'
            row['text'] = (OUT / row['full_text_path']).read_text(encoding='utf-8')
            captures[row['url']] = row


def page(part):
    return next(row for url, row in captures.items() if part in url)


def ev(row, quote):
    start = row['text'].find(quote)
    if start < 0:
        raise ValueError(f'Quote absent: {row["url"]}: {quote}')
    return dict(text=row['text'], quote=quote, start=start, end=start+len(quote),
                url=row['url'], text_path=row['full_text_path'])


def near(row, marker, length=120):
    start = row['text'].find(marker)
    if start < 0:
        raise ValueError(f'Marker absent: {marker}')
    return ev(row, row['text'][start:start+length])


def fact(row, marker, value, unit):
    return dict(value=value, unit=unit, evidence=near(row, marker))


def requirement(row, marker, name, value=None, unit=None, op='eq'):
    return dict(name=name, value=value, unit=unit, op=op, evidence=near(row, marker))


p400, p200, pine, revo, fermi = (page(x) for x in ['product/52.html', 'product/57.html', 'Product/Pine3.html', 'Product/Revo.html', '227.html'])
products = {
    'HBD_P400_6LASER': dict(supplier='广东汉邦激光科技有限公司', company_id='cmp_84d577f0e5a1449e81f89a16', model='HBD P400 / 500W×6配置', page=p400,
        facts={'category': fact(p400, '打印材料:', 'METAL_3D', 'category'),
               'build_size': fact(p400, '成型尺寸:', [350,400,400], 'mm'),
               'laser_count': fact(p400, '500W×6', 6, 'count')}),
    'HBD_200': dict(supplier='广东汉邦激光科技有限公司', company_id='cmp_84d577f0e5a1449e81f89a16', model='HBD 200', page=p200,
        facts={'category': fact(p200, '打印材料:', 'METAL_3D', 'category'),
               'build_size': fact(p200, '成型尺寸:', [265,170,120], 'mm'),
               'laser_count': fact(p200, '300W×2', 2, 'count')}),
    'PINE3': dict(supplier='武汉华日精密激光股份有限公司', company_id='cmp_7ffc20e0ab08425aab99cd10', model='PINE3中功率皮秒激光器', page=pine,
        facts={'category': fact(pine, 'PINE3中功率皮秒激光器', 'PICO_LASER', 'category'),
               'wavelength': fact(pine, '1064/532nm', [1064,532], 'nm')}),
    'REVO': dict(supplier='武汉华日精密激光股份有限公司', company_id='cmp_7ffc20e0ab08425aab99cd10', model='Revo（页面列明的型号族；不拼接不同版本参数）', page=revo,
        facts={'category': fact(revo, '光纤飞秒激光器', 'FEMTO_LASER', 'category'),
               'pulse_family': fact(revo, '脉宽 ： fs级', 'FEMTO', 'family'),
               'wavelength': fact(revo, '1035/517/345nm', [1035,517,345], 'nm')}),
    'FERMI_FACET': dict(supplier='费勉科技（上海）股份有限公司', company_id='cmp_a6f85f98b1f24796b3173274', model='激光器腔面处理系统', page=fermi,
        facts={'category': fact(fermi, '真空解理镀膜系统可实现', 'LASER_FACET_SYSTEM', 'category')}),
}
projects = []


def add(pid, row, name, buyer, category, model=None, *, requirements=None,
        budget=None, announcement=None, deadline=None, window=None, stage=None,
        demand_marker='采购需求', acquisition_closed=False, note=''):
    parsed = pp.parse_procurement_fields(row['text'])
    deadline_value = pp.parse_date_cn(deadline) if deadline else parsed['deadline']
    # Award price is not procurement budget.
    award = '中标公告' in row['title'] or '中标结果公告' in row['title']
    amount = budget if budget is not None else (None if award else parsed['budget_amount'])
    announce = pp.parse_date_cn(announcement) if announcement else parsed['announcement_time']
    phase = stage or ('AWARDED' if award else pp.parse_procurement_lifecycle(row['text'], deadline=deadline_value, now=AS_OF))
    unknown = ['完整采购文件/关键技术参数是否齐全', '供应商信用、资质及报名证明', '后续更正/终止/中标状态未完成穷尽核查']
    if phase == 'INTENTION':
        unknown.append('意向是否已转为招标、成交或延期；预计采购月份不是截止时间')
    if not deadline_value:
        unknown.append('真实投标截止时间 UNKNOWN')
    if acquisition_closed:
        unknown.append('获取文件期已结束；该供应商是否已报名 UNKNOWN')
    reqs = requirements or [requirement(row, name, 'category', category, 'category')]
    if model:
        result = match_product(reqs, products[model]['facts'])
    else:
        result = match_product(reqs, {})
    demand = near(row, demand_marker, 1000) if demand_marker in row['text'] else near(row, name, 600)
    # No confirmed immediate-bid eligibility in this research batch.
    projects.append(dict(id=pid, project_name=name, purchaser=buyer, category=category,
        url=row['url'], collected_at=row['collected_at'], raw_html_path=row['html_path'],
        raw_text_path=row['full_text_path'], announcement_date=announce.isoformat() if announce else 'UNKNOWN',
        deadline=deadline_value.isoformat() if deadline_value else 'UNKNOWN', procurement_window=window or 'UNKNOWN',
        lifecycle=phase, budget_cny=amount if amount is not None else 'UNKNOWN',
        award_amount_cny=parsed['budget_amount'] if award else 'UNKNOWN',
        procurement_content=demand, evaluated_product=model or 'UNKNOWN', match=result,
        unknowns=unknown, acquisition_closed=acquisition_closed, actionable_now=False,
        next_action=('仅历史研究，禁止当作当前投标机会' if phase in ['AWARDED','CLOSED','CANCELLED','EXPIRED'] else
                     '人工核对完整文件、最新更正与报名状态；意向仅用于跟踪，不承诺投标资格'), note=note))


r = page('27341471')
add('P01', r, '金属3D打印机采购项目', 'zycgr22011902（实际主体名称 UNKNOWN）', 'METAL_3D', 'HBD_P400_6LASER', acquisition_closed=True,
    requirements=[requirement(r,'最大成型尺寸','build_size',[265,265,325],'mm','ge_vector'),
                  requirement(r,'激光器数量','laser_count',6,'count'),
                  requirement(r,'激光器波长1060','wavelength_range',[1060,1080],'nm'),
                  requirement(r,'输出功率范围','power_adjustment',[10,100],'%'),
                  requirement(r,'聚焦光斑直径','focus_diameter',60,'um')],
    note='P400尺寸及六激光配置有依据；波长、调功范围、光斑 UNKNOWN。不是汉邦全产品线资格判定。')
r = page('27324817')
add('P02', r, '上海民航职业技术学院金属增材制造实训设备采购项目', '上海民航职业技术学院', 'METAL_3D', 'HBD_P400_6LASER', acquisition_closed=True,
    requirements=[requirement(r,'金属3D打印机','category','METAL_3D','category'),
                  requirement(r,'三维扫描系统','reverse_scanning',True,'feature'),
                  requirement(r,'30天内','delivery_days',30,'days')],
    note='只证明金属打印类别，整包配套、三维扫描、30天交付和预算内报价均 UNKNOWN。')

tyut = page('32620.htm')
soup = BeautifulSoup((OUT / tyut['html_path']).read_text(encoding='utf-8'), 'html.parser')
tyut_rows = {}
for tr in soup.select('tr'):
    cells = [c.get_text(' ',strip=True) for c in tr.find_all(['td','th'],recursive=False)]
    if len(cells) >= 6 and cells[0].isdigit():
        tyut_rows[cells[0]] = cells
for seq, pid, cat, model in [('21','P03','SUPERCONTINUUM','REVO'),('42','P04','PICO_LASER','PINE3'),
                             ('66','P05','FBG_SYSTEM','REVO'),('67','P06','DUAL_WAVELENGTH_WELDING',None)]:
    cells = tyut_rows[seq]; name=cells[1]
    if seq == '21':
        reqs=[requirement(tyut,'430nm—2400nm','wavelength',2400,'nm','contains'),
              requirement(tyut,'平均功率：>8W','average_power',8,'W','gt')]
    elif seq == '42':
        reqs=[requirement(tyut,'1064 ± 1 nm','wavelength',1064,'nm','contains'),
              requirement(tyut,'20-120','repetition_range',[20,120],'MHz'),
              requirement(tyut,'～100ps','pulse_width_approx',100,'ps'),
              requirement(tyut,'平均功率：>10W','average_power',10,'W','gt')]
    elif seq == '66':
        reqs=[requirement(tyut,'飞秒激光光源参数','pulse_family','FEMTO','family'),
              requirement(tyut,'纤芯智能识别功能','core_detection',True,'feature'),
              requirement(tyut,'超过 10000 个','import_points',10000,'count','gt'),
              requirement(tyut,'1550nm±0.3nm','fbg_center',1550,'nm')]
    else:
        reqs=[requirement(tyut,name,'category',cat,'category'),
              requirement(tyut,'额定功率≥6kw','red_power',6,'kW','ge'),
              requirement(tyut,'额定功率≥1kw','blue_power',1,'kW','ge')]
    add(pid,tyut,name,'太原理工大学',cat,model,requirements=reqs,budget=float(cells[3]),announcement='2026-09-07',
        window=cells[4],stage='INTENTION',demand_marker=name,
        note=('预计9月已过去，不能认定采购结束或当前仍有效；仅待核实跟踪。' if seq=='67' else
              '单列意向条目计一个项目，均来自同一公告；只比较已核实型号，非企业全产品线结论。'))
r=page('12754.chtml')
add('P07',r,'超耐磨件3D打印系统','中国矿业大学','CERAMIC_SLA','HBD_P400_6LASER',budget=1000000,window='2026年10月',stage='INTENTION',
    requirements=[requirement(r,'光固化增材制造技术','category','CERAMIC_SLA','category')],
    note='陶瓷光固化与所查金属粉末激光设备不是同一工艺；不得因3D打印关键词判MATCH。')
r=page('11873.htm')
add('P08',r,'增材制造中心建设项目','上海应用技术大学','UNKNOWN',announcement='2026-09-30',stage='ANNOUNCED',
    note='校方公告只有外链，设备清单、预算、截止时间、完整参数均 UNKNOWN；不得假设一定采购金属打印机。')
r=page('27229123')
add('P09',r,'某实验室激光隐切','zycgr21070801（实际主体名称 UNKNOWN）','LASER_STEALTH_DICING',
    note='隐切整机不等于裸激光器；未取得附件参数，型号比较 UNKNOWN。')
r=page('27308258')
add('P10',r,'多材异质增材制造科研平台','重庆电子科技职业大学','MATERIAL_TESTING_BUNDLE',
    deadline='2026年9月17日 10:00',budget=867000,
    note='概要87万元与正文86.7万元不同；按正文项目基本情况预算867000元，保留差异。标题含增材但所列采购不是金属打印机。')
r=page('26360966')
add('P11',r,'中原关键金属实验室高强高导Cu-Cr-X合金绿光增材制造关键技术开发设备采购项目','中原关键金属实验室','GREEN_LASER_METAL_3D',
    deadline='2026年04月17日 09:00',note='绿光设备不能以通用金属打印材料列表代替波长证据；整包参数 UNKNOWN，已截止。')
r=page('27433686')
add('P12',r,'航空航天先进材料与结构多激光增材制造平台','南京航空航天大学','METAL_3D','HBD_P400_6LASER',
    note='中标公告金额990万元单列为award_amount，预算UNKNOWN；中标只能证实历史供应关系，不能证实参数全部合格或购买BizPulse意图。')
r=page('27435266')
add('P13',r,'清华大学1064nm激光器采购项目','清华大学','LASER_1064','PINE3',
    requirements=[requirement(r,'1064nm','wavelength',1064,'nm','contains'),
                  requirement(r,'1064nm','complete_specs',None,'unknown')],
    note='1064nm一项满足不代表型号整体匹配；历史中标金额855000元不是预算。')
r=page('202608170029945219')
add('P14',r,'纳秒脉冲固体激光器','上海大学','NANOSECOND_SOLID_LASER','PINE3',budget=480000,announcement='2026-09-04',stage='INTENTION',window='2026年9月',
    requirements=[requirement(r,'纳秒脉冲固体激光器','category','NANOSECOND_SOLID_LASER','category'),
                  requirement(r,'1064nm单脉冲能量','wavelength',1064,'nm','contains'),
                  requirement(r,'400mJ','pulse_energy_1064',400,'mJ','ge')],
    note='纳秒需求与所查皮秒型号工艺不符；华日官网也有纳秒系列，本结论不排除其他型号，需人工补产品证据。意向公示期不是投标截止期。')
r=page('855331.html')
add('P15',r,'合肥物质院等离子体所激光-电弧复合焊接系统采购项目','中国科学院等离子体物理研究所','LASER_ARC_WELDING',
    announcement='2026-09-01',deadline='2026年9月22日 14:00',stage='CLOSED',note='采购需求只写详见招标文件；不能拿激光器功率代替焊接系统匹配。导航含废标流标，原解析会误判CANCELLED；按正文截止日期标CLOSED，最终结果UNKNOWN。')
r=page('15646.htm')
soup=BeautifulSoup((OUT/r['html_path']).read_text(encoding='utf-8'),'html.parser')
yangtze_rows=[]
for tr in soup.select('tr'):
    cells=[c.get_text(' ',strip=True) for c in tr.find_all(['td','th'],recursive=False)]
    if len(cells)>=6 and cells[0] in ['1','2']:
        yangtze_rows.append(cells)
for cells, pid, cat in zip(yangtze_rows,['P16','P17'],['FLUORESCENCE_SPECTROMETER','PLASMA_SPECTROSCOPY_SYSTEM']):
    add(pid,r,cells[1],'长江大学',cat,budget=float(cells[4])*10000,announcement='2026-09-20',window=cells[5],stage='INTENTION',demand_marker=cells[1],
        note='激光/光谱科研配套整机；不能只匹配皮秒光源或真空子系统就判完整整机MATCH。')

# Additional diagnostic product pairs; keep distinct from one primary result/project.
diagnostics=[]
for pid,model in [('P01','HBD_200'),('P07','HBD_200'),('P08','HBD_P400_6LASER')]:
    project=next(p for p in projects if p['id']==pid)
    diagnostics.append(dict(project_id=pid,product=model,**match_product(project['match']['checks'],products[model]['facts'])))


def compact(obj):
    if isinstance(obj,dict):
        return {k:compact(v) for k,v in obj.items() if k!='text'}
    if isinstance(obj,list):return [compact(v) for v in obj]
    return obj


payload=dict(as_of_beijing=AS_OF.isoformat(),sample_count=len(projects),supplier_count=3,
             status='STOPPED_FOR_HUMAN_QA_INCOMPLETE_GATE',
             projects=projects,products=products,diagnostic_pairs=diagnostics,
             metrics=dict(primary_match_distribution=dict(Counter(p['match']['status'] for p in projects)),
                          lifecycle_distribution=dict(Counter(p['lifecycle'] for p in projects)),
                          confirmed_actionable_projects=0,confirmed_eligible_projects=0,
                          customer_accepted_opportunities=0,false_positive_rate='UNVERIFIED',false_negative_rate='UNVERIFIED'))
for p in projects:
    p['scope'] = ('NEGATIVE_CONTROL' if p['id']=='P10' else 'RELATED_RESEARCH_EQUIPMENT' if p['id'] in ['P16','P17'] else 'DIRECT_INDUSTRY')
    row=captures[p['url']]
    p['field_evidence'] = dict(purchaser=near(row,p['purchaser'].split('（')[0]) if p['purchaser'].split('（')[0] in row['text'] else 'UNKNOWN',
                               project_name=near(row,p['project_name']),
                               budget_cny='UNKNOWN', announcement_date='UNKNOWN', deadline='UNKNOWN')
    for field in ['announcement_date','deadline']:
        if p[field]=='UNKNOWN':continue
        target=datetime.fromisoformat(p[field])
        for m in re.finditer(r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?(?:\s*\d{1,2}(?:[:：]\d{1,2}(?::\d{1,2})?|[点时]\d{1,2}分))?',row['text']):
            dt=pp.parse_date_cn(m[0])
            if dt==target:
                p['field_evidence'][field]=ev(row,m[0]);break
    if p['id'] in ['P03','P04','P05','P06']:
        seq={'P03':'21','P04':'42','P05':'66','P06':'67'}[p['id']]
        p['field_evidence']['budget_cny']=dict(url=p['url'],html_path=p['raw_html_path'],html_locator=f'tr with first cell {seq}, fourth cell (预算金额元)',quote=tyut_rows[seq][3])
    elif p['id']=='P07':
        p['field_evidence']['budget_cny']=dict(url=p['url'],html_path=p['raw_html_path'],html_locator='tr: CGYX202600129; 预算金额(万元) column',quote='100',unit='万元')
    elif p['id'] in ['P16','P17']:
        seq=int(p['id'][-2:])-15
        p['field_evidence']['budget_cny']=dict(url=p['url'],html_path=p['raw_html_path'],html_locator=f'tr with first cell {seq}; fifth cell (预算万元)',quote=yangtze_rows[seq-1][4])
    elif p['budget_cny']!='UNKNOWN':
        m=re.search(r'预算金额[^0-9]{0,12}[\d,.]+[^\s]{0,12}',row['text'])
        if m:p['field_evidence']['budget_cny']=ev(row,m[0])
    p['keyword_baseline_positive']=bool(re.search('激光|增材|3D',p['project_name']+' '+p['procurement_content']['quote']))
in_scope=[p for p in projects if p['scope']!='NEGATIVE_CONTROL']
payload['sample_count']=len(in_scope)
payload['audit_count']=len(projects)
payload['metrics']['primary_match_distribution']=dict(Counter(p['match']['status'] for p in in_scope))
payload['metrics']['lifecycle_distribution']=dict(Counter(p['lifecycle'] for p in in_scope))
payload['metrics']['keyword_baseline_positive']=sum(p['keyword_baseline_positive'] for p in in_scope)
(OUT/'research.json').write_text(json.dumps(compact(payload),ensure_ascii=False,indent=2),encoding='utf-8')

lines=['# T10-A 采购样本与参数匹配明细','',f'判定基准：{AS_OF.isoformat()} +08:00。所有结果待人工复核；MATCH仅指技术参数，不等于投标资格。',
       '每项目一个主要比较结果；UNKNOWN不等于供应商不能供货。MISMATCH仅针对所查型号。', '']
for p in projects:
    lines += [f'## {p["id"]} {p["project_name"]}', '',
              f'- 采购方：{p["purchaser"]}',f'- 阶段：{p["lifecycle"]}；公告日期：{p["announcement_date"]}',
              f'- 预算：{p["budget_cny"]} 元；历史中标金额：{p["award_amount_cny"]} 元',
              f'- 截止：{p["deadline"]}（北京时间）；预计采购月份：{p["procurement_window"]}',
              f'- 来源：[{p["project_name"]}]({p["url"]})',f'- 采集：{p["collected_at"]}；原文：[{p["raw_text_path"]}]({p["raw_text_path"]})；HTML：[{p["raw_html_path"]}]({p["raw_html_path"]})',
              f'- 比较型号：{p["evaluated_product"]}；结果：**{p["match"]["status"]}**；投标资格：UNKNOWN；确认可行动：否',
              f'- 说明：{p["note"]}',f'- 建议人工动作：{p["next_action"]}', '',
              '| 必需项 | 规则判定 | 采购原文及位置（字符，0起算，左闭右开） | 产品依据 |','|---|---|---|---|']
    for check in p['match']['checks']:
        e=check['evidence'];c=check['capability'];ce=c['evidence'] if c else None
        product_e=(f'[{ce["text_path"]}]({ce["text_path"]}) [{ce["start"]},{ce["end"]})，{c["value"]} {c["unit"]}' if ce else 'UNKNOWN：未取得该参数证据')
        quote=e['quote'].replace('|','/').replace('\n',' ')[:140]
        lines.append(f'| {check["name"]} {check["op"]} {check["value"]} {check["unit"]} | {check["result"]} | [{e["text_path"]}]({e["text_path"]}) [{e["start"]},{e["end"]})：{quote} | {product_e} |')
    lines += ['', '未知项：'+'；'.join(p['unknowns']), '', '采购内容原文：', '', '> '+p['procurement_content']['quote'].replace('\n',' '), '']
(OUT/'PROJECT_MATCH_DETAILS.md').write_text('\n'.join(lines),encoding='utf-8')

cards=['# T10-A 供应商采购研究卡片（人工审阅样例）','',
       '技术 PARTIAL 不等于可立即投标。没有客户认可、报名证明或资质核验；禁止作为已确认销售机会宣传。', '']
for supplier,pids in [('广东汉邦激光科技有限公司',['P01','P02']),('武汉华日精密激光股份有限公司',['P04','P05']),('费勉科技（上海）股份有限公司',[])]:
    cards += [f'## {supplier}', '',f'本轮卡片：{len(pids)} 条（最多5条）。', '']
    if not pids:
        cards += ['本轮没有核实到高相关的激光器腔面处理需求，0条卡片。可交付样例为官方产品证据清单和采购排除说明：激光-电弧焊接系统不能因“激光”词匹配到腔面解理/钝化/镀膜系统。', '']
    for pid in pids:
        p=next(p for p in projects if p['id']==pid)
        satisfied=[c['name'] for c in p['match']['checks'] if c['result']=='SATISFIED']
        failed=[c['name'] for c in p['match']['checks'] if c['result']=='UNSATISFIED']
        missing=[c['name'] for c in p['match']['checks'] if c['result']=='UNKNOWN']
        cards += [f'### {pid} {p["project_name"]}','',f'- 采购方：{p["purchaser"]}',
                  f'- 阶段：{p["lifecycle"]}；预算：{p["budget_cny"]}元；截止：{p["deadline"]}（北京时间）',
                  f'- 日期/时间：公告 {p["announcement_date"]}；预计采购 {p["procurement_window"]}；采集 {p["collected_at"]}',
                  f'- 匹配依据：{products[p["evaluated_product"]]["model"]}；{p["note"]}；满足项：{", ".join(satisfied)}',
                  f'- 不符合项：{", ".join(failed) if failed else "已检查项目中未发现明确不符合；不代表全部满足"}',
                  f'- 未知项：{", ".join(missing)}；'+ '；'.join(p['unknowns']),
                  f'- 结果：PARTIAL；客户认可：UNKNOWN；投标资格：UNKNOWN；可立即投标：未确认',
                  f'- 来源：[{p["project_name"]}]({p["url"]})；产品：[官网]({products[p["evaluated_product"]]["page"]["url"]})',
                  f'- 建议人工动作：{p["next_action"]}；先让供应商判断该样例是否有用，记录其原话。',
                  f'- 逐项证据位置：见 [匹配明细](PROJECT_MATCH_DETAILS.md) 的 {pid}；结构化字段见 [research.json](research.json)。', '']
(OUT/'SUPPLIER_CARDS.md').write_text('\n'.join(cards),encoding='utf-8')

review_pairs=[('P01','HBD_P400_6LASER'),('P01','HBD_200'),('P02','HBD_P400_6LASER'),('P03','REVO'),('P04','PINE3'),
              ('P05','REVO'),('P07','HBD_P400_6LASER'),('P08','HBD_P400_6LASER'),('P12','HBD_P400_6LASER'),('P14','PINE3')]
reviews=['# T10-A 10条人工复核准备','',
         '所有行 HUMAN_REVIEW_PENDING。由人工填写签名、时间、结论及引文；代码检查不能替代人工复核，更不能替代客户认可。','',
         '| 复核项目 | 产品 | 初步结论 | 重点核对 | 人工结论/签名/时间 |','|---|---|---|---|---|']
questions={
 'P01':'六激光配置是否同一交付版本；逐轴尺寸；波长/光斑/调功范围；报名是否已完成；采购方真实名称仍未知',
 'P02':'实训整包/逆向扫描/电路改造/30天交付；预算内报价；已经登记并取得文件的资格证明',
 'P03':'超连续谱430–2400nm与所查离散波长型号不同；华日其他型号有无证据，不可推断全企业不能供货',
 'P04':'约100ps与所查<10ps差异；20–120MHz连续可调与>10W；约值不能擅设容差',
 'P05':'裸飞秒光源不能等同FBG全自动平台；软件导入、光栅性能、送纤和控制系统',
 'P07':'陶瓷光固化与金属粉末激光工艺/材料不同；无采购资格确认',
 'P08':'官方外链的完整设备需求、预算与截止未知；项目名称不能证明金属打印需求',
 'P12':'已中标，绝不能当作当前投标机会；990万为成交金额；不推断当前购买BizPulse需求',
 'P14':'纳秒与皮秒不同；1–10Hz及400mJ；华日纳秒系列待人工取证；公示期不是投标期'}
for pid,model in review_pairs:
    p=next(p for p in projects if p['id']==pid)
    result=match_product(p['match']['checks'],products[model]['facts'])
    reviews.append(f'| {pid} | {model} | {result["status"]} | {questions[pid]} | UNKNOWN / 待填写 |')
reviews += ['', '复核顺序：打开匹配明细和原始HTML → 核对公告主体/预算/生命周期 → 逐参数核对同一产品配置 → 核对报名/资格/最新更正 → 记录人工结论。',
            '客户访谈另行记录：人工认可的项目ID、此前是否已知、此前是否因关键词遗漏、明确不符合原因、客户原话及记录时间。不能从本表自动创建回复/成交。']
(OUT/'HUMAN_REVIEW_QUEUE.md').write_text('\n'.join(reviews),encoding='utf-8')
print(json.dumps(dict(samples=len(in_scope),audit_count=len(projects),matches=payload['metrics'],diagnostics=[(r['project_id'],r['product'],r['status']) for r in diagnostics]),ensure_ascii=False))
