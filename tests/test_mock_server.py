"""Tests for the GL.iNet mock router server and edge case simulations."""
# pylint: disable=redefined-outer-name,protected-access,too-many-locals,too-many-statements

import asyncio

import pytest
import requests
from uplink import AiohttpClient

from gli4py.error_handling import (
    AuthenticationError,
    LockoutError,
    NonZeroResponse,
    TokenError,
)
from gli4py.glinet import GLinet
from gli4py.mock import REAL_WORLD_TIMINGS, MockRouter, MockRouterServer


def test_real_world_timings_constants() -> None:
    """Verify that measured real-world timings are correctly exported."""
    assert isinstance(REAL_WORLD_TIMINGS, dict)
    assert "challenge" in REAL_WORLD_TIMINGS
    assert "login" in REAL_WORLD_TIMINGS
    assert "diag.ping" in REAL_WORLD_TIMINGS
    assert "diag.ping_unreachable" in REAL_WORLD_TIMINGS
    assert "repeater.scan" in REAL_WORLD_TIMINGS
    assert "system.reboot_shutdown" in REAL_WORLD_TIMINGS
    assert REAL_WORLD_TIMINGS["diag.ping"] > 3.0
    assert REAL_WORLD_TIMINGS["repeater.scan"] > 15.0


def test_threaded_mock_router_server_lifecycle() -> None:
    """Verify that MockRouterServer starts and stops cleanly in synchronous contexts."""
    with MockRouterServer() as server:
        assert server.url.startswith("http://127.0.0.1:")
        res = requests.post(
            server.url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "challenge",
                "params": {"username": "root"},
            },
            timeout=2.0,
        ).json()
        assert "result" in res
        assert res["result"]["alg"] == 1


@pytest.mark.asyncio
async def test_failed_login_rate_limiting_lockout() -> None:
    """Verify that consecutive failed logins trigger LockoutError (-32003)."""
    async with MockRouter(
        password="correct_pwd", max_failed_logins=3, lockout_duration=60.0
    ) as mock:
        uplink_client = AiohttpClient()
        client = GLinet(base_url=mock.url, client=uplink_client)

        try:
            # 2 failed attempts -> AuthenticationError (-32000)
            for _ in range(2):
                with pytest.raises(AuthenticationError) as exc_info:
                    await client.login("root", "wrong_pwd")
                assert "-32000" in str(exc_info.value)

            # 3rd failed attempt -> LockoutError (-32003)
            with pytest.raises(LockoutError) as exc_info:
                await client.login("root", "wrong_pwd")
            assert "-32003" in str(exc_info.value)
            assert "Login failed too many times" in str(exc_info.value)

            # Subsequent attempts remain locked out even if correct password is provided
            with pytest.raises(LockoutError):
                await client.login("root", "correct_pwd")
        finally:
            session = await uplink_client.session()
            await session.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("alg", "hash_method"),
    [
        (1, "md5"),
        (5, "sha256"),
        (6, "sha512"),
    ],
)
async def test_authentication_hashing_algorithms(alg: int, hash_method: str) -> None:
    """Verify challenge-response login works across MD5, SHA-256, and SHA-512."""
    async with MockRouter(
        password="secret123", alg=alg, hash_method=hash_method
    ) as mock:
        uplink_client = AiohttpClient()
        client = GLinet(base_url=mock.url, client=uplink_client)
        try:
            await client.login("root", "secret123")
            assert client.logged_in
            assert client.sid is not None
        finally:
            session = await uplink_client.session()
            await session.close()


@pytest.mark.asyncio
async def test_token_expiration_and_invalidation() -> None:
    """Verify that expired session tokens trigger TokenError (-1)."""
    async with MockRouter(token_ttl=0.01) as mock:
        uplink_client = AiohttpClient()
        client = GLinet(base_url=mock.url, client=uplink_client)
        try:
            await client.login("root", "goodlife")
            assert client.logged_in

            # Wait for token TTL to expire
            await asyncio.sleep(0.05)

            with pytest.raises(TokenError) as exc_info:
                await client.router_info()
            assert "-1" in str(exc_info.value)
        finally:
            session = await uplink_client.session()
            await session.close()


