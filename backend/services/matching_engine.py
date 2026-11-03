"""
Multi-Signal Similarity Matching Engine
Computes weighted composite match scores from phash, dhash, histogram,
and video frame similarity. Integrates watermark verification and anomaly scoring.
"""

import imagehash
import cv2
import numpy as np
import json
from dataclasses import dataclass, asdict
from typing import Optional

from database.models import Asset, DiscoveredMedia, Incident, SystemSettings
from services.watermark_service import verify_watermark
from services.anomaly_scorer import calculate_anomaly_score
from services.evidence_service import create_evidence_object, create_manifest


# ─── Weight Configuration ──────────────────────────────────────────────────

# Weights for images (no video frame signal available)
IMAGE_WEIGHTS = {
    "phash": 0.45,
    "dhash": 0.30,
    "histogram": 0.25,
}

# Weights for videos (includes video frame matching)
VIDEO_WEIGHTS = {
    "phash": 0.35,
    "dhash": 0.20,
    "histogram": 0.15,
    "video_frames": 0.30,
}


@dataclass
class MatchResult:
    """Detailed result of comparing two media items."""
    phash_score: float = 0.0
    dhash_score: float = 0.0
    histogram_score: float = 0.0
    video_frame_score: float = 0.0
    composite_score: float = 0.0
    is_match: bool = False
    correspondences: list = None


# ─── Individual Signal Scoring ──────────────────────────────────────────────

def _hamming_similarity(hash1_str: str, hash2_str: str) -> float:
    """
    Calculates similarity (0–100) from Hamming distance between two hex hashes.
    """
    try:
        if not hash1_str or not hash2_str:
            return 0.0
        hash1 = imagehash.hex_to_hash(hash1_str)
        hash2 = imagehash.hex_to_hash(hash2_str)
        distance = hash1 - hash2
        max_distance = 64  # 64-bit hash
        similarity = max(0.0, ((max_distance - distance) / max_distance) * 100.0)
        return similarity
    except Exception as e:
        print(f"Hamming similarity error: {e}")
        return 0.0


def _histogram_similarity(hist1_json: str, hist2_json: str) -> float:
    """
    Calculates similarity (0–100) between two HSV histogram fingerprints
    using OpenCV correlation method.
    """
    try:
        if not hist1_json or not hist2_json:
            return 0.0

        h1 = np.array(json.loads(hist1_json), dtype=np.float32)
        h2 = np.array(json.loads(hist2_json), dtype=np.float32)

        if len(h1) != len(h2) or len(h1) == 0:
            return 0.0

        # Use correlation method: 1.0 = identical, -1.0 = inverse
        correlation = cv2.compareHist(h1, h2, cv2.HISTCMP_CORREL)

        # Convert from [-1, 1] to [0, 100]
        similarity = max(0.0, (correlation + 1.0) / 2.0 * 100.0)
        return similarity

    except Exception as e:
        print(f"Histogram similarity error: {e}")
        return 0.0


def _video_frame_similarity(asset_frames_json: str, discovered_frames_json: str, discovered_phash: str = "") -> tuple[float, list]:
    """Compare sampled frames and retain the strongest frame correspondences."""
    try:
        if not asset_frames_json or not discovered_frames_json:
            return 0.0, []
        asset_frames = json.loads(asset_frames_json)
        discovered_frames = json.loads(discovered_frames_json)
        best_score = 0.0
        matches = []
        for asset_frame in asset_frames or []:
            asset_hash = asset_frame.get("phash", "")
            for discovered_frame in discovered_frames or []:
                score = _hamming_similarity(asset_hash, discovered_frame.get("phash", ""))
                if score >= 90:
                    matches.append({
                        "reference_frame": asset_frame.get("frame"),
                        "candidate_frame": discovered_frame.get("frame"),
                        "score": round(score, 2),
                    })
                best_score = max(best_score, score)
        matches.sort(key=lambda item: item["score"], reverse=True)
        return best_score, matches[:20]
    except Exception as e:
        print(f"Video frame similarity error: {e}")
        return 0.0, []


