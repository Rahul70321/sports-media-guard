from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool
from datetime import datetime, timezone
import os


def utcnow() -> datetime:
    """Naive UTC timestamp, matching what SQLite/Postgres DateTime columns store."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

# Fetch from environment (e.g. postgresql://user:pass@host:port/dbname)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sports_media.db")

# If using PostgreSQL or MySQL, check_same_thread isn't needed
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine_options = {"connect_args": connect_args}
if DATABASE_URL.startswith("sqlite"):
    # Background crawler work and request handlers use separate threads.
    # Avoid retaining thread-bound SQLite connections between requests.
    engine_options["poolclass"] = NullPool

engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, default="Sports Media Guard")
    created_at = Column(DateTime, default=utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, default="User")
    role = Column(String, default="analyst") # 'admin', 'legal', 'analyst'
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)


class PasswordResetToken(Base):
    """One-time password reset token. Only the SHA-256 hash is stored."""
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String, nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String)
    file_path = Column(String)
    media_type = Column(String) # 'image' or 'video'
    rights_policy = Column(String) # e.g., 'exclusive_broadcast', 'region_locked_na'
    created_at = Column(DateTime, default=utcnow)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    content_sha256 = Column(String, nullable=True, index=True)
    media_metadata = Column(Text, nullable=True)
    algorithm_version = Column(String, nullable=True, default="visual-v1")

    # Multi-algorithm fingerprints
    fingerprint_hash = Column(String, index=True)    # Primary phash (backward compat)
    fingerprint_phash = Column(String, index=True)    # Perceptual hash
    fingerprint_dhash = Column(String, index=True)    # Difference hash
    fingerprint_histogram = Column(Text)              # JSON-serialized HSV histogram
    video_frame_hashes = Column(Text)                 # JSON array of per-frame phashes

    # Forensic watermark
    watermark_id = Column(String)                     # The ID embedded during upload (e.g. ORG-17...)

class DiscoveredMedia(Base):
    __tablename__ = "discovered_media"

    id = Column(Integer, primary_key=True, index=True)
    source_url = Column(String, index=True)
    platform = Column(String)
    platform_item_id = Column(String, nullable=True, index=True)
    evidence_type = Column(String, nullable=False, default="metadata_only")
    authorization_mode = Column(String, nullable=False, default="manual_upload")
    capabilities_json = Column(Text, nullable=True)
    source_metadata = Column(Text, nullable=True)
    content_sha256 = Column(String, nullable=True, index=True)
    file_path = Column(String)                        # local downloaded path for analysis
    discovered_at = Column(DateTime, default=utcnow)

    # Multi-algorithm fingerprints
    fingerprint_hash = Column(String)                 # Primary phash (backward compat)
    fingerprint_phash = Column(String)
    fingerprint_dhash = Column(String)
    fingerprint_histogram = Column(Text)
    video_frame_hashes = Column(Text)                 # JSON array of per-frame phashes

    # Watermark verification
    watermark_extracted = Column(String, nullable=True)   # Extracted watermark text (if found)
    watermark_verified = Column(Boolean, default=False)   # Whether watermark matched an asset

class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id", ondelete="CASCADE"))
    discovered_media_id = Column(Integer, ForeignKey("discovered_media.id"))
    match_score = Column(Float)                       # Composite weighted score 0 to 100
    status = Column(String, default="pending_review")  # workflow state
    confidence_label = Column(String, nullable=False, default="inconclusive")
    video_frame_score = Column(Float, default=0.0)
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)
    review_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Individual similarity signal scores
    phash_score = Column(Float, default=0.0)
    dhash_score = Column(Float, default=0.0)
    histogram_score = Column(Float, default=0.0)

    # Watermark verification
    watermark_match = Column(Boolean, default=False)

    # Anomaly scoring
    anomaly_score = Column(Float, default=0.0)        # Composite risk score 0-100
    anomaly_factors = Column(Text)                    # JSON list of triggered risk factor descriptions
    risk_level = Column(String, default="Low")        # 'Critical', 'High', 'Medium', 'Low'

    # Evidence bundle
    evidence_summary = Column(Text)                   # JSON with full forensic detail

class SystemSettings(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    settings_data = Column(String) # Stored as JSON string
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class ScanJob(Base):
    __tablename__ = "scan_jobs"

    id = Column(String, primary_key=True, index=True)
    url = Column(String, nullable=False)
    platform = Column(String, nullable=False)
    status = Column(String, nullable=False, default="queued", index=True)
    progress = Column(Integer, nullable=False, default=0)
    message = Column(String, nullable=False, default="Scan queued")
    result_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class MonitoringTarget(Base):
    __tablename__ = "monitoring_targets"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    name = Column(String, nullable=False)
    adapter_type = Column(String, nullable=False, index=True)
    canonical_url = Column(String, nullable=False)
    configuration_json = Column(Text, nullable=True)
    authorization_mode = Column(String, nullable=False, default="public_api")
    capabilities_json = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="active", index=True)
    last_success_at = Column(DateTime, nullable=True)
    last_failure_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class TargetSchedule(Base):
    __tablename__ = "target_schedules"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("monitoring_targets.id", ondelete="CASCADE"), nullable=False, index=True)
    interval_seconds = Column(Integer, nullable=False, default=900)
    timezone = Column(String, nullable=False, default="UTC")
    enabled = Column(Boolean, nullable=False, default=True)
    next_run_at = Column(DateTime, nullable=True, index=True)
    concurrency_policy = Column(String, nullable=False, default="skip")
    max_attempts = Column(Integer, nullable=False, default=3)
    created_at = Column(DateTime, default=utcnow)


class MonitoringRun(Base):
    __tablename__ = "monitoring_runs"

    id = Column(String, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("monitoring_targets.id"), nullable=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    adapter_type = Column(String, nullable=False)
    status = Column(String, nullable=False, default="queued", index=True)
    progress = Column(Integer, nullable=False, default=0)
    message = Column(String, nullable=False, default="Queued")
    attempt = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    checkpoint_json = Column(Text, nullable=True)
    metrics_json = Column(Text, nullable=True)
    error_class = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    idempotency_key = Column(String, nullable=True, unique=True, index=True)
    lease_owner = Column(String, nullable=True)
    lease_expires_at = Column(DateTime, nullable=True, index=True)
    heartbeat_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class RunEvent(Base):
    __tablename__ = "run_events"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String, ForeignKey("monitoring_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String, nullable=False)
    progress = Column(Integer, nullable=False, default=0)
    message = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow)


class EvidenceObject(Base):
    __tablename__ = "evidence_objects"

    id = Column(Integer, primary_key=True, index=True)
    discovered_media_id = Column(Integer, ForeignKey("discovered_media.id"), nullable=True, index=True)
    evidence_type = Column(String, nullable=False)
    storage_key = Column(String, nullable=False)
    content_type = Column(String, nullable=True)
    byte_size = Column(Integer, nullable=True)
    sha256 = Column(String, nullable=False, index=True)
    source_url = Column(String, nullable=True)
    authorization_mode = Column(String, nullable=False, default="manual_upload")
    created_at = Column(DateTime, default=utcnow)


class EvidenceManifest(Base):
    __tablename__ = "evidence_manifests"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=True, index=True)
    discovered_media_id = Column(Integer, ForeignKey("discovered_media.id"), nullable=True, index=True)
    version = Column(Integer, nullable=False, default=1)
    manifest_json = Column(Text, nullable=False)
    digest = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=utcnow)


class IncidentEvent(Base):
    __tablename__ = "incident_events"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    event_type = Column(String, nullable=False)
    old_status = Column(String, nullable=True)
    new_status = Column(String, nullable=True)
    reason = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class EnforcementCase(Base):
    __tablename__ = "enforcement_cases"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False, unique=True, index=True)
    status = Column(String, nullable=False, default="draft")
    jurisdiction = Column(String, nullable=True)
    claimant = Column(String, nullable=True)
    notice_text = Column(Text, nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class EnforcementAction(Base):
    __tablename__ = "enforcement_actions"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("enforcement_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String, nullable=False)
    status = Column(String, nullable=False, default="prepared")
    provider_reference = Column(String, nullable=True)
    request_json = Column(Text, nullable=True)
    response_json = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False, index=True)
    resource_type = Column(String, nullable=False)
    resource_id = Column(String, nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    event_type = Column(String, nullable=False)
    channel = Column(String, nullable=False)
    dedupe_key = Column(String, nullable=True, unique=True, index=True)
    status = Column(String, nullable=False, default="pending")
    payload_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    delivered_at = Column(DateTime, nullable=True)


class ScanJobEvent(Base):
    __tablename__ = "scan_job_events"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, ForeignKey("scan_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String, nullable=False)
    progress = Column(Integer, nullable=False, default=0)
    message = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow)


Base.metadata.create_all(bind=engine)

# Compatibility bridge for databases created before the durable monitoring schema.
# Alembic is the intended migration path for new deployments.
_COMPATIBILITY_COLUMNS = {
    "users": {"organization_id": "INTEGER"},
    "assets": {
        "organization_id": "INTEGER",
        "content_sha256": "VARCHAR",
        "media_metadata": "TEXT",
        "algorithm_version": "VARCHAR",
    },
    "discovered_media": {
        "video_frame_hashes": "TEXT",
        "platform_item_id": "VARCHAR",
        "evidence_type": "VARCHAR",
        "authorization_mode": "VARCHAR",
        "capabilities_json": "TEXT",
        "source_metadata": "TEXT",
        "content_sha256": "VARCHAR",
    },
    "incidents": {
        "confidence_label": "VARCHAR",
        "video_frame_score": "FLOAT",
        "assigned_to": "INTEGER",
        "review_reason": "TEXT",
        "updated_at": "DATETIME",
    },
}
inspector = inspect(engine)
for table_name, additions in _COMPATIBILITY_COLUMNS.items():
    if table_name not in inspector.get_table_names():
        continue
    existing = {column["name"] for column in inspector.get_columns(table_name)}
    missing = {name: definition for name, definition in additions.items() if name not in existing}
    if missing:
        with engine.begin() as connection:
            for name, definition in missing.items():
                connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {name} {definition}"))