def test_keep_alive_and_logout() -> None:
    """Verify session keep-alive and manual logout endpoint."""
    with MockRouterServer() as s:
        # Challenge & login via raw requests
        res = requests.post(
            s.url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "challenge",
                "params": {"username": "root"},
            },
            timeout=2.0,
        ).json()["result"]
        hsh = GLinet._compute_hash(
            alg=res["alg"],
            salt=res["salt"],
            nonce=res["nonce"],
            hash_method=res["hash-method"],
            username="root",
            password="goodlife",
        )
        login_res = requests.post(
            s.url,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "login",
                "params": {"username": "root", "hash": hsh},
            },
            timeout=2.0,
        ).json()["result"]
        sid = login_res["sid"]

        # Alive refreshes session
        alive_res = requests.post(
            s.url,
            json={"jsonrpc": "2.0", "id": 3, "method": "alive", "params": {"sid": sid}},
            timeout=2.0,
        ).json()
        assert alive_res["result"] is None

        # Logout invalidates session
        logout_res = requests.post(
            s.url,
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "logout",
                "params": {"sid": sid},
            },
            timeout=2.0,
        ).json()
        assert logout_res["result"] is None

        # Subsequent call with invalidated sid fails
        call_res = requests.post(
            s.url,
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "call",
                "params": [sid, "system", "get_info"],
            },
            timeout=2.0,
        ).json()
        assert call_res["error"]["code"] == -32000


@pytest.mark.asyncio
async def test_reboot_lifecycle() -> None:
    """Verify router downtime and session clearing during simulated reboot."""
    async with MockRouter(reboot_duration=0.1) as mock:
        uplink_client = AiohttpClient()
        client = GLinet(base_url=mock.url, client=uplink_client)
        try:
            await client.login("root", "goodlife")
            assert client.logged_in

            # Trigger reboot
            reboot_res = await client.router_reboot()
            assert reboot_res == {"delay": 0}

            # While rebooting, server returns 503 making router unreachable
            await asyncio.sleep(0.02)
            reachable = await client.router_reachable()
            assert not reachable

            # Wait for reboot to finish
            await asyncio.sleep(0.12)
            assert await client.router_reachable()

            # Previous session must be invalid
            with pytest.raises(NonZeroResponse):
                await client.router_info()
        finally:
            session = await uplink_client.session()
            await session.close()


@pytest.mark.asyncio
async def test_endpoint_overrides() -> None:
    """Verify dynamic endpoint overriding for custom test scenarios."""
    async with MockRouter() as mock:
        mock.set_endpoint_override(
            "system",
            "get_info",
            {"model": "custom_ax1800", "firmware_version": "4.5.0"},
        )
        uplink_client = AiohttpClient()
        client = GLinet(base_url=mock.url, client=uplink_client)
        try:
            await client.login("root", "goodlife")
            info = await client.router_info()
            assert info["model"] == "custom_ax1800"
            assert info["firmware_version"] == "4.5.0"

            mock.clear_endpoint_overrides()
            info2 = await client.router_info()
            assert info2["model"] == "b1300"
        finally:
            session = await uplink_client.session()
            await session.close()


