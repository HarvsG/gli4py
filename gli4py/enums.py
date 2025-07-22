"""This module defines enums for various states and types used in the GL-inet API client."""
from enum import Enum

class TailscaleConnection(Enum):
    """Enum representing the connection states of Tailscale."""
    
    Disconnected = 0
    LoginRequired = 1
    AuthorizationRequired = 2
    Connected = 3
    Connecting = 4