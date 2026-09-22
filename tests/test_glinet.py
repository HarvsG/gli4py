"""Unit tests for the GLinet client logic and utilities."""
# pylint: disable=protected-access,duplicate-code

from unittest.mock import AsyncMock, patch

import pytest
from semver import Version

from gli4py.enums import TailscaleConnection
from gli4py.error_codes import ERROR_CODES
from gli4py.error_handling import APIClientError
from gli4py.glinet import NEW_VPN_CLIENT_VERSION, GLinet
from gli4py.helpers import normalize_url

# ─── Initialization & Properties ───


def test_client_init_defaults() -> None:
    """Test default GLinet initialization values."""
    client = GLinet()
    assert client.sid is None
    assert client.logged_in is False
    assert client._firmware_version is None


def test_client_init_with_sid() -> None:
    """Test GLinet initialization with an existing session ID."""
    client = GLinet(sid="active_session_abc123")
    assert client.sid == "active_session_abc123"
    assert client.logged_in is True


def test_new_vpn_client_version_constant() -> None:
    """Test the NEW_VPN_CLIENT_VERSION threshold constant."""
    assert NEW_VPN_CLIENT_VERSION == Version(4, 8, 0, 0)
    assert Version.parse("4.8.0") >= NEW_VPN_CLIENT_VERSION
    assert Version.parse("4.8.2") >= NEW_VPN_CLIENT_VERSION
    assert Version.parse("4.3.25") < NEW_VPN_CLIENT_VERSION


# ─── JSON-RPC Payload Generation ───


def test_gen_sid_payload() -> None:
    """Test payload generation with session ID insertion."""
    params = ["system", "get_info"]
    payload = GLinet.gen_sid_payload("call", params, sid="my_sid_456")
    assert payload == {
        "method": "call",
        "jsonrpc": "2.0",
        "params": ["my_sid_456", "system", "get_info"],
        "id": 0,
    }


def test_gen_no_auth_payload() -> None:
    """Test payload generation without session ID."""
    params = {"username": "root"}
    payload = GLinet.gen_no_auth_payload("challenge", params)
    assert payload == {
        "method": "challenge",
        "jsonrpc": "2.0",
        "params": {"username": "root"},
        "id": 0,
    }


# ─── Password Hashing Logic ───


@pytest.mark.parametrize(
    ("alg", "hash_method"),
    [
        (1, "md5"),
        (1, "sha256"),
        (1, "sha512"),
        (5, "md5"),
        (5, "sha256"),
        (5, "sha512"),
        (6, "md5"),
        (6, "sha256"),
        (6, "sha512"),
    ],
)
def test_compute_hash_valid_algorithms(alg: int, hash_method: str) -> None:
    """Test password hashing logic across supported algorithms and hash methods."""
    result = GLinet._compute_hash(
        alg=alg,
        salt="salt1234",
        nonce="testnonce123",
        hash_method=hash_method,
        username="root",
        password="secret_password",
    )
    assert isinstance(result, str)
    assert len(result) in (32, 64, 128)  # MD5=32, SHA256=64, SHA512=128 hex chars


def test_compute_hash_unsupported_cipher_algorithm() -> None:
    """Test that unsupported cipher algorithm raises ValueError."""
    with pytest.raises(
        ValueError,
        match="Router requested unsupported hashing algorithm for cipher password",
    ):
        GLinet._compute_hash(
            alg=99,
            salt="salt",
            nonce="nonce",
            hash_method="md5",
            username="root",
            password="pwd",
        )


def test_compute_hash_unsupported_hash_method() -> None:
    """Test that unsupported hash method raises ValueError."""
    with pytest.raises(
        ValueError, match="Router requested unsupported hashing algorithm for hash"
    ):
        GLinet._compute_hash(
            alg=1,
            salt="salt",
            nonce="nonce",
            hash_method="sha1",
            username="root",
            password="pwd",
        )


# ─── router_info Version Parsing & Validation ───


@pytest.mark.asyncio
async def test_router_info_success() -> None:
    """Test successful router_info sets firmware_version attribute."""
    client = GLinet(sid="test_sid")
    fake_info = {
        "model": "mt6000",
        "firmware_version": "4.8.2",
        "mac": "94:83:C4:00:11:22",
    }
    with patch.object(client, "_request", new=AsyncMock(return_value=fake_info)):
        result = await client.router_info()
        assert result == fake_info
        assert client._firmware_version == Version(4, 8, 2)


