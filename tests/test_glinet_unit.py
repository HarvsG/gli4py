"""Offline unit tests for GLinet client — no router required.

These tests mock the HTTP layer to exercise all code paths and branches
in glinet.py, targeting the logic that is impractical to cover with live
tests (e.g., old firmware paths, all hash algorithms, error branches).
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from semver import Version

from gli4py.error_handling import APIClientError, AuthenticationError
from gli4py.enums import TailscaleConnection
from gli4py.glinet import GLinet, NEW_VPN_CLIENT_VERSION


# ═══════════════════════════════════════════════════════════════════
# Payload generation (pure-logic, no I/O)
# ═══════════════════════════════════════════════════════════════════


class TestPayloadGeneration:
    """Tests for static payload helper methods."""

    def test_gen_sid_payload(self) -> None:
        payload = GLinet.gen_sid_payload("call", ["system", "get_info"], sid="abc123")
        assert payload == {
            "method": "call",
            "jsonrpc": "2.0",
            "params": ["abc123", "system", "get_info"],
            "id": 0,
        }

    def test_gen_sid_payload_none_sid(self) -> None:
        payload = GLinet.gen_sid_payload("call", ["system", "get_info"], sid=None)
        assert payload["params"][0] is None

    def test_gen_sid_payload_mutates_params_list(self) -> None:
        """gen_sid_payload inserts sid at index 0 of the params list."""
        params = ["wifi", "get_config"]
        GLinet.gen_sid_payload("call", params, sid="sid1")
        assert params[0] == "sid1"

    def test_gen_no_auth_payload(self) -> None:
        payload = GLinet.gen_no_auth_payload("challenge", {"username": "root"})
        assert payload == {
            "method": "challenge",
            "jsonrpc": "2.0",
            "params": {"username": "root"},
            "id": 0,
        }


# ═══════════════════════════════════════════════════════════════════
# Constructor & properties
# ═══════════════════════════════════════════════════════════════════


class TestConstructor:
    """Tests for GLinet initialization and properties."""

    def test_default_init(self) -> None:
        client = GLinet(base_url="http://test/rpc")
        assert client.sid is None
        assert client.logged_in is False

    def test_init_with_sid(self) -> None:
        client = GLinet(sid="existing_session", base_url="http://test/rpc")
        assert client.sid == "existing_session"
        assert client.logged_in is True

    def test_logged_in_property(self) -> None:
        client = GLinet(base_url="http://test/rpc")
        assert client.logged_in is False
        client._logged_in = True
        assert client.logged_in is True


# ═══════════════════════════════════════════════════════════════════
# Login & Authentication
# ═══════════════════════════════════════════════════════════════════


class TestLogin:
    """Tests for login flow covering all hash algorithm branches."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "alg,hash_method",
        [
            pytest.param(1, "md5", id="md5-cipher-md5-hash"),
            pytest.param(5, "md5", id="sha256-cipher-md5-hash"),
            pytest.param(6, "md5", id="sha512-cipher-md5-hash"),
            pytest.param(1, "sha256", id="md5-cipher-sha256-hash"),
            pytest.param(5, "sha256", id="sha256-cipher-sha256-hash"),
            pytest.param(6, "sha256", id="sha512-cipher-sha256-hash"),
            pytest.param(1, "sha512", id="md5-cipher-sha512-hash"),
            pytest.param(5, "sha512", id="sha256-cipher-sha512-hash"),
            pytest.param(6, "sha512", id="sha512-cipher-sha512-hash"),
        ],
    )
    async def test_login_all_algorithm_combos(self, alg: int, hash_method: str) -> None:
        """Every combination of cipher algorithm × hash method succeeds."""
        client = GLinet(base_url="http://test/rpc")

        challenge_response = {
            "alg": alg,
            "salt": "saltsalt",
            "nonce": "nonce123",
            "hash-method": hash_method,
        }
        login_response = {"sid": "new_session_id"}

        client._request = AsyncMock(side_effect=[challenge_response, login_response])

        await client.login("root", "password")
        assert client.logged_in is True
        assert client.sid == "new_session_id"

    @pytest.mark.asyncio
    async def test_login_default_hash_method(self) -> None:
        """When hash-method is missing from challenge, defaults to md5."""
        client = GLinet(base_url="http://test/rpc")

        challenge_response = {
            "alg": 1,
            "salt": "saltsalt",
            "nonce": "nonce123",
            # no "hash-method" key — should default to md5
        }
        login_response = {"sid": "session_default_hash"}

        client._request = AsyncMock(side_effect=[challenge_response, login_response])

        await client.login("root", "password")
        assert client.logged_in is True

    @pytest.mark.asyncio
    async def test_login_unsupported_cipher_alg(self) -> None:
        """Unsupported cipher algorithm raises KeyError (wrapping ValueError)."""
        client = GLinet(base_url="http://test/rpc")

        challenge_response = {
            "alg": 99,
            "salt": "saltsalt",
            "nonce": "nonce123",
            "hash-method": "md5",
        }
        client._request = AsyncMock(return_value=challenge_response)

        with pytest.raises(KeyError, match="Parameter Exception"):
            await client.login("root", "password")

    @pytest.mark.asyncio
    async def test_login_unsupported_hash_method(self) -> None:
        """Unsupported hash method raises KeyError (wrapping ValueError)."""
        client = GLinet(base_url="http://test/rpc")

        challenge_response = {
            "alg": 1,
            "salt": "saltsalt",
            "nonce": "nonce123",
            "hash-method": "bcrypt",
        }
        client._request = AsyncMock(return_value=challenge_response)

        with pytest.raises(KeyError, match="Parameter Exception"):
            await client.login("root", "password")

    @pytest.mark.asyncio
    async def test_login_authentication_error(self) -> None:
        """AuthenticationError from _get_sid propagates correctly."""
        client = GLinet(base_url="http://test/rpc")

        challenge_response = {
            "alg": 1,
            "salt": "saltsalt",
            "nonce": "nonce123",
            "hash-method": "md5",
        }
        client._request = AsyncMock(
            side_effect=[challenge_response, AuthenticationError("Access denied")]
        )

        with pytest.raises(AuthenticationError):
            await client.login("root", "wrong_password")
        assert client.logged_in is False

    @pytest.mark.asyncio
    async def test_login_api_client_error(self) -> None:
        """Generic APIClientError during login is re-wrapped."""
        client = GLinet(base_url="http://test/rpc")

        challenge_response = {
            "alg": 1,
            "salt": "saltsalt",
            "nonce": "nonce123",
            "hash-method": "md5",
        }
        client._request = AsyncMock(
            side_effect=[challenge_response, APIClientError("Network error")]
        )

        with pytest.raises(APIClientError, match="unexpected error"):
            await client.login("root", "password")

    @pytest.mark.asyncio
    async def test_login_missing_sid_in_response(self) -> None:
        """Login response without 'sid' key does not set logged_in."""
        client = GLinet(base_url="http://test/rpc")

        challenge_response = {
            "alg": 1,
            "salt": "saltsalt",
            "nonce": "nonce123",
            "hash-method": "md5",
        }
        login_response = {"error": "something went wrong"}

        client._request = AsyncMock(side_effect=[challenge_response, login_response])

        await client.login("root", "password")
        assert client.logged_in is False


