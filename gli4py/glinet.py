"""This module provides an asynchronous client for the GL-inet router API using uplink."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Mapping
from typing import TYPE_CHECKING, Literal, TypeVar

from aiohttp import ClientError, ClientSession
from passlib.hash import md5_crypt, sha256_crypt, sha512_crypt
from requests import exceptions
from semver import Version
from uplink import (
    AiohttpClient,
    Body,
    Consumer,
    args,
    json,
    post,
    response_handler,
    timeout,
)

from gli4py.models import (
    ChallengeResponse,
    ClientEntry,
    ClientInterface,
    ClientsResponse,
    ConnectedClients,
    EdgeRouterStatusResponse,
    EmptyResponse,
    LoginResponse,
    MaccloneResponse,
    ModemInfoResponse,
    ModemSimInfoEntry,
    ModemSimSignalEntry,
    RouterStatusResponse,
    StaticBindListResponse,
    SystemInfoResponse,
    SystemLoadResponse,
    SystemPingResponse,
    SystemPingResult,
    TailscaleConfigResponse,
    TailscaleConnection,
    TailscaleStatusResponse,
    VpnClientStatusResponse,
    WifiConfigResponse,
    WifiIfacesMap,
    WireguardClientListItem,
    WireguardConfigListResponse,
    WireguardStatusItem,
)

from .error_handling import (
    APIClientError,
    AuthenticationError,
    raise_for_status,
)

if TYPE_CHECKING:
    from gli4py.types import (
        JsonRpcRequestPayload,
        TailscaleSetConfigParams,
        WifiConfigSetParams,
    )

try:
    import pydantic

    # Force Pydantic to resolve its lazy imports to prevent HA event loop blocking
    _ = pydantic.BaseModel
except ImportError:
    pass


# typical base url http://192.168.8.1/rpc
NEW_VPN_CLIENT_VERSION = Version(4, 8, 0, 0)

T = TypeVar("T")


class GLinet(Consumer):
    """A Python Client for the GL-inet API."""

    _firmware_version: Version | None = None
    sid: str | None = None
    _logged_in: bool = False

    def __init__(
        self,
        sid: str | None = None,
        client: AiohttpClient | None = None,
        session: ClientSession | None = None,
        base_url: str = "",
        **kwargs: object,
    ) -> None:
        """Initialise GLinet consumer client."""
        self.sid = sid
        self._logged_in = self.sid is not None

        if client is None:
            client = AiohttpClient(session=session) if session else AiohttpClient()

        # initialise the super class
        super().__init__(base_url=base_url, client=client, **kwargs)

    @staticmethod
    def gen_sid_payload(
        method: str, params: list[object], sid: str | None = None
    ) -> JsonRpcRequestPayload:
        """Generates a payload for the GL-inet API with a session ID."""
        params.insert(0, sid)
        payload: JsonRpcRequestPayload = {
            "method": method,
            "jsonrpc": "2.0",
            "params": params,
            "id": 0,
        }
        return payload

    @staticmethod
    def gen_no_auth_payload(
        method: str, params: dict[str, object] | list[object]
    ) -> JsonRpcRequestPayload:
        """Generates a payload for the GL-inet API without session ID authentication."""
        payload: JsonRpcRequestPayload = {
            "method": method,
            "jsonrpc": "2.0",
            "params": params,
            "id": 0,
        }
        return payload

    @response_handler(raise_for_status)
    @args(data=Body)
    @json
    @post("")
    @timeout(2)
    async def _request(self, data: object) -> T:
        """Base method to make a request to the GL-inet API."""
        raise NotImplementedError

    @response_handler(raise_for_status)
    @args(data=Body)
    @json
    @post("")
    @timeout(15)
    async def _request_long_timeout(self, data: object) -> T:
        """Base method to make a request to the GL-inet API with a longer timeout."""
        raise NotImplementedError

    async def _challenge(self, username: str) -> ChallengeResponse:
        """Requests a challenge from the GL-inet API to start the login process."""
        challenge_data = self.gen_no_auth_payload("challenge", {"username": username})
        raw = await self._request(challenge_data)
        if isinstance(raw, ChallengeResponse):
            return raw
        return ChallengeResponse.from_dict(raw)

    async def _get_sid(self, username: str, hsh: str) -> LoginResponse:
        """Requests a session ID from the GL-inet API using the provided username and hash."""
        login_data = self.gen_no_auth_payload(
            "login", {"username": username, "hash": hsh}
        )
        raw = await self._request(login_data)
        if isinstance(raw, LoginResponse):
            return raw
        return LoginResponse.from_dict(raw)

    async def router_reachable(self, username: str = "root") -> bool:
        """Checks if the router is reachable by attempting to get a challenge."""
        try:
            res = await self._challenge(username)
            if res:
                return True
        except (
            APIClientError,
            ClientError,
            TimeoutError,
            exceptions.RequestException,
        ):
            return False
        return False

    @staticmethod
    def _compute_hash(
        *,
        alg: int,
        salt: str,
        nonce: str,
        hash_method: str,
        username: str,
        password: str,
    ) -> str:
        """Synchronous helper for CPU-bound hashing."""
        # Step2: Generate cipher text using openssl algorithm
        if alg == 1:  # MD5
            cipher_password = md5_crypt.using(salt=salt).hash(password)
        elif alg == 5:  # SHA-256
            cipher_password = sha256_crypt.using(salt=salt, rounds=5000).hash(password)
        elif alg == 6:  # SHA-512
            cipher_password = sha512_crypt.using(salt=salt, rounds=5000).hash(password)
        else:
            raise ValueError(
                "Router requested unsupported hashing algorithm for cipher password"
            )

        # Step3: Generate hash values for login
        data = f"{username}:{cipher_password}:{nonce}"
        if hash_method == "md5":  # MD5
            return hashlib.md5(data.encode()).hexdigest()
        if hash_method == "sha256":  # SHA-256
            return hashlib.sha256(data.encode()).hexdigest()
        if hash_method == "sha512":  # SHA-512
            return hashlib.sha512(data.encode()).hexdigest()

        raise ValueError("Router requested unsupported hashing algorithm for hash")

    async def login(self, username: str, password: str) -> None:
        """Logs in to the GL-inet router using the provided username and password."""
        try:
            res = await self._challenge(username)

            alg = res.alg
            salt = res.salt
            nonce = res.nonce
            hash_method: str = str(res.hash_method or "md5")

            # Run the heavy, blocking cryptography operations in a separate thread
            hsh = await asyncio.to_thread(
                self._compute_hash,
                alg=alg,
                salt=salt,
                nonce=nonce,
                hash_method=hash_method,
                username=username,
                password=password,
            )

            # Step4: Get sid by login
            login_res = await self._get_sid(username, hsh)
            if login_res.sid:
                self.sid = login_res.sid
                self._logged_in = True

        except exceptions.RequestException as e:
            raise exceptions.RequestException(e)
        except (KeyError, ValueError) as e:
            raise KeyError("Parameter Exception:") from e
        except AuthenticationError:
            raise
        except APIClientError as e:
            raise APIClientError(
                f"An unexpected error of type {type(e).__name__} has occurred during login"
            ) from e

    async def router_info(self) -> SystemInfoResponse:
        """Retrieves information about the router, requires authentication."""
        raw = await self._request(
            self.gen_sid_payload("call", ["system", "get_info"], self.sid)
        )
        response = (
            raw
            if isinstance(raw, SystemInfoResponse)
            else SystemInfoResponse.from_dict(raw)
        )

        # Sanity check for firmware version
        if response.firmware_version:
            self._firmware_version = Version.parse(response.firmware_version)
        else:
            # No firmware version found, error
            raise ValueError("No firmware version found in router info")

        return response

    async def modem_info(self) -> ModemInfoResponse:
        """Retrieves information about the modems, requires authentication."""
        raw = await self._request(
            self.gen_sid_payload("call", ["modem", "get_info"], self.sid)
        )
        return (
            raw
            if isinstance(raw, ModemInfoResponse)
            else ModemInfoResponse.from_dict(raw)
        )

    async def modem_sim_info(self) -> list[ModemSimInfoEntry]:
        """Retrieves information about the modems, requires authentication."""
        raw = await self._request(
            self.gen_sid_payload("call", ["modem", "get_sim_info"], self.sid)
        )
        return [
            x if isinstance(x, ModemSimInfoEntry) else ModemSimInfoEntry.from_dict(x)
            for x in raw
        ]

    async def modem_sim_signal(self) -> list[ModemSimSignalEntry]:
        """Retrieves information about the modems, requires authentication."""
        raw = await self._request(
            self.gen_sid_payload("call", ["modem", "get_sim_signal"], self.sid)
        )
        return [
            x
            if isinstance(x, ModemSimSignalEntry)
            else ModemSimSignalEntry.from_dict(x)
            for x in raw
        ]

    async def router_get_status(self) -> RouterStatusResponse:
        """Retrieves the status of the router, requires authentication."""
        raw = await self._request(
            self.gen_sid_payload("call", ["system", "get_status"], self.sid)
        )
        response = (
            raw
            if isinstance(raw, RouterStatusResponse)
            else RouterStatusResponse.from_dict(raw)
        )

        # remove wifi passwords
        if response.wifi:
            for wifi_entry in response.wifi:
                wifi_entry.passwd = None
        return response

    async def router_get_load(self) -> SystemLoadResponse:
        """Retrieves the load information of the router, requires authentication."""
        raw = await self._request(
            self.gen_sid_payload("call", ["system", "get_load"], self.sid)
        )
        return (
            raw
            if isinstance(raw, SystemLoadResponse)
            else SystemLoadResponse.from_dict(raw)
        )

    async def router_mac(self) -> MaccloneResponse:
        """Retrieves the MAC address of the router, requires authentication."""
        raw = await self._request(
            self.gen_sid_payload("call", ["macclone", "get_mac"], self.sid)
        )
        return (
            raw
            if isinstance(raw, MaccloneResponse)
            else MaccloneResponse.from_dict(raw)
        )

    async def router_reboot(self, delay: int = 0) -> EmptyResponse:
        """Reboots the router, requires authentication."""
        return await self._request(
            self.gen_sid_payload(
                "call", ["system", "reboot", {"delay": delay}], self.sid
            )
        )

    async def ping(self, address: str = "8.8.8.8") -> bool:
        """Returns True if ping probe succeeded or False if unsuccessful."""
        result: SystemPingResult = await self._request_long_timeout(
            self.gen_sid_payload("call", ["diag", "ping", {"addr": address}], self.sid)
        )
        if isinstance(result, dict):
            result = SystemPingResponse.from_dict(result)
        if isinstance(result, SystemPingResponse):
            ping_output = result.ping_result or ""
            return bool(
                ping_output
                and "100% packet loss" not in ping_output
                and ("packets received" in ping_output or "bytes from" in ping_output)
            )
        return isinstance(result, list) and len(result) > 0

    async def connected_to_internet(self) -> EdgeRouterStatusResponse:
        """Is the internet reachable."""
        raw = await self._request(
            self.gen_sid_payload("call", ["edgerouter", "get_status"], self.sid)
        )
        return (
            raw
            if isinstance(raw, EdgeRouterStatusResponse)
            else EdgeRouterStatusResponse.from_dict(raw)
        )

    async def list_all_clients(self) -> ClientsResponse:
        """Gets all clients connected to the router."""
        raw = await self._request(
            self.gen_sid_payload("call", ["clients", "get_list"], self.sid)
        )
        return (
            raw if isinstance(raw, ClientsResponse) else ClientsResponse.from_dict(raw)
        )

    async def list_static_clients(self) -> StaticBindListResponse:
        """Gets all static clients connected to the router."""
        raw = await self._request(
            self.gen_sid_payload("call", ["lan", "get_static_bind_list"], self.sid)
        )
        return (
            raw
            if isinstance(raw, StaticBindListResponse)
            else StaticBindListResponse.from_dict(raw)
        )

    async def connected_clients(
        self, interface: ClientInterface | str | None = None
    ) -> ConnectedClients:
        """Gets all connected clients asynchronously.

        Optionally filters clients by interface (e.g. ClientInterface.CABLE,
        ClientInterface.BAND_5G, or a raw string).
        Returns a dictionary with MAC address as key and client data as value.
        """
        clients: ConnectedClients = {}
        all_clients = await self.list_all_clients()
        filter_iface = str(interface) if interface is not None else None
        client_list = (
            all_clients.clients
            if isinstance(all_clients, ClientsResponse)
            else all_clients.get("clients", [])
        )
        for client in client_list:
            if not isinstance(client, ClientEntry):
                client = ClientEntry.from_dict(client)
            if client.online is True:
                if filter_iface is None or client.iface == filter_iface:
                    clients[client.mac] = client
        return clients

    async def _wifi_config_get(self) -> WifiConfigResponse:
        """Retrieves the WiFi configuration from the router."""
        raw = await self._request(
            self.gen_sid_payload("call", ["wifi", "get_config"], self.sid)
        )
        return (
            raw
            if isinstance(raw, WifiConfigResponse)
            else WifiConfigResponse.from_dict(raw)
        )

    async def _wifi_config_set(self, config: WifiConfigSetParams) -> EmptyResponse:
        """Sets the WiFi configuration on the router."""
        return await self._request(
            self.gen_sid_payload("call", ["wifi", "set_config", config], self.sid)
        )

    async def wifi_ifaces_get(self, redact_keys: bool = True) -> WifiIfacesMap:
        """Returns a dictionary of wifi interfaces.

        If redact_keys, all key values will be set to None.
        """
        wifi_config = await self._wifi_config_get()
        if not isinstance(wifi_config, WifiConfigResponse):
            wifi_config = WifiConfigResponse.from_dict(wifi_config)
        ifaces: WifiIfacesMap = {}
        for dev in wifi_config.res:
            for iface in dev.ifaces:
                if redact_keys:
                    iface.key = None
                ifaces[iface.name] = iface
        return ifaces

    async def wifi_iface_set_enabled(
        self, iface_name: str, enabled: bool
    ) -> EmptyResponse:
        """Enable / disable wifi interface by name as found by wifi_ifaces_get()."""
        ifaces = await self.wifi_ifaces_get()
        if iface_name in ifaces:
            return await self._wifi_config_set(
                {"enabled": enabled, "iface_name": iface_name}
            )
        raise ValueError("iface_name does not exist")

    # VPN information

    async def wireguard_client_list(self) -> list[WireguardClientListItem]:
        """Gets the list of WireGuard clients."""
        raw = await self._request(
            self.gen_sid_payload("call", ["wg-client", "get_all_config_list"], self.sid)
        )
        response = (
            raw
            if isinstance(raw, WireguardConfigListResponse)
            else WireguardConfigListResponse.from_dict(raw)
        )
        configs: list[WireguardClientListItem] = []
        for item in response.config_list:
            peers = item.peers
            if not peers:
                continue
            for peer in peers:
                configs.append(
                    WireguardClientListItem(
                        name=f"{item.group_name}/{peer.name}",
                        group_id=item.group_id,
                        peer_id=peer.peer_id,
                    )
                )
        return configs

    async def wireguard_client_state(self) -> list[WireguardStatusItem]:
        """Retrieves WireGuard client connection status.

        Firmware 4.8 and greater returns a list of status objects.
        Firmware less than 4.8 returns a single status object wrapped in a list.
        """
        if self._firmware_version is None:
            await self.router_info()
        assert self._firmware_version is not None

        # If version is 4.8 or greater use vpn-client otherwise use wg-client
        if self._firmware_version < NEW_VPN_CLIENT_VERSION:
            raw = await self._request(
                self.gen_sid_payload("call", ["wg-client", "get_status"], self.sid)
            )
            old_item = (
                raw
                if isinstance(raw, WireguardStatusItem)
                else WireguardStatusItem.from_dict(raw)
            )
            return [old_item]

        raw = await self._request(
            self.gen_sid_payload("call", ["vpn-client", "get_status"], self.sid)
        )
        vpn_status = (
            raw
            if isinstance(raw, VpnClientStatusResponse)
            else VpnClientStatusResponse.from_dict(raw)
        )
        return vpn_status.status_list

    async def wireguard_client_start(
        self, group_id: int, peer_or_tunnel_id: int
    ) -> EmptyResponse:
        """Starts a WireGuard client with the specified tunnel ID."""
        return await self._wireguard_set_client_enabled(
            group_id, peer_or_tunnel_id, True
        )

    async def wireguard_client_stop(self, peer_or_tunnel_id: int) -> EmptyResponse:
        """Stops the WireGuard client with the specified tunnel ID."""
        # Pass -1 for group_id and peer_id as they are not needed to stop the client
        return await self._wireguard_set_client_enabled(-1, peer_or_tunnel_id, False)

    async def _wireguard_set_client_enabled(
        self, group_id: int, peer_or_tunnel_id: int, enabled: bool
    ) -> EmptyResponse:
        """Sets the WireGuard client enabled state."""
        if self._firmware_version is None:
            await self.router_info()
        assert self._firmware_version is not None

        # If version is 4.8 or greater use vpn-client otherwise use wg-client
        if self._firmware_version >= NEW_VPN_CLIENT_VERSION:
            tunnel_id = peer_or_tunnel_id
            return await self._request(
                self.gen_sid_payload(
                    "call",
                    [
                        "vpn-client",
                        "set_tunnel",
                        {"enabled": enabled, "tunnel_id": tunnel_id},
                    ],
                    self.sid,
                )
            )

        # Not version 4.8 or greater so use wg-client
        peer_id = peer_or_tunnel_id
        if enabled:
            return await self._request(
                self.gen_sid_payload(
                    "call",
                    [
                        "wg-client",
                        "start",
                        {"group_id": group_id, "peer_id": peer_id},
                    ],
                    self.sid,
                )
            )

        # Not enabled, call the stop method
        return await self._request(
            self.gen_sid_payload("call", ["wg-client", "stop"], self.sid)
        )

    async def _tailscale_get_config(self) -> TailscaleConfigResponse | Literal[False]:
        """Gets Tailscale configuration from router, returning False if unsupported."""
        try:
            raw = await self._request(
                self.gen_sid_payload("call", ["tailscale", "get_config"], self.sid)
            )
            return (
                raw
                if isinstance(raw, TailscaleConfigResponse)
                else TailscaleConfigResponse.from_dict(raw)
            )
        except APIClientError:
            return False

    async def _tailscale_set_config(
        self, config_updates: TailscaleSetConfigParams | dict[str, object]
    ) -> EmptyResponse:
        """Updates the Tailscale configuration with the provided updates."""
        current_config = await self._request(
            self.gen_sid_payload("call", ["tailscale", "get_config"], self.sid)
        )
        curr_dict = (
            current_config.to_dict()
            if isinstance(current_config, TailscaleConfigResponse)
            else dict(current_config)
        )
        new_config = curr_dict | dict(config_updates)
        return await self._request(
            self.gen_sid_payload(
                "call", ["tailscale", "set_config", new_config], self.sid
            )
        )

    async def _tailscale_status(self) -> TailscaleStatusResponse | list[object]:
        """Returns Tailscale status dictionary, or empty list if unconfigured/disconnected."""
        raw = await self._request(
            self.gen_sid_payload("call", ["tailscale", "get_status"], self.sid)
        )
        if isinstance(raw, dict):
            return TailscaleStatusResponse.from_dict(raw)
        return raw

    async def tailscale_connection_state(self) -> TailscaleConnection:
        """Retrieves the Tailscale connection state."""
        status_resp = await self._tailscale_status()
        if not isinstance(status_resp, Mapping) or not status_resp:
            return TailscaleConnection.DISCONNECTED
        status_code = status_resp.get("status", 0)
        try:
            return TailscaleConnection(status_code)
        except ValueError:
            return TailscaleConnection.DISCONNECTED

    async def tailscale_configured(self) -> bool:
        """Checks if Tailscale is configured on the router."""
        try:
            status = await self._tailscale_status()
            if isinstance(status, Mapping) and status:
                return True
        except APIClientError:
            return False
        if await self._tailscale_get_config() is False:
            return False
        return True

    async def tailscale_start(self, depth: int = 0) -> Literal[True]:
        """Starts Tailscale on the router. Uses recursion to handle connection attempts."""
        if depth > 15:
            raise ConnectionError(
                "Tailscale attempted to connect 15 times with no success"
            )
        response = await self._tailscale_status()
        if isinstance(response, list):
            if response == []:
                await self._tailscale_set_config({"enabled": True})
                if depth > 0:
                    await asyncio.sleep(0.5)
                depth += 1
                return await self.tailscale_start(depth)
            raise ConnectionError("Unexpected list response from tailscale status")
        status: int = response.get("status", 0) if isinstance(response, Mapping) else 0
        if status == 3:
            return True
        if status == 4:
            await asyncio.sleep(3)
            status_resp = await self._tailscale_status()
            if isinstance(status_resp, Mapping):
                status = status_resp.get("status", 0)
            if status != 3:
                raise ConnectionError(
                    f"Did not try to start tailscale as device reported 'Connecting' and then 3 seconds later {TailscaleConnection(status).name}"
                )
            return True
        if status in [1, 2]:
            raise ConnectionAbortedError(
                f"Connection not attempted as authorisation is not complete, due to {TailscaleConnection(status).name}"
            )

        raise ConnectionError(f"Unknown connection status: {status}")

    async def tailscale_stop(self, depth: int = 0) -> Literal[True]:
        """Stops Tailscale on the router. Uses recursion to handle disconnection attempts."""
        if depth > 10:
            raise ConnectionError(
                "Tailscale attempted to disconnect 10 times with no success"
            )
        response = await self._tailscale_status()
        if isinstance(response, list):
            if response == []:
                return True
            raise ConnectionError("Unexpected list response from tailscale status")
        status: int = response.get("status", 0) if isinstance(response, Mapping) else 0
        if status in [3, 4]:
            await self._tailscale_set_config({"enabled": False})
            if depth > 0:
                await asyncio.sleep(0.3)
            depth += 1
            return await self.tailscale_stop(depth)
        if status in [1, 2]:
            raise ConnectionAbortedError(
                f"Disconnection not attempted as tailscale authorisation is not complete, due to {TailscaleConnection(status).name}. Therefore tailscale was already not connected"
            )
        raise ConnectionError(f"Unknown connection status: {status}")

    @property
    def logged_in(self) -> bool:
        """Returns whether the client is logged in."""
        return self._logged_in


__all__ = ["GLinet", "NEW_VPN_CLIENT_VERSION"]
