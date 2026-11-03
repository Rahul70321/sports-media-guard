"""Allowlisted feed adapter for explicitly authorized sources."""

import json
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from services.adapters.base import AdapterCapabilities, DiscoveredItem, DiscoveryPage
from services.url_policy import configured_allow_hosts, validate_outbound_url


class AuthorizedFeedAdapter:
    adapter_type = "authorized_feed"
    capabilities = AdapterCapabilities(metadata=True, thumbnail=True, authorized_video=True, audio=False)

    def validate_target(self, url: str, configuration: dict) -> None:
        hosts = configured_allow_hosts("AUTHORIZED_FEED_ALLOWLIST")
        if not hosts:
            raise ValueError("AUTHORIZED_FEED_ALLOWLIST is required")
        validate_outbound_url(url, hosts)

    def discover(self, url: str, configuration: dict, checkpoint: dict | None = None) -> DiscoveryPage:
        self.validate_target(url, configuration)
        response = requests.get(url, timeout=20, headers={"User-Agent": "SportsMediaGuard/1.0"})
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        if "json" in content_type:
            payload = response.json()
            records = payload if isinstance(payload, list) else payload.get("items", [])
            items = [self._json_item(record, url) for record in records if isinstance(record, dict)]
        else:
            soup = BeautifulSoup(response.content, "xml")
            items = [self._feed_item(entry, url) for entry in soup.find_all(["item", "entry"])]
        return DiscoveryPage(items=[item for item in items if item], checkpoint=None)

    def _json_item(self, record: dict, source: str) -> DiscoveredItem | None:
        media_url = record.get("media_url") or record.get("url")
        if not media_url:
            return None
        validate_outbound_url(media_url, configured_allow_hosts("AUTHORIZED_FEED_ALLOWLIST"))
        item_id = str(record.get("id") or media_url)
        return DiscoveredItem(
            platform=urlparse(source).netloc,
            platform_item_id=item_id,
            source_url=record.get("source_url", source),
            title=record.get("title", "Authorized feed item"),
            evidence_type="authorized_video" if str(media_url).endswith((".mp4", ".webm", ".mov")) else "thumbnail",
            authorization_mode="authorized_feed",
            media_url=media_url,
            media_type="video" if str(media_url).endswith((".mp4", ".webm", ".mov")) else "image",
            metadata={"authorized": True},
            capabilities=self.capabilities,
        )

    def _feed_item(self, entry, source: str) -> DiscoveredItem | None:
        link = entry.find("link")
        media_url = link.get("href") if link and link.get("href") else (link.text.strip() if link else "")
        if not media_url:
            return None
        validate_outbound_url(media_url, configured_allow_hosts("AUTHORIZED_FEED_ALLOWLIST"))
        title = entry.find("title")
        return DiscoveredItem(
            platform=urlparse(source).netloc,
            platform_item_id=media_url,
            source_url=media_url,
            title=title.text.strip() if title and title.text else "Authorized feed item",
            evidence_type="authorized_video" if media_url.endswith((".mp4", ".webm", ".mov")) else "thumbnail",
            authorization_mode="authorized_feed",
            media_url=media_url,
            media_type="video" if media_url.endswith((".mp4", ".webm", ".mov")) else "image",
            metadata={"authorized": True},
            capabilities=self.capabilities,
        )

    def health(self) -> dict:
        hosts = sorted(configured_allow_hosts("AUTHORIZED_FEED_ALLOWLIST"))
        return {"status": "configured" if hosts else "not_configured", "allowlist": hosts, "capabilities": self.capabilities.to_dict()}
