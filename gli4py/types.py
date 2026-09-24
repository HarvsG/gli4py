"""Static type definitions for gli4py.

This module contains TypedDicts, TypeAliases, and Literals used across
the GL.iNet client API. It avoids importing runtime modules and does NOT use Any.
"""

from typing import Literal, NotRequired, TypeAlias, TypedDict

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


class EmptyResponseDict(TypedDict, total=False):
    """Empty or minimal JSON-RPC dictionary returned by mutation endpoints."""

    tunnel_id: NotRequired[int]


EmptyResponse: TypeAlias = EmptyResponseDict | list[object]


# ─── Authentication & Connectivity ────────────────────────────────────────────


class ChallengeParams(TypedDict):
    """Parameters for challenge request."""

    username: str


# "hash-method" contains a hyphen, define via functional syntax for exact key
ChallengeResponse = TypedDict(
    "ChallengeResponse",
    {
        "alg": int,
        "salt": str,
        "nonce": str,
        "hash-method": NotRequired[str],
    },
)


class LoginParams(TypedDict):
    """Parameters for login endpoint."""

    username: str
    hash: str


class LoginResponse(TypedDict):
    """Response payload for login endpoint."""

    sid: str


class PingParams(TypedDict):
    """Parameters for diag.ping call."""

    addr: str


class SystemPingResponse(TypedDict, total=False):
    """Response payload for diag.ping call."""

    ping_result: str


SystemPingResult: TypeAlias = SystemPingResponse | list[str]


class EdgeRouterStatusResponse(TypedDict):
    """Response payload for edgerouter.get_status endpoint."""

    detected: int
    dns: list[str]
    gateway: str
    ip: str
    netmask: str
    valid: bool


# ─── System & Hardware ────────────────────────────────────────────────────────


class SystemBoardInfo(TypedDict):
    """Board hardware and OS specifications."""

    architecture: str
    hostname: str
    kernel_version: str
    openwrt_version: str
    model: str


class SystemSoftwareFeature(TypedDict):
    """Software features supported and enabled by router firmware."""

    ipv6: bool
    adguard: bool
    passthrough: bool
    repeater_eap: bool
    vpn: bool
    ids_ips: bool
    bark: bool
    tor: bool
    secondwan: bool
    sms_forward: bool
    nas: bool


class SystemHardwareFeature(TypedDict):
    """Hardware components available on the router."""

    reset_button: str
    nand: bool
    bluetooth: bool
    wan: str
    usb_reset: str
    switch_button: str
    radio: str
    lan: str
    usb: str
    build_in_modem: str
    noled: bool
    hwnat: bool
    microsd: str
    modem_reset: int
    fan: bool
    mcu: bool
    nowds: bool


class SystemInfoResponse(TypedDict):
    """Response payload for system.get_info endpoint."""

    mac: str
    disable_guest_during_scan_wifi: bool
    hardware_version: str
    country_code: str
    sn_bak: str
    software_feature: SystemSoftwareFeature
    vendor: str
    hardware_feature: SystemHardwareFeature
    cpu_num: int
    board_info: SystemBoardInfo
    firmware_date: str
    model: str
    ddns: str
    sn: str
    firmware_type: str
    firmware_version: str


class SystemLoadResponse(TypedDict):
    """Response payload for system.get_load endpoint."""

    memory_free: int
    memory_buff_cache: int
    memory_total: int
    load_average: list[float]


class SystemStatusNetwork(TypedDict):
    """Per-interface network state within system.get_status."""

    online: bool
    up: bool
    interface: str


WifiBandType: TypeAlias = Literal["2G", "5G", "6G", "2.4G", "2g", "5g", "6g"] | str


class SystemStatusWifi(TypedDict):
    """Per-radio Wi-Fi state within system.get_status."""

    guest: bool
    ssid: str
    up: bool
    channel: int
    band: WifiBandType
    name: str
    passwd: str | None


class SystemStatusService(TypedDict):
    """Service state within system.get_status."""

    name: str
    status: int


class SystemStatusClient(TypedDict):
    """Aggregated client connection counts within system.get_status."""

    cable_total: int
    wireless_total: int


