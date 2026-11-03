"""Audit trail helpers."""

import json

from database.models import AuditLog, IncidentEvent


def audit(db, actor_id, action: str, resource_type: str, resource_id: str, metadata: dict | None = None, organization_id=None):
    db.add(AuditLog(
        organization_id=organization_id,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        metadata_json=json.dumps(metadata or {}),
    ))


def incident_event(db, incident, actor_id, event_type: str, old_status: str | None, new_status: str | None, reason: str = "", metadata: dict | None = None):
    db.add(IncidentEvent(
        incident_id=incident.id,
        actor_id=actor_id,
        event_type=event_type,
        old_status=old_status,
        new_status=new_status,
        reason=reason,
        metadata_json=json.dumps(metadata or {}),
    ))
