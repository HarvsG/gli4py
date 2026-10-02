"""Helper utilities for gli4py."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gli4py.types import MacAddress


def normalize_url(url: str) -> str:
    """Normalize router URL to ensure scheme and /rpc endpoint."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    url = url.rstrip("/")
    if not url.endswith("/rpc"):
        url = f"{url}/rpc"
    return url


def format_mac(mac: str, uppercase: bool = True) -> MacAddress:
    """Formats and normalizes MAC address strings to standard colon-separated octets.

    Accepts formats such as:
    - '28:CD:C1:06:77:67' / '28:cd:c1:06:77:67'
    - '28-CD-C1-06-77-67' / '28-cd-c1-06-77-67'
    - '28CDC1067767' / '28cdc1067767'
    - '28cd.c106.7767'

    Returns standard colon-delimited MAC string: '28:CD:C1:06:77:67' (or lowercase if uppercase=False).
    Raises ValueError if input is not a valid MAC address.
    """
    cleaned = re.sub(r"[^0-9a-fA-F]", "", mac.strip())
    if len(cleaned) != 12:
        raise ValueError(
            f"Invalid MAC address '{mac}': must contain 12 hexadecimal characters."
        )

    if uppercase:
        cleaned = cleaned.upper()
    else:
        cleaned = cleaned.lower()

    return ":".join(cleaned[i : i + 2] for i in range(0, 12, 2))
