"""明确标记的离线夹具；不计入真实采购/客户样本，无正式库写入。"""
import json,uuid
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
import pytest
from app.db.session import SessionLocal
from app.models.source import Source,SourceRecord
from app.models.company import Company
from app.models.signal import Signal,SignalEvidence,SignalCandidate
from app.models.opportunity import Opportunity,OpportunityEvidence
from app.models.audit import AuditLog
from app.services.evidence_integrity import exact_reference,record_issues,signal_issues,text_contract
from app.services.actionability import compute_actionability_by_rules,compute_signal_actionability
from app.analyzers.extractor import run_extractor,approve_candidate_manually
from app.services.url_safety import assert_no_credentials,safe_url_for_log
from app.collectors.crawl_policy import check_url,CrawlStopped,SafeFetch,Response
from app.collectors import crawl4ai_adapter as crawl

def setup(db):
    uid=uuid.uuid4().hex[:8]
    c=Company(company_name='离线测试企业'+uid,normalized_name=uid,verification_status='VERIFIED')
    s=Source(name='离线测试源'+uid,source_type='OFFICIAL_WEBSITE',reliability_grade='A',reliability_score=95)
    db.add_all([c,s]);db.flush()
    text='离线夹具：本公司正在招聘海外销售经理8名。\n公司完成B轮融资2亿元。'
    r=SourceRecord(source_id=s.id,company_id=c.id,url='https://example.com/news/'+uid,raw_text=text,content_hash=uid,version_number=1,company_resolve_status='EXACT')
    db.add(r);db.flush()
    r.metadata_json={'evidence_text_contract':text_contract(r)}
    return c,s,r

def test_exact_unicode_and_version_guard():
    text='汉字😀\n不换行\u00a0空格'
    assert exact_reference(text,text[2:9],2,9)
    assert not exact_reference(text,text[2:9].encode().decode().replace('\n',' '),2,9)
    assert not exact_reference(text,text[2:9],len(text[:2].encode()),9)
    with SessionLocal() as db:
        _,_,r=setup(db);assert not record_issues(r)
        r.raw_text+='改动';assert 'TEXT_VERSION_OR_HASH_MISMATCH' in record_issues(r)

@pytest.mark.parametrize('enabled',[True,False])
def test_no_auto_approval_environment_is_fail_closed(monkeypatch,enabled):
    from app.core.config import Settings
    monkeypatch.setenv('NO_AUTO_APPROVAL','true' if enabled else 'false')
    if enabled:assert Settings(_env_file=None).no_auto_approval is True
    else:
        with pytest.raises(ValueError):Settings(_env_file=None)

def test_high_confidence_no_auto_approval_and_manual_audit():
    from sqlalchemy import select
    with SessionLocal() as db:
        _,_,r=setup(db);stats=run_extractor(db,r,force=True)
        assert stats.auto_approved==0
        candidates=db.scalars(select(SignalCandidate).where(SignalCandidate.source_record_id==r.id)).all()
        assert candidates and all(c.status=='REVIEW_REQUIRED' for c in candidates)
        assert not db.scalars(select(Signal).where(Signal.source_record_id==r.id)).all()
        for c in candidates:
            assert exact_reference(r.raw_text,c.evidence_text,c.start_offset,c.end_offset)
        signal=approve_candidate_manually(db,candidates[0],actor='offline-test-reviewer',note='离线测试显式审核')
        assert signal.status=='APPROVED'
        audit=db.scalar(select(AuditLog).where(AuditLog.entity_id==signal.id,AuditLog.action=='SIGNAL_HUMAN_APPROVED'))
        assert audit.actor=='offline-test-reviewer' and signal.payload_json['human_review']['reviewed_at']

