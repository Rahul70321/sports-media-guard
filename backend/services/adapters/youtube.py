"""YouTube Data API adapter. Public results are thumbnail candidates only."""

import os
import re
from urllib.parse import parse_qs, urlparse

import requests

from services.adapters.base import AdapterCapabilities, DiscoveredItem, DiscoveryPage
from services.url_policy import validate_outbound_url


class YouTubeAdapter:
    adapter_type = "youtube"
    capabilities = AdapterCapabilities(metadata=True, thumbnail=True, authorized_video=False, rights_reporting=False)
    api_url = "https://www.googleapis.com/youtube/v3"

    def validate_target(self, url: str, configuration: dict) -> None:
        if not os.getenv("YOUTUBE_API_KEY"):
            raise ValueError("YOUTUBE_API_KEY is not configured")
        validate_outbound_url(url, {"youtube.com", "youtu.be", "www.youtube.com", "m.youtube.com"})

    def discover(self, url: str, configuration: dict, checkpoint: dict | None = None) -> DiscoveryPage:
        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            raise ValueError("YOUTUBE_API_KEY is not configured")
        video_id = _video_id(url)
        if video_id:
            response = requests.get(
                f"{self.api_url}/videos",
                params={"part": "snippet", "id": video_id, "key": api_key},
                timeout=20,
            )
        else:
            response = requests.get(
                f"{self.api_url}/search",
                params={
                    "part": "snippet", "type": "video", "maxResults": 10,
                    "q": _search_query(url), "pageToken": (checkpoint or {}).get("pageToken", ""),
                    "key": api_key,
                },
                timeout=20,
            )
        response.raise_for_status()
        payload = response.json()
        items = []
        for item in payload.get("items", []):
            item_id = item.get("id")
            item_id = item_id.get("videoId") if isinstance(item_id, dict) else item_id
            snippet = item.get("snippet", {})
            if not item_id:
                continue
            items.append(DiscoveredItem(
                platform="youtube",
                platform_item_id=item_id,
                source_url=f"https://www.youtube.com/watch?v={item_id}",
                title=snippet.get("title", "YouTube video"),
                account=snippet.get("channelTitle", ""),
                published_at=snippet.get("publishedAt", ""),
                evidence_type="thumbnail",
                authorization_mode="public_api",
                media_url=f"https://i.ytimg.com/vi/{item_id}/hqdefault.jpg",
                media_type="image",
                metadata={"channel_id": snippet.get("channelId", ""), "capability": "thumbnail_only"},
                capabilities=self.capabilities,
            ))
        next_token = payload.get("nextPageToken")
        return DiscoveryPage(items=items, checkpoint={"pageToken": next_token} if next_token else None, quota={})

    def health(self) -> dict:
        return {
            "status": "configured" if os.getenv("YOUTUBE_API_KEY") else "not_configured",
            "capabilities": self.capabilities.to_dict(),
            "limitation": "YouTube Data API provides metadata and public thumbnails, not authorized full-video frames.",
        }


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
    return parse_qs(parsed.query).get("q", [""])[0] or parsed.path.strip("/") or "sports"
