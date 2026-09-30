import hashlib
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.job import CollectionJob
from app.models.source import Source, SourceRecord


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs):  # type: ignore[no-untyped-def]
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        clean = re.sub(r"\s+", " ", data).strip()
        if not clean:
            return
        self.parts.append(clean)
        if self._in_title:
            self.title_parts.append(clean)

    @property
    def text(self) -> str:
        return "\n".join(self.parts)

    @property
    def title(self) -> str | None:
        value = " ".join(self.title_parts).strip()
        return value or None


def _validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Collection URL must be a public http/https URL")


def run_web_collection_job(db: Session, job: CollectionJob) -> SourceRecord:
    if not job.source_id:
        raise ValueError("Job must reference a source")
    source = db.get(Source, job.source_id)
    if not source:
        raise ValueError("Source not found")
    url = (job.query or source.base_url or "").strip()
    _validate_public_url(url)

    job.status = "RUNNING"
    job.progress = 5
    job.started_at = datetime.now(timezone.utc)
    db.commit()

    try:
        headers = {"User-Agent": "BizPulse/0.1 (+local commercial intelligence research)"}
        with httpx.Client(timeout=20, follow_redirects=True, headers=headers) as client:
            response = client.get(url)
            response.raise_for_status()
        parser = _TextExtractor()
        parser.feed(response.text)
        raw_text = parser.text[:2_000_000]
        fingerprint = hashlib.sha256((str(response.url) + "\n" + raw_text).encode("utf-8")).hexdigest()

        existing = db.scalar(select(SourceRecord).where(SourceRecord.source_id == source.id, SourceRecord.content_hash == fingerprint))
        if existing:
            record = existing
        else:
            record = SourceRecord(
                source_id=source.id,
                url=str(response.url),
                title=parser.title,
                raw_text=raw_text,
                content_hash=fingerprint,
                http_status=response.status_code,
                language=None,
                metadata_json={"content_type": response.headers.get("content-type")},
            )
            db.add(record)
            db.flush()

        end = datetime.now(timezone.utc)
        job.status = "COMPLETED"
        job.progress = 100
        job.finished_at = end
        job.record_count = 1
        job.duration_seconds = (end - job.started_at).total_seconds() if job.started_at else None
        source.last_run_at = end
        db.commit()
        db.refresh(record)
        return record
    except Exception as exc:
        end = datetime.now(timezone.utc)
        job.status = "FAILED"
        job.error_count += 1
        job.error_message = str(exc)[:2000]
        job.finished_at = end
        job.duration_seconds = (end - job.started_at).total_seconds() if job.started_at else None
        db.commit()
        raise
