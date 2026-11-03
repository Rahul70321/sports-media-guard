"""YouTube Data API integration for discovering public video thumbnails."""

import os
import re
import uuid
from urllib.parse import parse_qs, urlparse

import requests

from database.models import DiscoveredMedia, SessionLocal
from services.fingerprint_service import generate_fingerprint
from services.matching_engine import find_matches_for_media

YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3"
YOUTUBE_THUMBNAIL_URL = "https://i.ytimg.com/vi/{}/hqdefault.jpg"


def _video_id(value: str) -> str | None:
    parsed = urlparse(value)
    if parsed.netloc in {"youtu.be", "www.youtu.be"}:
        return parsed.path.strip("/").split("/")[0] or None
    if parsed.netloc.endswith("youtube.com"):
        query_id = parse_qs(parsed.query).get("v", [None])[0]
        if query_id:
            return query_id
        match = re.match(r"/(?:shorts|embed|live)/([^/?]+)", parsed.path)
        return match.group(1) if match else None
    return None


def _search_query(value: str) -> str:
    parsed = urlparse(value)
    query = parse_qs(parsed.query).get("q", [""])[0]
    return query or parsed.path.strip("/") or "sports"


def _youtube_videos(url: str, api_key: str) -> list[dict]:
    video_id = _video_id(url)
    if video_id:
        endpoint = f"{YOUTUBE_API_URL}/videos"
        params = {"part": "snippet", "id": video_id, "key": api_key}
    else:
        endpoint = f"{YOUTUBE_API_URL}/search"
        params = {
            "part": "snippet", "type": "video", "maxResults": 10,
            "q": _search_query(url), "key": api_key,
        }

    response = requests.get(endpoint, params=params, timeout=20)
    response.raise_for_status()
    items = response.json().get("items", [])
    videos = []
    for item in items:
        snippet = item.get("snippet", {})
        item_id = item.get("id")
        item_id = item_id.get("videoId") if isinstance(item_id, dict) else item_id
        if item_id:
            videos.append({
                "id": item_id,
                "title": snippet.get("title", "YouTube video"),
                "channel": snippet.get("channelTitle", ""),
            })
    return videos


def crawl_youtube(url: str) -> dict:
    """Discover YouTube videos and fingerprint their public thumbnails."""
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        return {"status": "error", "message": "YOUTUBE_API_KEY is not configured"}

    db = SessionLocal()
    download_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "downloads"))
    os.makedirs(download_dir, exist_ok=True)
    discovered_count = 0
    duplicate_count = 0

    try:
        videos = _youtube_videos(url, api_key)
        for video in videos:
            source_url = f"https://www.youtube.com/watch?v={video['id']}"
            if db.query(DiscoveredMedia).filter(DiscoveredMedia.source_url == source_url).first():
                duplicate_count += 1
                continue

            path = os.path.join(download_dir, f"youtube-{uuid.uuid4().hex}.jpg")
            image_response = requests.get(
                YOUTUBE_THUMBNAIL_URL.format(video["id"]), timeout=20
            )
            image_response.raise_for_status()
            with open(path, "wb") as media_file:
                media_file.write(image_response.content)

            try:
                fingerprint = generate_fingerprint(path, "image")
                if not fingerprint.primary_hash:
                    continue
                discovered = DiscoveredMedia(
                    source_url=source_url,
                    platform="youtube",
                    file_path=path,
                    fingerprint_hash=fingerprint.primary_hash,
                    fingerprint_phash=fingerprint.phash,
                    fingerprint_dhash=fingerprint.dhash,
                    fingerprint_histogram=fingerprint.histogram,
                )
                db.add(discovered)
                db.commit()
                db.refresh(discovered)
                find_matches_for_media(discovered, db)
                discovered_count += 1
            except Exception:
                db.rollback()
                if os.path.exists(path):
                    os.remove(path)
                raise

        return {
            "status": "success",
            "videos_found": len(videos),
            "media_discovered": discovered_count,
            "duplicates_skipped": duplicate_count,
        }
    except requests.HTTPError as exc:
        db.rollback()
        return {"status": "error", "message": f"YouTube API request failed: {exc}"}
    except Exception as exc:
        db.rollback()
        return {"status": "error", "message": str(exc)}
    finally:
        db.close()