def test_quarantine_blocks_analysis_approval_scoring_readiness_and_transition(client):
    from app.analyzers.opportunity.context import load_company_context
    from app.services.validation_readiness import company_readiness
    from app.services.evidence_integrity import opportunity_issues
    with SessionLocal() as db:
        c,_,r=setup(db)
        quote=r.raw_text
        sig=Signal(company_id=c.id,source_record_id=r.id,signal_type='HIRING',title='离线夹具',status='APPROVED',published_at=datetime.now(timezone.utc))
        db.add(sig);db.flush()
        e=SignalEvidence(signal_id=sig.id,source_record_id=r.id,quoted_text=quote,start_offset=0,end_offset=len(quote))
        o=Opportunity(company_id=c.id,primary_signal_id=sig.id,title='离线机会',problem='离线',solution='离线',review_status='APPROVED',evidence_score=90)
        db.add_all([e,o]);db.flush()
        db.add(OpportunityEvidence(opportunity_id=o.id,signal_id=sig.id,source_record_id=r.id,evidence_excerpt=quote))
        r.metadata_json={**r.metadata_json,'evidence_integrity':{'status':'QUARANTINED','reasons':['MISSING_SOURCE_SNAPSHOT']}}
        db.commit();sid,oid,cid=sig.id,o.id,c.id
        assert signal_issues(db,sig)
        assert compute_signal_actionability(db,sig)=='INVALID_EVIDENCE'
        assert not load_company_context(db,c.id).signals
        assert not company_readiness(db,c.id)['contact_ready']
        from app.services.market_validation import market_validation_candidates
        assert not any(c.company_name in x.get('company_names',[]) for x in market_validation_candidates(db))
        assert opportunity_issues(db,o)
        assert run_extractor(db,r,force=True).errors
        from app.services.validation import transition_target,validate_opportunity_stage_transition,TransitionDenied
        with pytest.raises(TransitionDenied):validate_opportunity_stage_transition(db,o,'READY',force=True,note='离线强制测试')
        with pytest.raises(TransitionDenied):transition_target(db,SimpleNamespace(opportunity_id=o.id,status='NEW'),'READY_TO_CONTACT',force=True,note='离线强制测试')
    assert client.post(f'/api/v1/signals/{sid}/approve',json={'note':'离线审核'}).status_code==422
    assert client.post(f'/api/v1/opportunities/{oid}/review',json={'action':'ready'}).status_code==422
    assert client.post(f'/api/v1/opportunities/{oid}/review',json={'action':'edit','updates':{'evidence_score':100}}).status_code==422
    assert client.post('/api/v1/opportunities',json={'company_id':cid,'primary_signal_id':sid,'title':'离线夹具新机会','problem':'离线','solution':'离线'}).status_code==422

@pytest.mark.parametrize('url',[
 'https://example.com/?%74oken=OFFLINE_TEST_VALUE',
 'https://example.com/?%2574oken=OFFLINE_TEST_VALUE',
 'https://example.com/?ToKeN=OFFLINE_TEST_VALUE',
 'https://example.com/?q=public&token=OFFLINE_TEST_VALUE&token=OFFLINE_TEST_VALUE',
 'https://name:OFFLINE_TEST_VALUE@example.com/',
 'https://example.com/?next=https%3A%2F%2Fexample.com%2F%3F%2574oken%3DOFFLINE_TEST_VALUE',
])
def test_encoded_credentials_rejected_without_network(url):
    with pytest.raises(ValueError):assert_no_credentials(url)
    with pytest.raises(CrawlStopped):check_url(url,{'example.com'})
    assert 'OFFLINE_TEST_VALUE' not in safe_url_for_log(url)

def test_legal_public_query_kept():
    url='https://example.com/?page=2&q=laser&tokenizer=unicode&next=https%3A%2F%2Fexample.com%2Fnews%3Fid%3D2'
    assert_no_credentials(url);assert check_url(url,{'example.com'})==('example.com',443)

def test_http_redirect_credentials_blocked_before_second_request(monkeypatch):
    from app.services import extractor
    from urllib.robotparser import RobotFileParser
    monkeypatch.setattr(extractor.socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('93.184.216.34',443))])
    robot=RobotFileParser();robot.parse(['User-agent: *','Allow: /'])
    monkeypatch.setattr(SafeFetch,'robot',lambda self,url:robot)
    calls=[]
    def response(self,url):
        calls.append(url)
        return Response(url,url,302,'text/html',b'',{'location':'https://example.com/?%74oken=OFFLINE_TEST_VALUE'})
    monkeypatch.setattr(SafeFetch,'_one',response)
    with pytest.raises(ValueError,match='CREDENTIAL_QUERY_NOT_ALLOWED'):
        extractor.fetch_public_page('https://example.com/public')
    assert len(calls)==1

