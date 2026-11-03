"""Manual enforcement export. This does not contact an external platform."""

import json


def export_bundle(incident, manifest: dict, notice: str) -> dict:
    return {
        "bundle_type": "manual_submission",
        "incident_id": incident.id,
        "status": "exported_for_manual_submission",
        "notice": notice,
        "manifest_digest": manifest.get("digest"),
        "evidence": json.loads(manifest.get("manifest_json", "{}")),
        "disclaimer": "This export prepares evidence for a human submission. It does not mean a platform received or removed content.",
    }