class SystemStatusCpu(TypedDict, total=False):
    """CPU metrics within system metrics."""

    temperature: float


class SystemStatusMetrics(TypedDict, total=False):
    """System memory, flash, and runtime metrics within system.get_status."""

    netnat_enabled: bool
    ddns_enabled: bool
    tzoffset: str
    guest_ip: str
    flash_app: int
    flash_total: int
    memory_total: int
    memory_free: int
    ipv6_enabled: bool
    memory_buff_cache: int
    uptime: float
    load_average: list[float]
    guest_netmask: str
    mode: int
    flash_free: int
    timestamp: int
    cpu: SystemStatusCpu


class RouterStatusResponse(TypedDict):
    """Response payload for system.get_status endpoint."""

    network: list[SystemStatusNetwork]
    wifi: list[SystemStatusWifi]
    service: list[SystemStatusService]
    client: list[SystemStatusClient]
    system: SystemStatusMetrics


class MaccloneResponse(TypedDict):
    """Response payload for macclone.get_mac endpoint."""

    mac: str
    secondwan_mac: str
    repeater_mac: str
    mode: int
    remote_mac: str
    factory_mac: str


class RebootParams(TypedDict):
    """Parameters for system.reboot call."""

    delay: int


# ─── Clients & Static DHCP ───────────────────────────────────────────────────


ClientInterfaceType: TypeAlias = (
    Literal["cable", "2.4G", "5G", "6G", "wifi2g", "wifi5g", "wifi6g"] | str
)


class ClientEntry(TypedDict, total=False):
    """Telemetry and identity details for a connected or offline client."""

    mac: str
    ip: str
    name: str
    online: bool
    iface: ClientInterfaceType
    type: int
    online_time: int
    blocked: bool
    total_tx: int
    total_rx: int
    total_tx_init: int
    total_rx_init: int
    limit_tx: int
    limit_rx: int
    tx: int
    rx: int
    last_update_rate: int
    last_rx: NotRequired[list[int]]
    last_tx: NotRequired[list[int]]

    alias: NotRequired[str]
    client_class: NotRequired[str]  # Maps to the JSON 'class' key

    # Additional keys not found in my testing but documented in the API reference
    remote: NotRequired[bool]
    vendor: NotRequired[str]
    alive: NotRequired[str | int]
    new_online: NotRequired[bool]
    qos_up: NotRequired[str]
    qos_down: NotRequired[str]
    node: NotRequired[str]


class ClientsResponse(TypedDict):
    """Response payload for clients.get_list endpoint."""

    clients: list[ClientEntry]


ConnectedClients: TypeAlias = dict[str, ClientEntry]


class StaticBindEntry(TypedDict):
    """Static DHCP reservation entry."""

    ip: str
    mac: str
    name: str


class StaticBindListResponse(TypedDict):
    """Response payload for lan.get_static_bind_list endpoint."""

    static_bind_list: list[StaticBindEntry]


# ─── Wi-Fi Management ────────────────────────────────────────────────────────


WifiEncryptionType: TypeAlias = Literal["none", "psk", "psk2", "sae", "sae-mixed"] | str


class WifiInterface(TypedDict):
    """Wi-Fi interface configuration and credentials."""

    enabled: bool
    encryption: WifiEncryptionType
    guest: bool
    hidden: bool
    key: str | None
    name: str
    ssid: str


class WifiDeviceEntry(TypedDict):
    """Wi-Fi radio device container with its logical interfaces."""

    band: WifiBandType
    device: str
    ifaces: list[WifiInterface]


class WifiConfigResponse(TypedDict):
    """Response payload for wifi.get_config endpoint."""

    dfs_support: bool
    res: list[WifiDeviceEntry]


WifiIfacesMap: TypeAlias = dict[str, WifiInterface]


class WifiConfigSetParams(TypedDict):
    """Parameters for wifi.set_config call."""

    enabled: bool
    iface_name: str


# ─── WireGuard & VPN ──────────────────────────────────────────────────────────


class WireguardPeerConfig(TypedDict):
    """WireGuard client peer configuration."""

    name: str
    peer_id: int
    address_v4: NotRequired[str]