def _confidence_label(discovered: DiscoveredMedia, match: MatchResult, watermark_match: bool, correspondences: list) -> str:
    evidence_type = discovered.evidence_type or "metadata_only"
    if evidence_type == "thumbnail":
        return "thumbnail_candidate"
    if watermark_match:
        return "watermark_match"
    if evidence_type == "authorized_video" and len(correspondences) >= 3 and match.video_frame_score >= 90:
        return "authorized_video_match"
    if evidence_type == "authorized_video" and correspondences:
        return "partial_match"
    if evidence_type == "metadata_only":
        return "metadata_only"
    return "inconclusive"


# ─── Composite Matching ────────────────────────────────────────────────────

def calculate_match(asset: Asset, discovered: DiscoveredMedia) -> MatchResult:
    """
    Calculates the weighted composite match score between an asset
    and a discovered media item using all available signals.
    """
    result = MatchResult()

    # Calculate individual signal scores
    result.phash_score = _hamming_similarity(
        asset.fingerprint_phash or asset.fingerprint_hash,
        discovered.fingerprint_phash or discovered.fingerprint_hash
    )
    result.dhash_score = _hamming_similarity(
        asset.fingerprint_dhash,
        discovered.fingerprint_dhash
    )
    result.histogram_score = _histogram_similarity(
        asset.fingerprint_histogram,
        discovered.fingerprint_histogram
    )

    # Video frame matching (if asset has frame hashes)
    has_authorized_video = (discovered.evidence_type == "authorized_video") and bool(asset.video_frame_hashes and discovered.video_frame_hashes)
    correspondences = []
    if has_authorized_video:
        result.video_frame_score, correspondences = _video_frame_similarity(
            asset.video_frame_hashes,
            discovered.video_frame_hashes,
        )
    result.correspondences = correspondences

    # Calculate weighted composite
    if has_authorized_video:
        weights = VIDEO_WEIGHTS
        result.composite_score = (
            result.phash_score * weights["phash"] +
            result.dhash_score * weights["dhash"] +
            result.histogram_score * weights["histogram"] +
            result.video_frame_score * weights["video_frames"]
        )
    else:
        weights = IMAGE_WEIGHTS
        result.composite_score = (
            result.phash_score * weights["phash"] +
            result.dhash_score * weights["dhash"] +
            result.histogram_score * weights["histogram"]
        )

    return result


# ─── Settings ───────────────────────────────────────────────────────────────

def get_match_threshold(db_session) -> float:
    """Reads the video match threshold from system settings."""
    DEFAULT_THRESHOLD = 80.0
    try:
        setting_row = db_session.query(SystemSettings).first()
        if setting_row and setting_row.settings_data:
            settings = json.loads(setting_row.settings_data)
            threshold = settings.get('videoMatchThreshold', DEFAULT_THRESHOLD)
            return float(threshold)
    except Exception as e:
        print(f"Error reading match threshold: {e}")
    return DEFAULT_THRESHOLD


# ─── Main Pipeline ──────────────────────────────────────────────────────────

