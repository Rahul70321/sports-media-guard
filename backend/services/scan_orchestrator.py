"""Durable monitoring execution shared by the API and worker."""

import json
import os
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlparse

import requests

from database.models import DiscoveredMedia, MonitoringRun, MonitoringTarget, RunEvent, SessionLocal, TargetSchedule, utcnow
from services.adapters.registry import adapter_for_url, get_adapter
from services.evidence_service import file_sha256
from services.fingerprint_service import generate_fingerprint
from services.matching_engine import find_matches_for_media
from services.url_policy import validate_outbound_url


def enqueue_run(db, url: str, user, adapter_type: str | None = None, target: MonitoringTarget | None = None):
    adapter_name = adapter_type or (target.adapter_type if target else adapter_for_url(url))
    run = MonitoringRun(
        id=uuid.uuid4().hex,
        target_id=target.id if target else None,
        organization_id=getattr(user, "organization_id", None),
        adapter_type=adapter_name,
        status="queued",
        message="Monitoring run queued",
        idempotency_key=f"manual:{adapter_name}:{uuid.uuid4().hex}",
        checkpoint_json=json.dumps({"url": url}),
        created_by=getattr(user, "id", None),
    )
    db.add(run)
    db.add(RunEvent(run_id=run.id, status="queued", progress=0, message="Monitoring run queued"))
    db.commit()
    return run


def execute_run(run_id: str):
    db = SessionLocal()
    try:
        run = db.query(MonitoringRun).filter(MonitoringRun.id == run_id).first()
        if not run or run.status in {"completed", "cancelled", "permanent_failure"}:
            return
        target = db.query(MonitoringTarget).filter(MonitoringTarget.id == run.target_id).first() if run.target_id else None
        checkpoint = json.loads(run.checkpoint_json or "{}") if run.checkpoint_json else {}
        url = target.canonical_url if target else checkpoint.get("url", "")
        configuration = json.loads(target.configuration_json or "{}") if target else checkpoint.get("configuration", {})
        _update(db, run, "running", 10, f"Starting {run.adapter_type} discovery")
        adapter = get_adapter(run.adapter_type)
        adapter.validate_target(url, configuration)
        page = adapter.discover(url, configuration, checkpoint or None)
        discovered = duplicates = 0
        for item in page.items:
            if _persist_item(db, item):
                discovered += 1
            else:
                duplicates += 1
        result = {
            "status": "success",
            "items_found": len(page.items),
            "media_discovered": discovered,
            "duplicates_skipped": duplicates,
            "capabilities": adapter.capabilities.to_dict(),
            "quota": page.quota,
        }
        run.metrics_json = json.dumps(result)
        # Preserve the target URL in the checkpoint so ad-hoc runs stay re-runnable;
        # pagination state lives alongside it.
        run.checkpoint_json = json.dumps({"url": url, "configuration": configuration, **(page.checkpoint or {})})
        _update(db, run, "completed", 100, "Monitoring run completed", result)
        if target:
            target.last_success_at = utcnow()
            db.commit()
    except Exception as exc:
        db.rollback()
        run = db.query(MonitoringRun).filter(MonitoringRun.id == run_id).first()
        if run:
            run.attempt += 1
            status = "retryable_failure" if run.attempt < run.max_attempts else "permanent_failure"
            run.error_class = exc.__class__.__name__
            _update(db, run, status, 100, str(exc), {"status": "error", "message": str(exc)})
    finally:
        db.close()


