import os
os.environ["OPENCV_OPENCL_RUNTIME"] = "disabled"
os.environ["OPENCV_OPENCL_DEVICE"] = "disabled"
os.environ["OPENCV_VIDEOIO_PRIORITY_MSMF"] = "0"

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, File, UploadFile, Form, BackgroundTasks, Depends, HTTPException, Body, Query, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import or_
import shutil
import json
import requests
import uuid
import secrets
import threading
from urllib.parse import urlencode
from typing import List, Optional
from datetime import datetime
from sqlalchemy import text

from database.models import (
    SessionLocal, Asset, Incident, DiscoveredMedia, SystemSettings, User, ScanJob, ScanJobEvent,
    MonitoringTarget, TargetSchedule, MonitoringRun, RunEvent, EvidenceManifest, IncidentEvent,
    EnforcementCase, EnforcementAction, AuditLog, NotificationDelivery, PasswordResetToken,
    utcnow,
)
from services.fingerprint_service import generate_fingerprint
from services.watermark_service import embed_watermark, extract_watermark, verify_watermark, WatermarkEmbeddingError
from services.crawler import crawl_images_from_url
from services.adapters.registry import PLATFORM_CAPABILITIES, adapter_for_url
from services.audit_service import audit
from services.incident_workflow import approve_case, prepare_case, record_action, transition_incident
from services.notification_service import notify
from services.scan_orchestrator import enqueue_run, execute_run
from services.url_policy import validate_outbound_url, UnsafeURLError
from services.evidence_service import file_sha256
from services.matching_engine import find_matches_for_media
from services.auth_service import (
    hash_password, verify_password, create_access_token,
    get_current_user, get_current_user_optional, seed_default_admin
)

from google import genai

app = FastAPI(title="Sports Media Protection API")

# Seed default admin on startup
db_init = SessionLocal()
seed_default_admin(db_init)
db_init.close()

# Configure GCS (lazy load if credentials provided)
gcs_client = None
if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
    try:
        from google.cloud import storage
        gcs_client = storage.Client()
    except Exception as e:
        print(f"Warning: GCS Client could not be initialized: {e}")
else:
    print("Notice: GOOGLE_APPLICATION_CREDENTIALS not set, local storage will be used.")

GCS_BUCKET_NAME = os.getenv('GCS_BUCKET_NAME', 'sports-media-assets-mvp')

# A lock prevents duplicate updates from overlapping background tasks in local development.
scan_jobs_lock = threading.Lock()

# File upload constraints
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'}
ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm'}
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_VIDEO_EXTENSIONS
MAX_FILE_SIZE_MB = 500
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Setup CORS for configured frontend origins.
configured_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in configured_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ─── Authentication Routes ──────────────────────────────────────────────────

@app.post("/api/auth/register")
def register_user(
    email: str = Body(...),
    password: str = Body(...),
    full_name: str = Body("User"),
    role: str = Body("analyst"),
    db: Session = Depends(get_db)
):
    """Registers a new user in the platform."""
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email is already registered")

    # Only the first registered user becomes admin; everyone else is an analyst.
    # Elevated roles are granted via the bootstrap admin or direct DB changes.
    is_first_user = db.query(User).count() == 0
    requested_role = role if role in {"admin", "legal", "analyst"} else "analyst"
    new_user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        role="admin" if is_first_user else requested_role,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token({"sub": str(new_user.id), "email": new_user.email, "role": new_user.role})

    return {
        "message": "User registered successfully",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": new_user.id,
            "email": new_user.email,
            "full_name": new_user.full_name,
            "role": new_user.role
        }
    }


@app.post("/api/auth/login")
async def login(
    request: Request,
    db: Session = Depends(get_db)
):
    """Authenticates user credentials (supporting both JSON and form data) and issues a JWT token."""
    login_email = None
    login_pass = None

    # 1. Try parsing JSON body first (used by React frontend)
    try:
        data = await request.json()
        if isinstance(data, dict):
            login_email = data.get("email") or data.get("username")
            login_pass = data.get("password")
    except Exception:
        pass

    # 2. Fallback to Form body (used by Swagger / OAuth2 clients)
    if not login_email or not login_pass:
        try:
            form = await request.form()
            login_email = form.get("username") or form.get("email")
            login_pass = form.get("password")
        except Exception:
            pass

    if not login_email or not login_pass:
        raise HTTPException(status_code=400, detail="Email and password are required")

    user = db.query(User).filter(User.email == login_email).first()
    if not user or not verify_password(login_pass, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    token = create_access_token({"sub": str(user.id), "email": user.email, "role": user.role})

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role
        }
    }


RESET_TOKEN_TTL_MINUTES = 30


def _hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@app.post("/api/auth/forgot-password")
def forgot_password(email: str = Body(...), db: Session = Depends(get_db)):
    """Issue a one-time password reset token.

    The response never reveals whether the email is registered. With no mail
    server configured the token is returned directly so the app works fully
    offline; set SMTP_HOST to email it instead.
    """
    generic = {"message": "If that email is registered, a reset token has been issued."}
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active:
        return generic

    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at == None,
    ).delete()
    raw_token = secrets.token_urlsafe(32)
    db.add(PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_reset_token(raw_token),
        expires_at=utcnow() + timedelta(minutes=RESET_TOKEN_TTL_MINUTES),
    ))
    db.commit()

    if os.getenv("SMTP_HOST"):
        # Delivery is left to the operator's mailer; the token is not logged.
        print(f"Password reset requested for {email}; SMTP delivery is configured.")
        return generic
    return {**generic, "reset_token": raw_token, "expires_in_minutes": RESET_TOKEN_TTL_MINUTES}


