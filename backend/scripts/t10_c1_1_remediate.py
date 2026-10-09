"""P0 修复基线/只读影响计划；备份放在 Git 工作目录之外。"""
import hashlib,json,sqlite3,sys,shutil,subprocess
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parent/'docs/reports/t10_c1_1'
OUT.mkdir(parents=True,exist_ok=True)
def sha(data):return hashlib.sha256(data).hexdigest()
def dump(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def inventory(db):
    db.row_factory=sqlite3.Row
    result={}
    for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
        name=row[0];quoted='"'+name.replace('"','""')+'"'
        values=sorted(json.dumps(dict(r),sort_keys=True,ensure_ascii=False) for r in db.execute('SELECT * FROM '+quoted))
        result[name]={'count':len(values),'sha256':sha('\n'.join(values).encode())}
    return result
def baseline():
    backup=ROOT.parent.parent/'bizpulse_backups'/('t10_c1_1_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir(parents=True,exist_ok=False)
    with sqlite3.connect(f'file:{(ROOT/"data/bizpulse.db").as_posix()}?mode=ro',uri=True) as src,sqlite3.connect(backup/'bizpulse.db') as dst:
        src.backup(dst)
    with sqlite3.connect(backup/'bizpulse.db') as db:tables=inventory(db)
    raw={}
    for path in (ROOT/'data/raw').rglob('*'):
        if path.is_file():
            relative=path.relative_to(ROOT);target=backup/relative
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
            raw[str(relative)]=sha(path.read_bytes())
            assert sha(target.read_bytes())==raw[str(relative)]
    tracked={}
    for folder in ('app','tests','scripts'):
        for p in (ROOT/folder).rglob('*.py'):
            tracked[str(p.relative_to(ROOT.parent))]=sha(p.read_bytes())
    dump(OUT/'code_before.json',tracked)
    dump(backup/'manifest.json',{'tables':tables,'raw':raw,'db_sha256':sha((backup/'bizpulse.db').read_bytes())})
    for path in backup.rglob('*'):
        if path.is_file():path.chmod(0o444)
    dump(OUT/'baseline.json',{'backup_path':str(backup),'tables':tables,'raw':raw,'created_at':datetime.now(timezone.utc).isoformat()})
    (OUT/'git_before.txt').write_text(subprocess.run(['git','status','--short'],cwd=ROOT.parent,capture_output=True,text=True,encoding='utf-8').stdout,encoding='utf-8')
    print(json.dumps({'backup':str(backup),'tables':len(tables),'raw_files':len(raw)}))
def plan():
    audit=json.loads((ROOT.parent/'docs/reports/t10_c1_acceptance/evidence_audit.json').read_text(encoding='utf-8'))
    missing={r['record_id'] for r in audit['production_missing_declared_snapshots']}
    bad={r['record_id'] for r in audit['quote_or_offset_errors']}
    results=[]
    with sqlite3.connect(f'file:{(ROOT/"data/bizpulse.db").as_posix()}?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        for rid in sorted(missing|bad):
            r=dict(db.execute('SELECT * FROM source_records WHERE id=?',(rid,)).fetchone())
            evidences=[dict(e) for e in db.execute('SELECT * FROM signal_evidences WHERE source_record_id=?',(rid,))]
            signals=[dict(s) for s in db.execute('SELECT id,status,company_id,signal_type FROM signals WHERE source_record_id=? OR id IN (SELECT signal_id FROM signal_evidences WHERE source_record_id=?)',(rid,rid))]
            deps=[dict(o) for o in db.execute('SELECT DISTINCT o.id,o.primary_signal_id,o.review_status,o.status FROM opportunities o LEFT JOIN opportunity_evidences e ON e.opportunity_id=o.id WHERE e.source_record_id=? OR e.signal_id IN (SELECT id FROM signals WHERE source_record_id=?) OR o.primary_signal_id IN (SELECT id FROM signals WHERE source_record_id=?)',(rid,rid,rid))]
            entries=[]
            for e in evidences:
                text=r['raw_text'] or '';a,b=e['start_offset'],e['end_offset'];quote=e['quoted_text']
                exact=isinstance(a,int) and isinstance(b,int) and 0<=a<b<=len(text) and text[a:b]==quote
                matches=[];pos=0
                while quote and (idx:=text.find(quote,pos))>=0:matches.append(idx);pos=idx+1
                entries.append(dict(evidence_id=e['id'],signal_id=e['signal_id'],stored_offset=[a,b],stored_excerpt=quote,actual_excerpt=text[a:b] if a is not None and b is not None else None,exact=exact,exact_quote_positions=matches,problem_type='OK' if exact else 'INVALID_EVIDENCE'))
            results.append(dict(source_record_id=rid,source_url=r['url'],snapshot_reference=r['raw_html_path'],text_version=r['version_number'],content_hash=r['content_hash'],body_sha256=sha((r['raw_text'] or '').encode()),metadata=json.loads(r['metadata_json'] or '{}'),problem_type=['MISSING_SOURCE_SNAPSHOT']*(rid in missing)+['INVALID_EVIDENCE']*(rid in bad),evidences=entries,downstream_dependency={'signals':signals,'opportunities':deps},proposed_action='QUARANTINE_RECORD_AND_DEPENDENCIES' if rid in missing else 'EXACT_OFFSET_REPAIR_IF_UNIQUE_ELSE_QUARANTINE',requires_human_review=True))
    dump(OUT/'repair_plan.json',results)
    print(json.dumps({'unique_records':len(results),'missing_records':len(missing),'bad_records':len(bad),'evidence_rows':sum(len(r['evidences']) for r in results)},ensure_ascii=False))

def apply_quarantine():
    """只执行已列明的可逆隔离，不修正文/偏移/历史批准结论。"""
    import uuid
    baseline=json.loads((OUT/'baseline.json').read_text(encoding='utf-8'))
    planned=json.loads((OUT/'repair_plan.json').read_text(encoding='utf-8'))
    for filename in ('independent_final.txt','related_final.txt','related_reverse.txt','full_final.txt'):
        log=(OUT/filename).read_text(encoding='utf-8-sig')
        assert 'passed' in log and 'FAILED ' not in log and 'ERROR ' not in log,filename
    backup=Path(baseline['backup_path']);manifest=json.loads((backup/'manifest.json').read_text(encoding='utf-8'))
    assert sha((backup/'bizpulse.db').read_bytes())==manifest['db_sha256']
    assert all((ROOT/path).is_file() and sha((ROOT/path).read_bytes())==digest for path,digest in baseline['raw'].items())
    changes=[];now=datetime.now(timezone.utc).isoformat();actor='system:T10-C1.1-remediation'
    with sqlite3.connect(ROOT/'data/bizpulse.db',timeout=10) as db:
        db.row_factory=sqlite3.Row;db.execute('BEGIN IMMEDIATE')
        assert inventory(db)==baseline['tables'],'Formal DB changed since baseline; stop without writes'
        def change(table,rid,values,reason):
            row=dict(db.execute(f'SELECT * FROM {table} WHERE id=?',(rid,)).fetchone())
            old={key:row[key] for key in values}
            if old==values:return
            aid='aud_'+uuid.uuid4().hex[:24]
            payload={'task':'T10-C1.1','reason':reason,'before':old,'after':values,'reversible':True,'review_required':True}
            db.execute(f'UPDATE {table} SET '+','.join(f'{key}=?' for key in values)+' WHERE id=?',(*values.values(),rid))
            db.execute('INSERT INTO audit_logs (id,action,entity_type,entity_id,actor,payload_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)',(aid,'P0_EVIDENCE_QUARANTINE',table,rid,actor,json.dumps(payload,ensure_ascii=False),now,now))
            changes.append({'table':table,'id':rid,'before':old,'after':values,'reason':reason,'audit_log_id':aid})
        signals=set();opps=set()
        for item in planned:
            rid=item['source_record_id'];row=dict(db.execute('SELECT * FROM source_records WHERE id=?',(rid,)).fetchone())
            assert sha((row['raw_text'] or '').encode())==item['body_sha256']
            meta=json.loads(row['metadata_json'] or '{}')
            state={'status':'QUARANTINED','reasons':item['problem_type'],'task':'T10-C1.1','requires_human_review':True,'quarantined_at':now}
            meta['evidence_integrity']=state
            change('source_records',rid,{'metadata_json':json.dumps(meta,ensure_ascii=False),'verification_status':item['problem_type'][0]},item['problem_type'])
            for entry in item['evidences']:
                reason='INVALID_EVIDENCE' if not entry['exact'] else 'MISSING_SOURCE_SNAPSHOT'
                change('signal_evidences',entry['evidence_id'],{'verification_status':reason},reason)
            signals.update(s['id'] for s in item['downstream_dependency']['signals'])
            opps.update(o['id'] for o in item['downstream_dependency']['opportunities'])
        for sid in sorted(signals):
            row=dict(db.execute('SELECT * FROM signals WHERE id=?',(sid,)).fetchone())
            payload=json.loads(row['payload_json'] or '{}')
            payload['evidence_integrity']={'status':'QUARANTINED','reasons':['INVALID_EVIDENCE_DEPENDENCY'],'task':'T10-C1.1','requires_human_review':True,'quarantined_at':now}
            change('signals',sid,{'payload_json':json.dumps(payload,ensure_ascii=False),'verification_status':'REVIEW_REQUIRED'},'INVALID_EVIDENCE_DEPENDENCY')
        for oid in sorted(opps):
            row=dict(db.execute('SELECT * FROM opportunities WHERE id=?',(oid,)).fetchone())
            notes=json.loads(row['risk_notes'] or '[]')
            if 'INVALID_EVIDENCE_REVIEW_REQUIRED' not in notes:notes.append('INVALID_EVIDENCE_REVIEW_REQUIRED')
            change('opportunities',oid,{'risk_notes':json.dumps(notes,ensure_ascii=False)},'INVALID_EVIDENCE_DEPENDENCY')
        after=inventory(db)
        targeted={'source_records','signal_evidences','signals','opportunities','audit_logs'}
        assert all(after[t]==baseline['tables'][t] for t in baseline['tables'] if t not in targeted)
        # 同一表的非目标记录也必须完全相同，不能只审计整表行数。
        with sqlite3.connect(f'file:{(backup/"bizpulse.db").as_posix()}?mode=ro',uri=True) as old_db:
            old_db.row_factory=sqlite3.Row
            for table in targeted-{'audit_logs'}:
                ids={x['id'] for x in changes if x['table']==table}
                before_rows={r['id']:dict(r) for r in old_db.execute(f'SELECT * FROM {table}') if r['id'] not in ids}
                after_rows={r['id']:dict(r) for r in db.execute(f'SELECT * FROM {table}') if r['id'] not in ids}
                assert before_rows==after_rows,table
        dump(OUT/'formal_changes.json',changes)
        db.commit()
    dump(OUT/'business_after.json',after)
    dump(OUT/'formal_hash_audit.json',{'changed_tables':[t for t in after if after[t]!=baseline['tables'][t]],'non_target_tables_unchanged':True,'non_target_rows_unchanged':True,'raw_files_unchanged':True,'new_records':0,'deleted_records':0,'audit_logs_added':len(changes),'backup_path':str(backup)})
    print(json.dumps({'changes':len(changes),'signals_quarantined':len(signals),'opportunities_quarantined':len(opps),'audit_logs_added':len(changes)}))

def verify_after():
    sys.path.insert(0,str(ROOT))
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.db import model_imports
    from app.models.signal import Signal,SignalEvidence
    from app.models.opportunity import Opportunity
    from app.services.evidence_integrity import signal_issues,opportunity_issues,exact_reference
    from app.services.actionability import compute_signal_actionability
    from app.services.validation_readiness import company_readiness
    from app.analyzers.opportunity.context import load_company_context
    base=json.loads((OUT/'baseline.json').read_text(encoding='utf-8'))
    changes=json.loads((OUT/'formal_changes.json').read_text(encoding='utf-8'))
    engine=create_engine('sqlite:///file:'+ (ROOT/'data/bizpulse.db').as_posix()+'?mode=ro&uri=true')
    results={'signals':[],'opportunities':[],'readiness':[]}
    with Session(engine,autoflush=False) as db:
        cids=set()
        for entry in changes:
            if entry['table']=='signals':
                s=db.get(Signal,entry['id']);issues=signal_issues(db,s)
                assert issues and compute_signal_actionability(db,s)=='INVALID_EVIDENCE'
                results['signals'].append({'id':s.id,'historical_status':s.status,'issues':issues,'actionability':'INVALID_EVIDENCE'})
                cids.add(s.company_id)
            if entry['table']=='opportunities':
                o=db.get(Opportunity,entry['id']);issues=opportunity_issues(db,o);assert issues
                results['opportunities'].append({'id':o.id,'issues':issues,'review_status_preserved':o.review_status})
        for cid in sorted(cids):
            readiness=company_readiness(db,cid)
            ctx=load_company_context(db,cid)
            assert all(not signal_issues(db,sc.signal) for sc in ctx.signals)
            results['readiness'].append({'company_id':cid,'validation_ready':readiness['validation_ready'],'contact_ready':readiness['contact_ready'],'usable_signal_ids':[sc.signal.id for sc in ctx.signals]})
    engine.dispose()
    with sqlite3.connect(f'file:{(ROOT/"data/bizpulse.db").as_posix()}?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        after=inventory(db)
        expected=json.loads((OUT/'business_after.json').read_text(encoding='utf-8'));assert after==expected
        raw={path:sha((ROOT/path).read_bytes()) for path in base['raw']}
        assert raw==base['raw']
        snapshot_missing=[];invalid_unquarantined=[];exact=0
        for e in db.execute('SELECT e.*,r.raw_text,r.metadata_json FROM signal_evidences e JOIN source_records r ON e.source_record_id=r.id'):
            good=exact_reference(e['raw_text'] or '',e['quoted_text'],e['start_offset'],e['end_offset'])
            exact+=good
            if not good and e['verification_status']!='INVALID_EVIDENCE':invalid_unquarantined.append(e['id'])
        assert not invalid_unquarantined
        for r in db.execute('SELECT id,raw_html_path,verification_status FROM source_records WHERE raw_html_path IS NOT NULL'):
            if not (ROOT/r['raw_html_path']).is_file():
                assert r['verification_status']=='MISSING_SOURCE_SNAPSHOT'
                snapshot_missing.append(r['id'])
        results['evidence']={'exact_offsets_preserved':exact,'invalid_unquarantined':invalid_unquarantined,'missing_snapshots_isolated':snapshot_missing}
    before_code=json.loads((OUT/'code_before.json').read_text(encoding='utf-8'))
    after_code={str(p.relative_to(ROOT.parent)):sha(p.read_bytes()) for folder in ('app','tests','scripts') for p in (ROOT/folder).rglob('*.py')}
    results['modified_files']=sorted(k for k,v in after_code.items() if before_code.get(k)!=v)
    dump(OUT/'post_repair_verification.json',results)
    (OUT/'git_after.txt').write_text(subprocess.run(['git','status','--short'],cwd=ROOT.parent,capture_output=True,text=True,encoding='utf-8').stdout,encoding='utf-8')
    print(json.dumps({'blocked_signals':len(results['signals']),'blocked_opportunities':len(results['opportunities']),'non_target_tables':24,'raw_unchanged':True,'invalid_unquarantined':0}))

def offline_proof():
    """离线生成计量，只写临时隔离库；不把夹具统计成真实业务样本。"""
    import tempfile
    from unittest.mock import patch
    sys.path.insert(0,str(ROOT))
    from sqlalchemy import create_engine,select
    from sqlalchemy.orm import Session
    from app.db.base import Base
    from app.db import model_imports
    from app.models.company import Company
    from app.models.source import Source,SourceRecord
    from app.models.signal import SignalCandidate,SignalEvidence
    from app.analyzers.extractor import run_extractor,approve_candidate_manually
    from app.services.evidence_integrity import exact_reference,text_contract
    cases=['离线夹具😀：本公司正在招聘海外销售经理8名。',
           '离线夹具：公司完成B轮融资2亿元。',
           '离线夹具：公司宣布设立海外办事处，拓展欧洲市场。',
           '离线夹具：公司\n正在招聘海外销售经理\u00a0五名。']
    refs=[]
    with tempfile.TemporaryDirectory(prefix='bizpulse-p0-proof-') as directory:
        engine=create_engine('sqlite:///'+str(Path(directory)/'isolated.db'))
        Base.metadata.create_all(engine)
        with Session(engine) as db,patch('app.analyzers.extractor.get_llm_adapter',return_value=None):
            company=Company(company_name='OFFLINE_FIXTURE',normalized_name='offline_fixture')
            source=Source(name='OFFLINE_FIXTURE',source_type='OFFICIAL_WEBSITE',reliability_grade='A',reliability_score=95)
            db.add_all([company,source]);db.flush()
            auto=0
            for index,text in enumerate(cases):
                r=SourceRecord(source_id=source.id,company_id=company.id,url=f'https://example.com/offline/{index}',raw_text=text,content_hash=sha(text.encode()),version_number=1,company_resolve_status='EXACT')
                db.add(r);db.flush();r.metadata_json={'evidence_text_contract':text_contract(r)}
                stats=run_extractor(db,r,force=True);auto+=stats.auto_approved
                candidates=list(db.scalars(select(SignalCandidate).where(SignalCandidate.source_record_id==r.id)))
                assert candidates
                for candidate in candidates:
                    assert candidate.status=='REVIEW_REQUIRED'
                    approve_candidate_manually(db,candidate,actor='offline-test-reviewer',note='仅临时隔离库计量')
            for e in db.scalars(select(SignalEvidence)):
                r=db.get(SourceRecord,e.source_record_id)
                ok=exact_reference(r.raw_text,e.quoted_text,e.start_offset,e.end_offset)
                refs.append({'id':e.id,'start':e.start_offset,'end':e.end_offset,'text_version':r.version_number,'body_sha256':text_contract(r)['body_sha256'],'exact':ok})
        engine.dispose()
    assert refs and all(r['exact'] for r in refs) and auto==0
    dump(OUT/'offline_generation_proof.json',{'synthetic_fixture':True,'real_business_samples':0,'network_requests':0,'production_writes':0,'automatic_approvals':auto,'new_evidence_count':len(refs),'exact_pass_count':sum(r['exact'] for r in refs),'references':refs})
    print(json.dumps({'offline_evidence_count':len(refs),'exact_pass_count':len(refs),'automatic_approvals':0}))
if __name__=='__main__':
    if sys.argv[1]=='baseline':baseline()
    elif sys.argv[1]=='plan':plan()
    elif sys.argv[1]=='apply':apply_quarantine()
    elif sys.argv[1]=='verify':verify_after()
    elif sys.argv[1]=='proof':offline_proof()
