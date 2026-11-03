"""Outbound URL policy for crawlers, adapters, and webhooks."""

import ipaddress
import os
import socket
from urllib.parse import urlparse


class UnsafeURLError(ValueError):
    """Raised when a server-side request target is not allowed."""


_BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def validate_outbound_url(url: str, allow_hosts: set[str] | None = None) -> str:
    """Validate a public HTTP(S) URL before making a server-side request."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeURLError("Only HTTP and HTTPS URLs are allowed")
    if parsed.username or parsed.password:
        raise UnsafeURLError("URLs containing credentials are not allowed")
    if not parsed.hostname:
        raise UnsafeURLError("URL host is required")
    if parsed.port and parsed.port not in {80, 443}:
        raise UnsafeURLError("Only ports 80 and 443 are allowed")

    host = parsed.hostname.lower().rstrip(".")
    if allow_hosts and host not in allow_hosts and not any(host.endswith(f".{item}") for item in allow_hosts):
        raise UnsafeURLError(f"Host is not on the configured allowlist: {host}")

    try:
        addresses = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise UnsafeURLError("URL host could not be resolved") from exc

    for item in addresses:
        address = ipaddress.ip_address(item[4][0])
        if address.is_private or address.is_loopback or address.is_link_local or address.is_multicast:
            raise UnsafeURLError("Private or local network targets are not allowed")
        if any(address in network for network in _BLOCKED_NETWORKS):
            raise UnsafeURLError("Blocked network target")
    return url


def configured_allow_hosts(name: str) -> set[str]:
    return {item.strip().lower() for item in os.getenv(name, "").split(",") if item.strip()}