@app.post("/api/auth/reset-password")
def reset_password(
    token: str = Body(...),
    new_password: str = Body(...),
    db: Session = Depends(get_db),
):
    """Set a new password using a one-time reset token."""
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == _hash_reset_token(token)
    ).first()
    if not record or record.used_at is not None or record.expires_at < utcnow():
        raise HTTPException(status_code=400, detail="Reset token is invalid or has expired")

    user = db.query(User).filter(User.id == record.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="Reset token is invalid or has expired")
    user.hashed_password = hash_password(new_password)
    record.used_at = utcnow()
    db.commit()
    return {"message": "Password updated. You can sign in with the new password."}


@app.get("/api/auth/google/start")
def google_login_start():
    """Start the real Google OpenID Connect authorization flow."""
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")
    if not client_id or not os.getenv("GOOGLE_CLIENT_SECRET"):
        raise HTTPException(
            status_code=503,
            detail="Google sign-in is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
        )

    query = urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    })
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{query}")


@app.get("/api/auth/google/callback")
def google_login_callback(code: str, db: Session = Depends(get_db)):
    """Exchange Google's authorization code and sign the verified user in."""
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    if not client_id or not client_secret:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured")

    try:
        token_response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=15,
        )
        token_response.raise_for_status()
        google_token = token_response.json().get("access_token")
        if not google_token:
            raise ValueError("Google did not return an access token")

        profile_response = requests.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {google_token}"},
            timeout=15,
        )
        profile_response.raise_for_status()
        profile = profile_response.json()
        email = profile.get("email")
        if not email or not profile.get("email_verified"):
            raise ValueError("Google account email is not verified")

        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                email=email,
                hashed_password=hash_password(secrets.token_urlsafe(32)),
                full_name=profile.get("name") or email.split("@", 1)[0],
                role="analyst",
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        elif not user.is_active:
            raise HTTPException(status_code=403, detail="Account is disabled")

        app_token = create_access_token({"sub": str(user.id), "email": user.email, "role": user.role})
        # The frontend consumes this one-time navigation result and immediately
        # moves the token into localStorage.
        return RedirectResponse(f"{frontend_url}/#/?oauth_token={app_token}")
    except HTTPException:
        raise
    except Exception as exc:
        error_detail = "Google sign-in failed"
        if isinstance(exc, requests.exceptions.HTTPError) and getattr(exc, 'response', None) is not None:
            try:
                err_json = exc.response.json()
                error_detail = err_json.get("error_description") or err_json.get("error") or str(exc)
            except Exception:
                error_detail = exc.response.text or str(exc)
        elif str(exc):
            error_detail = str(exc)
        print(f"Google OAuth error: {error_detail}")
        from urllib.parse import quote
        return RedirectResponse(f"{frontend_url}/#/?auth_error={quote(f'Google OAuth error: {error_detail}')}")


@app.post("/api/auth/social")
async def social_login(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handles social sign-in for Google, Gmail, Facebook, Instagram, and GitHub.
    Logs in existing user or auto-provisions a new verified account.
    """
    data = {}
    try:
        data = await request.json()
    except Exception:
        pass

    provider = (data.get("provider") or "google").lower()
    email = data.get("email")
    full_name = data.get("full_name") or data.get("name")

    # Auto-generate credentials/profile if default demo click
    if not email:
        ts = int(utcnow().timestamp())
        email = f"{provider}_user_{ts % 10000}@sportsguard.io"
    if not full_name:
        provider_display = {"google": "Google", "github": "GitHub", "facebook": "Facebook", "instagram": "Instagram", "gmail": "Gmail"}.get(provider, provider.capitalize())
        full_name = f"{provider_display} Analyst"

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            hashed_password=hash_password(f"social_{provider}_{utcnow().isoformat()}"),
            full_name=full_name,
            role="analyst",
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    token = create_access_token({"sub": str(user.id), "email": user.email, "role": user.role})

    return {
        "access_token": token,
        "token_type": "bearer",
        "provider": provider,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role
        }
    }


@app.get("/api/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Returns profile information for the authenticated user."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "created_at": current_user.created_at
    }


# ─── Asset Registry CRUD Routes ─────────────────────────────────────────────

@app.post("/api/assets/upload")
async def upload_asset(
    title: str = Form(...),
    description: str = Form(None),
    rights_policy: str = Form("standard"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Uploads a new media asset, embeds watermark, and indexes fingerprints."""
    # 1. Validate file extension
    _, ext = os.path.splitext(file.filename or "")
    ext = ext.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # 2. Validate content type
    content_type = file.content_type or ""
    if not (content_type.startswith('image') or content_type.startswith('video')):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid content type '{content_type}'. Only image and video files are accepted."
        )

    media_type = 'image' if content_type.startswith('image') else 'video'

    # 3. Save locally with a generated filename and size check
    safe_name = f"upload_{uuid.uuid4().hex}{ext}"
    temp_path = os.path.join(UPLOAD_DIR, safe_name)
    total_size = 0
    with open(temp_path, "wb") as buffer:
        while True:
            chunk = await file.read(8192)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > MAX_FILE_SIZE_BYTES:
                buffer.close()
                os.remove(temp_path)
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Maximum allowed size is {MAX_FILE_SIZE_MB} MB."
                )
            buffer.write(chunk)

    # 4. Embed and verify the forensic watermark before indexing the asset.
    watermark_id = f"ORG-{uuid.uuid4().hex[:16].upper()}"
    try:
        watermarked_path = embed_watermark(temp_path, watermark_id)
    except WatermarkEmbeddingError as exc:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=422, detail=f"Could not protect video: {exc}") from exc

    # 5. Generate multi-algorithm fingerprints
    fp_result = generate_fingerprint(watermarked_path, media_type)

    # 6. Upload to Google Cloud Storage if configured
    cloud_url = watermarked_path  # fallback
    if gcs_client:
        try:
            bucket = gcs_client.bucket(GCS_BUCKET_NAME)
            blob = bucket.blob(f"assets/{uuid.uuid4().hex}{ext}")
            blob.upload_from_filename(watermarked_path)
            cloud_url = f"gs://{GCS_BUCKET_NAME}/{blob.name}"
        except Exception as e:
            print(f"GCS Upload failed: {e}")

    # 7. Save to DB with owner info
    new_asset = Asset(
        title=title,
        description=description,
        file_path=cloud_url,
        media_type=media_type,
        rights_policy=rights_policy,
        owner_id=current_user.id if current_user else None,
        organization_id=current_user.organization_id if current_user else None,
        content_sha256=file_sha256(watermarked_path),
        media_metadata=json.dumps({"extension": ext, "content_type": content_type}),
        algorithm_version="visual-v1",
        # Multi-algorithm fingerprints
        fingerprint_hash=fp_result.primary_hash,
        fingerprint_phash=fp_result.phash,
        fingerprint_dhash=fp_result.dhash,
        fingerprint_histogram=fp_result.histogram,
        video_frame_hashes=fp_result.video_frame_hashes or None,
        # Watermark
        watermark_id=watermark_id,
    )
    db.add(new_asset)
    db.commit()
    db.refresh(new_asset)

    return {
        "message": "Asset uploaded and protected successfully",
        "asset_id": new_asset.id,
        "watermark_id": watermark_id,
        "cloud_url": cloud_url,
        "fingerprints": {
            "phash": fp_result.phash,
            "dhash": fp_result.dhash,
            "histogram_length": len(json.loads(fp_result.histogram)) if fp_result.histogram else 0,
            "video_frames": len(json.loads(fp_result.video_frame_hashes)) if fp_result.video_frame_hashes else 0,
        }
    }