@pytest.mark.asyncio
async def test_router_info_missing_firmware_version() -> None:
    """Test that router_info raises ValueError if firmware_version is missing."""
    client = GLinet(sid="test_sid")
    fake_info = {"model": "mt6000", "mac": "94:83:C4:00:11:22"}
    with (
        patch.object(client, "_request", new=AsyncMock(return_value=fake_info)),
        pytest.raises(ValueError, match="No firmware version found in router info"),
    ):
        await client.router_info()


# ─── Wi-Fi Interface Parsing and Configuration ───


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("redact_keys", "expected_key"),
    [
        (True, None),
        (False, "my_wifi_password"),
    ],
)
async def test_wifi_ifaces_get(redact_keys: bool, expected_key: str | None) -> None:
    """Test Wi-Fi interfaces parsing and optional credential redaction."""
    client = GLinet(sid="test_sid")
    fake_wifi_config = {
        "res": [
            {
                "device": "radio0",
                "ifaces": [
                    {
                        "name": "wifi2g",
                        "ssid": "GL-Router-2G",
                        "enabled": True,
                        "key": "my_wifi_password",
                        "encryption": "sae-mixed",
                    }
                ],
            },
            {
                "device": "radio1",
                "ifaces": [
                    {
                        "name": "wifi5g",
                        "ssid": "GL-Router-5G",
                        "enabled": False,
                        "key": "my_wifi_password",
                        "encryption": "sae-mixed",
                    }
                ],
            },
        ]
    }
    with patch.object(
        client, "_wifi_config_get", new=AsyncMock(return_value=fake_wifi_config)
    ):
        ifaces = await client.wifi_ifaces_get(redact_keys=redact_keys)
        assert set(ifaces.keys()) == {"wifi2g", "wifi5g"}
        assert ifaces["wifi2g"]["ssid"] == "GL-Router-2G"
        assert ifaces["wifi2g"]["enabled"] is True
        assert ifaces["wifi2g"]["key"] == expected_key
        assert ifaces["wifi5g"]["ssid"] == "GL-Router-5G"
        assert ifaces["wifi5g"]["enabled"] is False
        assert ifaces["wifi5g"]["key"] == expected_key


@pytest.mark.asyncio
async def test_wifi_iface_set_enabled_success() -> None:
    """Test enabling a Wi-Fi interface when interface exists."""
    client = GLinet(sid="test_sid")
    mock_ifaces = {"wifi2g": {"name": "wifi2g", "enabled": False}}
    with (
        patch.object(
            client, "wifi_ifaces_get", new=AsyncMock(return_value=mock_ifaces)
        ),
        patch.object(
            client, "_wifi_config_set", new=AsyncMock(return_value={"success": True})
        ) as mock_set,
    ):
        result = await client.wifi_iface_set_enabled("wifi2g", True)
        assert result == {"success": True}
        mock_set.assert_awaited_once_with({"enabled": True, "iface_name": "wifi2g"})


@pytest.mark.asyncio
async def test_wifi_iface_set_enabled_nonexistent() -> None:
    """Test setting enabled state on a non-existent Wi-Fi interface raises ValueError."""
    client = GLinet(sid="test_sid")
    mock_ifaces = {"wifi2g": {"name": "wifi2g"}}
    with (
        patch.object(
            client, "wifi_ifaces_get", new=AsyncMock(return_value=mock_ifaces)
        ),
        pytest.raises(ValueError, match="iface_name does not exist"),
    ):
        await client.wifi_iface_set_enabled("wifi5g", True)


# ─── WireGuard Client Logic ───


@pytest.mark.asyncio
async def test_wireguard_client_list() -> None:
    """Test parsing WireGuard client configurations and skipping empty peer lists."""
    client = GLinet(sid="test_sid")
    mock_response = {
        "config_list": [
            {
                "group_name": "ProtonVPN",
                "group_id": 101,
                "peers": [
                    {"name": "NL-Free", "peer_id": 1},
                    {"name": "US-Free", "peer_id": 2},
                ],
            },
            {
                "group_name": "EmptyGroup",
                "group_id": 102,
                "peers": [],
            },
        ]
    }
    with patch.object(client, "_request", new=AsyncMock(return_value=mock_response)):
        configs = await client.wireguard_client_list()
        assert configs == [
            {"name": "ProtonVPN/NL-Free", "group_id": 101, "peer_id": 1},
            {"name": "ProtonVPN/US-Free", "group_id": 101, "peer_id": 2},
        ]


