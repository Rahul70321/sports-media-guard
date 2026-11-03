"""
Anomaly & Risk Level Scoring Service
Evaluates risk factors such as high match score, watermark verification, platform risk, and rights policies.
"""
from dataclasses import dataclass, field
from datetime import datetime
import json
from typing import List, Optional

@dataclass
class AnomalyScoreResult:
    anomaly_score: float = 0.0
    risk_level: str = "Low"
    factors: List[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(self.factors)

def calculate_anomaly_score(
    match_score: float,
    watermark_match: bool,
    watermark_extracted: str,
    platform: str,
    rights_policy: str,
    asset_created_at: Optional[datetime],
    discovered_at: Optional[datetime],
    db_session=None
) -> AnomalyScoreResult:
    score = 0.0
    factors = []

    if watermark_match:
        score += 40.0
        factors.append("Forensic watermark verified")

    if match_score >= 95.0:
        score += 35.0
        factors.append("Near-identical perceptual match (>=95%)")
    elif match_score >= 85.0:
        score += 25.0
        factors.append("High similarity match (>=85%)")
    elif match_score >= 75.0:
        score += 15.0
        factors.append("Moderate similarity match (>=75%)")

    if rights_policy in ["exclusive_broadcast", "strict_copyright", "region_locked_na"]:
        score += 15.0
        factors.append(f"Protected rights policy violation: {rights_policy}")

    if platform and platform.lower() in ["youtube", "telegram", "pirate_site", "reddit", "twitter", "x", "vk"]:
        score += 10.0
        factors.append(f"High-risk distribution platform: {platform}")

    anomaly_score = min(100.0, score)

    if anomaly_score >= 75.0:
        risk_level = "Critical"
    elif anomaly_score >= 50.0:
        risk_level = "High"
    elif anomaly_score >= 25.0:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    return AnomalyScoreResult(
        anomaly_score=anomaly_score,
        risk_level=risk_level,
        factors=factors
    )
