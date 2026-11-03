"""Notification delivery with deduplication and safe webhook validation."""

import json
from datetime import datetime

import requests

from database.models import NotificationDelivery
from services.url_policy import configured_allow_hosts, validate_outbound_url


def notify(db, event_type: str, payload: dict, webhook_url: str = "", organization_id=None):
    key = f"{event_type}:{payload.get('incident_id') or payload.get('run_id') or payload.get('target_id')}"
    if db.query(NotificationDelivery).filter(NotificationDelivery.dedupe_key == key).first():
        return None
    delivery = NotificationDelivery(
        organization_id=organization_id,
        event_type=event_type,
        channel="webhook" if webhook_url else "internal",
        dedupe_key=key,
        payload_json=json.dumps(payload),
    )
    if webhook_url:
        try:
            validate_outbound_url(webhook_url, configured_allow_hosts("WEBHOOK_ALLOWLIST") or None)
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            delivery.status = "delivered"
        except Exception as exc:
            delivery.status = "failed"
            delivery.error_message = str(exc)[:500]
    else:
        delivery.status = "recorded"
    delivery.delivered_at = datetime.utcnow()
    db.add(delivery)
    db.commit()
    return delivery
