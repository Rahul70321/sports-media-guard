"""Role-aware incident workflow and enforcement preparation."""

from datetime import datetime

from fastapi import HTTPException

from database.models import EnforcementAction, EnforcementCase
from services.audit_service import incident_event


TRANSITIONS = {
    "pending_review": {"in_review", "confirmed", "false_positive", "enforcement_draft"},
    "new": {"pending_review", "in_review", "false_positive"},
    "in_review": {"confirmed", "false_positive", "escalated", "pending_review"},
    "confirmed": {"enforcement_draft", "resolved", "false_positive"},
    "escalated": {"in_review", "enforcement_draft"},
    "enforcement_draft": {"submitted", "pending_review"},
    "takedown_requested": {"submitted", "resolved", "pending_review"},
    "submitted": {"acknowledged", "rejected", "resolved"},
    "acknowledged": {"resolved", "rejected"},
    "resolved": {"closed"},
    "false_positive": {"closed", "pending_review"},
    "rejected": {"pending_review", "closed"},
    "closed": set(),
}

ROLE_PERMISSIONS = {
    "analyst": {"in_review", "confirmed", "false_positive", "pending_review"},
    "legal": {"in_review", "confirmed", "false_positive", "escalated", "enforcement_draft", "submitted", "resolved", "closed"},
    "admin": set().union(*TRANSITIONS.values()),
}


def transition_incident(db, incident, actor, new_status: str, reason: str = ""):
    allowed = TRANSITIONS.get(incident.status, set())
    if new_status == "takedown_requested":
        new_status = "enforcement_draft"
    if new_status not in allowed:
        raise HTTPException(status_code=409, detail=f"Cannot move incident from {incident.status} to {new_status}")
    if new_status not in ROLE_PERMISSIONS.get(actor.role, set()):
        raise HTTPException(status_code=403, detail="Your role cannot perform this incident transition")
    if new_status in {"false_positive", "confirmed", "closed"} and not reason.strip():
        raise HTTPException(status_code=400, detail="A reason is required for this decision")
    old = incident.status
    incident.status = new_status
    incident.review_reason = reason or incident.review_reason
    incident.assigned_to = actor.id
    incident.updated_at = datetime.utcnow()
    incident_event(db, incident, actor.id, "status_changed", old, new_status, reason)
    return incident


def prepare_case(db, incident, actor, jurisdiction: str = "", claimant: str = "", notice: str = ""):
    if actor.role not in {"admin", "legal", "analyst"}:
        raise HTTPException(status_code=403, detail="Analyst, legal, or admin role required to prepare a case")
    case = db.query(EnforcementCase).filter(EnforcementCase.incident_id == incident.id).first()
    if not case:
        case = EnforcementCase(incident_id=incident.id)
        db.add(case)
    case.status = "draft"
    case.jurisdiction = jurisdiction
    case.claimant = claimant
    case.notice_text = notice
    case.updated_at = datetime.utcnow()
    db.flush()
    return case


def approve_case(db, case, actor):
    if actor.role not in {"admin", "legal"}:
        raise HTTPException(status_code=403, detail="Admin or legal role required to approve an enforcement case")
    case.status = "approved"
    case.approved_by = actor.id
    case.approved_at = datetime.utcnow()
    return case


def record_action(db, case, actor, provider: str, status: str, reference: str = "", request: str = "", response: str = ""):
    if case.status != "approved" and status in {"submitted", "acknowledged", "removed"}:
        raise HTTPException(status_code=409, detail="Human legal approval is required before provider submission")
    if status == "removed" and not reference:
        raise HTTPException(status_code=400, detail="Provider confirmation is required before marking content removed")
    action = EnforcementAction(
        case_id=case.id, provider=provider, status=status, provider_reference=reference,
        request_json=request, response_json=response, created_by=actor.id,
    )
    case.status = status
    db.add(action)
    return action