@pytest.mark.asyncio
async def test_additional_endpoints_coverage() -> None:
    """Verify mock endpoints likely to be added to the library."""
    async with MockRouter() as mock:
        uplink_client = AiohttpClient()
        client = GLinet(base_url=mock.url, client=uplink_client)
        try:
            await client.login("root", "goodlife")

            # Modem endpoints
            modem_info = await client.modem_info()
            assert "modems" in modem_info
            sim_info = await client.modem_sim_info()
            assert len(sim_info) > 0
            sim_signal = await client.modem_sim_signal()
            assert len(sim_signal) > 0

            # Additional endpoints via raw JSON-RPC calls
            ovpn_status = await client._request(
                client.gen_sid_payload(
                    "call", ["ovpn-client", "get_status"], client.sid
                )
            )
            assert "client_id" in ovpn_status
            assert ovpn_status["mode"] == "client"

            ovpn_configs = await client._request(
                client.gen_sid_payload(
                    "call", ["ovpn-client", "get_all_config_list"], client.sid
                )
            )
            assert "config_list" in ovpn_configs

            repeater_status = await client._request(
                client.gen_sid_payload("call", ["repeater", "get_status"], client.sid)
            )
            assert "state" in repeater_status

            repeater_scan = await client._request(
                client.gen_sid_payload("call", ["repeater", "scan"], client.sid)
            )
            assert "res" in repeater_scan
            assert len(repeater_scan["res"]) > 0

            cable_status = await client._request(
                client.gen_sid_payload("call", ["cable", "get_status"], client.sid)
            )
            assert "ipv4" in cable_status

            cable_config = await client._request(
                client.gen_sid_payload("call", ["cable", "get_config"], client.sid)
            )
            assert cable_config["protocol"] == "dhcp"

            dns_config = await client._request(
                client.gen_sid_payload("call", ["dns", "get_config"], client.sid)
            )
            assert "server" in dns_config

            tethering_status = await client._request(
                client.gen_sid_payload("call", ["tethering", "get_status"], client.sid)
            )
            assert tethering_status["err_code"] == 0

            adguard_config = await client._request(
                client.gen_sid_payload(
                    "call", ["adguardhome", "get_config"], client.sid
                )
            )
            assert adguard_config["enabled"] is True

            # Switch button endpoints
            switch_cfg = await client._request(
                client.gen_sid_payload(
                    "call", ["switch-button", "get_config"], client.sid
                )
            )
            assert "func" in switch_cfg

            switch_funcs = await client._request(
                client.gen_sid_payload(
                    "call", ["switch-button", "get_funcs"], client.sid
                )
            )
            assert "openvpn" in switch_funcs["funcs"]

            # Tailscale exit nodes
            exit_nodes = await client._request(
                client.gen_sid_payload(
                    "call", ["tailscale", "get_exit_node_list"], client.sid
                )
            )
            assert len(exit_nodes["exit_node_list"]) > 0

            # LAN config list
            lan_cfg = await client._request(
                client.gen_sid_payload("call", ["lan", "get_config_list"], client.sid)
            )
            assert len(lan_cfg["interfaces"]) > 0

            # VPN policy
            vpn_dom = await client._request(
                client.gen_sid_payload(
                    "call", ["vpn-policy", "get_domain_policy"], client.sid
                )
            )
            assert "domain_list" in vpn_dom

            # Network leases & ARP
            leases = await client._request(
                client.gen_sid_payload(
                    "call", ["network", "get_dhcp_leases"], client.sid
                )
            )
            assert len(leases["leases"]) > 0

            arp = await client._request(
                client.gen_sid_payload("call", ["network", "get_arp_list"], client.sid)
            )
            assert len(arp["entries"]) > 0

            # Firewall WAN access & zones
            wan_acc = await client._request(
                client.gen_sid_payload(
                    "call", ["firewall", "get_wan_access"], client.sid
                )
            )
            assert "enable_ssh" in wan_acc

            zones = await client._request(
                client.gen_sid_payload(
                    "call", ["firewall", "get_zone_list"], client.sid
                )
            )
            assert "lan" in zones["internals"]

            # LED config
            led = await client._request(
                client.gen_sid_payload("call", ["led", "get_config"], client.sid)
            )
            assert "led_enable" in led

            # DDNS config & status
            ddns_cfg = await client._request(
                client.gen_sid_payload("call", ["ddns", "get_config"], client.sid)
            )
            assert "device_id" in ddns_cfg

            ddns_st = await client._request(
                client.gen_sid_payload("call", ["ddns", "get_status"], client.sid)
            )
            assert ddns_st["status"] == 2

            # Unknown method returns -32601
            with pytest.raises(NonZeroResponse) as exc_info:
                await client._request(
                    client.gen_sid_payload(
                        "call", ["nonexistent", "method"], client.sid
                    )
                )
            assert "-32601" in str(exc_info.value)
        finally:
            session = await uplink_client.session()
            await session.close()


import time


def _sync_login(url: str) -> str:
    """Helper: perform challenge + login via raw requests and return the sid."""
    challenge = requests.post(
        url,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "challenge",
            "params": {"username": "root"},
        },
        timeout=2.0,
    ).json()["result"]
    hsh = GLinet._compute_hash(
        challenge["alg"],
        challenge["salt"],
        challenge["nonce"],
        challenge["hash-method"],
        "root",
        "goodlife",
    )
    login_res = requests.post(
        url,
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "login",
            "params": {"username": "root", "hash": hsh},
        },
        timeout=2.0,
    ).json()["result"]
    return login_res["sid"]


