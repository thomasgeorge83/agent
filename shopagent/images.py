"""Fetch product images safely.

Used by the GUI to show thumbnails / a larger image. Kept separate so the core
scraping logic has no GUI or imaging dependency.

Safety notes:
* Only fetches over HTTPS from the shop's own image CDNs (allowlist), so a
  scraped URL can't make us fetch arbitrary or internal addresses.
* Caps the download size to avoid memory blowups.
* Never writes the image to disk; bytes stay in memory.
"""

from __future__ import annotations

import urllib.request
from typing import Optional
from urllib.parse import urlparse

# Allowed image hosts (suffix match). Amazon serves images from these.
ALLOWED_IMAGE_HOST_SUFFIXES = (
    "media-amazon.com",
    "ssl-images-amazon.com",
    "images-amazon.com",
)
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB cap
FETCH_TIMEOUT_SECONDS = 10


def is_allowed_image_url(url: Optional[str]) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    return any(host == s or host.endswith("." + s) for s in ALLOWED_IMAGE_HOST_SUFFIXES)


def fetch_image_bytes(url: Optional[str]) -> Optional[bytes]:
    """Return image bytes for an allowed HTTPS image URL, or None."""
    if not is_allowed_image_url(url):
        return None
    req = urllib.request.Request(url, headers={"User-Agent": "shopagent/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SECONDS) as resp:
            data = resp.read(MAX_IMAGE_BYTES + 1)
        if len(data) > MAX_IMAGE_BYTES:
            return None
        return data
    except Exception:
        return None
