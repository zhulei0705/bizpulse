"""R1 bounded acceptance tooling. Production is enforced read-only; no approvals."""
import os, sys, json, hashlib, subprocess, sqlite3
import re
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
OUT = ROOT.parent / 'docs/reports/t10_c1_2_r1'
OUT.mkdir(parents=True, exist_ok=True)
def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def baseline(stage):
    from m2_02_integrity import snapshot
    save('integrity_' + stage + '.json', snapshot())
    git = subprocess.run(['git','status','--porcelain','--untracked-files=all'],cwd=ROOT.parent,capture_output=True,text=True,encoding='utf-8').stdout
    (OUT / ('git_' + stage + '.txt')).write_text(git,encoding='utf-8')
    if stage == 'before':
        paths = subprocess.run(['git','ls-files','--cached','--others','--exclude-standard'],cwd=ROOT.parent,capture_output=True,text=True,encoding='utf-8').stdout.splitlines()
    else: paths = json.loads((OUT/'files_before.json').read_text(encoding='utf-8'))
    save('files_' + stage + '.json',{p:digest(ROOT.parent/p) if (ROOT.parent/p).is_file() else None for p in paths})
    save('archives_' + stage + '.json',{p.relative_to(ROOT.parent).as_posix():digest(p) for folder in ['t10_c1_2','t10_c1_2_p0a','t09'] for p in (OUT.parent/folder).rglob('*') if p.is_file()})
def audit():
    os.environ['DATABASE_URL'] = 'sqlite:///file:' + (ROOT/'data/bizpulse.db').as_posix() + '?mode=ro&uri=true'
    os.environ['ENABLE_SCHEDULER'] = 'false'
    from app.db import model_imports
    from sqlalchemy import create_engine, select, text
    from sqlalchemy.orm import Session
    from app.models.source import SourceRecord
    from app.models.signal import Signal, SignalEvidence
    from app.models.opportunity import Opportunity
    from app.models.opportunity_candidate import OpportunityCandidate
    from app.models.audit import AuditLog
    from app.services.evidence_integrity import record_issues, evidence_issues, signal_issues, exact_reference, text_contract
    from app.services.actionability import compute_signal_actionability, opportunity_actionability
    from app.services.validation_readiness import company_readiness
    from app.services.business_semantics import classify_business_text, bind_semantics_to_subject
    original=json.loads((OUT.parent/'t10_c1_2_p0a/production_impact.json').read_text(encoding='utf-8'))['signals']
    assert len(original)==116 and len({r['signal_id'] for r in original})==116
    engine=create_engine(os.environ['DATABASE_URL'])
    rows=[]
    with Session(engine, autoflush=False) as db:
        db.execute(text('PRAGMA query_only=ON'))
        opps=list(db.scalars(select(Opportunity)))
        ocands=list(db.scalars(select(OpportunityCandidate)))
        ready={}
        for old in original:
            s=db.get(Signal,old['signal_id']); assert s is not None
            r=db.get(SourceRecord,s.source_record_id)
            es=list(db.scalars(select(SignalEvidence).where(SignalEvidence.signal_id==s.id)))
            sem=bind_semantics_to_subject(classify_business_text(r.raw_text,signal_type=s.signal_type),s.company.company_name)
            linked=[o for o in opps if o.primary_signal_id==s.id or any(e.signal_id==s.id for e in o.evidences)]
            downstream=[]
            for o in linked:
                oa=opportunity_actionability(db,o)
                independent=[]
                for sid in {e.signal_id for e in o.evidences if e.signal_id} | ({o.primary_signal_id} if o.primary_signal_id else set()):
                    other=db.get(Signal,sid)
                    if other and sid!=s.id:
                        independent.append(dict(signal_id=sid,status=other.status,issues=signal_issues(db,other),actionability=compute_signal_actionability(db,other),semantic=bind_semantics_to_subject(classify_business_text(other.source_record.raw_text,signal_type=other.signal_type),other.company.company_name)))
                downstream.append(dict(id=o.id,title=o.title,status=o.status,review_status=o.review_status,stage=o.stage,actionability=oa,independent_other_signals=independent))
            if s.company_id not in ready:
                state=company_readiness(db,s.company_id)
                ready[s.company_id]={k:v for k,v in state.items() if k!='usable_contact_channels'}
            evidence=[]
            for e in es:
                er=db.get(SourceRecord,e.source_record_id)
                path=(ROOT/er.raw_html_path).resolve() if er.raw_html_path else None
                evidence.append(dict(id=e.id,record_id=e.source_record_id,version=er.version_number,body_sha256=text_contract(er)['body_sha256'],contract=(er.metadata_json or {}).get('evidence_text_contract'),snapshot=er.raw_html_path,snapshot_exists=bool(path and path.is_relative_to(ROOT) and path.is_file()),raw_sha256=digest(path) if path and path.is_relative_to(ROOT) and path.is_file() else None,excerpt=e.quoted_text,start=e.start_offset,end=e.end_offset,exact=exact_reference(er.raw_text,e.quoted_text,e.start_offset,e.end_offset),verification_status=e.verification_status,issues=evidence_issues(db,e)))
            issues=signal_issues(db,s)
            objective_errors=[e['id'] for e in evidence if not e['exact']]
            # A missing snapshot is unknown, never evidence of a semantic error.
            if objective_errors:
                category='CONFIRMED_ERROR';basis='Stored evidence slice mismatch: '+','.join(objective_errors)
            elif not evidence or any(not e['snapshot_exists'] or e['issues'] for e in evidence) or record_issues(r):
                category='INSUFFICIENT_EVIDENCE';basis='Missing/blocked original version or evidence; semantic verdict unavailable'
            else:
                category='REQUIRES_HUMAN_REVIEW';basis='New semantic rule differs; original snapshot exists but rule output alone is not historical truth'
            exposed=any(o['status']=='ACTIVE' and o['review_status']=='APPROVED' and o['actionability']['actionability_status']=='ACTIONABLE_NOW' for o in downstream)
            severity='P0' if category=='CONFIRMED_ERROR' and exposed else ('P1' if s.status=='APPROVED' or linked else ('P2' if s.status in {'SUPERSEDED','STALE','REJECTED','INVALID'} else 'UNKNOWN'))
            logs=[dict(id=a.id,action=a.action,actor=a.actor,created_at=a.created_at,details=a.payload_json) for a in db.scalars(select(AuditLog).where(AuditLog.entity_id==s.id))]
            retained=OUT/'history_stored_text'/f'{r.id}.txt';retained.parent.mkdir(exist_ok=True);retained.write_text(r.raw_text or '',encoding='utf-8')
            rawpath=(ROOT/r.raw_html_path).resolve() if r.raw_html_path else None
            rows.append(dict(record_type='Signal',id=s.id,trigger_rule=dict(stored_type=s.signal_type,stored_semantic=(s.payload_json or {}).get('business_semantics'),stored_payload=s.payload_json,created_by=s.created_by,prompt_version=s.prompt_version,candidate_reason=old['reason'],recomputed=sem),source_record=dict(id=r.id,url=r.url,title=r.title,version=r.version_number,published_at=r.published_at,collected_at=r.collected_at,verification_status=r.verification_status,publication_basis=(r.metadata_json or {}).get('publication_date'),body_sha256=text_contract(r)['body_sha256'],stored_text_copy=str(retained),raw_html_path=r.raw_html_path,snapshot_exists=bool(rawpath and rawpath.is_relative_to(ROOT) and rawpath.is_file()),raw_sha256=digest(rawpath) if rawpath and rawpath.is_relative_to(ROOT) and rawpath.is_file() else None,issues=record_issues(r)),company_id=s.company_id,company_name=s.company.company_name,signal_status=s.status,verification_status=s.verification_status,signal_published_at=s.published_at,signal_collected_at=s.collected_at,stored_fact=s.fact_summary,stored_inference=s.inference_summary,history_audit_logs=logs,evidence=evidence,signal_issues=issues,current_actionability=compute_signal_actionability(db,s),opportunities=downstream,opportunity_candidates=[dict(id=c.id,status=c.status) for c in ocands if s.id in (c.signal_ids_json or [])],pain_point_ids=old['pain_point_ids'],readiness=ready[s.company_id],classification=category,severity=severity,basis=basis,human_review='PENDING_HUMAN_REVIEW'))
        db.rollback()
    engine.dispose()
    save('risk_audit.json',dict(at=datetime.now(timezone.utc),mode='READ_ONLY',count=len(rows),classifications=Counter(r['classification'] for r in rows),severities=Counter(r['severity'] for r in rows),p0_ids=[r['id'] for r in rows if r['severity']=='P0'],signals=rows))
    print(json.dumps(dict(count=len(rows),classifications=Counter(r['classification'] for r in rows),severities=Counter(r['severity'] for r in rows),p0_ids=[r['id'] for r in rows if r['severity']=='P0'])))
