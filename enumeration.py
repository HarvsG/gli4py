#!/usr/bin/env python3
"""GL.iNet Router API Enumeration Script.

Probes a GL.iNet router to discover which API modules and methods are
supported by the device's firmware. Produces a JSON report that can be
contributed to build a model→feature-set registry.
"""

import sys
from pathlib import Path

# Ensure package can be loaded when running directly from a repository checkout
repo_dir = Path(__file__).resolve().parent
if str(repo_dir) not in sys.path:
    sys.path.insert(0, str(repo_dir))

from gli4py.enumeration import (  # noqa: E402 # pylint: disable=wrong-import-position
    API_REGISTRY,
    enumerate_router,
    filter_registry,
    main,
    normalize_url,
)

__all__ = [
    "API_REGISTRY",
    "enumerate_router",
    "filter_registry",
    "main",
    "normalize_url",
]

if __name__ == "__main__":
    main()