class WireguardGroupConfig(TypedDict):
    """WireGuard group configuration container."""

    auth_type: int
    group_id: int
    group_name: str
    password: str
    peers: list[WireguardPeerConfig]
    username: str


class WireguardConfigListResponse(TypedDict):
    """Response payload for wg-client.get_all_config_list endpoint."""

    config_list: list[WireguardGroupConfig]


class WireguardClientListItem(TypedDict):
    """Flattened WireGuard client peer entry returned by wireguard_client_list()."""

    name: str
    group_id: int
    peer_id: int
    tunnel_id: NotRequired[int]


class WireguardStatusItem(TypedDict):
    """WireGuard client tunnel operational status."""

    domain: str
    enabled: bool
    group_id: int
    ipv4: str
    ipv6: str
    log: str
    name: str
    peer_id: int
    port: int
    proxy: bool
    rx_bytes: int
    status: int
    tunnel_id: NotRequired[int]
    tx_bytes: int


class VpnClientStatusResponse(TypedDict):
    """Response payload for vpn-client.get_status endpoint (firmware >= 4.8)."""

    status_list: list[WireguardStatusItem]


class WireguardStartParams(TypedDict):
    """Parameters for wg-client.start call."""

    group_id: int
    peer_id: int


class VpnClientSetTunnelParams(TypedDict):
    """Parameters for vpn-client.set_tunnel call."""

    enabled: bool
    tunnel_id: int


# ─── Tailscale ────────────────────────────────────────────────────────────────


class TailscaleConfigResponse(TypedDict):
    """Response payload for tailscale.get_config endpoint."""

    enabled: bool
    lan_enabled: bool
    lan_ip: str
    wan_enabled: bool


class TailscaleSetConfigParams(TypedDict, total=False):
    """Parameters for tailscale.set_config call."""

    enabled: bool
    lan_enabled: bool
    lan_ip: str
    wan_enabled: bool


class TailscaleStatusResponse(TypedDict):
    """Response payload for tailscale.get_status endpoint."""

    address_v4: str
    login_name: str
    status: int


class TailscaleExitNodesResponse(TypedDict):
    """Response payload for tailscale.get_exit_node_list endpoint."""

    exit_node_list: list[str]


# ─── Cellular / Modem ─────────────────────────────────────────────────────────


ModemStatusType: TypeAlias = Literal["registered", "searching", "unregistered"] | str

ModemSimStateType: TypeAlias = Literal["ready", "not_inserted"] | str


class ModemEntry(TypedDict):
    """Modem device description."""

    carrier: str
    imei: str
    modem_id: int
    model: str
    status: ModemStatusType


class ModemInfoResponse(TypedDict):
    """Response payload for modem.get_info endpoint."""

    modems: list[ModemEntry]


class ModemSimInfoEntry(TypedDict):
    """SIM card info within modem.get_sim_info endpoint."""

    iccid: str
    imsi: str
    sim_state: ModemSimStateType


class ModemSimSignalEntry(TypedDict):
    """Modem signal strength metrics within modem.get_sim_signal endpoint."""

    rsrp: int
    rsrq: int
    rssi: int
    sinr: int


# ─── Additional API Endpoints for Full Verification & Discovery ──────────────


class CableStatusIpv4(TypedDict):
    """IPv4 network configuration within cable.get_status."""

    dns: list[str]
    gateway: str
    ip: str
    mask: str


class CableStatusSecondWan(TypedDict):
    """Second WAN mode within cable.get_status."""

    mode: int


class CableStatusResponse(TypedDict):
    """Response payload for cable.get_status endpoint."""

    ipv4: CableStatusIpv4
    mode: int
    protocol: str
    secondwan: CableStatusSecondWan
    status: int


class DnsConfigResponse(TypedDict):
    """Response payload for dns.get_config endpoint."""

    force_dns: bool
    mode: str
    rebind_protection: bool
    server: list[str]


class RepeaterConfigResponse(TypedDict):
    """Response payload for repeater.get_config endpoint."""

    antijam: bool
    auto: bool
    dfs: bool
    dfs_support: bool


