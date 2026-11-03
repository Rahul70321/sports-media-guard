import hashlib
import json
import socket
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from services.adapters.mock import MockAdapter
from services.adapters.registry import PLATFORM_CAPABILITIES, adapter_for_url
from services.enforcement.manual import export_bundle
from services.evidence_service import create_manifest
from services.incident_workflow import approve_case, prepare_case, record_action, transition_incident
from services.url_policy import UnsafeURLError, validate_outbound_url


class _Session:
    def __init__(self):
        self.added = []

    def add(self, record):
        self.added.append(record)

    def flush(self):
        return None

    def query(self, _model):
        return self

    def filter(self, *_args):
        return self

    def first(self):
        return None


def test_url_policy_rejects_private_and_credentialed_targets(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args: [(None, None, None, None, ("127.0.0.1", 443))])
    with pytest.raises(UnsafeURLError):
        validate_outbound_url("https://localhost/private")
    with pytest.raises(UnsafeURLError):
        validate_outbound_url("https://user:secret@example.com/media")


def test_url_policy_accepts_public_target(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args: [(None, None, None, None, ("1.1.1.1", 443))])
    assert validate_outbound_url("https://example.com/video") == "https://example.com/video"


def test_mock_adapter_paginates_and_reports_duplicate_identity():
    adapter = MockAdapter()
    first = adapter.discover("mock://sports/highlight", {"item_id": "clip-1"})
    second = adapter.discover("mock://sports/highlight", {"item_id": "clip-1"}, first.checkpoint)

    assert first.items[0].platform_item_id == "clip-1"
    assert first.items[0].authorization_mode == "mock"
    assert second.items == []
    assert adapter_for_url("mock://sports/highlight") == "mock"


def test_unsupported_platforms_are_explicitly_unavailable():
    assert PLATFORM_CAPABILITIES["youtube"]["authorized_video"] is False
    assert PLATFORM_CAPABILITIES["tiktok"]["status"] == "approved_api_required"
    assert PLATFORM_CAPABILITIES["reddit"]["status"] == "oauth_required"


def test_evidence_manifest_digest_is_stable():
    discovered = SimpleNamespace(
        id=1,
        source_url="mock://sports/highlight",
        platform="mock",
        platform_item_id="clip-1",
        evidence_type="metadata_only",
        authorization_mode="mock",
        content_sha256="abc",
    )
    incident = SimpleNamespace(id=7)
    session = _Session()

    manifest = create_manifest(session, incident, discovered, {"score": 50})
    payload = json.loads(manifest.manifest_json)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()

    assert manifest.digest == hashlib.sha256(encoded).hexdigest()
    assert "not by itself a legal determination" in payload["disclaimer"]


def test_incident_workflow_requires_reason_role_and_approval():
    db = _Session()
    analyst = SimpleNamespace(id=1, role="analyst")
    legal = SimpleNamespace(id=2, role="legal")
    incident = SimpleNamespace(id=4, status="pending_review", review_reason="", assigned_to=None, updated_at=None)

    with pytest.raises(HTTPException):
        transition_incident(db, incident, analyst, "false_positive")

    transition_incident(db, incident, analyst, "confirmed", "Matching frames reviewed")
    assert incident.status == "confirmed"

    viewer = SimpleNamespace(id=3, role="viewer")
    with pytest.raises(HTTPException):
        prepare_case(db, incident, viewer)

    case = prepare_case(db, incident, analyst, notice="Prepared for review")
    assert case.status == "draft"
    with pytest.raises(HTTPException):
        approve_case(db, case, analyst)

    case = prepare_case(db, incident, legal, notice="Prepared for review")
    with pytest.raises(HTTPException):
        record_action(db, case, legal, "manual", "submitted")

    case.status = "approved"
    with pytest.raises(HTTPException):
        record_action(db, case, legal, "manual", "removed")


def test_manual_export_does_not_claim_platform_removal():
    bundle = export_bundle(
        SimpleNamespace(id=4),
        {"digest": "abc", "manifest_json": "{}"},
        "Manual notice",
    )

    assert bundle["status"] == "exported_for_manual_submission"
    assert "does not mean a platform received or removed content" in bundle["disclaimer"]