def test_http_public_query_and_original_url_preserved(monkeypatch):
    from app.services import extractor
    from urllib.robotparser import RobotFileParser
    monkeypatch.setattr(extractor.socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('93.184.216.34',443))])
    robot=RobotFileParser();robot.parse(['User-agent: *','Allow: /'])
    monkeypatch.setattr(SafeFetch,'robot',lambda self,url:robot)
    monkeypatch.setattr(SafeFetch,'_one',lambda self,url:Response(url,url,200,'text/html','<p>离线合法公开URL正文</p>'.encode(),{}))
    url='https://example.com/?page=2&q=laser'
    result=extractor.fetch_public_page(url)
    assert result.url==url and result.final_url==url and '合法公开' in result.text

@pytest.mark.parametrize('mode',['http','js'])
def test_css_preserves_original_cleans_body_and_transmits_date(monkeypatch,tmp_path,mode):
    html='<html><script src="a.js"></script><article><nav>夹具菜单</nav><p>离线夹具业务正文，激光设备发布。</p><footer>夹具页脚</footer></article><time id="pub">2020年01月01日</time><time id="due">2026年12月31日</time></html>'
    monkeypatch.setattr(crawl,'BASE_DIR',tmp_path)
    monkeypatch.setenv('CRAWL4AI_ENABLED','true')
    monkeypatch.setattr(crawl,'site_permission',lambda host:{'status':'ALLOWED','interval_seconds':2,'allowed_path_prefixes':['/']})
    monkeypatch.setattr(SafeFetch,'get',lambda self,url:Response(url,url,200,'text/html',html.encode(),{}))
    monkeypatch.setattr(crawl,'render_guarded',lambda *a,**kw:{'html':html,'bytes':0,'requests':0})
    config={'css_selector':'article','field_css':{'published_at':'#pub','deadline':'#due'}}
    if mode=='js':config.update(mode='js',js_diagnosis={'reason':'JS_RENDER_REQUIRED','marker':'a.js','http_failure':'JS_RENDER_REQUIRED'})
    item=crawl.Crawl4AIAdapter(SimpleNamespace(id='OFFLINE',base_url='https://example.com/news'),config).fetch()[0]
    raw=(tmp_path/item.extra['raw_text_path']).read_text(encoding='utf-8')
    assert '夹具菜单' in raw and '夹具页脚' in raw
    assert '夹具菜单' not in item.raw_text and '夹具页脚' not in item.raw_text
    assert '激光设备发布' in item.raw_text
    assert item.published_at==datetime(2020,1,1) and item.published_at.tzinfo is None
    assert item.extra['structured_fields']['deadline']['value'].startswith('2026-12-31')
    crawl.validate_crawl_evidence(item)
    from app.services.collection_engine import persist_collected
    with SessionLocal() as db:
        source=Source(name='离线渲染'+uuid.uuid4().hex,source_type='TEST',collector_type='crawl4ai')
        db.add(source);db.flush()
        r,_=persist_collected(db,source,item)
        assert r.published_at==datetime(2020,1,1)
        sig=SimpleNamespace(signal_type='NEW_PRODUCT',published_at=r.published_at,collected_at=datetime.now(timezone.utc),payload_json={},source_record=r)
        assert compute_actionability_by_rules(sig)=='WATCH'

def test_metadata_date_missing_standard_field_not_current():
    r=SimpleNamespace(raw_text='离线新闻',metadata_json={'structured_fields':{'published_at':{'status':'EXTRACTED_UNVERIFIED','value':'2020-01-01T00:00:00'}}})
    sig=SimpleNamespace(signal_type='NEW_PRODUCT',published_at=None,collected_at=datetime.now(timezone.utc),payload_json={},source_record=r)
    assert compute_actionability_by_rules(sig)=='WATCH'
    r.metadata_json={};assert compute_actionability_by_rules(sig)=='WATCH'
    sig.signal_type='HIRING';assert compute_actionability_by_rules(sig)=='WATCH'
    sig.published_at=datetime.now(timezone.utc)-timedelta(days=2)
    assert compute_actionability_by_rules(sig)=='ACTIONABLE_NOW'
    sig.signal_type='CONTRACT_AWARD';sig.payload_json={'actionability':{'status':'ACTIONABLE_NOW'}}
    assert compute_signal_actionability(None,sig)=='HISTORICAL_SIGNAL'
