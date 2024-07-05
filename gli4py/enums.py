from enum import Enum

class TailscaleConnection(Enum):
    LoginRequired = 1
    AuthorizationRequired = 2
    Connected = 3
    Connecting = 4