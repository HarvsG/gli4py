"""Runtime models, dataclasses, and enumerations for the gli4py library.

This module provides strictly-typed dataclasses paired with mashumaro for fast,
reliable runtime deserialization and validation of API responses from GL.iNet routers.
"""
# pylint: disable=too-many-lines

from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field, fields
from enum import IntEnum, StrEnum
from typing import Any, Literal, TypeAlias

from mashumaro import field_options
from mashumaro.config import BaseConfig
from mashumaro.mixins.dict import DataClassDictMixin

_LOGGER = logging.getLogger(__name__)

# ─── Enumerations ─────────────────────────────────────────────────────────────


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


# ─── Type Aliases ─────────────────────────────────────────────────────────────

WifiBandType: TypeAlias = (
    Literal["2G", "5G", "6G", "2.4G", "2g", "5g", "6g"] | WifiBand | str
)
ClientInterfaceType: TypeAlias = (
    Literal["cable", "2.4G", "5G", "6G", "wifi2g", "wifi5g", "wifi6g"]
    | ClientInterface
    | str
)
WifiEncryptionType: TypeAlias = (
    Literal["none", "psk", "psk2", "sae", "sae-mixed"] | WifiEncryption | str
)
ModemStatusType: TypeAlias = (
    Literal["registered", "searching", "unregistered"] | ModemStatus | str
)
ModemSimStateType: TypeAlias = Literal["ready", "not_inserted"] | ModemSimState | str


# ─── Base Model ───────────────────────────────────────────────────────────────