def history():
    import m2_01_evidence_inventory as inv
    inv.OUT=OUT
    return inv.main()
def discovery():
    from app.collectors.crawl_policy import SafeFetch
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin, urlsplit
    targets=['https://github.com/MicrosoftDocs/azure-docs/blob/main/LICENSE','https://github.com/MicrosoftDocs/power-automate-docs/blob/main/LICENSE','https://www.energy.gov/cmei/technologycommercialization']
    rows=[]
    for i,url in enumerate(targets):
        client=SafeFetch({urlsplit(url).hostname},timeout=8,max_requests=6)
        row=dict(url=url,at=datetime.now(timezone.utc))
        try:
            resp=client.get(url)
            path=OUT/('discovery_'+str(i)+'.html');path.write_bytes(resp.body)
            soup=BeautifulSoup(resp.text(),'html.parser')
            row.update(status=resp.status,snapshot=str(path),text=soup.get_text(' ',strip=True),links=[dict(text=a.get_text(' ',strip=True),url=urljoin(resp.final_url,a['href'])) for a in soup.select('a[href]') if any(w in a.get_text(' ',strip=True).lower() for w in ['fund','manufactur','proposal','opportunit','copyright','creative','license'])])
        except Exception as e: row['error']=str(e)
        row.update(requests=client.requests,response_bytes=client.bytes)
        rows.append(row);save('discovery_license.json',rows)
        print(json.dumps({k:v for k,v in row.items() if k not in {'text','links'}},default=str),flush=True)