def claim_due_runs(limit: int = 5):
    db = SessionLocal()
    claimed = []
    try:
        now = utcnow()
        schedules = db.query(TargetSchedule).filter(TargetSchedule.enabled == True, TargetSchedule.next_run_at <= now).all()
        for schedule in schedules:
            target = db.query(MonitoringTarget).filter(MonitoringTarget.id == schedule.target_id, MonitoringTarget.status == "active").first()
            if not target:
                continue
            active = db.query(MonitoringRun).filter(MonitoringRun.target_id == target.id, MonitoringRun.status.in_(["queued", "running"])).first()
            if active and schedule.concurrency_policy == "skip":
                schedule.next_run_at = now + timedelta(seconds=schedule.interval_seconds)
                continue
            run = MonitoringRun(
                id=uuid.uuid4().hex, target_id=target.id, organization_id=target.organization_id,
                adapter_type=target.adapter_type, status="queued", message="Scheduled run queued",
                idempotency_key=f"target:{target.id}:{now.strftime('%Y%m%d%H%M%S')}",
            )
            db.add(run)
            schedule.next_run_at = now + timedelta(seconds=schedule.interval_seconds)
            claimed.append(run.id)
        recoverable = db.query(MonitoringRun).filter(
            MonitoringRun.status == "running", MonitoringRun.lease_expires_at < now
        ).limit(limit).all()
        for run in recoverable:
            run.status = "queued"
            run.message = "Recovered after expired worker lease"
            claimed.append(run.id)
        queued = db.query(MonitoringRun).filter(MonitoringRun.status.in_(["queued", "retryable_failure"])).limit(limit).all()
        owner = f"worker-{os.getpid()}"
        for run in queued:
            if run.id not in claimed:
                claimed.append(run.id)
            run.status = "running"
            run.lease_owner = owner
            run.lease_expires_at = now + timedelta(minutes=10)
            run.heartbeat_at = now
            if not run.started_at:
                run.started_at = now
        db.commit()
        return claimed[:limit]
    finally:
        db.close()


def _persist_item(db, item) -> bool:
    existing = db.query(DiscoveredMedia).filter(
        DiscoveredMedia.platform == item.platform,
        DiscoveredMedia.platform_item_id == item.platform_item_id,
    ).first()
    if existing:
        return False
    path = _download_authorized_media(item)
    media_type = item.media_type or ("video" if item.evidence_type == "authorized_video" else "image")
    fingerprint = generate_fingerprint(path, media_type) if path else None
    if path and (fingerprint is None or not getattr(fingerprint, "primary_hash", "")):
        # Media was downloaded but could not be fingerprinted; skip rather than
        # store an unfingerprinted row that would never match anything.
        return False
    discovered = DiscoveredMedia(
        source_url=item.source_url,
        platform=item.platform,
        platform_item_id=item.platform_item_id,
        evidence_type=item.evidence_type,
        authorization_mode=item.authorization_mode,
        capabilities_json=json.dumps(item.capabilities.to_dict()),
        source_metadata=json.dumps({**item.metadata, "title": item.title, "account": item.account, "published_at": item.published_at}),
        content_sha256=file_sha256(path) if path else "",
        file_path=path or "",
        fingerprint_hash=getattr(fingerprint, "primary_hash", "") or item.platform_item_id,
        fingerprint_phash=getattr(fingerprint, "phash", ""),
        fingerprint_dhash=getattr(fingerprint, "dhash", ""),
        fingerprint_histogram=getattr(fingerprint, "histogram", ""),
        video_frame_hashes=getattr(fingerprint, "video_frame_hashes", "") or None,
    )
    db.add(discovered)
    db.commit()
    db.refresh(discovered)
    # Matching requires an actual fingerprint (downloaded media); metadata-only
    # discoveries are retained as leads but cannot be similarity-matched.
    if fingerprint and getattr(fingerprint, "primary_hash", ""):
        find_matches_for_media(discovered, db)
    return True


def _download_authorized_media(item) -> str:
    if not item.media_url:
        return ""
    if item.authorization_mode not in {"public_api", "authorized_feed", "mock", "manual_upload"}:
        return ""
    if item.media_url.startswith(("http://", "https://")):
        validate_outbound_url(item.media_url)
        response = requests.get(item.media_url, timeout=20)
        response.raise_for_status()
        extension = os.path.splitext(urlparse(item.media_url).path)[1] or (".mp4" if item.media_type == "video" else ".jpg")
        directory = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "downloads"))
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, f"{item.platform}-{uuid.uuid4().hex}{extension}")
        with open(path, "wb") as output:
            output.write(response.content)
        return path
    return item.media_url if os.path.isfile(item.media_url) else ""


def _update(db, run: MonitoringRun, status: str, progress: int, message: str, result: dict | None = None):
    run.status = status
    run.progress = progress
    run.message = message[:500]
    run.updated_at = utcnow()
    run.heartbeat_at = utcnow()
    if status == "running" and not run.started_at:
        run.started_at = utcnow()
    if status in {"completed", "permanent_failure", "cancelled"}:
        run.completed_at = utcnow()
    if result and status != "completed":
        run.error_message = result.get("message", "")[:1000]
    db.add(RunEvent(run_id=run.id, status=status, progress=progress, message=run.message))
    db.commit()
