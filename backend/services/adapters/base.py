"""Normalized monitoring adapter contract."""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class AdapterCapabilities:
    metadata: bool = False
    thumbnail: bool = False
    authorized_video: bool = False
    audio: bool = False
    rights_reporting: bool = False

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class DiscoveredItem:
    platform: str
    platform_item_id: str
    source_url: str
    title: str
    account: str = ""
    published_at: str = ""
    evidence_type: str = "metadata_only"
    authorization_mode: str = "public_api"
    media_url: str = ""
    media_type: str = ""
    metadata: dict = field(default_factory=dict)
    capabilities: AdapterCapabilities = field(default_factory=AdapterCapabilities)


@dataclass
class DiscoveryPage:
    items: list[DiscoveredItem]
    checkpoint: dict | None = None
    quota: dict = field(default_factory=dict)


class MonitoringAdapter(Protocol):
    adapter_type: str
    capabilities: AdapterCapabilities

    def validate_target(self, url: str, configuration: dict) -> None:
        ...

    def discover(self, url: str, configuration: dict, checkpoint: dict | None = None) -> DiscoveryPage:
        ...

    def health(self) -> dict:
        ...