class RepeaterScanEncryption(TypedDict):
    """Encryption details for scanned Wi-Fi AP."""

    description: str
    enabled: bool
    uci: str


class RepeaterScanEntry(TypedDict):
    """Discovered Wi-Fi access point in repeater.scan."""

    band: WifiBandType
    bssid: str
    channel: int
    encryption: RepeaterScanEncryption
    signal: int
    ssid: str


class RepeaterScanResponse(TypedDict):
    """Response payload for repeater.scan endpoint."""

    res: list[RepeaterScanEntry]


class RepeaterStatusResponse(TypedDict):
    """Response payload for repeater.get_status endpoint."""

    eap: bool
    scanning: bool
    state: int
    state_name: str


class OvpnListEntry(TypedDict):
    """OpenVPN client peer entry in ovpn-client.get_config."""

    client_id: int
    name: str


class OvpnGroupConfig(TypedDict):
    """OpenVPN client group configuration."""

    group_id: int
    group_name: str
    ovpn_list: list[OvpnListEntry]


class OvpnConfigResponse(TypedDict):
    """Response payload for ovpn-client.get_config endpoint."""

    config_list: list[OvpnGroupConfig]


class OvpnStatusResponse(TypedDict):
    """Response payload for ovpn-client.get_status endpoint."""

    client_id: int
    domain: str
    group_id: int
    ipv4: str
    ipv6: str
    log: str
    mode: str
    name: str
    port: int
    rx_bytes: int
    status: int
    tx_bytes: int


class DhcpLeaseEntry(TypedDict):
    """Active DHCP lease entry."""

    expires: int
    hostname: str
    ip: str
    mac: str


class DhcpLeasesResponse(TypedDict):
    """Response payload for lan.get_dhcp_lease endpoint."""

    leases: list[DhcpLeaseEntry]


class LanInterfaceEntry(TypedDict):
    """LAN interface network parameters."""

    dns: list[str]
    enable: int
    end: str
    gateway: str
    interface: str
    ip: str
    leasetime: str
    lpr: list[object]
    netmask: str
    start: str


class LanConfigResponse(TypedDict):
    """Response payload for lan.get_config endpoint."""

    interfaces: list[LanInterfaceEntry]


class FirewallWanAccessResponse(TypedDict):
    """Response payload for firewall.get_wan_access endpoint."""

    enable_https: bool
    enable_ping: bool
    enable_ssh: bool
    enable_whitelist: bool
    whitelist: list[object]


class FirewallZonesResponse(TypedDict):
    """Response payload for firewall.get_zone_list endpoint."""

    externals: list[str]
    internals: list[str]


class DdnsConfigResponse(TypedDict):
    """Response payload for ddns.get_config endpoint."""

    device_id: str
    enable_http_access: bool
    enable_https_access: bool
    enable_ssh_access: bool


class DdnsIpEntry(TypedDict):
    """Interface IP assignment in ddns.get_status."""

    interface: str
    ip: list[str]


class DdnsStatusResponse(TypedDict):
    """Response payload for ddns.get_status endpoint."""

    ips: list[DdnsIpEntry]
    status: int


class TetheringStatusResponse(TypedDict):
    """Response payload for tethering.get_status endpoint."""

    err_code: int
    err_msg: str
    status: int


class SwitchButtonResponse(TypedDict):
    """Response payload for switch_button.get_config endpoint."""

    func: str
    funcs: list[str]


class LedConfigResponse(TypedDict):
    """Response payload for led.get_config endpoint."""

    led_enable: bool


class AdguardHomeConfigResponse(TypedDict):
    """Response payload for adguardhome.get_config endpoint."""

    enabled: bool
    port: int
    redirect_mode: str
    tls: bool


class ArpListEntry(TypedDict):
    """ARP cache table entry."""

    device: str
    ip: str
    mac: str


class ArpListResponse(TypedDict):
    """Response payload for lan.get_arp_list endpoint."""

    entries: list[ArpListEntry]


class VpnPolicyDomainPolicy(TypedDict):
    """Domain policy configuration."""

    default_policy: int
    domain_list: str


class VpnPolicyGlobalPolicy(TypedDict):
    """Global VPN routing policy configuration."""

    kill_switch: int
    service_policy: int
    vpn_server_policy: int
    wan_access: int


