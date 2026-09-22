"""Tests for the GL.iNet mock router server and edge case simulations."""
# pylint: disable=redefined-outer-name,protected-access,too-many-locals

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
            res["alg"],
            res["salt"],
            res["nonce"],
            res["hash-method"],
            "root",
            "goodlife",
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