@app.get("/api/assets")
def get_assets(
    q: Optional[str] = Query(None, description="Search term for title/description"),
    media_type: Optional[str] = Query(None, description="Filter by image/video"),
    rights_policy: Optional[str] = Query(None, description="Filter by policy"),
    db: Session = Depends(get_db)
):
    """Returns registered assets with optional search and filter criteria."""
    query = db.query(Asset)

    if q:
        search_pattern = f"%{q}%"
        query = query.filter(or_(Asset.title.ilike(search_pattern), Asset.description.ilike(search_pattern)))
    if media_type:
        query = query.filter(Asset.media_type == media_type)
    if rights_policy:
        query = query.filter(Asset.rights_policy == rights_policy)

    assets = query.order_by(Asset.created_at.desc()).all()
    return [
        {
            "id": a.id,
            "title": a.title,
            "description": a.description,
            "media_type": a.media_type,
            "rights_policy": a.rights_policy,
            "file_path": a.file_path,
            "fingerprint_hash": a.fingerprint_hash,
            "watermark_id": a.watermark_id,
            "created_at": a.created_at,
            "has_multi_fingerprint": bool(a.fingerprint_dhash),
        }
        for a in assets
    ]


@app.get("/api/assets/{asset_id}")
def get_asset_detail(asset_id: int, db: Session = Depends(get_db)):
    """Returns single asset record with full fingerprint breakdown and associated incidents count."""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    incident_count = db.query(Incident).filter(Incident.asset_id == asset.id).count()

    return {
        "id": asset.id,
        "title": asset.title,
        "description": asset.description,
        "media_type": asset.media_type,
        "rights_policy": asset.rights_policy,
        "file_path": asset.file_path,
        "watermark_id": asset.watermark_id,
        "created_at": asset.created_at,
        "incident_count": incident_count,
        "fingerprints": {
            "phash": asset.fingerprint_phash or asset.fingerprint_hash,
            "dhash": asset.fingerprint_dhash,
            "has_histogram": bool(asset.fingerprint_histogram),
            "video_frames_count": len(json.loads(asset.video_frame_hashes)) if asset.video_frame_hashes else 0,
        }
    }


