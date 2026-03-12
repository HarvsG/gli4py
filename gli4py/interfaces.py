"""Helpers for inspecting GL.iNet interface / Multi‑WAN state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Dict, Iterable, List, Optional

from .modem import ModemInfo, ModemManager, ModemStatusEntry

JSONDict = Dict[str, Any]


class InterfaceStatus(IntEnum):
    """Interface connectivity status reported by kmwan."""

    ONLINE = 0
    OFFLINE = 1
    ERROR = 2


class MultiWANMode(IntEnum):
    """Multi-WAN operating mode reported by kmwan."""

    FAILOVER = 0
    LOAD_BALANCING = 1


@dataclass(slots=True)
class InterfaceInfo:
    """Joined view of kmwan configuration and status for a single interface.

    Attributes
    ----------
    name:
        Logical interface name as used by kmwan (e.g. ``"wan"``, ``"wwan"``,
        ``"tethering"``, ``"modem_0001"``, ``"secondwan"``).
    metric:
        Fail‑over priority (lower value == higher priority).  ``None`` if not
        provided by the firmware / config.
    weight:
        Load‑balancing weight in balancing mode.  ``None`` if not present.
    status_v4:
        IPv4 status as reported by ``kmwan.get_status``.
        According to the device documentation this is typically:

        * ``0`` – online
        * ``1`` – offline

        Some firmwares also use ``2`` for an explicit error state.
    status_v6:
        IPv6 status, with the same coding as :attr:`status_v4`.
    """

    name: str
    metric: Optional[int] = None
    weight: Optional[int] = None
    status_v4: InterfaceStatus | None = None
    status_v6: InterfaceStatus | None = None
    modem: ModemDetails | None = None

    def ipv4_online(self) -> Optional[bool]:
        """Return ``True`` if IPv4 is explicitly online, ``False`` if
        explicitly offline, or ``None`` if there is no information.
        """

        if self.status_v4 is None:
            return None
        return self.status_v4 == InterfaceStatus.ONLINE

    def ipv6_online(self) -> Optional[bool]:
        """Return ``True`` if IPv6 is explicitly online, ``False`` if
        explicitly offline, or ``None`` if there is no information.
        """

        if self.status_v6 is None:
            return None
        return self.status_v6 == InterfaceStatus.ONLINE

    def is_online(self, prefer_ipv6: bool = False) -> bool:
        """Coarse "is this usable" predicate.

        The rules are conservative and intentionally simple:

        * If *prefer_ipv6* is true and there is an IPv6 state, use that.
        * Otherwise, prefer IPv4 if present.
        * If we only have one of them, use whichever we have.
        * Any non‑zero status is treated as *not online*.
        """

        v4 = self.ipv4_online()
        v6 = self.ipv6_online()

        if prefer_ipv6 and v6 is not None:
            return bool(v6)
        if v4 is not None:
            return bool(v4)
        if v6 is not None:
            return bool(v6)
        return False


@dataclass(slots=True)
class ModemDetails:
    """Combined modem runtime status and hardware info."""

    status: ModemStatusEntry | None = None
    info: ModemInfo | None = None


@dataclass(slots=True)
class MultiWANState:
    """Snapshot of the router's Multi‑WAN configuration and status."""

    mode: MultiWANMode
    """Multi‑WAN mode."""

    interfaces: Dict[str, InterfaceInfo]
    """Mapping from interface name to :class:`InterfaceInfo`."""

    primary: str | None = None
    """Interface name that is currently considered primary, if known."""


