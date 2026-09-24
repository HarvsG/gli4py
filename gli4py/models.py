"""Runtime models and enumerations for the gli4py library."""

from enum import IntEnum, StrEnum

from .types import (
    ClientEntry,
    ClientInterfaceType,
    ConnectedClients,
    ModemSimStateType,
    ModemStatusType,
    SystemStatusMetrics,
    WifiBandType,
    WifiEncryptionType,
)


class TailscaleConnection(IntEnum):
    """Enum representing the connection states of Tailscale."""

    DISCONNECTED = 0
    LOGIN_REQUIRED = 1
    AUTHORIZATION_REQUIRED = 2
    CONNECTED = 3
    CONNECTING = 4


class WifiBand(StrEnum):
    """Enumeration of Wi-Fi frequency bands."""

    BAND_2G = "2G"
    BAND_5G = "5G"
    BAND_6G = "6G"
    BAND_2_4G = "2.4G"


class WifiEncryption(StrEnum):
    """Enumeration of common Wi-Fi encryption types."""

    NONE = "none"
    PSK = "psk"
    PSK2 = "psk2"
    SAE = "sae"
    SAE_MIXED = "sae-mixed"


class ClientInterface(StrEnum):
    """Enumeration of network interface types for clients."""

    CABLE = "cable"
    WIFI_2G = "wifi2g"
    WIFI_5G = "wifi5g"
    BAND_2_4G = "2.4G"
    BAND_5G = "5G"
    BAND_6G = "6G"


class ModemStatus(StrEnum):
    """Enumeration of modem registration statuses."""

    REGISTERED = "registered"
    SEARCHING = "searching"
    UNREGISTERED = "unregistered"


class ModemSimState(StrEnum):
    """Enumeration of SIM card states."""

    READY = "ready"
    NOT_INSERTED = "not_inserted"


__all__ = [
    "ClientEntry",
    "ClientInterface",
    "ClientInterfaceType",
    "ConnectedClients",
    "ModemSimState",
    "ModemSimStateType",
    "ModemStatus",
    "ModemStatusType",
    "SystemStatusMetrics",
    "TailscaleConnection",
    "WifiBand",
    "WifiBandType",
    "WifiEncryption",
    "WifiEncryptionType",
]
