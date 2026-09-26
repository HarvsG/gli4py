"""Type definitions and runtime models for gli4py.

This module exports strictly typed dataclass response models (powered by mashumaro)
alongside JSON-RPC protocol TypedDicts and method parameter specifications.
"""
# ruff: noqa: F401

from __future__ import annotations

from typing import Literal, NotRequired, TypeAlias, TypedDict

# Re-export all runtime dataclass models, enums, and type aliases from models
from . import models
from .models import (
    AdguardHomeConfigResponse,
    ArpListEntry,
    ArpListResponse,
    BaseModel,
    CableStatusIpv4,
    CableStatusResponse,
    CableStatusSecondWan,
    ChallengeResponse,
    ClientEntry,
    ClientInterface,
    ClientInterfaceType,
    ClientsResponse,
    ConnectedClients,
    DdnsConfigResponse,
    DdnsIpEntry,
    DdnsStatusResponse,
    DhcpLeaseEntry,
    DhcpLeasesResponse,
    DnsConfigResponse,
    EdgeRouterStatusResponse,
    EmptyResponse,
    EmptyResponseDict,
    FirewallWanAccessResponse,
    FirewallZonesResponse,
    LanConfigResponse,
    LanInterfaceEntry,
    LedConfigResponse,
    LoginResponse,
    MaccloneResponse,
    ModemEntry,
    ModemInfoResponse,
    ModemSimInfoEntry,
    ModemSimSignalEntry,
    ModemSimState,
    ModemSimStateType,
    ModemStatus,
    ModemStatusType,
    OvpnConfigResponse,
    OvpnGroupConfig,
    OvpnListEntry,
    OvpnStatusResponse,
    RepeaterConfigResponse,
    RepeaterScanEncryption,
    RepeaterScanEntry,
    RepeaterScanResponse,
    RepeaterStatusResponse,
    RouterStatusResponse,
    StaticBindEntry,
    StaticBindListResponse,
    SwitchButtonResponse,
    SystemBoardInfo,
    SystemHardwareFeature,
    SystemInfoResponse,
    SystemLoadResponse,
    SystemPingResponse,
    SystemPingResult,
    SystemSoftwareFeature,
    SystemStatusClient,
    SystemStatusCpu,
    SystemStatusMetrics,
    SystemStatusNetwork,
    SystemStatusService,
    SystemStatusWifi,
    TailscaleConfigResponse,
    TailscaleConnection,
    TailscaleExitNodesResponse,
    TailscaleStatusResponse,
    TetheringStatusResponse,
    VpnClientStatusResponse,
    VpnPolicyDomainPolicy,
    VpnPolicyGlobalPolicy,
    VpnPolicyMacPolicy,
    VpnPolicyProxyMode,
    VpnPolicyResponse,
    VpnPolicyVlanEntry,
    VpnPolicyVlanPolicy,
    WifiBand,
    WifiBandType,
    WifiConfigResponse,
    WifiDeviceEntry,
    WifiEncryption,
    WifiEncryptionType,
    WifiIfacesMap,
    WifiInterface,
    WireguardClientListItem,
    WireguardConfigListResponse,
    WireguardGroupConfig,
    WireguardPeerConfig,
    WireguardStatusItem,
)

# ─── JSON-RPC 2.0 Core ────────────────────────────────────────────────────────

JsonRpcResult: TypeAlias = (
    dict[str, object] | list[object] | int | float | str | bool | None
)


class JsonRpcRequestPayload(TypedDict):
    """JSON-RPC 2.0 request payload structure."""

    method: str
    jsonrpc: Literal["2.0"]
    params: list[object] | dict[str, object]
    id: int


class JsonRpcError(TypedDict):
    """JSON-RPC 2.0 error object."""

    code: int
    message: str
    data: NotRequired[object]


class JsonRpcResponse(TypedDict):
    """JSON-RPC 2.0 response wrapper."""

    jsonrpc: Literal["2.0"]
    id: int
    result: NotRequired[object]
    error: NotRequired[JsonRpcError]


# ─── Method Parameter TypedDicts ──────────────────────────────────────────────


class ChallengeParams(TypedDict):
    """Parameters for challenge request."""

    username: str


class LoginParams(TypedDict):
    """Parameters for login endpoint."""

    username: str
    hash: str


class PingParams(TypedDict):
    """Parameters for diag.ping call."""

    addr: str


class RebootParams(TypedDict):
    """Parameters for system.reboot call."""

    delay: int


class WifiConfigSetParams(TypedDict):
    """Parameters for wifi.set_config call."""

    enabled: bool
    iface_name: str


class WireguardStartParams(TypedDict):
    """Parameters for wg-client.start call."""

    group_id: int
    peer_id: int


class VpnClientSetTunnelParams(TypedDict):
    """Parameters for vpn-client.set_tunnel call."""

    enabled: bool
    tunnel_id: int


class TailscaleSetConfigParams(TypedDict, total=False):
    """Parameters for tailscale.set_config call."""

    enabled: bool
    lan_enabled: bool
    lan_ip: str
    wan_enabled: bool


__all__ = [
    *models.__all__,
    "ChallengeParams",
    "JsonRpcError",
    "JsonRpcRequestPayload",
    "JsonRpcResponse",
    "JsonRpcResult",
    "LoginParams",
    "PingParams",
    "RebootParams",
    "TailscaleSetConfigParams",
    "VpnClientSetTunnelParams",
    "WifiConfigSetParams",
    "WireguardStartParams",
]
