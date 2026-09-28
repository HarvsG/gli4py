"""Helper utilities for gli4py."""


def normalize_url(url: str) -> str:
    """Normalize router URL to ensure scheme and /rpc endpoint."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    url = url.rstrip("/")
    if not url.endswith("/rpc"):
        url = f"{url}/rpc"
    return url