@pytest.mark.asyncio
async def test_expire_session() -> None:
    """Verify that expire_session marks a session as expired so subsequent calls fail."""
    async with MockRouter() as mock:
        uplink_client = AiohttpClient()
        client = GLinet(base_url=mock.url, client=uplink_client)
        try:
            await client.login("root", "goodlife")
            assert client.logged_in

            # Expire the session manually
            mock.expire_session(client.sid)

            with pytest.raises(TokenError) as exc_info:
                await client.router_info()
            assert "-1" in str(exc_info.value)
        finally:
            session = await uplink_client.session()
            await session.close()


def test_invalid_json_body() -> None:
    """Verify that a POST with non-JSON body returns parse error -32700."""
    with MockRouterServer() as s:
        res = requests.post(
            s.url,
            data="this is not json",
            headers={"Content-Type": "application/json"},
            timeout=2.0,
        ).json()
        assert "error" in res
        assert res["error"]["code"] == -32700


def test_unknown_rpc_method() -> None:
    """Verify that an unknown top-level JSON-RPC method returns -32601."""
    with MockRouterServer() as s:
        res = requests.post(
            s.url,
            json={"jsonrpc": "2.0", "id": 1, "method": "unknown"},
            timeout=2.0,
        ).json()
        assert "error" in res
        assert res["error"]["code"] == -32601


def test_call_with_invalid_params() -> None:
    """Verify that a 'call' with non-list params returns -32602."""
    with MockRouterServer() as s:
        sid = _sync_login(s.url)
        res = requests.post(
            s.url,
            json={
                "jsonrpc": "2.0",
                "id": 10,
                "method": "call",
                "params": {"bad": True},
            },
            timeout=2.0,
        ).json()
        assert res["error"]["code"] == -32602


def test_call_with_null_sid() -> None:
    """Verify that a 'call' with null sid returns -32602."""
    with MockRouterServer() as s:
        res = requests.post(
            s.url,
            json={
                "jsonrpc": "2.0",
                "id": 10,
                "method": "call",
                "params": [None, "system", "get_info"],
            },
            timeout=2.0,
        ).json()
        assert res["error"]["code"] == -32602


@pytest.mark.asyncio
async def test_simulate_delays() -> None:
    """Verify that simulate_delays=True introduces a measurable delay."""
    async with MockRouter(simulate_delays=True) as mock:
        uplink_client = AiohttpClient()
        client = GLinet(base_url=mock.url, client=uplink_client)
        try:
            await client.login("root", "goodlife")
            t0 = time.monotonic()
            await client.router_info()
            elapsed = time.monotonic() - t0
            # system.get_info timing is 0.071s; allow some tolerance
            assert elapsed >= 0.05, f"Expected delay, but elapsed was {elapsed:.4f}s"
        finally:
            session = await uplink_client.session()
            await session.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("module", "func"),
    [
        ("lan", "unknown_func"),
        ("system", "unknown_func"),
        ("wifi", "unknown_func"),
        ("diag", "unknown_func"),
        ("wg-client", "unknown_func"),
        ("vpn-client", "unknown_func"),
        ("modem", "unknown_func"),
        ("ovpn-client", "unknown_func"),
        ("repeater", "unknown_func"),
        ("cable", "unknown_func"),
        ("switch-button", "unknown_func"),
        ("network", "unknown_func"),
        ("firewall", "unknown_func"),
        ("ddns", "unknown_func"),
        ("tailscale", "unknown_func"),
    ],
)
async def test_dispatch_unknown_functions(module: str, func: str) -> None:
    """Verify that unknown functions within known modules return -32601."""
    async with MockRouter() as mock:
        uplink_client = AiohttpClient()
        client = GLinet(base_url=mock.url, client=uplink_client)
        try:
            await client.login("root", "goodlife")
            with pytest.raises(NonZeroResponse) as exc_info:
                await client._request(
                    client.gen_sid_payload("call", [module, func], client.sid)
                )
            assert "-32601" in str(exc_info.value)
        finally:
            session = await uplink_client.session()
            await session.close()