@dataclass(eq=False)
class BaseModel(Mapping[str, Any], DataClassDictMixin):
    """Base dataclass model for API responses with dict-like and mashumaro support."""

    class Config(BaseConfig):
        """Mashumaro model configuration."""

        serialize_by_alias = True

    @classmethod
    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        orig_mashumaro = getattr(cls, "__mashumaro_from_dict__", None)
        if callable(orig_mashumaro):

            def _wrapped_from_dict(
                subcls: type[Any], /, d: Mapping[str, Any], **kw: Any
            ) -> Any:
                if isinstance(d, Mapping) and _LOGGER.isEnabledFor(logging.DEBUG):
                    expected_keys: set[str] = set()
                    for f in fields(subcls):
                        expected_keys.add(f.name)
                        alias = f.metadata.get("alias")
                        if alias:
                            expected_keys.add(alias)

                    payload_keys = set(d.keys())

                    extra = payload_keys - expected_keys
                    if extra:
                        _LOGGER.debug(
                            "[%s] Unexpected extra key(s) in API response: %s",
                            subcls.__name__,
                            sorted(extra),
                        )

                    missing = {
                        (f.metadata.get("alias") or f.name)
                        for f in fields(subcls)
                        if f.name not in payload_keys
                        and f.metadata.get("alias") not in payload_keys
                    }
                    if missing:
                        _LOGGER.debug(
                            "[%s] Key(s) missing from API response (using defaults): %s",
                            subcls.__name__,
                            sorted(missing),
                        )

                return orig_mashumaro(d, **kw)  # pylint: disable=not-callable

            wrapped_cm = classmethod(_wrapped_from_dict)
            setattr(cls, "__mashumaro_from_dict__", wrapped_cm)
            setattr(cls, "from_dict", wrapped_cm)

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            val = getattr(self, key)
            if not callable(val) and not key.startswith("_"):
                return val
        for f in fields(self):
            if f.metadata.get("alias") == key:
                return getattr(self, f.name)
        raise KeyError(key)

    def __setitem__(self, key: str, value: Any) -> None:
        if hasattr(self, key) and not key.startswith("_"):
            setattr(self, key, value)
            return
        for f in fields(self):
            if f.metadata.get("alias") == key:
                setattr(self, f.name, value)
                return
        setattr(self, key, value)

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        if hasattr(self, key) and not key.startswith("_"):
            return True
        for f in fields(self):
            if f.metadata.get("alias") == key:
                return True
        return False

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for key if key is in the model, else default."""
        try:
            val = self[key]
            if val is None and default is not None:
                return default
            return val
        except KeyError:
            return default

    def __iter__(self) -> Iterator[str]:
        return (f.metadata.get("alias") or f.name for f in fields(self))

    def __len__(self) -> int:
        return len(fields(self))

    def __bool__(self) -> bool:
        return any(
            val is not None and val != "" and val != [] and val != {}
            for val in self.values()
        )

    def __eq__(self, other: object) -> bool:
        if isinstance(other, type(self)):
            return self.__dict__ == other.__dict__
        if isinstance(other, Mapping):
            return all(self.get(k) == v for k, v in other.items())
        return False


# ─── Authentication & Connectivity Models ─────────────────────────────────────


@dataclass(eq=False)
class EmptyResponseDict(BaseModel):
    """Empty or minimal JSON-RPC dictionary returned by mutation endpoints."""

    tunnel_id: int | None = None


EmptyResponse: TypeAlias = EmptyResponseDict | list[Any]


@dataclass(eq=False)
class ChallengeResponse(BaseModel):
    """Response payload for challenge endpoint."""

    alg: int = 0
    salt: str = ""
    nonce: str = ""
    hash_method: str | None = field(
        default=None, metadata=field_options(alias="hash-method")
    )


@dataclass(eq=False)
class LoginResponse(BaseModel):
    """Response payload for login endpoint."""

    sid: str = ""


@dataclass(eq=False)
class SystemPingResponse(BaseModel):
    """Response payload for diag.ping call."""

    ping_result: str | None = None


SystemPingResult: TypeAlias = SystemPingResponse | list[str]


@dataclass(eq=False)
class EdgeRouterStatusResponse(BaseModel):
    """Response payload for edgerouter.get_status endpoint."""

    detected: int = 0
    dns: list[str] = field(default_factory=list)
    gateway: str = ""
    ip: str = ""
    netmask: str = ""
    valid: bool = False


# ─── System & Hardware Models ─────────────────────────────────────────────────


@dataclass(eq=False)
class SystemBoardInfo(BaseModel):
    """Board hardware and OS specifications."""

    architecture: str = ""
    hostname: str = ""
    kernel_version: str = ""
    openwrt_version: str = ""
    model: str = ""


@dataclass(eq=False)
class SystemSoftwareFeature(BaseModel):
    """Software features supported and enabled by router firmware."""

    ipv6: bool = False
    adguard: bool = False
    passthrough: bool = False
    repeater_eap: bool = False
    vpn: bool = False
    ids_ips: bool = False
    bark: bool = False
    tor: bool = False
    secondwan: bool = False
    sms_forward: bool = False
    nas: bool = False


@dataclass(eq=False)
class SystemHardwareFeature(BaseModel):
    """Hardware components available on the router."""

    reset_button: str = ""
    nand: bool = False
    bluetooth: bool = False
    wan: str = ""
    usb_reset: str = ""
    switch_button: str = ""
    radio: str = ""
    lan: str = ""
    usb: str = ""
    build_in_modem: str = ""
    noled: bool = False
    hwnat: bool = False
    microsd: str = ""
    modem_reset: int = 0
    fan: bool = False
    mcu: bool = False
    nowds: bool = False


@dataclass(eq=False)
class SystemInfoResponse(BaseModel):
    """Response payload for system.get_info endpoint."""

    mac: str = ""
    disable_guest_during_scan_wifi: bool = False
    hardware_version: str = ""
    country_code: str = ""
    sn_bak: str = ""
    software_feature: SystemSoftwareFeature | None = None
    vendor: str = ""
    hardware_feature: SystemHardwareFeature | None = None
    cpu_num: int = 0
    board_info: SystemBoardInfo | None = None
    firmware_date: str = ""
    model: str = ""
    ddns: str = ""
    sn: str = ""
    firmware_type: str = ""
    firmware_version: str = ""


@dataclass(eq=False)
class SystemLoadResponse(BaseModel):
    """Response payload for system.get_load endpoint."""

    memory_free: int = 0
    memory_buff_cache: int = 0
    memory_total: int = 0
    load_average: list[float] = field(default_factory=list)


@dataclass(eq=False)
class SystemStatusNetwork(BaseModel):
    """Per-interface network state within system.get_status."""

    online: bool = False
    up: bool = False
    interface: str = ""


@dataclass(eq=False)
class SystemStatusWifi(BaseModel):
    """Per-radio Wi-Fi state within system.get_status."""

    guest: bool = False
    ssid: str = ""
    up: bool = False
    channel: int = 0
    band: WifiBandType = ""
    name: str = ""
    passwd: str | None = None


@dataclass(eq=False)
class SystemStatusService(BaseModel):
    """Service state within system.get_status."""

    name: str = ""
    status: int = 0


@dataclass(eq=False)
class SystemStatusClient(BaseModel):
    """Aggregated client connection counts within system.get_status."""

    cable_total: int = 0
    wireless_total: int = 0


@dataclass(eq=False)
class SystemStatusCpu(BaseModel):
    """CPU metrics within system metrics."""

    temperature: float | None = None


@dataclass(eq=False)
class SystemStatusMetrics(BaseModel):
    """System memory, flash, and runtime metrics within system.get_status."""

    netnat_enabled: bool | None = None
    ddns_enabled: bool | None = None
    tzoffset: str | None = None
    guest_ip: str | None = None
    flash_app: int | None = None
    flash_total: int | None = None
    memory_total: int | None = None
    memory_free: int | None = None
    ipv6_enabled: bool | None = None
    memory_buff_cache: int | None = None
    uptime: float | None = None
    load_average: list[float] = field(default_factory=list)
    guest_netmask: str | None = None
    mode: int | None = None
    flash_free: int | None = None
    timestamp: int | None = None
    cpu: SystemStatusCpu | None = None


@dataclass(eq=False)
class RouterStatusResponse(BaseModel):
    """Response payload for system.get_status endpoint."""

    network: list[SystemStatusNetwork] = field(default_factory=list)
    wifi: list[SystemStatusWifi] = field(default_factory=list)
    service: list[SystemStatusService] = field(default_factory=list)
    client: list[SystemStatusClient] = field(default_factory=list)
    system: SystemStatusMetrics = field(default_factory=SystemStatusMetrics)


@dataclass(eq=False)
class MaccloneResponse(BaseModel):
    """Response payload for macclone.get_mac endpoint."""

    mac: str = ""
    secondwan_mac: str = ""
    repeater_mac: str = ""
    mode: int = 0
    remote_mac: str = ""
    factory_mac: str = ""


# ─── Clients & Static DHCP Models ─────────────────────────────────────────────


@dataclass(eq=False)
class ClientEntry(BaseModel):
    """Telemetry and identity details for a connected or offline client."""

    mac: str = ""
    ip: str = ""
    name: str = ""
    online: bool = False
    iface: ClientInterfaceType = ""
    type: int = 0
    online_time: int = 0
    blocked: bool = False
    total_tx: int = 0
    total_rx: int = 0
    total_tx_init: int = 0
    total_rx_init: int = 0
    limit_tx: int = 0
    limit_rx: int = 0
    tx: int = 0
    rx: int = 0
    last_update_rate: int = 0
    last_rx: list[int] = field(default_factory=list)
    last_tx: list[int] = field(default_factory=list)
    alias: str | None = None
    client_class: str | None = field(
        default=None, metadata=field_options(alias="class")
    )
    remote: bool | None = None
    vendor: str | None = None
    alive: str | int | None = None
    new_online: bool | None = None
    qos_up: str | None = None
    qos_down: str | None = None
    node: str | None = None


@dataclass(eq=False)
class ClientsResponse(BaseModel):
    """Response payload for clients.get_list endpoint."""

    clients: list[ClientEntry] = field(default_factory=list)


ConnectedClients: TypeAlias = dict[str, ClientEntry]


@dataclass(eq=False)
class StaticBindEntry(BaseModel):
    """Static DHCP reservation entry."""

    ip: str = ""
    mac: str = ""
    name: str = ""


@dataclass(eq=False)
class StaticBindListResponse(BaseModel):
    """Response payload for lan.get_static_bind_list endpoint."""

    static_bind_list: list[StaticBindEntry] = field(default_factory=list)


# ─── Wi-Fi Management Models ──────────────────────────────────────────────────


@dataclass(eq=False)
class WifiInterface(BaseModel):
    """Wi-Fi interface configuration and credentials."""

    enabled: bool = False
    encryption: WifiEncryptionType = ""
    guest: bool = False
    hidden: bool = False
    key: str | None = None
    name: str = ""
    ssid: str = ""


@dataclass(eq=False)
class WifiDeviceEntry(BaseModel):
    """Wi-Fi radio device container with its logical interfaces."""

    band: WifiBandType = ""
    device: str = ""
    ifaces: list[WifiInterface] = field(default_factory=list)


@dataclass(eq=False)
class WifiConfigResponse(BaseModel):
    """Response payload for wifi.get_config endpoint."""

    dfs_support: bool = False
    res: list[WifiDeviceEntry] = field(default_factory=list)


WifiIfacesMap: TypeAlias = dict[str, WifiInterface]


# ─── WireGuard & VPN Models ───────────────────────────────────────────────────


@dataclass(eq=False)
class WireguardPeerConfig(BaseModel):
    """WireGuard client peer configuration."""

    name: str = ""
    peer_id: int = 0
    address_v4: str | None = None


@dataclass(eq=False)
class WireguardGroupConfig(BaseModel):
    """WireGuard group configuration container."""

    auth_type: int = 0
    group_id: int = 0
    group_name: str = ""
    password: str = ""
    peers: list[WireguardPeerConfig] = field(default_factory=list)
    username: str = ""


@dataclass(eq=False)
class WireguardConfigListResponse(BaseModel):
    """Response payload for wg-client.get_all_config_list endpoint."""

    config_list: list[WireguardGroupConfig] = field(default_factory=list)


@dataclass(eq=False)
class WireguardClientListItem(BaseModel):
    """Flattened WireGuard client peer entry returned by wireguard_client_list()."""

    name: str = ""
    group_id: int = 0
    peer_id: int = 0
    tunnel_id: int | None = None


@dataclass(eq=False)
class WireguardStatusItem(BaseModel):
    """WireGuard client tunnel operational status."""

    domain: str = ""
    enabled: bool = False
    group_id: int = 0
    ipv4: str = ""
    ipv6: str = ""
    log: str = ""
    name: str = ""
    peer_id: int = 0
    port: int = 0
    proxy: bool = False
    rx_bytes: int = 0
    status: int = 0
    tunnel_id: int | None = None
    tx_bytes: int = 0


@dataclass(eq=False)
class VpnClientStatusResponse(BaseModel):
    """Response payload for vpn-client.get_status endpoint (firmware >= 4.8)."""

    status_list: list[WireguardStatusItem] = field(default_factory=list)


# ─── Tailscale Models ─────────────────────────────────────────────────────────


@dataclass(eq=False)
class TailscaleConfigResponse(BaseModel):
    """Response payload for tailscale.get_config endpoint."""

    enabled: bool = False
    lan_enabled: bool = False
    lan_ip: str = ""
    wan_enabled: bool = False


@dataclass(eq=False)
class TailscaleStatusResponse(BaseModel):
    """Response payload for tailscale.get_status endpoint."""

    address_v4: str = ""
    login_name: str = ""
    status: int = 0


@dataclass(eq=False)
class TailscaleExitNodesResponse(BaseModel):
    """Response payload for tailscale.get_exit_node_list endpoint."""

    exit_node_list: list[str] = field(default_factory=list)


# ─── Cellular / Modem Models ──────────────────────────────────────────────────


@dataclass(eq=False)
class ModemEntry(BaseModel):
    """Modem device description."""

    carrier: str = ""
    imei: str = ""
    modem_id: int = 0
    model: str = ""
    status: ModemStatusType = ""


@dataclass(eq=False)
class ModemInfoResponse(BaseModel):
    """Response payload for modem.get_info endpoint."""

    modems: list[ModemEntry] = field(default_factory=list)


@dataclass(eq=False)
class ModemSimInfoEntry(BaseModel):
    """SIM card info within modem.get_sim_info endpoint."""

    iccid: str = ""
    imsi: str = ""
    sim_state: ModemSimStateType = ""


@dataclass(eq=False)
class ModemSimSignalEntry(BaseModel):
    """Modem signal strength metrics within modem.get_sim_signal endpoint."""

    rsrp: int = 0
    rsrq: int = 0
    rssi: int = 0
    sinr: int = 0


# ─── Additional Hardware & Service Models ─────────────────────────────────────


@dataclass(eq=False)
class CableStatusIpv4(BaseModel):
    """IPv4 network configuration within cable.get_status."""

    dns: list[str] = field(default_factory=list)
    gateway: str = ""
    ip: str = ""
    mask: str = ""


@dataclass(eq=False)
class CableStatusSecondWan(BaseModel):
    """Second WAN mode within cable.get_status."""

    mode: int = 0


@dataclass(eq=False)
class CableStatusResponse(BaseModel):
    """Response payload for cable.get_status endpoint."""

    ipv4: CableStatusIpv4 = field(default_factory=CableStatusIpv4)
    mode: int = 0
    protocol: str = ""
    secondwan: CableStatusSecondWan = field(default_factory=CableStatusSecondWan)
    status: int = 0


@dataclass(eq=False)
class DnsConfigResponse(BaseModel):
    """Response payload for dns.get_config endpoint."""

    force_dns: bool = False
    mode: str = ""
    rebind_protection: bool = False
    server: list[str] = field(default_factory=list)


@dataclass(eq=False)
class RepeaterConfigResponse(BaseModel):
    """Response payload for repeater.get_config endpoint."""

    antijam: bool = False
    auto: bool = False
    dfs: bool = False
    dfs_support: bool = False


@dataclass(eq=False)
class RepeaterScanEncryption(BaseModel):
    """Encryption details for scanned Wi-Fi AP."""

    description: str = ""
    enabled: bool = False
    uci: str = ""


@dataclass(eq=False)
class RepeaterScanEntry(BaseModel):
    """Discovered Wi-Fi access point in repeater.scan."""

    band: WifiBandType = ""
    bssid: str = ""
    channel: int = 0
    encryption: RepeaterScanEncryption = field(default_factory=RepeaterScanEncryption)
    signal: int = 0
    ssid: str = ""


@dataclass(eq=False)
class RepeaterScanResponse(BaseModel):
    """Response payload for repeater.scan endpoint."""

    res: list[RepeaterScanEntry] = field(default_factory=list)


@dataclass(eq=False)
class RepeaterStatusResponse(BaseModel):
    """Response payload for repeater.get_status endpoint."""

    eap: bool = False
    scanning: bool = False
    state: int = 0
    state_name: str = ""


@dataclass(eq=False)
class OvpnListEntry(BaseModel):
    """OpenVPN client peer entry in ovpn-client.get_config."""

    client_id: int = 0
    name: str = ""


@dataclass(eq=False)
class OvpnGroupConfig(BaseModel):
    """OpenVPN client group configuration."""

    group_id: int = 0
    group_name: str = ""
    ovpn_list: list[OvpnListEntry] = field(default_factory=list)


@dataclass(eq=False)
class OvpnConfigResponse(BaseModel):
    """Response payload for ovpn-client.get_config endpoint."""

    config_list: list[OvpnGroupConfig] = field(default_factory=list)


@dataclass(eq=False)
class OvpnStatusResponse(BaseModel):
    """Response payload for ovpn-client.get_status endpoint."""

    client_id: int = 0
    domain: str = ""
    group_id: int = 0
    ipv4: str = ""
    ipv6: str = ""
    log: str = ""
    mode: str = ""
    name: str = ""
    port: int = 0
    rx_bytes: int = 0
    status: int = 0
    tx_bytes: int = 0


@dataclass(eq=False)
class DhcpLeaseEntry(BaseModel):
    """Active DHCP lease entry."""

    expires: int = 0
    hostname: str = ""
    ip: str = ""
    mac: str = ""


@dataclass(eq=False)
class DhcpLeasesResponse(BaseModel):
    """Response payload for lan.get_dhcp_lease endpoint."""

    leases: list[DhcpLeaseEntry] = field(default_factory=list)


@dataclass(eq=False)
class LanInterfaceEntry(BaseModel):
    """LAN interface network parameters."""

    dns: list[str] = field(default_factory=list)
    enable: int = 1
    end: str = ""
    gateway: str = ""
    interface: str = ""
    ip: str = ""
    leasetime: str = ""
    lpr: list[Any] = field(default_factory=list)
    netmask: str = ""
    start: str = ""


@dataclass(eq=False)
class LanConfigResponse(BaseModel):
    """Response payload for lan.get_config endpoint."""

    interfaces: list[LanInterfaceEntry] = field(default_factory=list)


@dataclass(eq=False)
class FirewallWanAccessResponse(BaseModel):
    """Response payload for firewall.get_wan_access endpoint."""

    enable_https: bool = False
    enable_ping: bool = False
    enable_ssh: bool = False
    enable_whitelist: bool = False
    whitelist: list[Any] = field(default_factory=list)


@dataclass(eq=False)
class FirewallZonesResponse(BaseModel):
    """Response payload for firewall.get_zone_list endpoint."""

    externals: list[str] = field(default_factory=list)
    internals: list[str] = field(default_factory=list)


@dataclass(eq=False)
class DdnsConfigResponse(BaseModel):
    """Response payload for ddns.get_config endpoint."""

    device_id: str = ""
    enable_http_access: bool = False
    enable_https_access: bool = False
    enable_ssh_access: bool = False


@dataclass(eq=False)
class DdnsIpEntry(BaseModel):
    """Interface IP assignment in ddns.get_status."""

    interface: str = ""
    ip: list[str] = field(default_factory=list)


@dataclass(eq=False)
class DdnsStatusResponse(BaseModel):
    """Response payload for ddns.get_status endpoint."""

    ips: list[DdnsIpEntry] = field(default_factory=list)
    status: int = 0


@dataclass(eq=False)
class TetheringStatusResponse(BaseModel):
    """Response payload for tethering.get_status endpoint."""

    err_code: int = 0
    err_msg: str = ""
    status: int = 0


@dataclass(eq=False)
class SwitchButtonResponse(BaseModel):
    """Response payload for switch_button.get_config endpoint."""

    func: str = ""
    funcs: list[str] = field(default_factory=list)


@dataclass(eq=False)
class LedConfigResponse(BaseModel):
    """Response payload for led.get_config endpoint."""

    led_enable: bool = False


@dataclass(eq=False)
class AdguardHomeConfigResponse(BaseModel):
    """Response payload for adguardhome.get_config endpoint."""

    enabled: bool = False
    port: int = 0
    redirect_mode: str = ""
    tls: bool = False


@dataclass(eq=False)
class ArpListEntry(BaseModel):
    """ARP cache table entry."""

    device: str = ""
    ip: str = ""
    mac: str = ""


@dataclass(eq=False)
class ArpListResponse(BaseModel):
    """Response payload for lan.get_arp_list endpoint."""

    entries: list[ArpListEntry] = field(default_factory=list)


@dataclass(eq=False)
class VpnPolicyDomainPolicy(BaseModel):
    """Domain policy configuration."""

    default_policy: int = 0
    domain_list: str = ""


@dataclass(eq=False)
class VpnPolicyGlobalPolicy(BaseModel):
    """Global VPN routing policy configuration."""

    kill_switch: int = 0
    service_policy: int = 0
    vpn_server_policy: int = 0
    wan_access: int = 0


@dataclass(eq=False)
class VpnPolicyMacPolicy(BaseModel):
    """MAC address VPN routing policy."""

    default_policy: int = 0
    mac_list: list[Any] = field(default_factory=list)


@dataclass(eq=False)
class VpnPolicyProxyMode(BaseModel):
    """VPN proxy mode."""

    mode: int = 0


@dataclass(eq=False)
class VpnPolicyVlanEntry(BaseModel):
    """VLAN mapping in VPN policy."""

    id: int = 0
    vpn: int = 0


@dataclass(eq=False)
class VpnPolicyVlanPolicy(BaseModel):
    """VLAN VPN policy."""

    vlans: list[VpnPolicyVlanEntry] = field(default_factory=list)


@dataclass(eq=False)
class VpnPolicyResponse(BaseModel):
    """Response payload for vpn_policy.get_policy endpoint."""

    domain_policy: VpnPolicyDomainPolicy = field(default_factory=VpnPolicyDomainPolicy)
    global_policy: VpnPolicyGlobalPolicy = field(default_factory=VpnPolicyGlobalPolicy)
    mac_policy: VpnPolicyMacPolicy = field(default_factory=VpnPolicyMacPolicy)
    proxy_mode: VpnPolicyProxyMode = field(default_factory=VpnPolicyProxyMode)
    vlan_policy: VpnPolicyVlanPolicy = field(default_factory=VpnPolicyVlanPolicy)


__all__ = [
    "AdguardHomeConfigResponse",
    "ArpListEntry",
    "ArpListResponse",
    "BaseModel",
    "CableStatusIpv4",
    "CableStatusResponse",
    "CableStatusSecondWan",
    "ChallengeResponse",
    "ClientEntry",
    "ClientInterface",
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
    "EmptyResponseDict",
    "FirewallWanAccessResponse",
    "FirewallZonesResponse",
    "LanConfigResponse",
    "LanInterfaceEntry",
    "LedConfigResponse",
    "LoginResponse",
    "MaccloneResponse",
    "ModemEntry",
    "ModemInfoResponse",
    "ModemSimInfoEntry",
    "ModemSimSignalEntry",
    "ModemSimState",
    "ModemSimStateType",
    "ModemStatus",
    "ModemStatusType",
    "OvpnConfigResponse",
    "OvpnGroupConfig",
    "OvpnListEntry",
    "OvpnStatusResponse",
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
    "TailscaleConnection",
    "TailscaleExitNodesResponse",
    "TailscaleStatusResponse",
    "TetheringStatusResponse",
    "VpnClientStatusResponse",
    "VpnPolicyDomainPolicy",
    "VpnPolicyGlobalPolicy",
    "VpnPolicyMacPolicy",
    "VpnPolicyProxyMode",
    "VpnPolicyResponse",
    "VpnPolicyVlanEntry",
    "VpnPolicyVlanPolicy",
    "WifiBand",
    "WifiBandType",
    "WifiConfigResponse",
    "WifiDeviceEntry",
    "WifiEncryption",
    "WifiEncryptionType",
    "WifiIfacesMap",
    "WifiInterface",
    "WireguardClientListItem",
    "WireguardConfigListResponse",
    "WireguardGroupConfig",
    "WireguardPeerConfig",
    "WireguardStatusItem",
]
