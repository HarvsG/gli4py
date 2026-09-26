"""Tests verifying runtime dataclass models and strict type enforcement with mashumaro."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from mashumaro.exceptions import InvalidFieldValue
from semver import Version

from gli4py.glinet import GLinet
from gli4py.models import (
    ChallengeResponse,
    ClientEntry,
    ClientsResponse,
    EdgeRouterStatusResponse,
    LoginResponse,
    RouterStatusResponse,
    SystemInfoResponse,
    SystemLoadResponse,
    TailscaleStatusResponse,
    WifiConfigResponse,
    WireguardClientListItem,
    WireguardStatusItem,
)


def test_system_info_model_runtime_types() -> None:
    """Test that SystemInfoResponse validates types at runtime."""
    valid_data = {
        "mac": "94:83:C4:00:11:22",
        "model": "mt6000",
        "firmware_version": "4.8.2",
        "cpu_num": 4,
    }
    model = SystemInfoResponse.from_dict(valid_data)
    assert isinstance(model, SystemInfoResponse)
    assert model.model == "mt6000"
    assert model.cpu_num == 4
    assert model.mac == "94:83:C4:00:11:22"

    # Attribute access and Mapping access both work
    assert model["model"] == "mt6000"
    assert model.get("model") == "mt6000"
    assert "model" in model

    # Reject unexpected types at runtime
    invalid_data = {
        "mac": "94:83:C4:00:11:22",
        "cpu_num": "not_an_int",
    }
    with pytest.raises(InvalidFieldValue):
        SystemInfoResponse.from_dict(invalid_data)


def test_client_entry_alias_mapping() -> None:
    """Test ClientEntry handles JSON alias 'class' -> client_class and dict-like access."""
    data = {
        "mac": "AA:BB:CC:DD:EE:FF",
        "ip": "192.168.1.100",
        "class": "workstation",
        "online": True,
    }
    client = ClientEntry.from_dict(data)
    assert isinstance(client, ClientEntry)
    assert client.client_class == "workstation"

    # Both alias and field name are accessible via mapping
    assert client["class"] == "workstation"
    assert client["client_class"] == "workstation"
    assert client.get("class") == "workstation"
    assert "class" in client
    assert "client_class" in client

    # Serialization preserves alias
    assert client.to_dict()["class"] == "workstation"
    assert dict(client)["class"] == "workstation"


def test_challenge_response_alias() -> None:
    """Test ChallengeResponse handles hyphenated 'hash-method' key."""
    data = {
        "alg": 1,
        "salt": "testsalt",
        "nonce": "testnonce",
        "hash-method": "sha256",
    }
    resp = ChallengeResponse.from_dict(data)
    assert resp.alg == 1
    assert resp.hash_method == "sha256"
    assert resp["hash-method"] == "sha256"
    assert resp["hash_method"] == "sha256"
    assert "hash-method" in resp
    assert resp.to_dict()["hash-method"] == "sha256"


def test_model_dict_unpacking_and_equality() -> None:
    """Test that BaseModel supports dictionary unpacking and mapping equality."""
    load = SystemLoadResponse(
        memory_free=1000,
        memory_buff_cache=2000,
        memory_total=4000,
        load_average=[0.1, 0.2, 0.3],
    )
    unpacked = {**load}
    assert unpacked["memory_free"] == 1000
    assert unpacked["load_average"] == [0.1, 0.2, 0.3]

    # Mapping equality
    assert load == {
        "memory_free": 1000,
        "memory_buff_cache": 2000,
        "memory_total": 4000,
        "load_average": [0.1, 0.2, 0.3],
    }


@pytest.mark.asyncio
async def test_glinet_methods_return_dataclass_instances() -> None:
    """Test that GLinet client methods return strictly-typed dataclass instances."""
    client = GLinet(sid="test_session")

    # 1. router_info
    fake_info = {
        "model": "mt6000",
        "firmware_version": "4.8.2",
        "mac": "94:83:C4:00:11:22",
    }
    with patch.object(client, "_request", new=AsyncMock(return_value=fake_info)):
        info = await client.router_info()
        assert isinstance(info, SystemInfoResponse)
        assert info.model == "mt6000"
        assert info.firmware_version == "4.8.2"

    # 2. connected_to_internet
    fake_edge = {
        "detected": 1,
        "dns": ["1.1.1.1"],
        "gateway": "192.168.1.1",
        "ip": "192.168.1.50",
        "netmask": "255.255.255.0",
        "valid": True,
    }
    with patch.object(client, "_request", new=AsyncMock(return_value=fake_edge)):
        edge = await client.connected_to_internet()
        assert isinstance(edge, EdgeRouterStatusResponse)
        assert edge.valid is True
        assert edge.gateway == "192.168.1.1"

    # 3. list_all_clients
    fake_clients = {
        "clients": [{"mac": "11:22:33:44:55:66", "ip": "192.168.1.10", "online": True}]
    }
    with patch.object(client, "_request", new=AsyncMock(return_value=fake_clients)):
        all_clients = await client.list_all_clients()
        assert isinstance(all_clients, ClientsResponse)
        assert len(all_clients.clients) == 1
        assert isinstance(all_clients.clients[0], ClientEntry)
        assert all_clients.clients[0].mac == "11:22:33:44:55:66"

    # 4. connected_clients
    with patch.object(client, "_request", new=AsyncMock(return_value=fake_clients)):
        clients = await client.connected_clients()
        assert "11:22:33:44:55:66" in clients
        assert isinstance(clients["11:22:33:44:55:66"], ClientEntry)

    # 5. _challenge and _get_sid
    fake_challenge = {"alg": 1, "salt": "s", "nonce": "n"}
    with patch.object(client, "_request", new=AsyncMock(return_value=fake_challenge)):
        ch = await client._challenge("root")
        assert isinstance(ch, ChallengeResponse)
        assert ch.alg == 1

    fake_login = {"sid": "new_sid_123"}
    with patch.object(client, "_request", new=AsyncMock(return_value=fake_login)):
        lg = await client._get_sid("root", "hsh")
        assert isinstance(lg, LoginResponse)
        assert lg.sid == "new_sid_123"

    # 6. router_get_status
    fake_status = {
        "network": [{"online": True, "up": True, "interface": "wan"}],
        "wifi": [
            {
                "ssid": "MySSID",
                "passwd": "pass",
                "guest": False,
                "up": True,
                "channel": 1,
                "band": "2.4G",
                "name": "wlan0",
            }
        ],
        "service": [{"name": "vpn", "status": 1}],
        "client": [{"cable_total": 2, "wireless_total": 3}],
        "system": {"uptime": 1234.5},
    }
    with patch.object(client, "_request", new=AsyncMock(return_value=fake_status)):
        status = await client.router_get_status()
        assert isinstance(status, RouterStatusResponse)
        assert status.network[0].online is True
        assert status.wifi[0].passwd is None  # verified redacted

    # 7. wireguard_client_state
    fake_wg_status = {
        "domain": "vpn.example.com",
        "enabled": True,
        "group_id": 1,
        "name": "peer1",
        "peer_id": 10,
    }
    client._firmware_version = Version(4, 3, 0)
    with patch.object(client, "_request", new=AsyncMock(return_value=fake_wg_status)):
        wg_items = await client.wireguard_client_state()
        assert isinstance(wg_items[0], WireguardStatusItem)
        assert wg_items[0].name == "peer1"

    # 8. wireguard_client_list
    fake_wg_configs = {
        "config_list": [
            {
                "group_name": "Proton",
                "group_id": 1,
                "peers": [{"name": "node1", "peer_id": 5}],
            }
        ]
    }
    with patch.object(client, "_request", new=AsyncMock(return_value=fake_wg_configs)):
        wg_list = await client.wireguard_client_list()
        assert isinstance(wg_list[0], WireguardClientListItem)
        assert wg_list[0].name == "Proton/node1"

    # 9. _tailscale_status
    fake_ts = {"address_v4": "100.64.0.1", "status": 3, "login_name": "user"}
    with patch.object(client, "_request", new=AsyncMock(return_value=fake_ts)):
        ts = await client._tailscale_status()
        assert isinstance(ts, TailscaleStatusResponse)
        assert ts.address_v4 == "100.64.0.1"

    # 10. _wifi_config_get
    fake_wifi = {
        "dfs_support": True,
        "res": [
            {
                "band": "2.4G",
                "device": "radio0",
                "ifaces": [{"name": "wifi2g", "ssid": "MyNet"}],
            }
        ],
    }
    with patch.object(client, "_request", new=AsyncMock(return_value=fake_wifi)):
        wifi_cfg = await client._wifi_config_get()
        assert isinstance(wifi_cfg, WifiConfigResponse)
        assert wifi_cfg.dfs_support is True


@pytest.mark.asyncio
async def test_unexpected_response_structure_rejection() -> None:
    """Test that unexpected responses at runtime are not silently passed to users."""
    client = GLinet(sid="test_session")

    # API returns unexpected string instead of int for detected
    bad_edge_response = {
        "detected": "unexpected_string",
        "dns": ["1.1.1.1"],
        "gateway": "192.168.1.1",
        "ip": "192.168.1.50",
        "netmask": "255.255.255.0",
        "valid": True,
    }
    with patch.object(
        client, "_request", new=AsyncMock(return_value=bad_edge_response)
    ):
        with pytest.raises(InvalidFieldValue):
            await client.connected_to_internet()

    # API returns int instead of list for clients
    bad_clients_response = {"clients": 12345}
    with patch.object(
        client, "_request", new=AsyncMock(return_value=bad_clients_response)
    ):
        with pytest.raises(InvalidFieldValue):
            await client.list_all_clients()