# ═══════════════════════════════════════════════════════════════════
# Router Reachability
# ═══════════════════════════════════════════════════════════════════


class TestRouterReachable:
    """Tests for router_reachable method."""

    @pytest.mark.asyncio
    async def test_reachable_true(self) -> None:
        client = GLinet(base_url="http://test/rpc")
        client._request = AsyncMock(return_value={"alg": 1, "salt": "s", "nonce": "n"})
        assert await client.router_reachable() is True

    @pytest.mark.asyncio
    async def test_reachable_false_on_error(self) -> None:
        client = GLinet(base_url="http://test/rpc")
        client._request = AsyncMock(side_effect=APIClientError("unreachable"))
        assert await client.router_reachable() is False

    @pytest.mark.asyncio
    async def test_reachable_false_on_empty(self) -> None:
        """When challenge returns falsy value, reachable is False."""
        client = GLinet(base_url="http://test/rpc")
        client._request = AsyncMock(return_value={})
        assert await client.router_reachable() is False


# ═══════════════════════════════════════════════════════════════════
# Router Info
# ═══════════════════════════════════════════════════════════════════


class TestRouterInfo:
    """Tests for router_info and firmware version parsing."""

    @pytest.mark.asyncio
    async def test_router_info_sets_firmware_version(self) -> None:
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(
            return_value={
                "model": "mt6000",
                "firmware_version": "4.8.0",
                "mac": "AA:BB:CC:DD:EE:FF",
            }
        )
        result = await client.router_info()
        assert result["model"] == "mt6000"
        assert client._firmware_version == Version.parse("4.8.0")

    @pytest.mark.asyncio
    async def test_router_info_missing_firmware_version(self) -> None:
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(
            return_value={"model": "mt6000", "mac": "AA:BB:CC:DD:EE:FF"}
        )
        with pytest.raises(ValueError, match="No firmware version"):
            await client.router_info()