@pytest.mark.asyncio
async def test_wireguard_client_state_pre_4_8() -> None:
    """Test wireguard_client_state on firmware < 4.8 wraps single object in list."""
    client = GLinet(sid="test_sid")
    client._firmware_version = Version(4, 3, 25)
    single_status = {
        "name": "wg0",
        "peer_id": 1,
        "group_id": 10,
        "status": 1,
        "enabled": True,
    }
    with patch.object(client, "_request", new=AsyncMock(return_value=single_status)):
        state = await client.wireguard_client_state()
        assert state == [single_status]


@pytest.mark.asyncio
async def test_wireguard_client_state_post_4_8() -> None:
    """Test wireguard_client_state on firmware >= 4.8 extracts status_list."""
    client = GLinet(sid="test_sid")
    client._firmware_version = Version(4, 8, 2)
    status_list = [
        {"name": "wg1", "tunnel_id": 100, "enabled": True},
        {"name": "wg2", "tunnel_id": 200, "enabled": False},
    ]
    with patch.object(
        client, "_request", new=AsyncMock(return_value={"status_list": status_list})
    ):
        state = await client.wireguard_client_state()
        assert state == status_list


@pytest.mark.asyncio
async def test_wireguard_start_and_stop_legacy_firmware() -> None:
    """Test wireguard start/stop on firmware < 4.8 uses wg-client start/stop methods."""
    client = GLinet(sid="test_sid")
    client._firmware_version = Version(4, 3, 25)
    with patch.object(
        client, "_request", new=AsyncMock(return_value={"success": True})
    ) as mock_req:
        await client.wireguard_client_start(group_id=5, peer_or_tunnel_id=12)
        mock_req.assert_awaited_with(
            client.gen_sid_payload(
                "call",
                ["wg-client", "start", {"group_id": 5, "peer_id": 12}],
                client.sid,
            )
        )

        await client.wireguard_client_stop(peer_or_tunnel_id=12)
        mock_req.assert_awaited_with(
            client.gen_sid_payload("call", ["wg-client", "stop"], client.sid)
        )


@pytest.mark.asyncio
async def test_wireguard_start_and_stop_modern_firmware() -> None:
    """Test wireguard start/stop on firmware >= 4.8 uses vpn-client set_tunnel."""
    client = GLinet(sid="test_sid")
    client._firmware_version = Version(4, 8, 2)
    with patch.object(
        client, "_request", new=AsyncMock(return_value={"tunnel_id": 100})
    ) as mock_req:
        await client.wireguard_client_start(group_id=5, peer_or_tunnel_id=100)
        mock_req.assert_awaited_with(
            client.gen_sid_payload(
                "call",
                [
                    "vpn-client",
                    "set_tunnel",
                    {"enabled": True, "tunnel_id": 100},
                ],
                client.sid,
            )
        )

        await client.wireguard_client_stop(peer_or_tunnel_id=100)
        mock_req.assert_awaited_with(
            client.gen_sid_payload(
                "call",
                [
                    "vpn-client",
                    "set_tunnel",
                    {"enabled": False, "tunnel_id": 100},
                ],
                client.sid,
            )
        )


# ─── Client and Network Monitoring Logic ───


@pytest.mark.asyncio
async def test_connected_clients_filtering() -> None:
    """Test connected_clients filters only online clients keyed by MAC."""
    client = GLinet(sid="test_sid")
    mock_all_clients = {
        "clients": [
            {"mac": "AA:BB:CC:11:22:33", "name": "laptop", "online": True},
            {"mac": "AA:BB:CC:44:55:66", "name": "phone", "online": False},
            {"mac": "AA:BB:CC:77:88:99", "name": "tv", "online": True},
        ]
    }
    with patch.object(
        client, "list_all_clients", new=AsyncMock(return_value=mock_all_clients)
    ):
        online = await client.connected_clients()
        assert set(online.keys()) == {"AA:BB:CC:11:22:33", "AA:BB:CC:77:88:99"}
        assert online["AA:BB:CC:11:22:33"]["name"] == "laptop"
        assert online["AA:BB:CC:77:88:99"]["name"] == "tv"


