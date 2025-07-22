"""This module defines enums for various states and types used in the GL-inet API client."""

from enum import Enum


class TailscaleConnection(Enum):
    """Enum representing the connection states of Tailscale."""

    DISCONNECTED = 0
    LOGIN_REQUIRED = 1
    AUTHORIZATION_REQUIRED = 2
    CONNECTED = 3
    CONNECTING = 4
