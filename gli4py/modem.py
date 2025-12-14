"""Helpers for fetching and parsing modem status."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Dict, List, Optional

JSONDict = dict[str, Any]


class ModemConnectionState(IntEnum):
    """Connection state derived from modem network status."""

    UNKNOWN = -1
    DISCONNECTED = 0
    CONNECTED = 1


class ModemRegistrationStatus(IntEnum):
    """SIM registration status."""

    REGISTERED = 0
    UNREGISTERED = 1
    NEEDS_PIN = 2


class ModemNetworkStatus(IntEnum):
    """Network status for modem network block."""

    CONNECTED = 0
    CONNECTING = 1


class ModemNetworkMode(IntEnum):
    """Network mode reported in signal section."""

    GSM = 2
    UMTS = 3
    LTE = 4
    FIVE_G = 5
    LTE_ADVANCED = 41

    @property
    def label(self) -> str:
        """Return a user-friendly label for the network mode."""

        return {
            ModemNetworkMode.GSM: "2G",
            ModemNetworkMode.UMTS: "3G",
            ModemNetworkMode.LTE: "LTE",
            ModemNetworkMode.FIVE_G: "5G",
            ModemNetworkMode.LTE_ADVANCED: "4G+",
        }.get(self, self.name)


class ModemSignalStrength(IntEnum):
    """Overall signal strength buckets."""

    POOR = 1
    FAIR = 2
    GOOD = 3
    EXCELLENT = 4


class ModemAutoSwitchState(IntEnum):
    """SIM auto-switch state for dual-SIM devices."""

    ENABLED = 0
    DISABLED = 1


class ModemType(IntEnum):
    """Modem type as reported by modem.get_info."""

    BUILT_IN = 0
    EXTERNAL = 1
    UNSUPPORTED = 2


@dataclass(slots=True)
class SimCardInfo:
    """SIM card details."""

    iccid: str | None = None
    phone_number: str | None = None
    mcc: str | None = None
    mnc: str | None = None


@dataclass(slots=True)
class ModemInfo:
    """Hardware info returned by modem.get_info."""

    bus: str | None
    type: ModemType | None
    at_port: str | None
    data_port: str | None
    sms_support: bool | None
    lock_tower_support: bool | None
    qcfg_unsupport: bool | None
    imei: str | None
    name: str | None
    version: str | None
    vendor: str | None
    protocols: list[str] | None
    devices: list[str] | None
    simcard: SimCardInfo | None


@dataclass(slots=True)
class ModemSignal:
    """Signal details for a SIM."""

    mode: ModemNetworkMode | None
    strength: ModemSignalStrength | None
    rssi: int | None
    rsrp: int | None
    rsrq: int | None
    sinr: int | None
    ecio: int | None


@dataclass(slots=True)
class ModemNetworkIP:
    """IP details for a stack."""

    ip: str | None
    netmask: str | None
    gateway: str | None
    dns: list[str] | None


@dataclass(slots=True)
class ModemNetwork:
    """Network status for the modem."""

    status: ModemNetworkStatus | None
    traffic_total: int | None
    ipv4: ModemNetworkIP | None
    ipv6: ModemNetworkIP | None


@dataclass(slots=True)
class CellInfo:
    """Cell details from modem.get_cells_info."""

    ul_bandwidth: str | None
    dl_bandwidth: str | None
    rsrp: int | None
    id: str | None
    rssi: int | None
    tx_channel: str | None
    sinr_level: int | None
    rsrq_level: int | None
    sinr: int | None
    rsrq: int | None
    rssi_level: int | None
    rsrp_level: int | None
    mode: str | None
    band: int | None
    type: str | None


@dataclass(slots=True)
class ModemStatusEntry:
    """Status entry returned by modem.get_status."""

    bus: str | None
    current_sim: int | None
    switch_status: ModemAutoSwitchState | None
    sim_status: ModemRegistrationStatus | None
    sim_operator: str | None
    sim_iccid: str | None
    sim_phone_number: str | None
    sim_mcc: str | None
    sim_mnc: str | None
    signal: ModemSignal | None
    network: ModemNetwork | None
    cells_info: list[CellInfo] | None
    connection_state: ModemConnectionState
    new_sms_count: int | None
    passthrough: JSONDict | None
    err_code: int | None
    err_msg: str | None


class ModemManager:
    """High-level helper for modem status retrieval."""

    def __init__(self, client: Any) -> None:
        self._client = client

    async def _rpc_call(
        self, namespace: str, method: str, params: Optional[JSONDict] = None
    ) -> JSONDict:
        """Thin wrapper around the parent client's JSON-RPC helper."""

        return await self._client._request(  # type: ignore[attr-defined,no-any-return]
            self._client.gen_sid_payload(  # type: ignore[attr-defined]
                "call", [namespace, method, params or {}], self._client.sid  # type: ignore[attr-defined]
            )
        )

    async def fetch_modem_status(self) -> JSONDict:
        """Return raw modem runtime status for all modems."""

        return await self._rpc_call("modem", "get_status", {})

    async def fetch_modem_info(self) -> JSONDict:
        """Return raw modem hardware info."""

        return await self._rpc_call("modem", "get_info", {})

    async def fetch_cells_info(self, bus: str) -> JSONDict:
        """Return raw cell information for a modem."""

        return await self._rpc_call("modem", "get_cells_info", {"bus": bus})

    async def get_status(self) -> list[ModemStatusEntry]:
        """Fetch and parse modem status."""

        payload = await self.fetch_modem_status()
        modems = payload.get("modems", []) if isinstance(payload, dict) else []

        parsed_entries: list[ModemStatusEntry] = []
        for entry in modems:
            if not isinstance(entry, dict):
                continue
            bus = entry.get("bus")
            cells_info: list[CellInfo] | None = None
            if bus is not None:
                try:
                    cells_payload = await self.fetch_cells_info(str(bus))
                    cells_info = self._parse_cells_info(cells_payload)
                except Exception:  # noqa: BLE001
                    cells_info = None
            parsed_entries.append(self._parse_status_entry(entry, cells_info))
        return parsed_entries

    async def get_info(self) -> list[ModemInfo]:
        """Fetch and parse modem hardware info."""

        payload = await self.fetch_modem_info()
        modems = payload.get("modems", []) if isinstance(payload, dict) else []
        return [self._parse_info(entry) for entry in modems]

    async def get_cells_info(self, bus: str) -> list[CellInfo] | None:
        """Fetch and return parsed cell information for a modem."""

        payload = await self.fetch_cells_info(bus)
        return self._parse_cells_info(payload)

    @staticmethod
    def _parse_info(entry: JSONDict) -> ModemInfo:
        """Parse a modem entry from modem.get_info."""

        type_value = entry.get("type")
        modem_type: ModemType | None = None
        try:
            modem_type = ModemType(int(type_value))
        except (TypeError, ValueError):
            modem_type = None

        sim_entry = entry.get("simcard") or {}
        simcard = SimCardInfo(
            iccid=sim_entry.get("iccid"),
            phone_number=sim_entry.get("phone_number"),
            mcc=sim_entry.get("mcc"),
            mnc=sim_entry.get("mnc"),
        ) if sim_entry else None

        devices = entry.get("devices")
        if isinstance(devices, list):
            devices_list: List[str] | None = [str(dev) for dev in devices]
        else:
            devices_list = None

        protocols = entry.get("protocols")
        if isinstance(protocols, list):
            protocols_list: List[str] | None = [str(proto) for proto in protocols]
        else:
            protocols_list = None

        return ModemInfo(
            bus=entry.get("bus"),
            type=modem_type,
            at_port=entry.get("at_port"),
            data_port=entry.get("data_port"),
            sms_support=entry.get("sms_support"),
            lock_tower_support=entry.get("lock_tower_support"),
            qcfg_unsupport=entry.get("qcfg_unsupport"),
            imei=entry.get("imei"),
            name=entry.get("name"),
            version=entry.get("version"),
            vendor=entry.get("vendor"),
            protocols=protocols_list,
            devices=devices_list,
            simcard=simcard,
        )

    @staticmethod
    def _parse_status_entry(
        entry: JSONDict, cells_info: list[CellInfo] | None = None
    ) -> ModemStatusEntry:
        """Parse a modem entry from modem.get_status."""

        sim_entry = entry.get("simcard") or {}
        signal_entry = sim_entry.get("signal") or {}
        network_entry = entry.get("network") or {}

        def _parse_signal() -> ModemSignal | None:
            if not signal_entry:
                return None
            mode_value = signal_entry.get("mode")
            try:
                mode = ModemNetworkMode(int(mode_value)) if mode_value is not None else None
            except ValueError:
                mode = None
            strength_value = signal_entry.get("strength")
            try:
                strength = (
                    ModemSignalStrength(int(strength_value))
                    if strength_value is not None
                    else None
                )
            except ValueError:
                strength = None
            return ModemSignal(
                mode=mode,
                strength=strength,
                rssi=signal_entry.get("rssi"),
                rsrp=signal_entry.get("rsrp"),
                rsrq=signal_entry.get("rsrq"),
                sinr=signal_entry.get("sinr"),
                ecio=signal_entry.get("ecio"),
            )

        def _parse_ip(ip_entry: Any) -> ModemNetworkIP | None:
            if not isinstance(ip_entry, dict):
                return None
            dns = ip_entry.get("dns")
            if isinstance(dns, list):
                dns_list: list[str] | None = [str(v) for v in dns]
            else:
                dns_list = None
            return ModemNetworkIP(
                ip=ip_entry.get("ip"),
                netmask=ip_entry.get("netmask"),
                gateway=ip_entry.get("gateway"),
                dns=dns_list,
            )

        def _parse_network() -> tuple[ModemNetwork | None, ModemConnectionState]:
            if not network_entry:
                return None, ModemConnectionState.UNKNOWN
            status_value = network_entry.get("status")
            status: ModemNetworkStatus | None = None
            if isinstance(status_value, str):
                lowered = status_value.lower()
                if lowered == "connected":
                    status = ModemNetworkStatus.CONNECTED
                elif lowered == "connecting":
                    status = ModemNetworkStatus.CONNECTING
                else:
                    try:
                        status = ModemNetworkStatus(int(status_value))
                    except ValueError:
                        status = None
            elif status_value is not None:
                try:
                    status = ModemNetworkStatus(int(status_value))
                except ValueError:
                    status = None
            conn_state = ModemConnectionState.UNKNOWN
            if status == ModemNetworkStatus.CONNECTED:
                conn_state = ModemConnectionState.CONNECTED
            elif status == ModemNetworkStatus.CONNECTING:
                conn_state = ModemConnectionState.DISCONNECTED
            return (
                ModemNetwork(
                    status=status,
                    traffic_total=network_entry.get("traffic_total"),
                    ipv4=_parse_ip(network_entry.get("ipv4")),
                    ipv6=_parse_ip(network_entry.get("ipv6")),
                ),
                conn_state,
            )

        sim_status_value = sim_entry.get("status")
        try:
            sim_status = (
                ModemRegistrationStatus(int(sim_status_value))
                if sim_status_value is not None
                else None
            )
        except ValueError:
            sim_status = None

        network_parsed, conn_state = _parse_network()

        switch_status_value = entry.get("switch_status")
        try:
            switch_status = (
                ModemAutoSwitchState(int(switch_status_value))
                if switch_status_value is not None
                else None
            )
        except ValueError:
            switch_status = None

        return ModemStatusEntry(
            bus=entry.get("bus"),
            current_sim=entry.get("current_sim"),
            switch_status=switch_status,
            sim_status=sim_status,
            sim_operator=sim_entry.get("carrier"),
            sim_iccid=sim_entry.get("iccid"),
            sim_phone_number=sim_entry.get("phone_number"),
            sim_mcc=sim_entry.get("mcc"),
            sim_mnc=sim_entry.get("mnc"),
            signal=_parse_signal(),
            network=network_parsed,
            cells_info=cells_info,
            connection_state=conn_state,
            new_sms_count=entry.get("new_sms_count"),
            passthrough=entry.get("passthrough"),
            err_code=entry.get("err_code"),
            err_msg=entry.get("err_msg"),
        )

    @staticmethod
    def _parse_cells_info(payload: JSONDict | None) -> list[CellInfo] | None:
        """Parse cell info payload."""

        if not isinstance(payload, dict):
            return None
        body: JSONDict = payload.get("result", payload) if isinstance(payload, dict) else {}
        cells = body.get("cells") if isinstance(body, dict) else None
        if not isinstance(cells, list):
            return None

        parsed: list[CellInfo] = []

        def _as_int(value: Any) -> int | None:
            try:
                return int(value) if value is not None else None
            except (TypeError, ValueError):
                return None

        for cell in cells:
            if not isinstance(cell, dict):
                continue
            parsed.append(
                CellInfo(
                    ul_bandwidth=cell.get("ul_bandwidth"),
                    dl_bandwidth=cell.get("dl_bandwidth"),
                    rsrp=_as_int(cell.get("rsrp")),
                    id=str(cell.get("id")) if cell.get("id") is not None else None,
                    rssi=_as_int(cell.get("rssi")),
                    tx_channel=str(cell.get("tx_channel")) if cell.get("tx_channel") is not None else None,
                    sinr_level=_as_int(cell.get("sinr_level")),
                    rsrq_level=_as_int(cell.get("rsrq_level")),
                    sinr=_as_int(cell.get("sinr")),
                    rsrq=_as_int(cell.get("rsrq")),
                    rssi_level=_as_int(cell.get("rssi_level")),
                    rsrp_level=_as_int(cell.get("rsrp_level")),
                    mode=cell.get("mode"),
                    band=_as_int(cell.get("band")),
                    type=cell.get("type"),
                )
            )

        return parsed or None