def collect():
    risk=json.loads((OUT/'risk_audit.json').read_text(encoding='utf-8'))
    assert not risk['p0_ids'], 'P0 STOP: no new collection allowed'
    os.environ['DATABASE_URL']='sqlite:///'+(OUT/'acceptance.db').as_posix()
    os.environ['ENABLE_SCHEDULER']='false'
    os.environ['LLM_API_KEY']=''
    from app.core.config import settings
    settings.llm_api_key=None
    assert settings.real_data_only and settings.no_fake_data and settings.no_auto_approval
    from app.db import model_imports
    from app.db.base import Base
    from sqlalchemy import create_engine,select
    from sqlalchemy.orm import Session
    from app.collectors import web
    from app.services import evidence_integrity as ei
    from app.services.extractor import parse_html
    from app.services.collection_engine import persist_collected
    from app.analyzers.extractor import run_extractor
    from app.analyzers.signal_rules import run_signal_rules
    from app.models.source import Source
    from app.models.signal import Signal,SignalCandidate,SignalEvidence
    from app.services.business_semantics import classify_business_text,bind_semantics_to_subject
    web.BASE_DIR=OUT;ei.BASE_DIR=OUT
    policy=next(r for r in json.loads((OUT/'discovery.json').read_text(encoding='utf-8')) if r['url']=='https://www.energy.gov/web-policies')
    assert policy['status']==200 and 'Public domain information may be freely distributed and copied' in policy['text']
    urls=[
      ('FUNDING_CALL','https://www.energy.gov/articles/energy-department-announces-293-million-funding-support-genesis-mission-national-science'),
      ('FUNDING_CALL','https://www.energy.gov/articles/energy-department-announces-500-million-strengthen-domestic-critical-materials-processing'),
      ('APPLICATION_SOLICITATION','https://www.energy.gov/cmei/articles/energy-department-solicits-applications-program-strengthen-us-manufacturing-sector'),
      ('REQUESTS_FOR_INFORMATION','https://www.energy.gov/oe/funding-opportunities-and-requests-information'),
      ('FUNDING_CALL','https://www.energy.gov/indianenergy/current-funding-and-technical-assistance-opportunities'),
    ]
    save('planned_urls.json',urls)
    old={r['url'] for r in json.loads((OUT.parent/'t10_c1_2/collection.json').read_text(encoding='utf-8')) if r.get('business_fetch_success')}
    assert len(urls)==len({u for _,u in urls}) and not old & {u for _,u in urls}
    engine=create_engine(os.environ['DATABASE_URL']);Base.metadata.create_all(engine)
    results=[]
    with Session(engine) as db:
        for kind,url in urls:
            row=dict(url=url,source_type=kind,publisher='U.S. Department of Energy',permission_basis='DOE government public-domain text; attributed local factual research; excludes third-party protected materials',permission_url=policy['url'],permission_snapshot=policy['snapshot'],permission_sha256=digest(Path(policy['snapshot'])),human_review='PENDING_HUMAN_REVIEW',attempted_at=datetime.now(timezone.utc))
            try:
                source=Source(name='R1 DOE isolated '+kind,source_type='GOVERNMENT',base_url=url,collector_type='web_page')
                db.add(source);db.flush()
                item=web.WebPageCollector(source,{'url':url,'max_retries':0}).fetch()[0]
                row.update(collected_item=dict(published_at=item.published_at,publication_date=item.extra.get('publication_date'),parse_status=item.parse_status),robots='ALLOWED_BY_SAFEFETCH')
                if item.parse_status!='PARSE_SUCCESS' or len(item.raw_text or '')<300:raise ValueError('BUSINESS_BODY_NOT_AVAILABLE: '+str(item.error_message))
                record,_=persist_collected(db,source,item);stats=run_extractor(db,record);db.commit()
                body=record.raw_text;path=OUT/'raw'/f'{record.id}.txt';path.parent.mkdir(exist_ok=True);path.write_text(body,encoding='utf-8')
                sem=classify_business_text(body)
                candidates=list(db.scalars(select(SignalCandidate).where(SignalCandidate.source_record_id==record.id)))
                signals=list(db.scalars(select(Signal).where(Signal.source_record_id==record.id)))
                evidence=list(db.scalars(select(SignalEvidence).where(SignalEvidence.source_record_id==record.id)))
                # Review excerpts are not formal Evidence and do not represent human approval.
                marks=[]
                for needle in ['applications','proposals','deadline','funding opportunity','Request for Information','closed','awards','manufacturing']:
                    start=body.lower().find(needle.lower())
                    if start>=0:
                        a=max(0,start-90);b=min(len(body),start+240)
                        marks.append(dict(kind='REVIEW_EXCERPT',excerpt=body[a:b],start=a,end=b,exact=ei.exact_reference(body,body[a:b],a,b)))
                    if len(marks)>=3:break
                if not marks:marks=[dict(kind='REVIEW_EXCERPT',excerpt=body[:250],start=0,end=250,exact=True)]
                snapshot=OUT/record.raw_html_path
                parsed=parse_html(record.url,record.url,200,'text/html',snapshot.read_text(encoding='utf-8'))
                assert parsed.text==body, 'SNAPSHOT_BODY_MISMATCH'
                row.update(success=True,record_id=record.id,title=record.title,source_id=source.id,final_url=record.url,body_path=str(path),raw_html_path=str(snapshot),raw_sha256=digest(snapshot),body_sha256=ei.text_contract(record)['body_sha256'],content_hash=record.content_hash,version=record.version_number,published_at=record.published_at,collected_at=record.collected_at,publication_date=record.metadata_json.get('publication_date'),semantic=sem,system_subject=record.company.company_name if record.company else 'UNKNOWN',event_subject='UNKNOWN_PENDING_HUMAN_REVIEW',event_role='FUNDING_PUBLISHER_NOT_PURCHASER',event_at='UNKNOWN',deadline='UNKNOWN_PENDING_EVENT_LEVEL_REVIEW',opportunities=[],record_issues=ei.record_issues(record),stats=stats.__dict__,rule_drafts=[d.__dict__ for d in run_signal_rules(body,'GOVERNMENT')],candidates=[dict(id=c.id,type=c.candidate_type,status=c.status,excerpt=c.evidence_text,start=c.start_offset,end=c.end_offset,exact=ei.exact_reference(body,c.evidence_text,c.start_offset,c.end_offset),structured=c.structured_json) for c in candidates],signals=[dict(id=s.id,type=s.signal_type,status=s.status,published_at=s.published_at,payload=s.payload_json) for s in signals],evidence=[dict(id=e.id,record_id=e.source_record_id,excerpt=e.quoted_text,start=e.start_offset,end=e.end_offset,exact=ei.exact_reference(body,e.quoted_text,e.start_offset,e.end_offset)) for e in evidence],review_excerpts=marks)
                assert not any(s.status=='APPROVED' for s in signals)
                assert all(c['exact'] for c in row['candidates'] if c['excerpt'])
                assert all(e['exact'] for e in row['evidence'])
                assert not row['record_issues']
            except Exception as exc:
                db.rollback();row.update(success=False,error=str(exc))
            results.append(row);save('collection.json',results)
            print(json.dumps({k:row.get(k) for k in ['url','success','error','record_id','title','published_at','semantic']},default=str),flush=True)
            if row.get('error') in {'SNAPSHOT_BODY_MISMATCH'}:
                save('stop.json',{'reason':row['error'],'url':url});break
    engine.dispose()
