"""Registry of authorized monitoring adapters."""

from services.adapters.authorized_feed import AuthorizedFeedAdapter
from services.adapters.mock import MockAdapter
from services.adapters.youtube import YouTubeAdapter


ADAPTERS = {
    "youtube": YouTubeAdapter(),
    "mock": MockAdapter(),
    "authorized_feed": AuthorizedFeedAdapter(),
}

PLATFORM_CAPABILITIES = {
    "youtube": ADAPTERS["youtube"].capabilities.to_dict(),
    "mock": ADAPTERS["mock"].capabilities.to_dict(),
    "authorized_feed": ADAPTERS["authorized_feed"].capabilities.to_dict(),
    "meta": {"metadata": False, "thumbnail": False, "authorized_video": False, "audio": False, "rights_reporting": False, "status": "credentials_required"},
    "tiktok": {"metadata": False, "thumbnail": False, "authorized_video": False, "audio": False, "rights_reporting": False, "status": "approved_api_required"},
    "reddit": {"metadata": False, "thumbnail": False, "authorized_video": False, "audio": False, "rights_reporting": False, "status": "oauth_required"},
    "x": {"metadata": False, "thumbnail": False, "authorized_video": False, "audio": False, "rights_reporting": False, "status": "approved_api_required"},
    "twitch": {"metadata": False, "thumbnail": False, "authorized_video": False, "audio": False, "rights_reporting": False, "status": "approved_api_required"},
}


def get_adapter(adapter_type: str):
    adapter = ADAPTERS.get(adapter_type)
    if not adapter:
        raise ValueError(f"Adapter is not available: {adapter_type}")
    return adapter


def adapter_for_url(url: str) -> str:
    lowered = url.lower()
    if lowered.startswith("mock://"):
        return "mock"
    if "youtube.com" in lowered or "youtu.be" in lowered:
        return "youtube"
    return "authorized_feed"