# ═══════════════════════════════════════════════════════════════════
# Router Status (WiFi password redaction)
# ═══════════════════════════════════════════════════════════════════


class TestRouterGetStatus:
    """Tests for router_get_status wifi password redaction."""

    @pytest.mark.asyncio
    async def test_redacts_wifi_passwords(self) -> None:
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(
            return_value={
                "wifi": [
                    {"ssid": "MyWifi", "passwd": "secret123"},
                    {"ssid": "Guest", "passwd": "guest456"},
                ],
                "system": {"uptime": 100},
            }
        )
        result = await client.router_get_status()
        for wifi in result["wifi"]:
            assert wifi["passwd"] is None

    @pytest.mark.asyncio
    async def test_no_wifi_key(self) -> None:
        """Status response without 'wifi' key doesn't error."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(return_value={"system": {"uptime": 100}})
        result = await client.router_get_status()
        assert "wifi" not in result


# ═══════════════════════════════════════════════════════════════════
# Connected Clients
# ═══════════════════════════════════════════════════════════════════


class TestConnectedClients:
    """Tests for connected_clients filtering."""

    @pytest.mark.asyncio
    async def test_filters_offline_clients(self) -> None:
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(
            return_value={
                "clients": [
                    {"mac": "AA:BB:CC:DD:EE:01", "online": True, "name": "Phone"},
                    {"mac": "AA:BB:CC:DD:EE:02", "online": False, "name": "Laptop"},
                    {"mac": "AA:BB:CC:DD:EE:03", "online": True, "name": "Tablet"},
                ]
            }
        )
        result = await client.connected_clients()
        assert len(result) == 2
        assert "AA:BB:CC:DD:EE:01" in result
        assert "AA:BB:CC:DD:EE:03" in result
        assert "AA:BB:CC:DD:EE:02" not in result


# ═══════════════════════════════════════════════════════════════════
# WiFi Interfaces
# ═══════════════════════════════════════════════════════════════════


class TestWifiIfaces:
    """Tests for wifi_ifaces_get and wifi_iface_set_enabled."""

    @pytest.mark.asyncio
    async def test_wifi_ifaces_get_redacts_keys(self) -> None:
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(
            return_value={
                "res": [
                    {
                        "ifaces": [
                            {
                                "name": "wifi2g",
                                "enabled": True,
                                "ssid": "MyWifi-2G",
                                "key": "secret",
                            },
                            {
                                "name": "wifi5g",
                                "enabled": True,
                                "ssid": "MyWifi-5G",
                                "key": "secret2",
                            },
                        ]
                    }
                ]
            }
        )
        result = await client.wifi_ifaces_get(redact_keys=True)
        assert result["wifi2g"]["key"] is None
        assert result["wifi5g"]["key"] is None

    @pytest.mark.asyncio
    async def test_wifi_ifaces_get_unredacted(self) -> None:
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(
            return_value={
                "res": [
                    {
                        "ifaces": [
                            {
                                "name": "wifi2g",
                                "enabled": True,
                                "ssid": "MyWifi-2G",
                                "key": "secret",
                            },
                        ]
                    }
                ]
            }
        )
        result = await client.wifi_ifaces_get(redact_keys=False)
        assert result["wifi2g"]["key"] == "secret"

    @pytest.mark.asyncio
    async def test_wifi_iface_set_enabled_valid(self) -> None:
        client = GLinet(sid="s", base_url="http://test/rpc")
        # First call: _wifi_config_get (via wifi_ifaces_get)
        # Second call: _wifi_config_set
        client._request = AsyncMock(
            side_effect=[
                {
                    "res": [
                        {
                            "ifaces": [
                                {
                                    "name": "wifi2g",
                                    "enabled": True,
                                    "ssid": "MyWifi-2G",
                                    "key": "s",
                                },
                            ]
                        }
                    ]
                },
                {},  # set_config response
            ]
        )
        result = await client.wifi_iface_set_enabled("wifi2g", False)
        assert result == {}

    @pytest.mark.asyncio
    async def test_wifi_iface_set_enabled_invalid_name(self) -> None:
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(
            return_value={
                "res": [
                    {
                        "ifaces": [
                            {"name": "wifi2g", "enabled": True, "ssid": "X", "key": "s"}
                        ]
                    }
                ]
            }
        )
        with pytest.raises(ValueError, match="iface_name does not exist"):
            await client.wifi_iface_set_enabled("nonexistent", True)


# ═══════════════════════════════════════════════════════════════════
# WireGuard Client
# ═══════════════════════════════════════════════════════════════════


class TestWireguardClient:
    """Tests for WireGuard client operations."""

    @pytest.mark.asyncio
    async def test_wireguard_client_list(self) -> None:
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(
            return_value={
                "config_list": [
                    {
                        "group_name": "Group1",
                        "group_id": 100,
                        "peers": [
                            {"name": "Peer1", "peer_id": 1},
                            {"name": "Peer2", "peer_id": 2},
                        ],
                    },
                    {
                        "group_name": "EmptyGroup",
                        "group_id": 200,
                        "peers": [],
                    },
                ]
            }
        )
        result = await client.wireguard_client_list()
        assert len(result) == 2
        assert result[0]["name"] == "Group1/Peer1"
        assert result[1]["name"] == "Group1/Peer2"

    @pytest.mark.asyncio
    async def test_wireguard_client_state_new_firmware(self) -> None:
        """Firmware >= 4.8 uses vpn-client and returns status_list."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._firmware_version = Version(4, 8, 0)

        client._request = AsyncMock(
            return_value={"status_list": [{"enabled": True, "name": "VPN1"}]}
        )
        result = await client.wireguard_client_state()
        assert len(result) == 1
        assert result[0]["enabled"] is True

    @pytest.mark.asyncio
    async def test_wireguard_client_state_old_firmware(self) -> None:
        """Firmware < 4.8 uses wg-client and wraps single object in list."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._firmware_version = Version(4, 3, 0)

        client._request = AsyncMock(
            return_value={"status": 0, "name": "VPN1", "rx_bytes": 0}
        )
        result = await client.wireguard_client_state()
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["status"] == 0

    @pytest.mark.asyncio
    async def test_wireguard_client_state_fetches_firmware_if_missing(self) -> None:
        """If _firmware_version is None, calls router_info first."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        assert client._firmware_version is None

        # First call: router_info, second call: get_status
        client._request = AsyncMock(
            side_effect=[
                {
                    "model": "mt6000",
                    "firmware_version": "4.8.0",
                    "mac": "AA:BB:CC:DD:EE:FF",
                },
                {"status_list": [{"enabled": False}]},
            ]
        )
        result = await client.wireguard_client_state()
        assert client._firmware_version == Version(4, 8, 0)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_wireguard_client_state_empty_status_list(self) -> None:
        """New firmware with empty status_list returns empty list."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._firmware_version = Version(4, 8, 0)

        client._request = AsyncMock(return_value={"status_list": []})
        result = await client.wireguard_client_state()
        assert result == []

    @pytest.mark.asyncio
    async def test_wireguard_start_new_firmware(self) -> None:
        """Start uses vpn-client/set_tunnel on firmware >= 4.8."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._firmware_version = Version(4, 8, 0)

        client._request = AsyncMock(return_value={"tunnel_id": 42})
        result = await client.wireguard_client_start(group_id=1, peer_or_tunnel_id=42)
        assert result["tunnel_id"] == 42
        call_args = client._request.call_args[0][0]
        assert "vpn-client" in call_args["params"]

    @pytest.mark.asyncio
    async def test_wireguard_start_old_firmware(self) -> None:
        """Start uses wg-client/start on firmware < 4.8."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._firmware_version = Version(4, 3, 0)

        client._request = AsyncMock(return_value={})
        result = await client.wireguard_client_start(group_id=100, peer_or_tunnel_id=5)
        call_args = client._request.call_args[0][0]
        assert "wg-client" in call_args["params"]
        assert {"group_id": 100, "peer_id": 5} in call_args["params"]

    @pytest.mark.asyncio
    async def test_wireguard_stop_new_firmware(self) -> None:
        """Stop uses vpn-client/set_tunnel with enabled=False on firmware >= 4.8."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._firmware_version = Version(4, 8, 0)

        client._request = AsyncMock(return_value={"tunnel_id": 42})
        result = await client.wireguard_client_stop(peer_or_tunnel_id=42)
        call_args = client._request.call_args[0][0]
        assert "vpn-client" in call_args["params"]
        assert {"enabled": False, "tunnel_id": 42} in call_args["params"]

    @pytest.mark.asyncio
    async def test_wireguard_stop_old_firmware(self) -> None:
        """Stop uses wg-client/stop on firmware < 4.8."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._firmware_version = Version(4, 3, 0)

        client._request = AsyncMock(return_value={})
        result = await client.wireguard_client_stop(peer_or_tunnel_id=5)
        call_args = client._request.call_args[0][0]
        assert "wg-client" in call_args["params"]
        assert "stop" in call_args["params"]

    @pytest.mark.asyncio
    async def test_wireguard_set_client_fetches_firmware_if_missing(self) -> None:
        """_wireguard_set_client_enabled fetches firmware version if None."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        assert client._firmware_version is None

        client._request = AsyncMock(
            side_effect=[
                {
                    "model": "mt6000",
                    "firmware_version": "4.3.0",
                    "mac": "AA:BB:CC:DD:EE:FF",
                },
                {},  # start response
            ]
        )
        await client.wireguard_client_start(group_id=1, peer_or_tunnel_id=1)
        assert client._firmware_version == Version(4, 3, 0)


