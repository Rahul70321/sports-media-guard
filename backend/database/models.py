from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import os

# Fetch from environment (e.g. postgresql://user:pass@host:port/dbname)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sports_media.db")

# If using PostgreSQL or MySQL, check_same_thread isn't needed
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String)
    file_path = Column(String)
    media_type = Column(String) # 'image' or 'video'
    fingerprint_hash = Column(String, index=True) # Perceptual hash for visual
    rights_policy = Column(String) # e.g., 'no_distribution', 'region_locked'
    created_at = Column(DateTime, default=datetime.utcnow)

class DiscoveredMedia(Base):
    __tablename__ = "discovered_media"

    id = Column(Integer, primary_key=True, index=True)
    source_url = Column(String, index=True)
    platform = Column(String)
    file_path = Column(String) # local downloaded path for analysis
    fingerprint_hash = Column(String)
    discovered_at = Column(DateTime, default=datetime.utcnow)

class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"))
    discovered_media_id = Column(Integer, ForeignKey("discovered_media.id"))
    match_score = Column(Float) # Confidence score 0 to 100
    status = Column(String, default="pending_review") # 'pending_review', 'takedown_requested', 'false_positive'
    created_at = Column(DateTime, default=datetime.utcnow)

class SystemSettings(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    settings_data = Column(String) # Stored as JSON string
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

Base.metadata.create_all(bind=engine)