def find_matches_for_media(discovered_media: DiscoveredMedia, db_session) -> list:
    """
    Full AI detection pipeline for a discovered media item:
    1. Compares against all registered assets using multi-signal matching
    2. Verifies watermark on discovered media
    3. Calculates anomaly score
    4. Creates incidents with full forensic evidence
    """
    match_threshold = get_match_threshold(db_session)
    assets = db_session.query(Asset).all()
    incidents_created = []

    # Step 1: Watermark verification (once per discovered media)
    watermark_result = None
    if discovered_media.file_path and os.path.exists(discovered_media.file_path):
        watermark_result = verify_watermark(discovered_media.file_path, db_session)

        # Update discovered media with watermark info
        discovered_media.watermark_extracted = watermark_result.extracted or None
        discovered_media.watermark_verified = watermark_result.verified
        db_session.commit()

    for asset in assets:
        # Need at least a primary hash on both sides
        asset_hash = asset.fingerprint_phash or asset.fingerprint_hash
        discovered_hash = discovered_media.fingerprint_phash or discovered_media.fingerprint_hash
        if not asset_hash or not discovered_hash:
            continue

        # Step 2: Multi-signal matching
        match = calculate_match(asset, discovered_media)

        if match.composite_score >= match_threshold:
            # Deduplicate
            existing = db_session.query(Incident).filter(
                Incident.asset_id == asset.id,
                Incident.discovered_media_id == discovered_media.id
            ).first()
            if existing:
                continue

            # Step 3: Determine watermark match for this specific asset
            watermark_match = False
            watermark_extracted = ""
            if watermark_result:
                watermark_match = watermark_result.verified and watermark_result.matched_asset_id == asset.id
                watermark_extracted = watermark_result.extracted

            # Step 4: Anomaly scoring
            anomaly = calculate_anomaly_score(
                match_score=match.composite_score,
                watermark_match=watermark_match,
                watermark_extracted=watermark_extracted,
                platform=discovered_media.platform or "",
                rights_policy=asset.rights_policy or "",
                asset_created_at=asset.created_at,
                discovered_at=discovered_media.discovered_at,
                db_session=db_session
            )

            # Step 5: Build evidence summary
            confidence = _confidence_label(discovered_media, match, watermark_match, match.correspondences or [])
            if confidence == "thumbnail_candidate":
                match.composite_score = min(match.composite_score, 74.0)
            evidence = {
                "matching": {
                    "phash_score": round(match.phash_score, 2),
                    "dhash_score": round(match.dhash_score, 2),
                    "histogram_score": round(match.histogram_score, 2),
                    "video_frame_score": round(match.video_frame_score, 2),
                    "composite_score": round(match.composite_score, 2),
                    "threshold": match_threshold,
                    "confidence_label": confidence,
                    "evidence_type": discovered_media.evidence_type,
                    "frame_correspondences": match.correspondences or [],
                    "frame_coverage_count": len(match.correspondences or []),
                },
                "watermark": {
                    "extracted": watermark_extracted,
                    "verified": watermark_match,
                    "matched_asset_id": watermark_result.matched_asset_id if watermark_result else None,
                    "confidence": watermark_result.confidence if watermark_result else "none",
                },
                "anomaly": {
                    "score": round(anomaly.anomaly_score, 2),
                    "risk_level": anomaly.risk_level,
                    "factors": anomaly.factors,
                },
            }

            # Step 6: Create incident
            incident = Incident(
                asset_id=asset.id,
                discovered_media_id=discovered_media.id,
                match_score=round(match.composite_score, 2),
                status="pending_review",
                confidence_label=confidence,
                video_frame_score=round(match.video_frame_score, 2),
                phash_score=round(match.phash_score, 2),
                dhash_score=round(match.dhash_score, 2),
                histogram_score=round(match.histogram_score, 2),
                watermark_match=watermark_match,
                anomaly_score=round(anomaly.anomaly_score, 2),
                anomaly_factors=anomaly.to_json(),
                risk_level=anomaly.risk_level,
                evidence_summary=json.dumps(evidence),
            )
            db_session.add(incident)
            db_session.flush()
            create_evidence_object(db_session, discovered_media, discovered_media.evidence_type or "metadata_only", discovered_media.file_path or "")
            create_manifest(db_session, incident, discovered_media, evidence)
            db_session.commit()
            db_session.refresh(incident)
            incidents_created.append(incident)

            print(
                f"INCIDENT CREATED | Score: {match.composite_score:.1f}% "
                f"(P:{match.phash_score:.0f} D:{match.dhash_score:.0f} H:{match.histogram_score:.0f}) "
                f"| Anomaly: {anomaly.anomaly_score:.0f} ({anomaly.risk_level}) "
                f"| WM: {'yes' if watermark_match else 'no'} "
                f"| Asset: {asset.title}"
            )

    return incidents_created


import os  # needed for watermark file check
