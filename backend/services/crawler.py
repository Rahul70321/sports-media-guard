"""
Web Crawler
Discovers media from public URLs, generates multi-algorithm fingerprints,
attempts watermark extraction, and triggers the matching pipeline.
"""

import requests
from bs4 import BeautifulSoup
import os
import time
import uuid
from urllib.parse import urljoin, urlparse

MAX_DOWNLOAD_BYTES = int(os.getenv("CRAWLER_MAX_DOWNLOAD_BYTES", str(500 * 1024 * 1024)))
IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp", "image/tiff"}
VIDEO_CONTENT_TYPES = {"video/mp4", "video/quicktime", "video/x-msvideo", "video/webm", "video/x-matroska"}
from database.models import SessionLocal, DiscoveredMedia
from services.fingerprint_service import generate_fingerprint
from services.matching_engine import find_matches_for_media

VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm'}


def download_media(url: str, save_dir: str):
    """Download one media file with type and size checks.

    Returns ``(path, media_type)`` or ``(None, None)`` when the response is
    not a supported media resource.
    """
    filepath = None
    try:
        response = requests.get(url, stream=True, timeout=30, headers={
            'User-Agent': 'SportsMediaGuard/1.0'
        })
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
        media_type = _media_type(url, content_type)
        if content_type and not (content_type in IMAGE_CONTENT_TYPES or content_type in VIDEO_CONTENT_TYPES):
            raise ValueError(f"unsupported content type: {content_type}")

        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_DOWNLOAD_BYTES:
            raise ValueError("media exceeds crawler size limit")

        extension = os.path.splitext(urlparse(url).path)[1].lower()
        if media_type == "video" and extension not in VIDEO_EXTENSIONS:
            extension = ".mp4"
        elif media_type == "image" and not extension:
            extension = ".jpg"
        filename = f"{uuid.uuid4().hex}{extension}"
        filepath = os.path.join(save_dir, filename)
        total_size = 0
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    total_size += len(chunk)
                    if total_size > MAX_DOWNLOAD_BYTES:
                        raise ValueError("media exceeds crawler size limit")
                    f.write(chunk)
        return filepath, media_type
    except Exception as e:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
        print(f"Failed to download {url}: {e}")
        return None, None


def _media_urls(page_url: str, soup: BeautifulSoup):
    """Yield unique image and directly-addressable video URLs from a page."""
    seen = set()
    for tag in soup.find_all(['img', 'video', 'source']):
        media_url = tag.get('src')
        if not media_url:
            continue
        media_url = urljoin(page_url, media_url)
        if media_url.startswith(('http://', 'https://')) and media_url not in seen:
            seen.add(media_url)
            yield media_url


def _media_type(url: str, response_content_type: str = '') -> str:
    extension = os.path.splitext(urlparse(url).path)[1].lower()
    if extension in VIDEO_EXTENSIONS or response_content_type.startswith('video/'):
        return 'video'
    return 'image'


def crawl_images_from_url(url: str):
    print(f"Starting crawl on: {url}")
    db = SessionLocal()

    # Save discovered files to downloads directory
    temp_dir = os.path.join(os.path.dirname(__file__), '..', 'downloads')
    os.makedirs(temp_dir, exist_ok=True)

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        media_urls = list(_media_urls(url, soup))
        print(f"Found {len(media_urls)} image/video media URLs on {url}")

        discovered_count = 0
        skipped_duplicates = 0

        for media_url in media_urls:
            existing = db.query(DiscoveredMedia).filter(
                DiscoveredMedia.source_url == media_url
            ).first()
            if existing:
                skipped_duplicates += 1
                continue

            filepath, media_type = download_media(media_url, temp_dir)
            if not filepath:
                continue

            try:
                fp_result = generate_fingerprint(filepath, media_type)
                if not fp_result.primary_hash:
                    os.remove(filepath)
                    continue

                discovered = DiscoveredMedia(
                    source_url=media_url,
                    platform=urlparse(url).netloc,
                    file_path=filepath,
                    fingerprint_hash=fp_result.primary_hash,
                    fingerprint_phash=fp_result.phash,
                    fingerprint_dhash=fp_result.dhash,
                    fingerprint_histogram=fp_result.histogram,
                    video_frame_hashes=fp_result.video_frame_hashes if media_type == 'video' else None,
                )
                db.add(discovered)
                db.commit()
                db.refresh(discovered)

                find_matches_for_media(discovered, db)
                discovered_count += 1
            except Exception as media_error:
                db.rollback()
                if os.path.exists(filepath):
                    os.remove(filepath)
                print(f"Failed to process discovered media {media_url}: {media_error}")

        print(f"Crawl complete: {discovered_count} new media, {skipped_duplicates} duplicates skipped.")
        return {"status": "success", "media_discovered": discovered_count, "duplicates_skipped": skipped_duplicates}

    except Exception as e:
        print(f"Crawler error: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
        print("Crawl completed.")
