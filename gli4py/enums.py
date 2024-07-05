from enum import Enum

class TailscaleConnection(Enum):
    Disconnected = 0
    LoginRequired = 1
    AuthorizationRequired = 2
    Connected = 3
    Connecting = 4