"""Mock package for GL.iNet router API."""

from .server import REAL_WORLD_TIMINGS, MockRouter, MockRouterServer

__all__ = ["MockRouter", "MockRouterServer", "REAL_WORLD_TIMINGS"]