def verify():
    from bs4 import BeautifulSoup
    from app.services.extractor import parse_html,extract_signal_hits
    from app.services.publication_dates import publication_from_html,parse_date_literal
    from app.analyzers.signal_rules import run_signal_rules
    from app.services.business_semantics import classify_business_text,term_mentions
    from app.services.evidence_integrity import exact_reference
    from app.services.procurement_parser import parse_deadline,parse_procurement_lifecycle
    samples=json.loads((OUT/'collection.json').read_text(encoding='utf-8'))
    checked=[]
    with sqlite3.connect((OUT/'acceptance.db').as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        for sample in samples:
            if not sample.get('success'):continue
            record=dict(db.execute('select * from source_records where id=?',(sample['record_id'],)).fetchone())
            html=Path(sample['raw_html_path']).read_text(encoding='utf-8')
            body=record['raw_text'];soup=BeautifulSoup(html,'html.parser')
            page=parse_html(sample['url'],sample['final_url'],200,'text/html',html)
            assert page.text==body and hashlib.sha256(body.encode()).hexdigest()==sample['body_sha256']
            assert digest(Path(sample['raw_html_path']))==sample['raw_sha256']
            dates=[]
            for tag in soup.select('meta[property="article:published_time"], [itemprop="datePublished"], article .display-date'):
                literal=tag.get('content') or tag.get('datetime') or tag.get_text(' ',strip=True)
                dates.append(dict(literal=literal,basis='META_PUBLISHED' if tag.name=='meta' else 'ARTICLE_DISPLAY_DATE',parsed=parse_date_literal(literal)))
            dayvalues={v['parsed']['value'][:10] for v in dates if v['parsed']['value']}
            # Compare source calendar dates; timezone alone is not a conflict.
            conflict=len(dayvalues)>1
            rawdate=page.publication_metadata['value']
            expected=datetime.fromisoformat(rawdate)
            if expected.tzinfo:expected=expected.astimezone(timezone.utc).replace(tzinfo=None)
            assert datetime.fromisoformat(record['published_at'])==expected
            refs=[*sample['review_excerpts'],*sample['candidates'],*sample['evidence']]
            for e in refs:assert exact_reference(body,e['excerpt'],e['start'],e['end'])
            deadline=parse_deadline(body)
            checked.append(dict(id=sample['record_id'],url=sample['url'],raw_sha256=sample['raw_sha256'],body_sha256=sample['body_sha256'],version=sample['version'],body_equals_reparsed_snapshot=True,publication_candidates=dates,date_conflict=conflict,publication_status='CONFLICT_REQUIRES_HUMAN_REVIEW' if conflict else 'EXTRACTED_UNVERIFIED_DOCUMENT_DATE',collected_item_published=sample['collected_item']['published_at'],source_record_published=record['published_at'],date_transfer_pass=True,system_deadline=deadline,system_lifecycle=parse_procurement_lifecycle(body,deadline=deadline),event_at='UNKNOWN',references=refs,reference_count=len(refs),semantic=sample['semantic'],signals=sample['signals'],opportunities=sample['opportunities'],signal_opportunity_date_chain='NOT_EXERCISED_NO_REAL_SIGNALS_OR_OPPORTUNITIES',original_meta=page.publication_metadata))
    original=json.loads((OUT.parent/'t10_c1_2/collection.json').read_text(encoding='utf-8'))
    previous=list({r['url']:r for r in original if r.get('business_fetch_success')}.values())
    packet=json.loads((OUT.parent/'t10_c1_2/human_review_packet.json').read_text(encoding='utf-8'))
    oldchecked=[]
    for r in previous:
        htmlpath=OUT.parent/'t10_c1_2'/r['raw_html_path'];html=htmlpath.read_text(encoding='utf-8')
        page=parse_html(r['url'],r['final_url'],200,'text/html',html)
        assert hashlib.sha256(page.text.encode()).hexdigest()==r['body_sha256']
        refs=[dict(kind='ORIGINAL_CANDIDATE',**c) for c in r['candidates']]+[dict(kind='ORIGINAL_REVIEW_EXCERPT',**e) for e in next(p for p in packet if p['source_record_id']==r['source_record_id'])['exact_excerpts']]
        for e in refs:assert exact_reference(page.text,e['excerpt'],e['start'],e['end'])
        drafts=[d.__dict__ for d in run_signal_rules(page.text,'GOVERNMENT')]
        hits=[h.__dict__ for h in extract_signal_hits(page)]
        assert not any(d['signal_type']=='AUTOMATION_DEMAND' for d in drafts)
        oldchecked.append(dict(id=r['source_record_id'],url=r['url'],publisher=r['publisher'],title=r['title'],raw_html_path=str(htmlpath),body_path=r['body_path'],raw_sha256=digest(htmlpath),body_sha256=r['body_sha256'],version=r['text_version'],collected_at=r['collected_at'],original_stored_published=r['published_at'],publication=page.publication_metadata,semantic=classify_business_text(page.text),rule_drafts=drafts,legacy_hits=hits,references=refs,reference_count=len(refs),network_requests=0,mode='OFFLINE_ORIGINAL_VERSION_NO_PERSISTENCE'))
    assert len(checked)==5 and len(oldchecked)==3
    oldurls={r['url'] for r in oldchecked};newurls={r['url'] for r in checked}
    assert not oldurls&newurls
    save('verification.json',dict(at=datetime.now(timezone.utc),new=checked,previous=oldchecked,new_unique_urls=len(newurls),old_unique_urls=len(oldurls),overlap=[],reference_count=sum(r['reference_count'] for r in checked+oldchecked),exact_reference_count=sum(r['reference_count'] for r in checked+oldchecked),date_conflicts=[r['id'] for r in checked if r['date_conflict']],formal_evidence_count=sum(len(r['evidence']) for r in samples),human_review_completed=0))
    print(json.dumps(dict(new_versions=5,old_versions=3,references=sum(r['reference_count'] for r in checked+oldchecked),date_conflicts=sum(r['date_conflict'] for r in checked))))
def reports():
    def read(n):return json.loads((OUT/n).read_text(encoding='utf-8'))
    def link(p,label):return '['+label+']('+str(p).replace('\\','/')+')'
    def esc(v):return str(v).replace('|','\\|').replace('\n',' ')
    audit=read('risk_audit.json');verify=read('verification.json');samples=read('collection.json');gate=read('evidence_inventory.json')
    before=read('integrity_before.json');after=read('integrity_after.json')
    assert before==after
    fbefore=read('files_before.json');fafter=read('files_after.json')
    existing_changes={k:dict(before=v,after=fafter[k]) for k,v in fbefore.items() if v!=fafter[k] and k!='backend/scripts/t10_c1_2_r1.py'}
    assert not existing_changes
    assert read('archives_before.json')==read('archives_after.json')
    save('protection_result.json',dict(production_tables=len(before['tables']),historical_raw_files=len(before['raw']),tables_and_raw_equal=True,existing_files_changed=existing_changes,prior_archives_equal=True,gate_checks=gate['gate_checks'],allowed_new_script='backend/scripts/t10_c1_2_r1.py',interaction_delta=0))
    related=(OUT/'related_pytest.txt').read_text(encoding='utf-16') if (OUT/'related_pytest.txt').read_bytes().startswith(b'\xff\xfe') else (OUT/'related_pytest.txt').read_text(encoding='utf-8')
    full=(OUT/'full_pytest.txt').read_text(encoding='utf-16') if (OUT/'full_pytest.txt').read_bytes().startswith(b'\xff\xfe') else (OUT/'full_pytest.txt').read_text(encoding='utf-8')
    related_result=related.strip().splitlines()[-1];full_result=full.strip().splitlines()[-1]
    assert '232 passed' in related_result and '743 passed' in full_result and 'failed' not in full_result
    lines=['# T10-C1.2-R1：116 条历史风险只读审计','', '执行日期：2026-10-13（Asia/Shanghai）。116 条是上一轮 production_impact.json 的 **Signal ID 集合**，逐 ID 集合一致，不是 116 条已确认错误。正式库 URI mode=ro + PRAGMA query_only，ORM autoflush=False，未修改历史状态。','',
      '|分类|数量|','|---|---:|']
    for k in ['CONFIRMED_ERROR','CONFIRMED_SAFE','REQUIRES_HUMAN_REVIEW','INSUFFICIENT_EVIDENCE']:lines.append(f'|{k}|{audit["classifications"].get(k,0)}|')
    lines+=['','|严重度|数量|','|---|---:|']
    for k in ['P0','P1','P2','UNKNOWN']:lines.append(f'|{k}|{audit["severities"].get(k,0)}|')
    lines+=['','2 条 CONFIRMED_ERROR 仅确认已存引用偏移不等于已存正文切片，并非确认采购语义错误；其缺失历史快照仍不能恢复原事件真值。这两条已在既有隔离范围内，不是新发现未隔离 P0。其余 114 条证据不足：其中大量旧 Signal 没有正式 SignalEvidence；不能以新规则或 SUPERSEDED 状态宣布其原语义安全。CONFIRMED_SAFE / REQUIRES_HUMAN_REVIEW 为 0，是按证据条件所得，不是强制均分。所有记录仍需要真实审核，没有模型签字。','',
      'P1 为 6 条历史 APPROVED Signal，关联 3 个 Opportunity；当前三者均 INVALID_EVIDENCE，企业 validation_ready/contact_ready 均 false。华南理工历史机会仍保存 APPROVED / CONTACTED，这是历史状态，不证明当前允许触达；既有 Interaction 仅只读保护，本轮新增 0。P2 为 110 条已 SUPERSEDED、无关联当前机会的历史低风险记录；低风险仅针对当前行动影响，不等于确认原信号正确。','',
      '当前 Actionability：'+esc(dict(Counter(r['current_actionability'] for r in audit['signals'])))+'。已证实影响当前可行动机会的 P0=0；不能由此宣布历史风险清零。汉邦激光仍按原 6/9/16/4 隔离门禁禁止验证与联系。','',
      '完整机器材料：'+link(OUT/'risk_audit.json','risk_audit.json')+'。包含真实 ID、旧规则/payload、重算诊断、记录版本/正文哈希/快照存在性、准确引用/偏移、历史审核日志、痛点与候选关联、下游机会及其他信号、当前行动及就绪状态。保留的 history_stored_text 只复制正式库已存正文，不替代缺失历史 HTML。','',
      '|Signal ID|SourceRecord|旧类型/状态|分类 / 严重度|Evidence IDs|Opportunity IDs|Actionability|验证/联系|','|---|---|---|---|---|---|---|---|']
    for r in audit['signals']:
        lines.append('|'+ '|'.join(map(esc,[r['id'],r['source_record']['id'],r['trigger_rule']['stored_type']+'/'+r['signal_status'],r['classification']+'/'+r['severity'],','.join(e['id'] for e in r['evidence']) or 'NONE',','.join(o['id'] for o in r['opportunities']) or 'NONE',r['current_actionability'],str(r['readiness']['validation_ready'])+'/'+str(r['readiness']['contact_ready'])]))+'|')
    lines+=['','## 逐条依据与下游','']
    for r in audit['signals']:
        lines += [f'### {r["id"]}','',f'- 原始来源：{link(r["source_record"]["url"],r["source_record"]["title"] or "原文")}；企业：{r["company_name"]}。',f'- 分类依据：{r["basis"]}；原版本快照：{r["source_record"]["snapshot_exists"]}；版本：{r["source_record"]["version"]}；正文 SHA256：`{r["source_record"]["body_sha256"]}`。',f'- 证据问题：{esc(r["signal_issues"])}；新规则仅诊断：{r["trigger_rule"]["recomputed"]["classification"]}；历史标志：{r["trigger_rule"]["recomputed"]["historical"]}。',f'- PainPoint：{esc(r["pain_point_ids"])}；OpportunityCandidate：{esc(r["opportunity_candidates"])}；审批日志 {len(r["history_audit_logs"])} 条，actor/动作/时间/原 payload 见 JSON；没有独立真人审核结论。','']
    lines+=['## 需要单独授权的历史修复步骤','', '本轮不执行修复。先由真实审核人确认两条偏移错误及 6 条 P1 的原版本证据；缺失快照只接受可信历史备份，不使用当前在线页面顶替。另立授权任务后备份正式库、限定 ID、修复版本与精确引用、检查下游依赖，记录逐行 before/after 和可回滚日志。恢复验证或联系就绪必须另经正式人工审批，不能因为本轮测试通过解除隔离。','', 'R1 历史审计覆盖完成；真实性恢复/历史批准修正仍 BLOCKED。']
    (OUT.parent/'T10-C1_2_R1_116_RISK_AUDIT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    packet=['# T10-C1.2-R1：独立人工审核包','', '全部 **PENDING_HUMAN_REVIEW**，真实审核 0/8。Codex 只准备材料；自动复核与 pytest 不计真人审核。审查材料结论与正式 Signal APPROVE 是两个动作，本包填写不会自动批准。','', '建议优先核查 5 条：Genesis 资助征集（日期冲突）、制造业申请征集（明确合作申请）、OE RFP/RFI 混合历史页面、此前 NIST counterpart 样本、此前 DOE 历史意向公告。企业能力样本尚缺，不能声称这些类别完整覆盖。','']
    allrows=[]
    for v in verify['new']:
        s=next(s for s in samples if s['record_id']==v['id'])
        allrows.append(dict(id=v['id'],url=v['url'],publisher=s['publisher'],title=s['title'],raw_html_path=s['raw_html_path'],body_path=s['body_path'],body_sha256=s['body_sha256'],raw_sha256=s['raw_sha256'],version=s['version'],collected_at=s['collected_at'],publication=v['original_meta'],date_candidates=v['publication_candidates'],date_status=v['publication_status'],semantic=v['semantic'],references=v['references'],system_signals=s['signals'],system_candidates=s['candidates'],system_subject=s['system_subject'],disputes=['FUNDING_IS_NOT_PROCUREMENT','PUBLISHER_IS_NOT_BUYER','EVENT_LEVEL_DEADLINE_AND_STATUS_REQUIRE_REVIEW']+(['PUBLICATION_CONFLICT'] if v['date_conflict'] else []),reviewer=None,reviewed_at=None,judgment=None,basis=None,opinion=None,signature=None,status='PENDING_HUMAN_REVIEW'))
    for v in verify['previous']:
        allrows.append({**v,'date_candidates':[],'date_status':'REPARSED_ORIGINAL_DOCUMENT_DATE_NOT_HUMAN_CONFIRMED','system_signals':[],'system_candidates':'Original candidate preserved; see references','system_subject':'UNKNOWN','disputes':['ORIGINAL_STANDARD_DATE_UNKNOWN','OLD_DATE_NOT_RETROACTIVELY_REPAIRED','FUNDING_IS_NOT_PROCUREMENT','PUBLISHER_IS_NOT_BUYER'],'reviewer':None,'reviewed_at':None,'judgment':None,'basis':None,'opinion':None,'signature':None,'status':'PENDING_HUMAN_REVIEW'})
    save('human_review_packet.json',allrows)
    for r in allrows:
        packet += [f'## {r["id"]} — {r["title"]}','',f'发布方：{r["publisher"]}；{link(r["url"],"真实原始来源")}。',f'{link(r["raw_html_path"],"原始 HTML")}；{link(r["body_path"],"同版本清洗正文")}。版本 {r["version"]}；采集时间（UTC）：{r["collected_at"]}。',f'正文 SHA256：`{r["body_sha256"]}`；原文 SHA256：`{r["raw_sha256"]}`。',f'发布时间及依据：{esc(r["publication"])}。日期状态：{r["date_status"]}；其他明确日期：{esc(r["date_candidates"])}。',f'主体系统标签：{r["system_subject"]}；事件主体、采购方/供应商/代理/合作方角色：UNKNOWN，发布方不能自动继承购买意图。',f'系统实际语义：{r["semantic"]["classification"]} / {r["semantic"]["demand_level"]}；正式 Signal：{esc(r["system_signals"])}；候选：{esc(r["system_candidates"])}。',f'争议：{esc(r["disputes"])}。事件时间和截止时间须逐事件引用并核实，不能使用采集时间或页面创建日期。','', '|精确引用（完整内容）|起始|结束|同版本切片|','|---|---:|---:|---|']
        for e in r['references']:packet.append(f'|{esc(e["excerpt"])}|{e["start"]}|{e["end"]}|PASS|')
        packet += ['', '审核人：________；审核时间（含时区）：________；签字/确认记录：________。', '', '|判断项|真人结论|依据/意见|','|---|---|---|','|来源、原版本及精确引用|待填写|待填写|','|事件主体及采购/供给/合作角色|待填写|待填写|','|术语/供给/招聘/明确需求/推断/未知|待填写|待填写|','|原始发布时间与事件时间、截止时间|待填写|待填写|','|当前状态与是否允许进入验证|待填写|待填写|','', '最终判断：________；审核依据：________；意见：________。未填写前保持 PENDING_HUMAN_REVIEW。','']
    (OUT.parent/'T10-C1_2_R1_HUMAN_REVIEW_PACKET.md').write_text('\n'.join(packet)+'\n',encoding='utf-8')
    report=['# T10-C1.2-R1：真实来源小批次复验','', '执行日期：2026-10-13（Asia/Shanghai）。**R1 BLOCKED / TECHNICAL_REVALIDATION_INCOMPLETE / HUMAN_REVIEW_PENDING**。未发现已证实影响当前可行动机会的 P0；没有声称整个 T10-C1.2 通过。T10-C1.2 保持 FAIL / 待复验，T10-C2 继续 BLOCKED，下一轮扩量未授权，本轮结束后停止。','',
      '本轮读完三份前报告及采集、规则、提取、日期、Evidence、Actionability、readiness、审核/隔离代码。只新增验收脚本与报告/证据目录，未开发产品功能、未修改现有业务实现。Git 起始已有大量未提交修改，全部保留。','',
      '## 真实来源与去重','', '新增 5 个不同真实业务 URL，均与原 3 个样本不重叠，合计 8 个独立版本。全部使用 SafeFetch → WebPageCollector → persist_collected → run_extractor，独立 acceptance.db 和原文目录；LLM disabled，REAL_DATA_ONLY / NO_FAKE_DATA / NO_AUTO_APPROVAL 均 true。HTTP 5/5 成功；RSS/Crawl4AI 真实采集 0，静态页无需 JS。robots、固定公网 IP/TLS、逐跳检查、限频、大小和超时保护未放宽。','',
      'DOE 许可：'+link('https://www.energy.gov/web-policies','官方 Web Policies')+' 的政府信息公开复制条款；保留政策快照及 SHA256，署名本地事实研究，排除第三方版权材料。正文不是普通宣传首页，分别包含资助申请、制造合作申请、RFP/RFI 与具体截止历史条目。资助金额不是采购预算，资助方不是企业买方。','',
      '|真实 ID / URL|业务类型|系统语义|标准发布时间（UTC）|日期检查|','|---|---|---|---|---|']
    for s in samples:
        v=next(v for v in verify['new'] if v['id']==s['record_id'])
        report.append('|'+ '|'.join(map(esc,[link(s['url'],s['record_id']),s['source_type'],s['semantic']['classification']+'/'+s['semantic']['demand_level'],s['published_at'],v['publication_status']]))+'|')
    report+=['','逐条来源类型、发布方、许可及版本、原始 HTML/清洗正文、采集/发布时间、哈希、准确引用、主体角色 UNKNOWN 和真实输出见 '+link(OUT/'collection.json','collection.json')+' 与 '+link(OUT/'verification.json','verification.json')+'。','',
      '**覆盖缺口**：新增中至少 2 条明确资助/合作申请征集（不是企业采购）；直接企业采购 0。企业产品/服务能力来源 0/2；不能把政府资助页计为企业供给。NIST policy/news 与 GitHub/raw GitHub 独立文档许可证 SafeFetch 网络失败；Microsoft Learn 通用许可有非商业限制，未准入其产品文档。额外 DOE 技术商业化路径 404 未计数。没有绕过拒绝，未用模拟页面凑数。DOE/电力、材料、制造、部落能源覆盖不等于充分跨行业验证。若下一任务完成许可核验，应优先补齐 2 条企业能力来源，仍需另行受控授权。','',
      '## 语义与主体角色','', '新增分类：'+esc(dict(Counter(s['semantic']['classification'] for s in samples)))+'；全部 D0/D1，DEMAND_EXPLICIT 0。5 页均正式 Signal 0、候选 0、Opportunity 0、自动批准 0。原 3 个历史快照本轮独立离线重放规则及 legacy extraction；counterpart 未再触发 AUTOMATION_DEMAND；4 处旧引用准确。独立 RPA/ERP/CRM、英文子串、供给/招聘/历史中标、角色及未知日期用本轮 232 项专项测试覆盖，测试夹具不计真实商业来源或人工审核。真实供给/招聘场景尚缺，不能宣称真实覆盖完成。','',
      '发布方 DOE/NIST 与业务主体分离：系统网站标签不作为买方确认。OE 混合页“Request for Proposals”只得到 D1 推断，没有高价值购买事实；关键主体、采购意图、业务角色待人工核实。','',
      '## 日期端到端与新发现','', '5/5 CollectedItem → SourceRecord 按选中明确元数据正确转换 UTC；没有使用采集时间补原发布日期。原时区与字面值存元数据，原始发布时间和正文显示日期同时保留在 verification.json。没有真实 Signal/Opportunity，因此这两层日期链真实验收 **BLOCKED / NOT_EXERCISED**，单元测试通过不冒充端到端真实验证。','',
      '发现 **P1 日期来源冲突**：Genesis、Critical Materials 的 META / JSONLD 为 2026-02-25，但文章 display-date 分别 March 17, 2026 / March 13, 2026；制造业申请公告 META 日期 September 30, 2026，与 display-date October 2, 2026 不同。现行解析首个有效元数据后返回，未暴露后续冲突。未认定哪一方为真、未修改历史或业务代码，审计标为 CONFLICT_REQUIRES_HUMAN_REVIEW，不能声称发布时间准确通过。三者不是因时区差产生的日历差异。','',
      'OE 页面 DOCUMENT 创建日期 2022-05-31，列表内事件日期单独存在，如 7/9/2026 公布、9/7/2026 截止；不能把文档创建或采集时间当该事件日期。Indian Energy 文档创建日期 2023-02-24，不代表所有资助仍有效。事件时间、逐项目截止和当前状态 UNKNOWN / 待核；没有产生 ACTIONABLE_NOW。原 3 条只做留存快照重放，原 acceptance.db 的 UNKNOWN 发布时间未回写修复。','',
      '## Evidence 与历史影响','', f'8 个版本均保留原始 HTML、同版本正文、版本和原文/正文 SHA256；5 个新正文由同版本 HTML 重解析逐字相等。引用 {verify["exact_reference_count"]}/{verify["reference_count"]} 精确，Unicode [start,end) 切片相等，100%。正式 SignalEvidence 0；审核摘录和旧候选引用不能包装成正式 Evidence。116 条历史记录证据问题另列，不混入新样本 100% 指标。缺失历史快照未用在线页面替代。','',
      '116 条审计：CONFIRMED_ERROR 2（已隔离偏移不匹配）、INSUFFICIENT_EVIDENCE 114；P0=0、P1=6、P2=110、UNKNOWN=0。3 个关联机会被 INVALID_EVIDENCE 门禁阻断；没有可确认独立有效购买证据。完整逐条审计见 '+link(OUT.parent/'T10-C1_2_R1_116_RISK_AUDIT.md','116 风险审计')+'。','',
      '## 真人审核','', '真实审核完成 0；全部 8 条 PENDING_HUMAN_REVIEW。已准备原 3 + 新 5 条完整材料，推荐 5 条不同关注点优先审查。'+link(OUT.parent/'T10-C1_2_R1_HUMAN_REVIEW_PACKET.md','真人审核包')+' 内有审核人、时间、依据、判断、意见、签字栏；没有代填结果、没有正式 APPROVE。','',
      '## 本轮实际测试与保护','', '|执行|结果|日志|','|---|---|---|',f'|语义、缩写、角色、日期生命周期、Evidence、审核、采集安全专项 pytest|{related_result}|related_pytest.txt|',f'|全量 pytest|{full_result}|full_pytest.txt|',f'|8 版本 / 精确引用验证|8 版本；{verify["reference_count"]} 引用准确；3 日期冲突|verification.json|','|历史门禁回归|6 SourceRecord / 9 Evidence / 16 Signal / 4 Opportunity；7 gate_checks 全 true|history_gate.txt|','|前端构建|N/A：未改前端、无新增 UI 行为|没有借用旧结果|','',
      '正式库 29 张表排序行哈希与 91 份历史原文文件哈希前后全等，integrity_check ok / foreign_key_check 空；T09、Interaction、审核状态包含在核对中。原 C1.2/P0A 归档逐文件全等，执行前所有既有文件哈希一致，除本轮新脚本开发变化外无既有文件变化。无 reset/clean/提交/推送、客户邮件、Interaction 创建、生产写入或隔离解除。'+link(OUT/'protection_result.json','保护核对')+'；baseline/git/文件与归档清单均存本轮目录。','',
      '工具过程错误如实保留：初次 audit 导入 OpportunityCandidate 路径错误，未执行生产写入，修正后再运行；一次终端正文查看因 GBK UnicodeEncodeError 失败，不影响原文。搜索工具 429/验证码页面未绕过，改用已有 SafeFetch 有界公开路径调查。多次 discovery 最初复用了临时编号，后一次 404 覆盖了 Microsoft 通用政策临时快照；该来源未准入、未计样本、未作许可依据。DOE 已使用的政策 discovery_1.html 哈希复核一致；后续不再写入临时调查文件。','',
      '## 验收判定与停止范围','', '|条件|状态|','|---|---|','|116 条逐项分类及下游风险|PASS（真实性恢复未完成）|','|至少 5 条新增合法真实业务 URL|PASS，5，与旧 3 无重叠|','|缩写误报回归|PASS（历史真实反例 + 专项）|','|真实企业供给不误认采购|BLOCKED，企业能力来源 0/2|','|严重角色误判为零|未发现自动高价值错误，但真人角色核实 BLOCKED|','|原发布时间准确及完整真实下游传递|BLOCKED，3 冲突；正式下游真实链未生成|','|所有被引用新旧复验 Evidence 精确|PASS，审核/候选引用；正式 Evidence 0|','|历史隔离与安全回归|PASS|','|全量 pytest 零失败|PASS，本轮 743 passed|','|正式库/原文/既有修改保护|PASS|','|独立真人审核|BLOCKED，0/8|','',
      '**不放行 TECHNICAL_PASS，也不宣布 T10-C1.2 PASS。** 下轮只可在另行授权后处理日期冲突门禁、补齐 2 个合法企业能力样本、逐事件日期证据和 3–5 条真实审核；不自动进入扩量或 T10-C2。确认当前可行动 P0 时应立即停止并另行授权历史修复；本轮未触发该条件。新增采集已停止。']
    (OUT.parent/'T10-C1_2_R1_REAL_SOURCE_REVALIDATION.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    print(json.dumps(dict(r1='BLOCKED',human_review='PENDING',reports=3,new_urls=5,audited=116)))
if __name__=='__main__':
    {'before':lambda:baseline('before'),'after':lambda:baseline('after'),'audit':audit,'history':history,'discovery':discovery,'collect':collect,'verify':verify,'reports':reports}[sys.argv[1]]()
