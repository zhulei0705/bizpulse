"""真实采集结果的隔离库版本/去重验收；正式库从不打开写连接。"""
import json
import os
import sys
import uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
TARGET=(ROOT/"data/bizpulse_t10_c1_validation.db").resolve()
assert TARGET != (ROOT/"data/bizpulse.db").resolve()
assert TARGET != (ROOT/"data/bizpulse_test.db").resolve()
os.environ["DATABASE_URL"]="sqlite:///"+TARGET.as_posix()
os.environ["NO_FAKE_DATA"]="true"
sys.path.insert(0,str(ROOT))
from app.db.base import Base
from app.db import model_imports
from app.models.source import Source, SourceRecord
from app.models.signal import Signal
from app.models.opportunity import Opportunity
from app.models.experiment import Interaction
from app.collectors.base import CollectedItem
from app.services.collection_engine import persist_collected
from app.collectors.crawl4ai_adapter import verify_quote
from sqlalchemy import select,func,create_engine,event
from sqlalchemy.orm import sessionmaker
# 显式绑定隔离数据库，不依赖应用 Settings 的环境读取/缓存。
engine=create_engine("sqlite:///"+TARGET.as_posix(),connect_args={"check_same_thread":False})
SessionLocal=sessionmaker(bind=engine,expire_on_commit=False)
@event.listens_for(engine,"connect")
def foreign_keys(connection,record):
    connection.execute("PRAGMA foreign_keys=ON")
OUT=ROOT.parent/"docs/reports/t10_c1"
if __name__ == "__main__":
    assert Path(engine.url.database).resolve()==TARGET
    Base.metadata.create_all(engine)
    rows=[json.loads(line) for line in (OUT/"ab_results.jsonl").read_text(encoding="utf-8").splitlines()]
    manifest=[]
    with SessionLocal() as db:
        source=Source(name="T10-C1真实采集沙盒验收"+uuid.uuid4().hex[:8],source_type="PUBLIC_SANDBOX",collector_type="crawl4ai",enabled=False,reliability_grade="C")
        db.add(source);db.flush()
        for row in rows:
            if "metadata" not in row: continue
            meta=row["metadata"]
            # 从本轮已归档的真实原件恢复；绝不重抓后伪装成旧版本。
            from app.collectors.crawl_policy import digest
            key=digest(row["url"])[:16]
            for field in ("raw_html_path","raw_text_path","cleaned_text_path","rendered_html_path","raw_bytes_path"):
                if field not in meta: continue
                destination=ROOT/meta[field]
                suffix=destination.name.split(".",1)[1]
                archived=OUT/"samples"/f"{key}.new.{suffix}"
                body=archived.read_bytes()
                if destination.exists():
                    assert destination.read_bytes()==body
                else:
                    destination.parent.mkdir(parents=True,exist_ok=True)
                    destination.write_bytes(body)
            text=(ROOT/meta["cleaned_text_path"]).read_text(encoding="utf-8")
            item=CollectedItem(url=row["url"],canonical_url=meta["final_url"],title="Quotes to Scrape",raw_text=text,http_status=200,content_type="text/html",extra=meta)
            record,outcome=persist_collected(db,source,item)
            same,duplicate=persist_collected(db,source,item)
            assert outcome=="CREATED" and duplicate=="SKIPPED_UNCHANGED" and record.id==same.id
            refs=[]
            for evidence in row["evidence"]:
                assert verify_quote(item,evidence["quote"],evidence["start"],evidence["end"],evidence["text_hash"])
                assert record.raw_text[evidence["start"]:evidence["end"]]==evidence["quote"]
                refs.append(dict(source_record_id=record.id,version=record.version_number,**evidence))
            manifest.append(dict(url=row["url"],record_id=record.id,version=record.version_number,
                                 verification_status=record.verification_status,company_id=record.company_id,
                                 duplicate_outcome=duplicate,evidence_refs=refs))
        for model in (Signal,Opportunity,Interaction):
            assert db.scalar(select(func.count()).select_from(model))==0
        db.commit()
    engine.dispose()
    (OUT/"isolated_record_validation.json").write_text(json.dumps(dict(database=TARGET.as_posix(),rows=manifest,signals=0,opportunities=0,interactions=0),ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"real_records":len(manifest),"duplicates_skipped":len(manifest),"evidence_refs":sum(len(r["evidence_refs"]) for r in manifest),"database":TARGET.as_posix()}))