class VpnPolicyMacPolicy(TypedDict):
    """MAC address VPN routing policy."""

    default_policy: int
    mac_list: list[object]


class VpnPolicyProxyMode(TypedDict):
    """VPN proxy mode."""

    mode: int


class VpnPolicyVlanEntry(TypedDict):
    """VLAN mapping in VPN policy."""

    id: int
    vpn: int


class VpnPolicyVlanPolicy(TypedDict):
    """VLAN VPN policy."""

    vlans: list[VpnPolicyVlanEntry]


class VpnPolicyResponse(TypedDict):
    """Response payload for vpn_policy.get_policy endpoint."""

    domain_policy: VpnPolicyDomainPolicy
    global_policy: VpnPolicyGlobalPolicy
    mac_policy: VpnPolicyMacPolicy
    proxy_mode: VpnPolicyProxyMode
    vlan_policy: VpnPolicyVlanPolicy


__all__ = [
    "AdguardHomeConfigResponse",
    "ArpListEntry",
    "ArpListResponse",
    "CableStatusIpv4",
    "CableStatusResponse",
    "CableStatusSecondWan",
    "ChallengeParams",
    "ChallengeResponse",
    "ClientEntry",
    "ClientInterfaceType",
    "ClientsResponse",
    "ConnectedClients",
    "DdnsConfigResponse",
    "DdnsIpEntry",
    "DdnsStatusResponse",
    "DhcpLeaseEntry",
    "DhcpLeasesResponse",
    "DnsConfigResponse",
    "EdgeRouterStatusResponse",
    "EmptyResponse",
    "FirewallWanAccessResponse",
    "FirewallZonesResponse",
    "JsonRpcError",
    "JsonRpcRequestPayload",
    "JsonRpcResponse",
    "JsonRpcResult",
    "LanConfigResponse",
    "LanInterfaceEntry",
    "LedConfigResponse",
    "LoginParams",
    "LoginResponse",
    "MaccloneResponse",
    "ModemEntry",
    "ModemInfoResponse",
    "ModemSimInfoEntry",
    "ModemSimSignalEntry",
    "ModemSimStateType",
    "ModemStatusType",
    "OvpnConfigResponse",
    "OvpnGroupConfig",
    "OvpnListEntry",
    "OvpnStatusResponse",
    "PingParams",
    "RebootParams",
    "RepeaterConfigResponse",
    "RepeaterScanEncryption",
    "RepeaterScanEntry",
    "RepeaterScanResponse",
    "RepeaterStatusResponse",
    "RouterStatusResponse",
    "StaticBindEntry",
    "StaticBindListResponse",
    "SwitchButtonResponse",
    "SystemBoardInfo",
    "SystemHardwareFeature",
    "SystemInfoResponse",
    "SystemLoadResponse",
    "SystemPingResponse",
    "SystemPingResult",
    "SystemSoftwareFeature",
    "SystemStatusClient",
    "SystemStatusCpu",
    "SystemStatusMetrics",
    "SystemStatusNetwork",
    "SystemStatusService",
    "SystemStatusWifi",
    "TailscaleConfigResponse",
    "TailscaleExitNodesResponse",
    "TailscaleSetConfigParams",
    "TailscaleStatusResponse",
    "TetheringStatusResponse",
    "VpnClientSetTunnelParams",
    "VpnClientStatusResponse",
    "VpnPolicyDomainPolicy",
    "VpnPolicyGlobalPolicy",
    "VpnPolicyMacPolicy",
    "VpnPolicyProxyMode",
    "VpnPolicyResponse",
    "VpnPolicyVlanEntry",
    "VpnPolicyVlanPolicy",
    "WifiBandType",
    "WifiConfigResponse",
    "WifiConfigSetParams",
    "WifiDeviceEntry",
    "WifiEncryptionType",
    "WifiIfacesMap",
    "WifiInterface",
    "WireguardClientListItem",
    "WireguardConfigListResponse",
    "WireguardGroupConfig",
    "WireguardPeerConfig",
    "WireguardStartParams",
    "WireguardStatusItem",
]