class InterfaceManager:
    """High‑level helper for kmwan interface status.

    Parameters
    ----------
    client:
        A GL.iNet API client instance that exposes ``gen_sid_payload`` and
        ``_request`` helpers like :class:`gli4py.glinet.GLinet`.
    """

    def __init__(self, client: Any) -> None:
        self._client = client
        self._modem_manager = ModemManager(client)

    # ------------------------------------------------------------------
    # Raw fetchers
    # ------------------------------------------------------------------
    async def fetch_kmwan_status(self) -> JSONDict:
        """Return the raw payload from ``kmwan.get_status``.

        Typical shape::

            {
                "interfaces": [
                    {
                        "interface": "wan",
                        "status_v4": 0,
                        "status_v6": 1,
                    },
                    ...
                ]
            }
        """

        return await self._client._request(
            self._client.gen_sid_payload(
                "call",
                ["kmwan", "get_status"],
                self._client.sid,
            )
        )

    async def fetch_kmwan_config(self) -> JSONDict:
        """Return the raw payload from ``kmwan.get_config``.

        Firmware‑specific details vary, but you can generally expect::

            {
                "mode": 0 | 1,
                "interfaces": [
                    {
                        "interface": "wan",
                        "metric": 1,
                        "weight": 1,
                        ...
                    },
                    ...
                ]
            }
        """

        return await self._client._request(
            self._client.gen_sid_payload(
                "call",
                ["kmwan", "get_config"],
                self._client.sid,
            )
        )

    async def fetch_network_interface_status(self) -> JSONDict:
        """Return status for a single interface via ``network.interface status``."""

        return await self._client._request(
            self._client.gen_sid_payload(
                "call",
                ["network.interface", "status", {"interface": "wan"}],
                self._client.sid,
            )
        )

    # ------------------------------------------------------------------
    # Joined / parsed state
    # ------------------------------------------------------------------
    async def get_state(self, prefer_ipv6: bool = False) -> MultiWANState:
        """Fetch and join kmwan configuration + status into one object."""

        config = await self.fetch_kmwan_config()
        mwan_status = await self.fetch_kmwan_status()
        # iface_status = await self.fetch_network_interface_status()

        interfaces: Dict[str, InterfaceInfo] = {}

        # First layer in config (metric / weight).
        for entry in config.get("interfaces", []) or []:
            name = entry.get("interface")
            if not name:
                continue
            info = interfaces.get(name)
            if info is None:
                info = InterfaceInfo(name=name)
                interfaces[name] = info

            info.metric = entry.get("metric")
            info.weight = entry.get("weight")

        # Second layer: live status (IPv4 / IPv6 online / offline).
        for entry in mwan_status.get("interfaces", []) or []:
            name = entry.get("interface")
            if not name:
                continue
            info = interfaces.get(name)
            if info is None:
                info = InterfaceInfo(name=name)
                interfaces[name] = info

            # kmwan uses 0 = online, 1 = offline; some firmwares extend this
            # to 2 = error.  We keep the raw integer and interpret it in
            # InterfaceInfo helper methods.
            info.status_v4 = self._parse_status(entry.get("status_v4"))
            info.status_v6 = self._parse_status(entry.get("status_v6"))

        mode_value = int(config.get("mode", 0))
        try:
            mode = MultiWANMode(mode_value)
        except ValueError:
            mode = MultiWANMode.FAILOVER
        primary = self._select_primary(interfaces, mode, prefer_ipv6)

        # Attach modem status entries to modem interfaces if available.
        modem_interfaces = sorted(
            [name for name in interfaces if name.startswith("modem")]
        )
        if modem_interfaces:
            modem_statuses = await self._modem_manager.get_status()
            modem_infos = await self._modem_manager.get_info()
            for idx, iface_name in enumerate(modem_interfaces):
                modem_details = ModemDetails()
                if idx < len(modem_statuses):
                    modem_details.status = modem_statuses[idx]
                if idx < len(modem_infos):
                    modem_details.info = modem_infos[idx]
                interfaces[iface_name].modem = modem_details

        return MultiWANState(
            mode=mode,
            interfaces=interfaces,
            primary=primary.name if primary else None,
        )

    # ------------------------------------------------------------------
    # High‑level helpers
    # ------------------------------------------------------------------
    def _select_primary(
        self,
        interfaces: Dict[str, InterfaceInfo],
        mode: MultiWANMode,
        prefer_ipv6: bool,
    ) -> Optional[InterfaceInfo]:
        """Return the primary interface based on kmwan mode and status."""

        if not interfaces:
            return None

        def by_metric(iters: Iterable[InterfaceInfo]) -> List[InterfaceInfo]:
            def metric_key(info: InterfaceInfo) -> int:
                # Higher metrics are lower priority; push "None" to the end.
                return info.metric if info.metric is not None else 10_000

            return sorted(iters, key=metric_key)

        online = [
            i for i in interfaces.values() if i.is_online(prefer_ipv6=prefer_ipv6)
        ]
        if not online:
            return None

        if mode == MultiWANMode.FAILOVER:
            return by_metric(online)[0]

        def weight_metric_key(info: InterfaceInfo) -> tuple[int, int]:
            w = info.weight if info.weight is not None else 0
            m = info.metric if info.metric is not None else 10_000
            return (-w, m)

        return sorted(online, key=weight_metric_key)[0]

    @staticmethod
    def _parse_status(value: Any) -> InterfaceStatus | None:
        """Convert kmwan status integers to InterfaceStatus."""

        if value is None:
            return None
        if isinstance(value, InterfaceStatus):
            return value
        if isinstance(value, bool):
            return InterfaceStatus.ONLINE if value else InterfaceStatus.OFFLINE
        if isinstance(value, dict):
            for key in ("up", "online", "connected", "link", "state", "status"):
                if key in value:
                    v = value[key]
                    if isinstance(v, bool):
                        return InterfaceStatus.ONLINE if v else InterfaceStatus.OFFLINE
                    if isinstance(v, str):
                        lowered = v.lower()
                        if lowered in {"up", "online", "connected"}:
                            return InterfaceStatus.ONLINE
                        if lowered in {"down", "offline", "disconnected"}:
                            return InterfaceStatus.OFFLINE
                    if isinstance(v, int):
                        try:
                            return InterfaceStatus(int(v))
                        except ValueError:
                            pass
            # As a fallback, treat any truthy dict with no known key as unknown.
        if isinstance(value, str):
            lowered = value.lower()
            if lowered in {"online", "up", "connected"}:
                return InterfaceStatus.ONLINE
            if lowered in {"offline", "down", "disconnected"}:
                return InterfaceStatus.OFFLINE
        try:
            return InterfaceStatus(int(value))
        except ValueError:
            return None