# ═══════════════════════════════════════════════════════════════════
# Tailscale
# ═══════════════════════════════════════════════════════════════════


class TestTailscale:
    """Tests for Tailscale operations."""

    @pytest.mark.asyncio
    async def test_tailscale_get_config_success(self) -> None:
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(
            return_value={"enabled": True, "lan_enabled": True, "wan_enabled": False}
        )
        result = await client._tailscale_get_config()
        assert result["enabled"] is True

    @pytest.mark.asyncio
    async def test_tailscale_get_config_not_available(self) -> None:
        """Returns False when tailscale is not available."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(side_effect=APIClientError("not available"))
        result = await client._tailscale_get_config()
        assert result is False

    @pytest.mark.asyncio
    async def test_tailscale_set_config(self) -> None:
        """set_config merges updates with current config."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(
            side_effect=[
                {"enabled": False, "lan_enabled": True},  # get_config
                {},  # set_config
            ]
        )
        result = await client._tailscale_set_config({"enabled": True})
        # Verify the merged config was sent
        set_call = client._request.call_args_list[1]
        payload = set_call[0][0]
        config_param = payload["params"][-1]
        assert config_param["enabled"] is True
        assert config_param["lan_enabled"] is True

    @pytest.mark.asyncio
    async def test_tailscale_connection_state_connected(self) -> None:
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(
            return_value={"status": 3, "address_v4": "100.1.2.3"}
        )
        result = await client.tailscale_connection_state()
        assert result == TailscaleConnection.CONNECTED

    @pytest.mark.asyncio
    async def test_tailscale_connection_state_disconnected(self) -> None:
        """Empty list means disconnected."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(return_value=[])
        result = await client.tailscale_connection_state()
        assert result == TailscaleConnection.DISCONNECTED

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "status,expected",
        [
            pytest.param(1, TailscaleConnection.LOGIN_REQUIRED, id="login-required"),
            pytest.param(
                2, TailscaleConnection.AUTHORIZATION_REQUIRED, id="auth-required"
            ),
            pytest.param(4, TailscaleConnection.CONNECTING, id="connecting"),
        ],
    )
    async def test_tailscale_connection_state_variants(
        self, status: int, expected: TailscaleConnection
    ) -> None:
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(return_value={"status": status})
        result = await client.tailscale_connection_state()
        assert result == expected

    @pytest.mark.asyncio
    async def test_tailscale_configured_true_via_status(self) -> None:
        """Configured returns True when status returns non-empty."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(return_value={"status": 3})
        result = await client.tailscale_configured()
        assert result is True

    @pytest.mark.asyncio
    async def test_tailscale_configured_true_via_config(self) -> None:
        """Configured returns True when status is [] but config is available."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(
            side_effect=[
                [],  # _tailscale_status returns empty
                {"enabled": False},  # _tailscale_get_config
            ]
        )
        result = await client.tailscale_configured()
        assert result is True

    @pytest.mark.asyncio
    async def test_tailscale_configured_false(self) -> None:
        """Configured returns False when status is [] and config errors."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(
            side_effect=[
                [],  # _tailscale_status returns empty
                APIClientError("not available"),  # _tailscale_get_config errors
            ]
        )
        result = await client.tailscale_configured()
        assert result is False

    @pytest.mark.asyncio
    async def test_tailscale_configured_status_errors(self) -> None:
        """Configured returns False when _tailscale_status raises APIClientError."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(side_effect=APIClientError("unavailable"))
        result = await client.tailscale_configured()
        assert result is False

    @pytest.mark.asyncio
    async def test_tailscale_start_already_connected(self) -> None:
        """Start returns True when already connected (status=3)."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(
            return_value={"status": 3, "address_v4": "100.1.2.3"}
        )
        result = await client.tailscale_start()
        assert result is True

    @pytest.mark.asyncio
    async def test_tailscale_start_from_disconnected(self) -> None:
        """Start from disconnected state enables tailscale and retries."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(
            side_effect=[
                [],  # _tailscale_status: disconnected
                {"enabled": False},  # _tailscale_set_config -> get_config
                {},  # _tailscale_set_config -> set_config
                {"status": 3},  # _tailscale_status on retry: connected
            ]
        )
        result = await client.tailscale_start()
        assert result is True

    @pytest.mark.asyncio
    async def test_tailscale_start_connecting_then_connected(self) -> None:
        """Start when status=4 (connecting) waits and then finds status=3."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(
            side_effect=[
                {"status": 4},  # First call: connecting
                {"status": 3},  # Second call after sleep: connected
            ]
        )
        with patch("gli4py.glinet.asyncio.sleep", new_callable=AsyncMock):
            result = await client.tailscale_start()
        assert result is True

    @pytest.mark.asyncio
    async def test_tailscale_start_connecting_then_fails(self) -> None:
        """Start when status=4 (connecting) then status != 3 raises ConnectionError."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(
            side_effect=[
                {"status": 4},  # connecting
                {"status": 0},  # disconnected after wait
            ]
        )
        with patch("gli4py.glinet.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(ConnectionError, match="Did not try to start"):
                await client.tailscale_start()

    @pytest.mark.asyncio
    async def test_tailscale_start_login_required(self) -> None:
        """Start with status=1 raises ConnectionAbortedError."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(return_value={"status": 1})
        with pytest.raises(ConnectionAbortedError, match="authorisation"):
            await client.tailscale_start()

    @pytest.mark.asyncio
    async def test_tailscale_start_auth_required(self) -> None:
        """Start with status=2 raises ConnectionAbortedError."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(return_value={"status": 2})
        with pytest.raises(ConnectionAbortedError, match="authorisation"):
            await client.tailscale_start()

    @pytest.mark.asyncio
    async def test_tailscale_start_unknown_status(self) -> None:
        """Start with unknown status raises ConnectionError."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(return_value={"status": 99})
        with pytest.raises(ConnectionError, match="Unknown connection status"):
            await client.tailscale_start()

    @pytest.mark.asyncio
    async def test_tailscale_start_max_depth(self) -> None:
        """Start exceeding max recursion depth raises ConnectionError."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        with pytest.raises(ConnectionError, match="10 times"):
            await client.tailscale_start(depth=11)

    @pytest.mark.asyncio
    async def test_tailscale_stop_already_disconnected(self) -> None:
        """Stop returns True when already disconnected."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(return_value=[])
        result = await client.tailscale_stop()
        assert result is True

    @pytest.mark.asyncio
    async def test_tailscale_stop_connected(self) -> None:
        """Stop from connected state disables tailscale and retries."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(
            side_effect=[
                {"status": 3},  # connected
                {"enabled": True},  # _tailscale_set_config -> get_config
                {},  # _tailscale_set_config -> set_config
                [],  # _tailscale_status on retry: disconnected
            ]
        )
        result = await client.tailscale_stop()
        assert result is True

    @pytest.mark.asyncio
    async def test_tailscale_stop_connecting(self) -> None:
        """Stop from connecting state (status=4) disables and retries."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(
            side_effect=[
                {"status": 4},  # connecting
                {"enabled": True},  # _tailscale_set_config -> get_config
                {},  # _tailscale_set_config -> set_config
                [],  # _tailscale_status on retry: disconnected
            ]
        )
        result = await client.tailscale_stop()
        assert result is True

    @pytest.mark.asyncio
    async def test_tailscale_stop_login_required(self) -> None:
        """Stop with status=1 raises ConnectionAbortedError."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(return_value={"status": 1})
        with pytest.raises(ConnectionAbortedError, match="Disconnection not attempted"):
            await client.tailscale_stop()

    @pytest.mark.asyncio
    async def test_tailscale_stop_auth_required(self) -> None:
        """Stop with status=2 raises ConnectionAbortedError."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(return_value={"status": 2})
        with pytest.raises(ConnectionAbortedError, match="Disconnection not attempted"):
            await client.tailscale_stop()

    @pytest.mark.asyncio
    async def test_tailscale_stop_max_depth(self) -> None:
        """Stop exceeding max recursion depth raises ConnectionError."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        with pytest.raises(ConnectionError, match="10 times"):
            await client.tailscale_stop(depth=11)


# ═══════════════════════════════════════════════════════════════════
# Ping
# ═══════════════════════════════════════════════════════════════════


class TestPing:
    """Tests for ping method."""

    @pytest.mark.asyncio
    async def test_ping_success(self) -> None:
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request_long_timeout = AsyncMock(return_value={"packets_received": 3})
        result = await client.ping("google.com")
        assert result is True

    @pytest.mark.asyncio
    async def test_ping_failure(self) -> None:
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request_long_timeout = AsyncMock(return_value=[])
        result = await client.ping("0.0.0.1")
        assert result is False


# ═══════════════════════════════════════════════════════════════════
# Simple delegate methods (modem, reboot, load, mac)
# ═══════════════════════════════════════════════════════════════════


class TestSimpleDelegates:
    """Tests for straightforward delegate methods."""

    @pytest.mark.asyncio
    async def test_modem_info(self) -> None:
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(return_value={"modem_id": 1, "name": "Quectel"})
        result = await client.modem_info()
        assert result["modem_id"] == 1

    @pytest.mark.asyncio
    async def test_modem_sim_info(self) -> None:
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(return_value={"imei": "12345"})
        result = await client.modem_sim_info()
        assert result["imei"] == "12345"

    @pytest.mark.asyncio
    async def test_modem_sim_signal(self) -> None:
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(return_value={"rssi": -70})
        result = await client.modem_sim_signal()
        assert result["rssi"] == -70

    @pytest.mark.asyncio
    async def test_router_get_load(self) -> None:
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(
            return_value={
                "load_average": [0.1, 0.2, 0.3],
                "memory_free": 100000,
                "memory_total": 200000,
            }
        )
        result = await client.router_get_load()
        assert "load_average" in result

    @pytest.mark.asyncio
    async def test_router_mac(self) -> None:
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(return_value={"factory_mac": "AA:BB:CC:DD:EE:FF"})
        result = await client.router_mac()
        assert result["factory_mac"] == "AA:BB:CC:DD:EE:FF"

    @pytest.mark.asyncio
    async def test_router_reboot(self) -> None:
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(return_value={})
        result = await client.router_reboot(delay=5)
        call_args = client._request.call_args[0][0]
        assert {"delay": 5} in call_args["params"]

    @pytest.mark.asyncio
    async def test_list_all_clients(self) -> None:
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(return_value={"clients": []})
        result = await client.list_all_clients()
        assert result == {"clients": []}

    @pytest.mark.asyncio
    async def test_list_static_clients(self) -> None:
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(return_value={"bind_list": []})
        result = await client.list_static_clients()
        assert result == {"bind_list": []}

    @pytest.mark.asyncio
    async def test_connected_to_internet(self) -> None:
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(
            return_value={"detected": 2, "ip": "1.2.3.4", "gateway": "1.2.3.1"}
        )
        result = await client.connected_to_internet()
        assert result["detected"] == 2


# ═══════════════════════════════════════════════════════════════════
# Error handling extras (fill gaps in error_handling coverage)
# ═══════════════════════════════════════════════════════════════════


class TestErrorHandlingExtras:
    """Additional tests for edge cases in raise_for_status."""

    @pytest.mark.asyncio
    async def test_raise_for_status_invalid_json(self) -> None:
        """Non-JSON response raises UnsuccessfulRequest."""
        from gli4py.error_handling import UnsuccessfulRequest, raise_for_status

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(side_effect=ValueError("Not JSON"))
        mock_resp.text = AsyncMock(return_value="<html>Error</html>")

        with pytest.raises(UnsuccessfulRequest, match="invalid JSON"):
            await raise_for_status(mock_resp)

    @pytest.mark.asyncio
    async def test_raise_for_status_no_error_no_result(self) -> None:
        """Response with neither 'result' nor 'error' raises ConnectionError."""
        from gli4py.error_handling import raise_for_status

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"unexpected": "data"})

        with pytest.raises(ConnectionError, match="Unexpected response"):
            await raise_for_status(mock_resp)

    @pytest.mark.asyncio
    async def test_raise_for_status_error_missing_message(self) -> None:
        """Error response without 'message' key gets 'null' message."""
        from gli4py.error_handling import NonZeroResponse, raise_for_status

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"error": {"code": -5}})

        with pytest.raises(NonZeroResponse, match="null"):
            await raise_for_status(mock_resp)

    @pytest.mark.asyncio
    async def test_raise_for_status_positive_error_code(self) -> None:
        """Positive error code falls through to return res dict."""
        from gli4py.error_handling import raise_for_status

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"error": {"code": 0, "message": "ok"}})

        result = await raise_for_status(mock_resp)
        assert "error" in result


# ═══════════════════════════════════════════════════════════════════
# Additional coverage for remaining uncovered lines
# ═══════════════════════════════════════════════════════════════════


class TestRemainingCoverage:
    """Tests targeting specific uncovered lines."""

    @pytest.mark.asyncio
    async def test_login_request_exception(self) -> None:
        """RequestException during login is re-raised."""
        from requests import exceptions as req_exceptions

        client = GLinet(base_url="http://test/rpc")
        client._request = AsyncMock(
            side_effect=req_exceptions.RequestException("Connection refused")
        )
        with pytest.raises(req_exceptions.RequestException):
            await client.login("root", "password")

    @pytest.mark.asyncio
    async def test_tailscale_start_with_depth_gt_zero(self) -> None:
        """Tailscale start with depth>0 hits the asyncio.sleep(0.3) branch."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(
            side_effect=[
                [],  # depth=1 _tailscale_status: disconnected
                {"enabled": False},  # _tailscale_set_config -> get_config
                {},  # _tailscale_set_config -> set_config
                {"status": 3},  # depth=2 _tailscale_status: connected
            ]
        )
        with patch("gli4py.glinet.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await client.tailscale_start(depth=1)
        assert result is True
        mock_sleep.assert_called_with(0.3)

    @pytest.mark.asyncio
    async def test_tailscale_stop_with_depth_gt_zero(self) -> None:
        """Tailscale stop with depth>0 hits the asyncio.sleep(0.3) branch."""
        client = GLinet(sid="s", base_url="http://test/rpc")
        client._request = AsyncMock(
            side_effect=[
                {"status": 3},  # depth=1 connected
                {"enabled": True},  # _tailscale_set_config -> get_config
                {},  # _tailscale_set_config -> set_config
                [],  # depth=2 _tailscale_status: disconnected
            ]
        )
        with patch("gli4py.glinet.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await client.tailscale_stop(depth=1)
        assert result is True
        mock_sleep.assert_called_with(0.3)
