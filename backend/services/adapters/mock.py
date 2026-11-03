"""Deterministic adapter used for local demonstrations and tests."""

from services.adapters.base import AdapterCapabilities, DiscoveredItem, DiscoveryPage


class MockAdapter:
    adapter_type = "mock"
    capabilities = AdapterCapabilities(metadata=True, thumbnail=True, authorized_video=True, audio=False)

    def validate_target(self, url: str, configuration: dict) -> None:
        if not url.startswith(("mock://", "https://")):
            raise ValueError("Mock targets must use mock:// or https://")

    def discover(self, url: str, configuration: dict, checkpoint: dict | None = None) -> DiscoveryPage:
        if configuration.get("fail"):
            raise RuntimeError("Configured mock adapter failure")
        page = int((checkpoint or {}).get("page", 0))
        if page > 0:
            return DiscoveryPage(items=[], checkpoint=None)
        item = DiscoveredItem(
            platform="mock",
            platform_item_id=configuration.get("item_id", "mock-item-1"),
            source_url=url,
            title=configuration.get("title", "Mock sports candidate"),
            account=configuration.get("account", "mock-channel"),
            evidence_type=configuration.get("evidence_type", "metadata_only"),
            authorization_mode="mock",
            media_url=configuration.get("media_url", ""),
            media_type=configuration.get("media_type", ""),
            metadata={"fixture": True},
            capabilities=self.capabilities,
        )
        return DiscoveryPage(items=[item], checkpoint={"page": 1}, quota={"remaining": "unlimited"})

    def health(self) -> dict:
        return {"status": "ok", "capabilities": self.capabilities.to_dict()}
