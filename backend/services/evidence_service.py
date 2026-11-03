"""Append-only evidence manifests and provenance records."""

import hashlib
import json
import os
from datetime import datetime

from database.models import EvidenceManifest, EvidenceObject, utcnow


def file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_evidence_object(db, discovered, evidence_type: str, storage_key: str, content_type: str = ""):
    sha256 = file_sha256(storage_key) if storage_key and os.path.isfile(storage_key) else ""
    size = os.path.getsize(storage_key) if storage_key and os.path.isfile(storage_key) else 0
    record = EvidenceObject(
        discovered_media_id=discovered.id,
        evidence_type=evidence_type,
        storage_key=storage_key or "",
        content_type=content_type,
        byte_size=size,
        sha256=sha256 or hashlib.sha256((discovered.source_url or "").encode()).hexdigest(),
        source_url=discovered.source_url,
        authorization_mode=discovered.authorization_mode or "manual_upload",
    )
    db.add(record)
    db.flush()
    return record


def create_manifest(db, incident, discovered, evidence: dict):
    payload = {
        "version": 1,
        "created_at": utcnow().isoformat() + "Z",
        "source_url": discovered.source_url,
        "platform": discovered.platform,
        "platform_item_id": discovered.platform_item_id,
        "evidence_type": discovered.evidence_type,
        "authorization_mode": discovered.authorization_mode,
        "content_sha256": discovered.content_sha256,
        "analysis": evidence,
        "disclaimer": "Similarity is an investigation signal and is not by itself a legal determination.",
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    manifest = EvidenceManifest(
        incident_id=incident.id,
        discovered_media_id=discovered.id,
        version=1,
        manifest_json=json.dumps(payload, indent=2),
        digest=hashlib.sha256(encoded).hexdigest(),
    )
    db.add(manifest)
    db.flush()
    return manifest
