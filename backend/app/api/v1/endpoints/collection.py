"""T03 采集中心 API：

- POST /sources/{id}/run        执行一次采集（创建 Job 并同步运行）
- POST /ingest/urls             批量 URL 采集（≤100，逐条独立结果）
- POST /ingest/import           CSV 导入（企业/URL 列表，USER_PROVIDED 标记）
- GET  /source-records/{id}     详情含 versions / company
- POST /source-records/{id}/assign-company   人工关联企业（写 AuditLog）
- POST /source-records/{id}/verify           人工核验证据（VERIFIED / STALE / INVALID）
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.collectors import get_adapter
from app.db.session import get_db
from app.models.company import Company
from app.models.job import CollectionJob
from app.models.source import Source, SourceRecord
from app.services.audit import write_audit
from app.services.collection_engine import persist_collected, run_collection_job
from app.services.ingest import get_manual_source
from app.services.extractor import URLSafetyError

router = APIRouter(tags=["collection"])


# ---------------------------------------------------------------------------
# Source 运行
# ---------------------------------------------------------------------------

class SourceRunResponse(BaseModel):
    job_id: str
    status: str
    items_found: int
    items_created: int
    items_updated: int
    items_skipped: int
    error_count: int


@router.post("/sources/{source_id}/run")
def run_source(source_id: str, db: Session = Depends(get_db)) -> dict:
    """对已配置的数据源执行一次采集（手动触发）。"""
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    if not source.enabled:
        raise HTTPException(status_code=422, detail="数据源已停用")

    try:
        adapter = get_adapter(source.collector_type, source, dict(source.config_json or {}))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    job = CollectionJob(
        source_id=source.id,
        name=f"手动执行 · {source.name}",
        job_type="MANUAL",
        status="PENDING",
    )
    db.add(job)
    db.flush()
    write_audit(db, "RUN_SOURCE", "source", source.id, {"job_id": job.id})
    db.commit()
    db.refresh(job)

    try:
        run_collection_job(db, job, adapter)
    except Exception as exc:  # noqa: BLE001 - Job 内已记录失败详情
        raise HTTPException(status_code=502, detail=f"采集执行失败：{str(exc)[:200]}") from exc

    return {
        "success": True,
        "data": SourceRunResponse(
            job_id=job.id, status=job.status, items_found=job.items_found,
            items_created=job.items_created, items_updated=job.items_updated,
            items_skipped=job.items_skipped, error_count=job.error_count,
        ).model_dump(),
        "message": None,
    }


# ---------------------------------------------------------------------------
# 批量 URL / CSV 导入
# ---------------------------------------------------------------------------

class BatchIngestRequest(BaseModel):
    urls: list[str] = Field(min_length=1, max_length=100)
    note: str = Field(default="", max_length=2000)


@router.post("/ingest/urls")
def ingest_urls(payload: BatchIngestRequest, db: Session = Depends(get_db)) -> dict:
    """批量 URL 采集：逐条独立记录结果（不因单条失败中断）。"""
    from app.collectors import ManualUrlCollector

    manual_source = get_manual_source(db)
    results = []
    job = CollectionJob(source_id=manual_source.id, name="批量URL采集", job_type="INGEST", status="RUNNING", started_at=datetime.now(timezone.utc))
    db.add(job)
    db.flush()

    for url in payload.urls:
        url = url.strip()
        entry: dict = {"url": url}
        if not url:
            continue
        try:
            adapter = ManualUrlCollector(manual_source, {"url": url, "max_retries": 1})
            adapter.validate_config()
            items = adapter.build_records()
            for item in items:
                record, outcome = persist_collected(db, manual_source, item)
                entry.update({
                    "outcome": outcome,
                    "source_record_id": record.id,
                    "company_id": record.company_id,
                    "version": record.version_number,
                    "run_log": adapter.run_log,
                })
        except URLSafetyError as exc:
            entry.update({"outcome": "REJECTED", "error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            entry.update({"outcome": "FAILED", "error": str(exc)[:200]})
        results.append(entry)

    job.items_found = len(results)
    job.items_created = sum(1 for r in results if r.get("outcome") == "CREATED")
    job.items_updated = sum(1 for r in results if r.get("outcome") == "UPDATED_VERSION")
    job.items_skipped = sum(1 for r in results if r.get("outcome") == "SKIPPED_UNCHANGED")
    job.error_count = sum(1 for r in results if r.get("outcome") in {"FAILED", "REJECTED"})
    job.finished_at = datetime.now(timezone.utc)
    job.duration_seconds = (job.finished_at - job.started_at).total_seconds() if job.started_at else None
    job.status = "PARTIAL_SUCCESS" if job.error_count else "SUCCESS"
    job.run_log_json = [{"url": r["url"], "status": r.get("outcome", "?")} for r in results]
    db.commit()

    return {"success": True, "data": {"job_id": job.id, "items": results}, "message": None}


class ImportRow(BaseModel):
    company_name: str | None = None
    website: str | None = None
    source_url: str | None = None
    industry: str | None = None
    note: str | None = None


class ImportRequest(BaseModel):
    csv_text: str = Field(min_length=1, max_length=2_000_000)


@router.post("/ingest/import")
def import_csv(payload: ImportRequest, db: Session = Depends(get_db)) -> dict:
    """CSV 导入（表头：company_name,website,source_url,industry,note）。

    - 带 source_url 的行：创建 MANUAL_IMPORT Source 后真实采集该 URL，
      只有实际采集成功的内容才成为外部事实；
    - 仅手工信息（无 source_url）：Company 标记 USER_PROVIDED，
      不得冒充 OFFICIAL_VERIFIED。
    """
    reader = csv.DictReader(io.StringIO(payload.csv_text.strip()))
    required = {"company_name", "website", "source_url", "industry", "note"}
    if reader.fieldnames and not required.issubset({f.strip().lower() for f in reader.fieldnames}):
        raise HTTPException(status_code=422, detail=f"CSV 表头需包含：{', '.join(sorted(required))}")

    imported_source = db.scalar(select(Source).where(Source.source_type == "MANUAL_IMPORT"))
    if not imported_source:
        imported_source = Source(
            name="CSV 导入", source_type="MANUAL_IMPORT", reliability_grade="C",
            reliability_score=50, enabled=True, collector_type="web_page",
            notes="人工导入的企业/URL 列表。",
        )
        db.add(imported_source)
        db.flush()

    results = []
    for row in reader:
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        name = row.get("company_name") or None
        website = row.get("website") or None
        source_url = row.get("source_url") or None
        industry = row.get("industry") or None
        note = row.get("note") or None
        entry: dict = {"company_name": name, "source_url": source_url}

        domain = website.replace("https://", "").replace("http://", "").strip("/") or None if website else None
        company = None
        if name or domain:
            normalized = "".join((name or domain or "").lower().split())
            company = db.scalar(select(Company).where(Company.normalized_name == normalized)) if normalized else None
            if not company:
                company = Company(
                    company_name=name or domain,  # type: ignore[arg-type]
                    normalized_name=normalized,
                    website=website, domain=domain, industry=industry,
                    company_description=note,
                    source_count=0,
                )
                db.add(company)
                db.flush()
                # 人工输入的企业信息：标记 USER_PROVIDED，不冒充官方核验（见 AuditLog）
                write_audit(db, "IMPORT_COMPANY", "company", company.id, {
                    "company_name": company.company_name, "verification": "USER_PROVIDED", "note": note,
                })
                entry["company_created"] = True
        entry["company_id"] = company.id if company else None
        entry["company_verification"] = "USER_PROVIDED"

        if source_url:
            try:
                from app.collectors import ManualUrlCollector
                adapter = ManualUrlCollector(imported_source, {"url": source_url, "max_retries": 1})
                adapter.validate_config()
                for item in adapter.build_records():
                    record, outcome = persist_collected(db, imported_source, item)
                    if company and outcome == "CREATED":
                        record.company_id = company.id
                        record.company_resolve_status = "USER_LINKED"
                        company.source_count = (company.source_count or 0) + 1
                    entry.update({"collect_outcome": outcome, "source_record_id": record.id, "version": record.version_number})
            except URLSafetyError as exc:
                entry.update({"collect_outcome": "REJECTED", "error": str(exc)})
            except Exception as exc:  # noqa: BLE001
                entry.update({"collect_outcome": "FAILED", "error": str(exc)[:200]})
        results.append(entry)
    db.commit()
    return {"success": True, "data": {"imported": len(results), "items": results}, "message": None}


# ---------------------------------------------------------------------------
# SourceRecord 详情（含版本链）与人工关联
# ---------------------------------------------------------------------------

def _record_brief(record: SourceRecord) -> dict:
    return {
        "id": record.id, "version_number": record.version_number, "is_latest": record.is_latest,
        "collected_at": record.collected_at, "content_hash": record.content_hash,
        "title": record.title, "http_status": record.http_status,
    }


class AssignCompanyRequest(BaseModel):
    company_id: str | None = None
    new_company_name: str | None = Field(default=None, max_length=300)


@router.post("/source-records/{record_id}/assign-company")
def assign_company(record_id: str, payload: AssignCompanyRequest, db: Session = Depends(get_db)) -> dict:
    """人工关联企业（UNRESOLVED/POSSIBLE → USER_LINKED），写 AuditLog。"""
    record = db.get(SourceRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Source record not found")

    company = None
    if payload.company_id:
        company = db.get(Company, payload.company_id)
        if not company:
            raise HTTPException(status_code=422, detail="company_id does not exist")
    elif payload.new_company_name:
        normalized = "".join(payload.new_company_name.lower().split())
        company = db.scalar(select(Company).where(Company.normalized_name == normalized))
        if not company:
            from app.collectors.urlutils import canonicalize_url  # noqa: F401
            from urllib.parse import urlparse
            domain = (urlparse(record.url).hostname or "").lower() or None
            company = Company(company_name=payload.new_company_name, normalized_name=normalized, domain=domain, source_count=0)
            db.add(company)
            db.flush()
    else:
        raise HTTPException(status_code=422, detail="必须提供 company_id 或 new_company_name")

    record.company_id = company.id
    record.company_resolve_status = "USER_LINKED"
    company.source_count = (company.source_count or 0) + 1
    write_audit(db, "ASSIGN_COMPANY", "source_record", record.id, {
        "company_id": company.id, "company_name": company.company_name, "manual": True,
    })
    db.commit()
    return {"success": True, "data": {"record_id": record.id, "company_id": company.id, "status": "USER_LINKED"}, "message": None}


class VerifyRequest(BaseModel):
    status: str  # VERIFIED / STALE / INVALID / REMOVED / UNVERIFIED


@router.post("/source-records/{record_id}/verify")
def verify_record(record_id: str, payload: VerifyRequest, db: Session = Depends(get_db)) -> dict:
    """人工核验证据状态（VERIFIED/STALE/INVALID/REMOVED），写 AuditLog。"""
    if payload.status not in {"VERIFIED", "STALE", "INVALID", "REMOVED", "UNVERIFIED"}:
        raise HTTPException(status_code=422, detail="status 必须是 VERIFIED/STALE/INVALID/REMOVED/UNVERIFIED")
    record = db.get(SourceRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Source record not found")
    record.verification_status = payload.status
    record.last_verified_at = datetime.now(timezone.utc)
    if payload.status == "STALE":
        record.is_active = False
    write_audit(db, "VERIFY_RECORD", "source_record", record.id, {"status": payload.status})
    db.commit()
    return {"success": True, "data": {"record_id": record.id, "verification_status": payload.status}, "message": None}


@router.get("/jobs/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)) -> dict:
    job = db.get(CollectionJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    from app.schemas.job import JobRead
    data = JobRead.model_validate(job).model_dump()
    data.update({
        "job_type": job.job_type, "scheduled_at": job.scheduled_at,
        "items_found": job.items_found, "items_created": job.items_created,
        "items_updated": job.items_updated, "items_skipped": job.items_skipped,
        "run_log": job.run_log_json,
    })
    return {"success": True, "data": data, "message": None}


@router.get("/collectors")
def list_collectors() -> dict:
    from app.collectors import available_collectors
    return {"success": True, "data": {"collectors": available_collectors()}, "message": None}