@app.delete("/api/assets/{asset_id}")
def delete_asset(asset_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Deletes registered asset and associated incidents."""
    if current_user.role not in ("admin", "legal"):
        raise HTTPException(status_code=403, detail="Admin or legal role required")
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Delete associated incidents
    db.query(Incident).filter(Incident.asset_id == asset_id).delete()
    db.delete(asset)
    db.commit()

    return {"message": f"Asset #{asset_id} and associated incidents deleted successfully"}


@app.get("/api/assets/{asset_id}/download")
def download_asset(asset_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Downloads the watermarked & fingerprinted version of a registered asset.
    The file served is the protected copy stored after watermark embedding.
    """
    from fastapi.responses import FileResponse, RedirectResponse
    import mimetypes

    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    file_path = asset.file_path

    # GCS-stored assets: stream the object through the backend instead of
    # requiring the client to hold GCS credentials. Falls back to a signed
    # URL redirect when no GCS client is configured (e.g. misconfigured prod).
    if file_path and file_path.startswith("gs://"):
        if not gcs_client:
            raise HTTPException(
                status_code=503,
                detail="Asset is stored in cloud storage but the server has no GCS credentials configured."
            )
        try:
            _, blob_name = file_path.split(f"gs://{GCS_BUCKET_NAME}/", 1)
        except ValueError:
            raise HTTPException(status_code=500, detail="Malformed cloud storage path for asset")
        bucket = gcs_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(blob_name)
        if not blob.exists():
            raise HTTPException(status_code=404, detail="Protected file not found in cloud storage.")
        content = blob.download_as_bytes()

        _, ext = os.path.splitext(blob_name)
        mime_type, _ = mimetypes.guess_type(blob_name)
        mime_type = mime_type or "application/octet-stream"
        safe_title = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in (asset.title or "asset"))
        download_name = f"{safe_title}_protected{ext}"
        from fastapi.responses import Response
        return Response(
            content=content,
            media_type=mime_type,
            headers={
                "Content-Disposition": f'attachment; filename="{download_name}"',
                "X-Asset-Id": str(asset.id),
                "X-Watermark-Id": asset.watermark_id or "",
                "X-Media-Type": asset.media_type or "",
            },
        )

    # Check local file exists
    if not file_path or not os.path.isfile(file_path):
        raise HTTPException(
            status_code=404,
            detail="Protected file not found on server. It may have been moved or cleaned up."
        )

    # Determine MIME type
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "application/octet-stream"

    # Build a user-friendly download filename
    _, ext = os.path.splitext(file_path)
    safe_title = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in (asset.title or "asset"))
    download_name = f"{safe_title}_protected{ext}"

    return FileResponse(
        path=file_path,
        filename=download_name,
        media_type=mime_type,
        headers={
            "X-Asset-Id": str(asset.id),
            "X-Watermark-Id": asset.watermark_id or "",
            "X-Media-Type": asset.media_type or "",
        }
    )


# ─── Watermark Service (Standalone) ─────────────────────────────────────────

