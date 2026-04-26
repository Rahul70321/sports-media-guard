from fastapi import FastAPI, File, UploadFile, Form, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import shutil
import os
from typing import List
from datetime import datetime

from database.models import SessionLocal, Asset, Incident, DiscoveredMedia, SystemSettings
from services.fingerprint_service import generate_fingerprint
from services.watermark_service import embed_watermark
from services.crawler import crawl_images_from_url

from dotenv import load_dotenv
import google.generativeai as genai
from google.cloud import storage

load_dotenv()

app = FastAPI(title="Sports Media Protection API")

# Configure Google AI
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
# Configure GCS
try:
    gcs_client = storage.Client()
except:
    gcs_client = None
    print("Warning: GCS Client could not be initialized.")
    
GCS_BUCKET_NAME = os.getenv('GCS_BUCKET_NAME', 'sports-media-assets-mvp')

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
    
    # 1. Save locally temporarily for processing
    temp_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # 2. Embed Forensic Watermark
    watermark_id = f"ORG-{int(datetime.utcnow().timestamp())}"
    watermarked_path = embed_watermark(temp_path, watermark_id)
        
    fingerprint = generate_fingerprint(watermarked_path, media_type)
    
    # 3. Upload to Google Cloud Storage if configured
    cloud_url = watermarked_path # fallback
    if gcs_client:
        try:
            bucket = gcs_client.bucket(GCS_BUCKET_NAME)
            blob = bucket.blob(f"assets/{int(datetime.utcnow().timestamp())}_{file.filename}")
            blob.upload_from_filename(watermarked_path)
            cloud_url = f"gs://{GCS_BUCKET_NAME}/{blob.name}"
        except Exception as e:
            print(f"GCS Upload failed: {e}")
    
    # 4. Save to DB
    new_asset = Asset(
        title=title,
        description=description,
        file_path=cloud_url,
        media_type=media_type,
        fingerprint_hash=fingerprint,
        rights_policy=rights_policy
    )
    db.add(new_asset)
    db.commit()
    db.refresh(new_asset)
    
    return {"message": "Asset uploaded to cloud successfully", "asset_id": new_asset.id, "fingerprint": fingerprint, "cloud_url": cloud_url, "watermark_id": watermark_id}

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

@app.post("/api/incidents/{incident_id}/takedown")
def issue_takedown(incident_id: int, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        return {"error": "Incident not found"}
        
    incident.status = "takedown_requested"
    
    # Generate Google AI Legal Summary
    ai_summary = "Legal summary generation unavailable."
    if os.getenv("GEMINI_API_KEY"):
        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = f"Write a brief, formal DMCA takedown notice and legal case summary for an intellectual property violation. Asset ID: {incident.asset_id}. Discovered Media ID: {incident.discovered_media_id}. Confidence Match Score: {incident.match_score}%. State that this is an unauthorized distribution of copyrighted sports media."
            response = model.generate_content(prompt)
            ai_summary = response.text
        except Exception as e:
            print(f"Gemini API error: {e}")
            
    # Fire Webhook (Simulated)
    import requests
    settings = get_settings(db)
    if 'webhookUrl' in settings and settings['webhookUrl']:
        try:
            requests.post(settings['webhookUrl'], json={
                "event": "takedown_requested",
                "incident_id": incident.id,
                "asset_id": incident.asset_id,
                "legal_summary": ai_summary
            })
        except:
            pass

    db.commit()
    
    return {
        "message": "Takedown requested",
        "incident_id": incident.id,
        "ai_legal_summary": ai_summary
    }

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
