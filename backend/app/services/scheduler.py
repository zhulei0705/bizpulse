"""采集调度（T03）：APScheduler 定时执行 daily 数据源。

- 默认关闭：BIZPULSE_ENABLE_SCHEDULER=true 才启动（开发环境不自动跑）
- V1 只调度 collection_frequency=daily 的启用数据源
- 每次执行创建 SCHEDULED 类型 Job，完整走 Adapter + collection_engine
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.job import CollectionJob
from app.models.source import Source
from app.services.audit import write_audit
from app.services.collection_engine import run_collection_job

logger = logging.getLogger(__name__)

scheduler = None


def run_scheduled_source(source_id: str) -> None:
    """调度入口：对单个数据源执行采集。"""
    from app.collectors import get_adapter

    with SessionLocal() as db:
        source = db.get(Source, source_id)
        if not source or not source.enabled:
            return
        try:
            adapter = get_adapter(source.collector_type, source, dict(source.config_json or {}))
        except ValueError as exc:
            logger.warning("scheduled source %s config invalid: %s", source_id, exc)
            return
        job = CollectionJob(
            source_id=source.id,
            name=f"定时执行 · {source.name}",
            job_type="SCHEDULED",
            status="PENDING",
            scheduled_at=datetime.now(timezone.utc),
        )
        db.add(job)
        db.flush()
        write_audit(db, "SCHEDULED_RUN", "source", source.id, {"job_id": job.id})
        db.commit()
        db.refresh(job)
        try:
            run_collection_job(db, job, adapter)
        except Exception as exc:  # noqa: BLE001 - Job 内已记录
            logger.error("scheduled run failed for %s: %s", source_id, exc)


def start_scheduler():
    global scheduler
    if not settings.enable_scheduler:
        logger.info("采集调度器未启用（BIZPULSE_ENABLE_SCHEDULER != true）")
        return
    if scheduler is not None:
        return
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler(timezone="UTC")

    def _schedule_daily_sources() -> None:
        with SessionLocal() as db:
            source_ids = [s for s in db.scalars(
                select(Source.id).where(Source.enabled.is_(True), Source.collection_frequency == "daily")
            ).all()]
        for source_id in source_ids:
            scheduler.add_job(run_scheduled_source, args=[source_id], id=f"daily_{source_id}", replace_existing=True)

    # 每天UTC 02:00 触发一次调度注册（低峰）
    scheduler.add_job(_schedule_daily_sources, "cron", hour=2, minute=0, id="register_daily_sources")
    _schedule_daily_sources()
    scheduler.start()
    logger.info("采集调度器已启动（daily 数据源 + 每日注册任务）")


def stop_scheduler():
    global scheduler
    if scheduler is not None:
        scheduler.shutdown(wait=False)
        scheduler = None