@pytest.mark.asyncio
async def test_ping() -> None:
    """Test ping returns boolean based on whether stdout is empty list."""
    client = GLinet(sid="test_sid")
    with patch.object(
        client, "_request_long_timeout", new=AsyncMock(return_value=["bytes from..."])
    ):
        assert await client.ping("8.8.8.8") is True

    with patch.object(client, "_request_long_timeout", new=AsyncMock(return_value=[])):
        assert await client.ping("0.0.0.1") is False


# ─── Tailscale Logic ───


@pytest.mark.asyncio
async def test_tailscale_connection_state_mapping() -> None:
    """Test mapping of tailscale status integers and empty response to enum."""
    client = GLinet(sid="test_sid")

    # Empty response -> DISCONNECTED
    with patch.object(client, "_tailscale_status", new=AsyncMock(return_value=[])):
        assert (
            await client.tailscale_connection_state()
            == TailscaleConnection.DISCONNECTED
        )

    # Status 0 -> DISCONNECTED
    with patch.object(
        client, "_tailscale_status", new=AsyncMock(return_value={"status": 0})
    ):
        assert (
            await client.tailscale_connection_state()
            == TailscaleConnection.DISCONNECTED
        )

    # Status 1 -> LOGIN_REQUIRED
    with patch.object(
        client, "_tailscale_status", new=AsyncMock(return_value={"status": 1})
    ):
        assert (
            await client.tailscale_connection_state()
            == TailscaleConnection.LOGIN_REQUIRED
        )

    # Status 3 -> CONNECTED
    with patch.object(
        client, "_tailscale_status", new=AsyncMock(return_value={"status": 3})
    ):
        assert (
            await client.tailscale_connection_state() == TailscaleConnection.CONNECTED
        )


@pytest.mark.asyncio
async def test_tailscale_configured() -> None:
    """Test tailscale_configured detection under configured, unconfigured, and error states."""
    client = GLinet(sid="test_sid")

    # Configured and active
    with (
        patch.object(
            client, "_tailscale_status", new=AsyncMock(return_value={"status": 3})
        ),
        patch.object(
            client,
            "_tailscale_get_config",
            new=AsyncMock(return_value={"enabled": True}),
        ),
    ):
        assert await client.tailscale_configured() is True

    # Not active, but config exists
    with (
        patch.object(client, "_tailscale_status", new=AsyncMock(return_value=[])),
        patch.object(
            client,
            "_tailscale_get_config",
            new=AsyncMock(return_value={"enabled": False}),
        ),
    ):
        assert await client.tailscale_configured() is True

    # API error -> False
    with (
        patch.object(
            client,
            "_tailscale_status",
            new=AsyncMock(side_effect=APIClientError("fail")),
        ),
    ):
        assert await client.tailscale_configured() is False


# ─── Enums & Constants Verification ───


def test_tailscale_connection_enum_members() -> None:
    """Verify TailscaleConnection enum values."""
    assert TailscaleConnection.DISCONNECTED.value == 0
    assert TailscaleConnection.LOGIN_REQUIRED.value == 1
    assert TailscaleConnection.AUTHORIZATION_REQUIRED.value == 2
    assert TailscaleConnection.CONNECTED.value == 3
    assert TailscaleConnection.CONNECTING.value == 4


def test_error_codes_dictionary() -> None:
    """Verify ERROR_CODES mapping contains standard codes."""
    assert "-1" in ERROR_CODES
    assert "-32000" in ERROR_CODES
    assert "-32003" not in ERROR_CODES or isinstance(ERROR_CODES["-32003"], str)
    assert "-32601" in ERROR_CODES
    assert ERROR_CODES["-32601"] == "Method not found"


def test_helpers_normalize_url() -> None:
    """Verify helpers.normalize_url handles various input formats."""
    assert normalize_url("192.168.0.4") == "http://192.168.0.4/rpc"
    assert normalize_url("http://192.168.0.4/") == "http://192.168.0.4/rpc"
    assert normalize_url("https://192.168.0.4:8443") == "https://192.168.0.4:8443/rpc"
