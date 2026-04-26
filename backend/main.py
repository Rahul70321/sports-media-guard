from fastapi import FastAPI, File, UploadFile, Form, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import shutil
import os
from typing import List

from database.models import SessionLocal, Asset, Incident, DiscoveredMedia
from services.fingerprint_service import generate_fingerprint
from services.crawler import crawl_images_from_url

from dotenv import load_dotenv
import boto3

load_dotenv()

app = FastAPI(title="Sports Media Protection API")

s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION', 'us-east-1')
)
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME', 'sports-media-assets-mvp')

# Setup CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For MVP, allow all
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

@app.post("/api/assets/upload")
async def upload_asset(
    title: str = Form(...),
    description: str = Form(None),
    rights_policy: str = Form("standard"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    media_type = 'image' if file.content_type.startswith('image') else 'video'
    
    # 1. Save locally temporarily for fingerprinting
    temp_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    fingerprint = generate_fingerprint(temp_path, media_type)
    
    # 2. Upload to S3 if configured
    s3_url = temp_path # fallback
    if os.getenv('AWS_ACCESS_KEY_ID'):
        try:
            s3_key = f"assets/{int(datetime.utcnow().timestamp())}_{file.filename}"
            s3_client.upload_file(temp_path, S3_BUCKET_NAME, s3_key)
            s3_url = f"s3://{S3_BUCKET_NAME}/{s3_key}"
            # Optionally remove local temp file to save space
            # os.remove(temp_path)
        except Exception as e:
            print(f"S3 Upload failed: {e}")
    
    # 3. Save to DB
    new_asset = Asset(
        title=title,
        description=description,
        file_path=s3_url,
        media_type=media_type,
        fingerprint_hash=fingerprint,
        rights_policy=rights_policy
    )
    db.add(new_asset)
    db.commit()
    db.refresh(new_asset)
    
    return {"message": "Asset uploaded to cloud successfully", "asset_id": new_asset.id, "fingerprint": fingerprint, "s3_url": s3_url}

@app.get("/api/assets")
def get_assets(db: Session = Depends(get_db)):
    return db.query(Asset).all()

@app.post("/api/monitor/crawl")
def trigger_crawl(url: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(crawl_images_from_url, url)
    return {"message": f"Crawling started in background for {url}"}

@app.get("/api/incidents")
def get_incidents(db: Session = Depends(get_db)):
    incidents = db.query(Incident).order_by(Incident.created_at.desc()).all()
    results = []
    for inc in incidents:
        asset = db.query(Asset).filter(Asset.id == inc.asset_id).first()
        media = db.query(DiscoveredMedia).filter(DiscoveredMedia.id == inc.discovered_media_id).first()
        
        results.append({
            "id": inc.id,
            "asset_title": asset.title,
            "discovered_url": media.source_url,
            "platform": media.platform,
            "match_score": inc.match_score,
            "status": inc.status,
            "created_at": inc.created_at
        })
    return results

@app.post("/api/incidents/{incident_id}/action")
def update_incident_status(incident_id: int, status: str = Form(...), db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if incident:
        incident.status = status
        db.commit()
        return {"message": f"Incident updated to {status}"}
    return {"error": "Incident not found"}

@app.get("/api/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    total_assets = db.query(Asset).count()
    total_incidents = db.query(Incident).count()
    pending_incidents = db.query(Incident).filter(Incident.status == "pending_review").count()
    
    return {
        "total_assets": total_assets,
        "total_incidents": total_incidents,
        "pending_incidents": pending_incidents
    }

from fastapi import Body
from database.models import SystemSettings
import json

@app.get("/api/settings")
def get_settings(db: Session = Depends(get_db)):
    setting_row = db.query(SystemSettings).first()
    if setting_row and setting_row.settings_data:
        try:
            return json.loads(setting_row.settings_data)
        except:
            return {}
    return {}

@app.post("/api/settings")
def update_settings(settings: dict = Body(...), db: Session = Depends(get_db)):
    setting_row = db.query(SystemSettings).first()
    settings_str = json.dumps(settings)
    
    if setting_row:
        setting_row.settings_data = settings_str
    else:
        setting_row = SystemSettings(settings_data=settings_str)
        db.add(setting_row)
        
    db.commit()
    return {"message": "Settings updated successfully"}