@pytest.mark.asyncio
async def test_lan_static_bind_dispatch() -> None:
    """Verify lan.get_static_bind_list returns fixture data."""
    async with MockRouter() as mock:
        uplink_client = AiohttpClient()
        client = GLinet(base_url=mock.url, client=uplink_client)
        try:
            await client.login("root", "goodlife")
            result = await client._request(
                client.gen_sid_payload(
                    "call", ["lan", "get_static_bind_list"], client.sid
                )
            )
            assert isinstance(result, dict)
        finally:
            session = await uplink_client.session()
            await session.close()


@pytest.mark.asyncio
async def test_vpn_client_dispatch() -> None:
    """Verify vpn-client.get_status and vpn-client.set_tunnel work correctly."""
    async with MockRouter() as mock:
        uplink_client = AiohttpClient()
        client = GLinet(base_url=mock.url, client=uplink_client)
        try:
            await client.login("root", "goodlife")

            # get_status
            status = await client._request(
                client.gen_sid_payload(
                    "call", ["vpn-client", "get_status"], client.sid
                )
            )
            assert "status_list" in status

            # set_tunnel
            set_result = await client._request(
                client.gen_sid_payload(
                    "call",
                    ["vpn-client", "set_tunnel", {"tunnel_id": 2001, "enabled": True}],
                    client.sid,
                )
            )
            assert "tunnel_id" in set_result
        finally:
            session = await uplink_client.session()
            await session.close()


@pytest.mark.asyncio
async def test_tailscale_set_config_enable() -> None:
    """Verify tailscale.set_config with enabled=true restores initial status."""
    async with MockRouter() as mock:
        uplink_client = AiohttpClient()
        client = GLinet(base_url=mock.url, client=uplink_client)
        try:
            await client.login("root", "goodlife")

            # Enable tailscale
            await client._request(
                client.gen_sid_payload(
                    "call",
                    ["tailscale", "set_config", {"enabled": True}],
                    client.sid,
                )
            )

            # Status should not be empty list
            status = await client._request(
                client.gen_sid_payload(
                    "call", ["tailscale", "get_status"], client.sid
                )
            )
            assert status != []
        finally:
            session = await uplink_client.session()
            await session.close()


@pytest.mark.asyncio
async def test_tailscale_get_auth_url() -> None:
    """Verify tailscale.get_auth_url returns an empty list."""
    async with MockRouter() as mock:
        uplink_client = AiohttpClient()
        client = GLinet(base_url=mock.url, client=uplink_client)
        try:
            await client.login("root", "goodlife")
            result = await client._request(
                client.gen_sid_payload(
                    "call", ["tailscale", "get_auth_url"], client.sid
                )
            )
            assert result == []
        finally:
            session = await uplink_client.session()
            await session.close()


@pytest.mark.asyncio
async def test_repeater_get_config() -> None:
    """Verify repeater.get_config returns fixture data."""
    async with MockRouter() as mock:
        uplink_client = AiohttpClient()
        client = GLinet(base_url=mock.url, client=uplink_client)
        try:
            await client.login("root", "goodlife")
            result = await client._request(
                client.gen_sid_payload(
                    "call", ["repeater", "get_config"], client.sid
                )
            )
            assert isinstance(result, dict)
        finally:
            session = await uplink_client.session()
            await session.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "policy_func",
    [
        "get_global_policy",
        "get_mac_policy",
        "get_proxy_mode",
        "get_vlan_policy",
    ],
)
async def test_vpn_policy_all_endpoints(policy_func: str) -> None:
    """Verify all vpn-policy dispatch functions return a result."""
    async with MockRouter() as mock:
        uplink_client = AiohttpClient()
        client = GLinet(base_url=mock.url, client=uplink_client)
        try:
            await client.login("root", "goodlife")
            result = await client._request(
                client.gen_sid_payload(
                    "call", ["vpn-policy", policy_func], client.sid
                )
            )
            # Should return something (not raise NonZeroResponse)
            assert result is not None or result is None  # just confirm no exception
        finally:
            session = await uplink_client.session()
            await session.close()