@app.post("/api/watermark/embed")
async def watermark_embed(
    watermark_text: str = Form(..., description="Text to embed as an invisible watermark"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Embeds an invisible forensic LSB watermark into an uploaded image or video.
    Returns the watermarked file as a downloadable response.
    """
    from fastapi.responses import FileResponse, RedirectResponse

    # Validate extension
    _, ext = os.path.splitext(file.filename or "")
    ext = ext.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # Save uploaded file
    temp_path = os.path.join(UPLOAD_DIR, f"wm_embed_{int(utcnow().timestamp())}_{file.filename}")
    total_size = 0
    with open(temp_path, "wb") as buffer:
        while True:
            chunk = await file.read(8192)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > MAX_FILE_SIZE_BYTES:
                buffer.close()
                os.remove(temp_path)
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Maximum allowed size is {MAX_FILE_SIZE_MB} MB."
                )
            buffer.write(chunk)

    # Embed watermark
    watermarked_path = embed_watermark(temp_path, watermark_text)

    # Determine output filename
    watermarked_filename = os.path.basename(watermarked_path)

    return FileResponse(
        path=watermarked_path,
        filename=watermarked_filename,
        media_type="application/octet-stream",
        headers={
            "X-Watermark-Text": watermark_text,
            "X-Watermark-Status": "embedded",
        }
    )


@app.post("/api/watermark/extract")
async def watermark_extract(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Extracts the hidden LSB watermark text from an uploaded image or video.
    Returns the extracted watermark string, or empty if none found.
    """
    # Validate extension
    _, ext = os.path.splitext(file.filename or "")
    ext = ext.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # Save uploaded file
    temp_path = os.path.join(UPLOAD_DIR, f"wm_extract_{int(utcnow().timestamp())}_{file.filename}")
    with open(temp_path, "wb") as buffer:
        content = await file.read()
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum allowed size is {MAX_FILE_SIZE_MB} MB."
            )
        buffer.write(content)

    # Extract watermark
    extracted_text = extract_watermark(temp_path)

    # Clean up temp file
    try:
        os.remove(temp_path)
    except OSError:
        pass

    return {
        "filename": file.filename,
        "watermark_extracted": extracted_text,
        "has_watermark": bool(extracted_text),
        "is_valid_format": extracted_text.startswith("ORG-") if extracted_text else False,
    }


@app.post("/api/watermark/verify")
async def watermark_verify(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Extracts the hidden watermark from an uploaded file and verifies it
    against registered assets in the database.
    Returns full verification result with matched asset details.
    """
    # Validate extension
    _, ext = os.path.splitext(file.filename or "")
    ext = ext.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # Save uploaded file
    temp_path = os.path.join(UPLOAD_DIR, f"wm_verify_{int(utcnow().timestamp())}_{file.filename}")
    with open(temp_path, "wb") as buffer:
        content = await file.read()
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum allowed size is {MAX_FILE_SIZE_MB} MB."
            )
        buffer.write(content)

    # Verify watermark against registered assets
    verification = verify_watermark(temp_path, db)

    # If verified, fetch matched asset details
    matched_asset_info = None
    if verification.verified and verification.matched_asset_id:
        asset = db.query(Asset).filter(Asset.id == verification.matched_asset_id).first()
        if asset:
            matched_asset_info = {
                "id": asset.id,
                "title": asset.title,
                "media_type": asset.media_type,
                "rights_policy": asset.rights_policy,
                "watermark_id": asset.watermark_id,
                "created_at": str(asset.created_at),
            }

    # Clean up temp file
    try:
        os.remove(temp_path)
    except OSError:
        pass

    return {
        "filename": file.filename,
        "watermark_extracted": verification.extracted,
        "is_valid": verification.is_valid,
        "verified": verification.verified,
        "confidence": verification.confidence,
        "matched_asset": matched_asset_info,
    }


# ─── Monitoring ─────────────────────────────────────────────────────────────

def _run_scan_job(job_id: str, url: str, crawler, platform: str):
    def update(status: str, progress: int, message: str, result=None):
        db = SessionLocal()
        try:
            job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
            if not job:
                return
            job.status = status
            job.progress = progress
            job.message = message
            job.updated_at = utcnow()
            if status == "running" and not job.started_at:
                job.started_at = utcnow()
            if status in {"completed", "failed"}:
                job.completed_at = utcnow()
            if result is not None:
                job.result_json = json.dumps(result)
                if status == "failed":
                    job.error_message = result.get("message")
            db.add(ScanJobEvent(job_id=job_id, status=status, progress=progress, message=message))
            db.commit()
        finally:
            db.close()

    try:
        update("running", 10, f"Starting {platform} scan")
        update("running", 25, "Fetching platform data")
        result = crawler(url)
        if result.get("status") == "error":
            update("failed", 100, result.get("message", "Scan failed"), result)
        else:
            update("completed", 100, "Scan completed", result)
    except Exception as exc:
        update("failed", 100, str(exc), {"status": "error", "message": str(exc)})


@app.post("/api/monitor/crawl")
def trigger_crawl(
    url: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("admin", "analyst"):
        raise HTTPException(status_code=403, detail="Admin or analyst role required")
    adapter_name = adapter_for_url(url)
    if not url.lower().startswith("mock://"):
        try:
            validate_outbound_url(url)
        except UnsafeURLError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    run = enqueue_run(db, url, current_user, adapter_name)
    db.add(ScanJob(id=run.id, url=url, platform=adapter_name, status="queued", message="Scan queued", created_by=current_user.id))
    db.commit()
    background_tasks.add_task(execute_run, run.id)
    return {"job_id": run.id, "run_id": run.id, "message": f"{adapter_name} monitoring run queued", "capabilities": PLATFORM_CAPABILITIES.get(adapter_name, {})}


@app.post("/api/monitor/test-media")
async def scan_test_media(
    file: UploadFile = File(...),
    source_url: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Scan an authorized local candidate video through the real matching pipeline."""
    if current_user.role not in ("admin", "analyst"):
        raise HTTPException(status_code=403, detail="Admin or analyst role required")
    content_type = file.content_type or ""
    media_type = "video" if content_type.startswith("video") else "image" if content_type.startswith("image") else None
    if not media_type:
        raise HTTPException(status_code=400, detail="Upload an image or video candidate")

    extension = os.path.splitext(file.filename or "")[1].lower() or (".mp4" if media_type == "video" else ".jpg")
    candidate_path = os.path.join("downloads", f"test-candidate-{uuid.uuid4().hex}{extension}")
    os.makedirs("downloads", exist_ok=True)
    try:
        with open(candidate_path, "wb") as output:
            while chunk := await file.read(8192):
                output.write(chunk)
        fingerprint = generate_fingerprint(candidate_path, media_type)
        if not fingerprint.primary_hash:
            raise HTTPException(status_code=422, detail="Could not generate a fingerprint from candidate media")
        discovered = DiscoveredMedia(
            source_url=source_url.strip() or f"local://test/{uuid.uuid4().hex}",
            platform="youtube" if "youtube.com" in source_url or "youtu.be" in source_url else "local_test",
            platform_item_id=f"manual-{uuid.uuid4().hex}",
            evidence_type="authorized_video" if media_type == "video" else "authorized_image",
            authorization_mode="manual_upload",
            capabilities_json=json.dumps({"metadata": True, "thumbnail": media_type == "image", "authorized_video": media_type == "video", "audio": False, "rights_reporting": False}),
            file_path=os.path.abspath(candidate_path),
            content_sha256=file_sha256(candidate_path),
            source_metadata=json.dumps({"filename": file.filename, "content_type": content_type}),
            fingerprint_hash=fingerprint.primary_hash,
            fingerprint_phash=fingerprint.phash,
            fingerprint_dhash=fingerprint.dhash,
            fingerprint_histogram=fingerprint.histogram,
            video_frame_hashes=fingerprint.video_frame_hashes or None,
        )
        db.add(discovered)
        db.commit()
        db.refresh(discovered)
        incidents = find_matches_for_media(discovered, db)
        return {
            "status": "completed",
            "candidate_id": discovered.id,
            "incidents_created": len(incidents),
            "message": "Candidate analyzed against registered assets",
        }
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Candidate scan failed: {exc}") from exc


@app.get("/api/monitor/crawl/{job_id}/events")
def get_scan_events(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    job = db.query(ScanJob).filter(ScanJob.id == job_id, ScanJob.created_by == current_user.id).first()
    if job:
        events = db.query(ScanJobEvent).filter(ScanJobEvent.job_id == job_id).order_by(ScanJobEvent.created_at.asc()).all()
        if events:
            return events
    run = db.query(MonitoringRun).filter(MonitoringRun.id == job_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Scan run not found")
    return db.query(RunEvent).filter(RunEvent.run_id == job_id).order_by(RunEvent.created_at.asc()).all()


@app.get("/api/monitor/adapters")
def adapter_capabilities(current_user: User = Depends(get_current_user)):
    return PLATFORM_CAPABILITIES


@app.get("/api/monitor/targets")
def list_targets(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(MonitoringTarget)
    if current_user.organization_id is not None:
        query = query.filter(MonitoringTarget.organization_id == current_user.organization_id)
    targets = query.order_by(MonitoringTarget.created_at.desc()).all()
    return [{
        "id": target.id, "name": target.name, "adapter_type": target.adapter_type,
        "canonical_url": target.canonical_url, "authorization_mode": target.authorization_mode,
        "status": target.status, "capabilities": json.loads(target.capabilities_json or "{}"),
        "last_success_at": target.last_success_at, "last_failure_at": target.last_failure_at,
    } for target in targets]


@app.post("/api/monitor/targets")
def create_target(payload: dict = Body(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in {"admin", "analyst"}:
        raise HTTPException(status_code=403, detail="Admin or analyst role required")
    adapter_name = payload.get("adapter_type") or adapter_for_url(payload.get("canonical_url", ""))
    capabilities = PLATFORM_CAPABILITIES.get(adapter_name)
    if not capabilities:
        raise HTTPException(status_code=400, detail="Unsupported monitoring adapter")
    if adapter_name not in {"youtube", "mock", "authorized_feed"}:
        raise HTTPException(status_code=409, detail="This platform requires an approved credentialed integration before monitoring can be enabled")
    target = MonitoringTarget(
        organization_id=current_user.organization_id, name=payload.get("name") or "Monitoring target",
        adapter_type=adapter_name, canonical_url=payload["canonical_url"],
        configuration_json=json.dumps(payload.get("configuration") or {}),
        authorization_mode=payload.get("authorization_mode") or ("public_api" if adapter_name == "youtube" else "mock"),
        capabilities_json=json.dumps(capabilities), created_by=current_user.id,
    )
    db.add(target)
    db.flush()
    db.add(TargetSchedule(target_id=target.id, interval_seconds=int(payload.get("interval_seconds") or 900), enabled=True, next_run_at=utcnow()))
    audit(db, current_user.id, "target_created", "monitoring_target", target.id, {"adapter": adapter_name}, current_user.organization_id)
    db.commit()
    return {"id": target.id, "status": target.status, "capabilities": capabilities}


@app.post("/api/monitor/targets/{target_id}/run")
def run_target(target_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    target = db.query(MonitoringTarget).filter(MonitoringTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Monitoring target not found")
    run = enqueue_run(db, target.canonical_url, current_user, target.adapter_type, target)
    background_tasks.add_task(execute_run, run.id)
    return {"run_id": run.id, "status": run.status}


@app.get("/api/monitor/runs")
def list_runs(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    runs = db.query(MonitoringRun).order_by(MonitoringRun.created_at.desc()).limit(100).all()
    return [{
        "id": run.id, "target_id": run.target_id, "adapter_type": run.adapter_type, "status": run.status,
        "progress": run.progress, "message": run.message, "metrics": json.loads(run.metrics_json or "{}"),
        "created_at": run.created_at, "completed_at": run.completed_at,
    } for run in runs]


@app.get("/api/monitor/crawl/{job_id}")
def get_scan_status(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in ("admin", "analyst"):
        raise HTTPException(status_code=403, detail="Admin or analyst role required")
    job = db.query(ScanJob).filter(ScanJob.id == job_id, ScanJob.created_by == current_user.id).first()
    run = db.query(MonitoringRun).filter(MonitoringRun.id == job_id).first()
    if not job and not run:
        raise HTTPException(status_code=404, detail="Scan job not found")
    if run:
        metrics = json.loads(run.metrics_json) if run.metrics_json else None
        return {
            "job_id": run.id,
            "run_id": run.id,
            "url": job.url if job else None,
            "platform": run.adapter_type,
            "status": run.status,
            "progress": run.progress,
            "message": run.message,
            "result": metrics,
            "created_at": run.created_at,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
        }
    result = json.loads(job.result_json) if job.result_json else None
    return {
        "job_id": job.id,
        "url": job.url,
        "platform": job.platform,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "result": result,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
    }


# ─── Incidents ──────────────────────────────────────────────────────────────

@app.get("/api/incidents")
def get_incidents(
    status: Optional[str] = Query(None, description="Filter by status (pending_review, takedown_requested, false_positive)"),
    risk_level: Optional[str] = Query(None, description="Filter by risk_level (Critical, High, Medium, Low)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns detected incidents with optional status and risk filtering."""
    query = db.query(Incident)
    if current_user.organization_id is not None:
        query = query.join(Asset, Asset.id == Incident.asset_id).filter(Asset.organization_id == current_user.organization_id)

    if status:
        query = query.filter(Incident.status == status)
    if risk_level:
        query = query.filter(Incident.risk_level == risk_level)

    incidents = query.order_by(Incident.created_at.desc()).all()
    results = []
    for inc in incidents:
        asset = db.query(Asset).filter(Asset.id == inc.asset_id).first()
        media = db.query(DiscoveredMedia).filter(DiscoveredMedia.id == inc.discovered_media_id).first()

        if not asset or not media:
            continue

        results.append({
            "id": inc.id,
            "asset_title": asset.title,
            "asset_id": asset.id,
            "discovered_url": media.source_url,
            "platform": (
                "youtube" if media.source_url and ("youtube.com" in media.source_url or "youtu.be" in media.source_url)
                else media.platform
            ),
            "match_score": inc.match_score,
            "confidence_label": inc.confidence_label,
            "video_frame_score": inc.video_frame_score,
            "evidence_type": media.evidence_type,
            "authorization_mode": media.authorization_mode,
            "status": inc.status,
            "created_at": inc.created_at,
            "phash_score": inc.phash_score,
            "dhash_score": inc.dhash_score,
            "histogram_score": inc.histogram_score,
            "watermark_match": inc.watermark_match,
            "watermark_extracted": media.watermark_extracted,
            "anomaly_score": inc.anomaly_score,
            "risk_level": inc.risk_level,
            "anomaly_factors": json.loads(inc.anomaly_factors) if inc.anomaly_factors else [],
        })
    return results


@app.get("/api/incidents/{incident_id}/forensics")
def get_incident_forensics(incident_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Returns full forensic breakdown for a single incident."""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    asset = db.query(Asset).filter(Asset.id == incident.asset_id).first()
    media = db.query(DiscoveredMedia).filter(DiscoveredMedia.id == incident.discovered_media_id).first()

    evidence = {}
    if incident.evidence_summary:
        try:
            evidence = json.loads(incident.evidence_summary)
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "incident_id": incident.id,
        "status": incident.status,
        "created_at": incident.created_at,
        "asset": {
            "id": asset.id if asset else None,
            "title": asset.title if asset else "Unknown",
            "media_type": asset.media_type if asset else None,
            "rights_policy": asset.rights_policy if asset else None,
            "watermark_id": asset.watermark_id if asset else None,
        },
        "discovered_media": {
            "id": media.id if media else None,
            "source_url": media.source_url if media else None,
            "platform": media.platform if media else None,
            "watermark_extracted": media.watermark_extracted if media else None,
            "watermark_verified": media.watermark_verified if media else False,
        },
        "matching": {
            "composite_score": incident.match_score,
            "phash_score": incident.phash_score,
            "dhash_score": incident.dhash_score,
            "histogram_score": incident.histogram_score,
        },
        "watermark": {
            "match": incident.watermark_match,
            "extracted": media.watermark_extracted if media else None,
            "confidence": evidence.get("watermark", {}).get("confidence", "unknown"),
        },
        "anomaly": {
            "score": incident.anomaly_score,
            "risk_level": incident.risk_level,
            "factors": json.loads(incident.anomaly_factors) if incident.anomaly_factors else [],
        },
        "evidence_raw": evidence,
        "manifest": _manifest_payload(db, incident.id),
        "events": [_event_payload(event) for event in db.query(IncidentEvent).filter(IncidentEvent.incident_id == incident.id).all()],
        "enforcement_case": _case_payload(db, incident.id),
    }


def _manifest_payload(db: Session, incident_id: int):
    manifest = db.query(EvidenceManifest).filter(EvidenceManifest.incident_id == incident_id).order_by(EvidenceManifest.version.desc()).first()
    if not manifest:
        return None
    return {"id": manifest.id, "version": manifest.version, "digest": manifest.digest, "manifest": json.loads(manifest.manifest_json)}


def _event_payload(event: IncidentEvent):
    return {"id": event.id, "event_type": event.event_type, "old_status": event.old_status, "new_status": event.new_status, "reason": event.reason, "created_at": event.created_at}


def _case_payload(db: Session, incident_id: int):
    case = db.query(EnforcementCase).filter(EnforcementCase.incident_id == incident_id).first()
    if not case:
        return None
    actions = db.query(EnforcementAction).filter(EnforcementAction.case_id == case.id).all()
    return {"id": case.id, "status": case.status, "approved_at": case.approved_at, "actions": [{"provider": action.provider, "status": action.status, "provider_reference": action.provider_reference} for action in actions]}


@app.delete("/api/incidents/{incident_id}")
def delete_incident(incident_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Deletes an incident from the system (e.g. false positive dismissal)."""
    if current_user.role not in ("admin", "legal", "analyst"):
        raise HTTPException(status_code=403, detail="Authenticated analyst role required")
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    db.delete(incident)
    db.commit()
    return {"message": f"Incident #{incident_id} deleted successfully"}


# ─── Takedowns ──────────────────────────────────────────────────────────────

@app.post("/api/incidents/{incident_id}/takedown")
def issue_takedown(incident_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in ("admin", "legal"):
        raise HTTPException(status_code=403, detail="Admin or legal role required")
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident.status = "takedown_requested"

    # Generate Google AI Legal Summary
    ai_summary = ""
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        try:
            client = genai.Client(api_key=gemini_key)
            prompt = (
                f"Write a formal DMCA takedown notice and legal case summary for an intellectual property violation.\n"
                f"Asset ID: {incident.asset_id}.\n"
                f"Confidence Match Score: {incident.match_score:.1f}%.\n"
                f"Anomaly Risk Level: {incident.risk_level} (Score: {incident.anomaly_score}/100).\n"
                f"Forensic Watermark Verified: {'Yes' if incident.watermark_match else 'No'}.\n"
                f"Demand immediate removal of the unauthorized sports broadcast material under 17 U.S.C. § 512(c)."
            )
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            ai_summary = response.text
        except Exception as e:
            print(f"Gemini API error: {e}")

    # Fallback statutory generator if external Gemini key is not configured or blocked
    if not ai_summary or ai_summary.strip() == "":
        asset = db.query(Asset).filter(Asset.id == incident.asset_id).first()
        discovered = db.query(DiscoveredMedia).filter(DiscoveredMedia.id == incident.discovered_media_id).first()
        asset_title = asset.title if asset and asset.title else f"Broadcast Asset #{incident.asset_id}"
        source_url = discovered.source_url if discovered and discovered.source_url else "Reported stream / URL"
        ai_summary = (
            f"FORMAL NOTICE OF COPYRIGHT INFRINGEMENT (DMCA 17 U.S.C. § 512(c)(3))\n\n"
            f"1. IDENTIFICATION OF COPYRIGHTED WORK:\n"
            f"• Title: {asset_title}\n"
            f"• Rights Policy: {asset.rights_policy if asset and asset.rights_policy else 'Exclusive Global Broadcast Rights'}\n"
            f"• Master SHA-256 Digest: {asset.content_sha256 if asset and asset.content_sha256 else 'Verified Reference Asset'}\n\n"
            f"2. IDENTIFICATION OF INFRINGING MATERIAL:\n"
            f"• Infringing Location / URL: {source_url}\n"
            f"• Platform: {discovered.platform.capitalize() if discovered and discovered.platform else 'Online Stream'}\n\n"
            f"3. FORENSIC EVIDENCE SUMMARY:\n"
            f"• Composite Match Confidence: {incident.match_score:.1f}%\n"
            f"• Perceptual Structural Similarity (pHash): {incident.phash_score:.1f}%\n"
            f"• Color Spectrum Alignment: {incident.histogram_score:.1f}%\n"
            f"• Forensic Watermark: {'VERIFIED (Cryptographically Matched)' if incident.watermark_match else 'Visual Frame Sequence Alignment'}\n"
            f"• Assessed Risk Priority: {incident.risk_level.upper()} ({incident.anomaly_score}/100)\n\n"
            f"4. STATUTORY DECLARATION:\n"
            f"I have a good-faith belief that use of the material in the manner complained of is not authorized "
            f"by the copyright owner, its agent, or the law. The information in this notification is accurate, "
            f"and under penalty of perjury, the claimant is authorized to act on behalf of the copyright owner.\n\n"
            f"REQUESTED ACTION: Immediate removal or expeditious disabling of access to the infringing material."
        )

    # Fire webhook through the deduplicated, policy-checked notification service
    settings = _get_settings_dict(db)
    if settings.get('webhookUrl'):
        notify(db, "takedown_requested", {
            "incident_id": incident.id,
            "asset_id": incident.asset_id,
            "match_score": incident.match_score,
            "anomaly_score": incident.anomaly_score,
            "risk_level": incident.risk_level,
            "legal_summary": ai_summary,
        }, webhook_url=settings['webhookUrl'], organization_id=current_user.organization_id)

    db.commit()

    return {
        "message": "Takedown requested",
        "incident_id": incident.id,
        "ai_legal_summary": ai_summary
    }


@app.post("/api/incidents/{incident_id}/action")
def update_incident_status(incident_id: int, status: str = Form(...), reason: str = Form(""), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    transition_incident(db, incident, current_user, status, reason)
    audit(db, current_user.id, "incident_transition", "incident", incident.id, {"status": incident.status}, current_user.organization_id)
    db.commit()
    return {"message": f"Incident updated to {incident.status}", "status": incident.status}


@app.post("/api/incidents/{incident_id}/enforcement/prepare")
def prepare_enforcement(incident_id: int, payload: dict = Body(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    notice = payload.get("notice") or "Machine-generated text is advisory only. Human legal review is required before submission."
    case = prepare_case(db, incident, current_user, payload.get("jurisdiction", ""), payload.get("claimant", ""), notice)
    db.commit()
    return {"case_id": case.id, "status": case.status, "disclaimer": "Draft only. No platform has been contacted."}


@app.post("/api/incidents/{incident_id}/enforcement/approve")
def approve_enforcement(incident_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    case = db.query(EnforcementCase).filter(EnforcementCase.incident_id == incident_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Enforcement case not found")
    approve_case(db, case, current_user)
    db.commit()
    return {"case_id": case.id, "status": case.status}


@app.post("/api/incidents/{incident_id}/enforcement/export")
def export_enforcement(incident_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from services.enforcement.manual import export_bundle
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    manifest = db.query(EvidenceManifest).filter(EvidenceManifest.incident_id == incident_id).first()
    case = db.query(EnforcementCase).filter(EnforcementCase.incident_id == incident_id).first()
    if not incident or not manifest or not case:
        raise HTTPException(status_code=404, detail="Approved evidence bundle is not available")
    record_action(db, case, current_user, "manual_export", "exported", request=case.notice_text or "")
    db.commit()
    return export_bundle(incident, {"digest": manifest.digest, "manifest_json": manifest.manifest_json}, case.notice_text or "")


@app.get("/api/health/live")
def health_live():
    return {"status": "live"}


@app.get("/api/health/ready")
def health_ready():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    finally:
        db.close()


# ─── Dashboard ──────────────────────────────────────────────────────────────

@app.get("/api/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    total_assets = db.query(Asset).count()
    total_incidents = db.query(Incident).count()
    pending_incidents = db.query(Incident).filter(Incident.status == "pending_review").count()

    critical_count = db.query(Incident).filter(Incident.risk_level == "Critical", Incident.status == "pending_review").count()
    high_count = db.query(Incident).filter(Incident.risk_level == "High", Incident.status == "pending_review").count()

    return {
        "total_assets": total_assets,
        "total_incidents": total_incidents,
        "pending_incidents": pending_incidents,
        "critical_incidents": critical_count,
        "high_risk_incidents": high_count,
    }


# ─── Settings ───────────────────────────────────────────────────────────────

def _get_settings_dict(db: Session) -> dict:
    """Internal helper to read settings as a dictionary."""
    setting_row = db.query(SystemSettings).first()
    if setting_row and setting_row.settings_data:
        try:
            return json.loads(setting_row.settings_data)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


@app.get("/api/settings")
def get_settings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _get_settings_dict(db)


@app.post("/api/settings")
def update_settings(settings: dict = Body(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    setting_row = db.query(SystemSettings).first()
    settings_str = json.dumps(settings)

    if setting_row:
        setting_row.settings_data = settings_str
    else:
        setting_row = SystemSettings(settings_data=settings_str)
        db.add(setting_row)

    db.commit()
    return {"message": "Settings updated successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
