"""Live tests for the GLinet router API — requires a physical GL.iNet router.

Usage:
  # Non-disruptive tests against a router at 192.168.0.4:
  pytest -m live --router-url http://192.168.0.4/rpc --router-pwd-file router_pwd -v

  # Include disruptive tests (WiFi toggle, WireGuard start/stop, reboot):
  pytest -m live --router-url http://192.168.0.4/rpc --router-pwd-file router_pwd --disruptive -v

  # Generate a JSON report for contributor upload:
  pytest -m live --router-url http://192.168.0.4/rpc --router-pwd-file router_pwd --test-report report.json -v
"""

import asyncio

import pytest
from semver import Version

from gli4py.enums import TailscaleConnection
from gli4py.error_handling import NonZeroResponse
from gli4py.glinet import NEW_VPN_CLIENT_VERSION, GLinet

from .conftest import LiveTestReport

# All tests share one GLinet client (and one aiohttp session), so they must
# run on a single event loop. Tests in this file require a physical router.
pytestmark = [
    pytest.mark.asyncio(loop_scope="module"),
    pytest.mark.live,
]

# Module-level state shared across tests (populated by fixtures on first use)
_router: GLinet | None = None
_router_info_cache: dict | None = None


@pytest.fixture(scope="module")
async def router(router_url: str, router_pwd: str) -> GLinet:
    """Create and authenticate a shared GLinet client for all live tests."""
    global _router  # noqa: PLW0603
    if _router is None:
        _router = GLinet(base_url=router_url)
        await _router.login("root", router_pwd)
    return _router


@pytest.fixture(scope="module")
async def router_info_data(router: GLinet) -> dict:
    """Cached router_info response shared across tests."""
    global _router_info_cache  # noqa: PLW0603
    if _router_info_cache is None:
        _router_info_cache = await router.router_info()
    return _router_info_cache


# ─── Authentication & Reachability ───


async def test_router_reachable(router_url: str) -> None:
    """Test if the router is reachable (before login)."""
    probe = GLinet(base_url=router_url)
    response = await probe.router_reachable()
    assert response is True


async def test_login(router: GLinet) -> None:
    """Test that the router fixture is logged in."""
    assert router.logged_in is True
    assert router.sid is not None


# ─── System Information ───


async def test_router_info(
    router: GLinet,
    router_info_data: dict,
    test_report: LiveTestReport | None,
) -> None:
    """Test retrieving router information."""
    response = router_info_data
    assert "model" in response
    assert "firmware_version" in response
    assert "mac" in response
    if test_report is not None:
        test_report.router_info = response
        test_report.record("test_router_info", "system/get_info", response)


async def test_router_get_status(
    router: GLinet,
    test_report: LiveTestReport | None,
) -> None:
    """Test retrieving router status."""
    response = await router.router_get_status()
    assert "service" in response
    assert "network" in response
    assert "system" in response
    system = response.get("system")
    assert "uptime" in system
    assert "load_average" in system
    # WiFi passwords should be redacted
    if "wifi" in response:
        for wifi_entry in response["wifi"]:
            assert wifi_entry["passwd"] is None
    if test_report is not None:
        test_report.record("test_router_get_status", "system/get_status", response)


async def test_router_get_load(
    router: GLinet,
    test_report: LiveTestReport | None,
) -> None:
    """Test retrieving router load information."""
    response = await router.router_get_load()
    assert "load_average" in response
    assert "memory_free" in response
    assert "memory_total" in response
    if test_report is not None:
        test_report.record("test_router_get_load", "system/get_load", response)


async def test_router_mac(
    router: GLinet,
    test_report: LiveTestReport | None,
) -> None:
    """Test retrieving the router's MAC address."""
    response = await router.router_mac()
    assert "factory_mac" in response
    if test_report is not None:
        test_report.record("test_router_mac", "macclone/get_mac", response)


# ─── Network & Clients ───


async def test_connected_clients(
    router: GLinet,
    test_report: LiveTestReport | None,
) -> None:
    """Test retrieving connected clients."""
    clients = await router.connected_clients()
    assert len(clients) > 0
    if test_report is not None:
        test_report.record(
            "test_connected_clients", "clients/get_list (filtered)", clients
        )


async def test_list_all_clients(
    router: GLinet,
    test_report: LiveTestReport | None,
) -> None:
    """Test retrieving all clients (including offline)."""
    response = await router.list_all_clients()
    assert "clients" in response
    if test_report is not None:
        test_report.record("test_list_all_clients", "clients/get_list", response)


async def test_list_static_clients(
    router: GLinet,
    test_report: LiveTestReport | None,
) -> None:
    """Test retrieving static DHCP client bindings."""
    response = await router.list_static_clients()
    if test_report is not None:
        test_report.record(
            "test_list_static_clients", "lan/get_static_bind_list", response
        )


async def test_connected_to_internet(
    router: GLinet,
    test_report: LiveTestReport | None,
) -> None:
    """Test checking if the router is connected to the internet."""
    response = await router.connected_to_internet()
    assert response["detected"] in [0, 1, 2, 3]
    assert "ip" in response
    if test_report is not None:
        test_report.record(
            "test_connected_to_internet", "edgerouter/get_status", response
        )


async def test_ping(
    router: GLinet,
    test_report: LiveTestReport | None,
) -> None:
    """Test pinging a host."""
    response = await router.ping("google.com")
    assert response is True
    response_ip = await router.ping("8.8.8.8")
    assert response_ip is True
    response_fail = await router.ping("0.0.0.1")
    assert response_fail is False
    if test_report is not None:
        test_report.record(
            "test_ping",
            "diag/ping",
            {"google.com": True, "8.8.8.8": True, "0.0.0.1": False},
        )


# ─── WiFi ───


async def test_wifi_ifaces_get(
    router: GLinet,
    test_report: LiveTestReport | None,
) -> None:
    """Test retrieving WiFi interfaces with keys redacted."""
    wifi_ifaces = await router.wifi_ifaces_get()
    for iface in wifi_ifaces.values():
        assert "enabled" in iface
        assert "ssid" in iface
        assert "name" in iface
        assert iface["key"] is None  # redacted by default
    if test_report is not None:
        test_report.record("test_wifi_ifaces_get", "wifi/get_config", wifi_ifaces)


async def test_wifi_ifaces_get_unredacted(router: GLinet) -> None:
    """Test retrieving WiFi interfaces with keys NOT redacted."""
    wifi_ifaces = await router.wifi_ifaces_get(redact_keys=False)
    for iface in wifi_ifaces.values():
        assert "key" in iface
        # key should be a non-None string when not redacted
        assert iface["key"] is not None


async def test_wifi_iface_set_enabled_invalid(router: GLinet) -> None:
    """Test that setting an invalid WiFi interface name raises ValueError."""
    with pytest.raises(ValueError, match="iface_name does not exist"):
        await router.wifi_iface_set_enabled("nonexistent_iface_999", True)


async def test_wifi_ifaces_set_enabled(
    router: GLinet,
    disruptive: bool,
    test_report: LiveTestReport | None,
) -> None:
    """Test enabling/disabling a WiFi interface (disruptive)."""
    if not disruptive:
        pytest.skip("Disruptive tests disabled (use --disruptive to enable)")

    wifi_ifaces = await router.wifi_ifaces_get()
    iface = next(iter(wifi_ifaces.values()))
    iface_enabled = iface.get("enabled")

    response = await router.wifi_iface_set_enabled(iface.get("name"), not iface_enabled)
    await asyncio.sleep(1)

    wifi_ifaces2 = await router.wifi_ifaces_get()
    iface_enabled_after = wifi_ifaces2.get(iface.get("name")).get("enabled")
    assert iface_enabled_after != iface_enabled

    # Restore original state
    await router.wifi_iface_set_enabled(iface.get("name"), iface_enabled)

    if test_report is not None:
        test_report.record("test_wifi_ifaces_set_enabled", "wifi/set_config", response)


# ─── Modem (may not be present on all routers) ───


async def test_modem_info(
    router: GLinet,
    test_report: LiveTestReport | None,
) -> None:
    """Test retrieving modem information (skips if no modem present)."""
    try:
        response = await router.modem_info()
    except Exception as exc:
        if test_report is not None:
            test_report.record(
                "test_modem_info", "modem/get_info", None, error=str(exc)
            )
        pytest.skip(f"Modem not available: {exc}")
    else:
        if test_report is not None:
            test_report.record("test_modem_info", "modem/get_info", response)


async def test_modem_sim_info(
    router: GLinet,
    test_report: LiveTestReport | None,
) -> None:
    """Test retrieving SIM card information (skips if no modem present)."""
    try:
        response = await router.modem_sim_info()
    except Exception as exc:
        if test_report is not None:
            test_report.record(
                "test_modem_sim_info", "modem/get_sim_info", None, error=str(exc)
            )
        pytest.skip(f"Modem not available: {exc}")
    else:
        if test_report is not None:
            test_report.record("test_modem_sim_info", "modem/get_sim_info", response)


async def test_modem_sim_signal(
    router: GLinet,
    test_report: LiveTestReport | None,
) -> None:
    """Test retrieving SIM signal information (skips if no modem present)."""
    try:
        response = await router.modem_sim_signal()
    except Exception as exc:
        if test_report is not None:
            test_report.record(
                "test_modem_sim_signal", "modem/get_sim_signal", None, error=str(exc)
            )
        pytest.skip(f"Modem not available: {exc}")
    else:
        if test_report is not None:
            test_report.record(
                "test_modem_sim_signal", "modem/get_sim_signal", response
            )


# ─── WireGuard VPN ───


async def test_wireguard_client_list(
    router: GLinet,
    test_report: LiveTestReport | None,
) -> None:
    """Test retrieving the list of WireGuard clients."""
    response = await router.wireguard_client_list()
    assert isinstance(response, list)
    if test_report is not None:
        test_report.record(
            "test_wireguard_client_list", "wg-client/get_all_config_list", response
        )


async def test_wireguard_client_state(
    router: GLinet,
    router_info_data: dict,
    test_report: LiveTestReport | None,
) -> None:
    """Test retrieving the state of the WireGuard client."""
    firmware_version = router_info_data["firmware_version"]
    parsed_version = Version.parse(firmware_version)
    response = await router.wireguard_client_state()
    assert isinstance(response, list)
    if len(response) > 0:
        first_status = response[0]
        if parsed_version >= NEW_VPN_CLIENT_VERSION:
            assert first_status["enabled"] in [True, False]
        else:
            assert first_status["status"] in [0, 1, 2]
    if test_report is not None:
        endpoint = (
            "vpn-client/get_status"
            if parsed_version >= NEW_VPN_CLIENT_VERSION
            else "wg-client/get_status"
        )
        test_report.record("test_wireguard_client_state", endpoint, response)


async def test_wireguard_start(
    router: GLinet,
    disruptive: bool,
    test_report: LiveTestReport | None,
) -> None:
    """Test starting the WireGuard client (disruptive)."""
    if not disruptive:
        pytest.skip("Disruptive tests disabled (use --disruptive to enable)")

    status_list = await router.wireguard_client_state()
    if not status_list:
        pytest.skip("No WireGuard client configured")

    first_status = status_list[0]
    group_id = first_status["group_id"]
    peer_id = first_status["peer_id"]
    tunnel_id = first_status.get("tunnel_id")

    result = await router.wireguard_client_start(group_id, tunnel_id or peer_id)
    if test_report is not None:
        test_report.record(
            "test_wireguard_start", "vpn-client/set_tunnel or wg-client/start", result
        )

    # Wait for the client to connect (up to 10s)
    for i in range(10):
        status_list = await router.wireguard_client_state()
        first_status = status_list[0]
        if (
            "status" in first_status
            and first_status["status"] == 1
            and "enabled" in first_status
            and first_status["enabled"]
        ):
            break
        await asyncio.sleep(1)
        if i == 9:
            pytest.fail("WireGuard client took too long to connect.")


async def test_wireguard_stop(
    router: GLinet,
    disruptive: bool,
    test_report: LiveTestReport | None,
) -> None:
    """Test stopping the WireGuard client (disruptive)."""
    if not disruptive:
        pytest.skip("Disruptive tests disabled (use --disruptive to enable)")

    info_response = await router.router_info()
    firmware_version = info_response["firmware_version"]
    status_list = await router.wireguard_client_state()
    if not status_list:
        pytest.skip("No WireGuard client configured")

    first_status = status_list[0]
    tunnel_id = first_status["tunnel_id"]
    result = await router.wireguard_client_stop(tunnel_id)
    if test_report is not None:
        test_report.record(
            "test_wireguard_stop", "vpn-client/set_tunnel or wg-client/stop", result
        )

    parsed_version = Version.parse(firmware_version)

    # Wait for the client to disconnect (up to 10s)
    for i in range(10):
        status_list = await router.wireguard_client_state()
        first_status = status_list[0]
        if parsed_version >= NEW_VPN_CLIENT_VERSION:
            if "enabled" in first_status and not first_status["enabled"]:
                break
        elif "status" in first_status and first_status["status"] == 0:
            break
        await asyncio.sleep(1)
        if i == 9:
            pytest.fail("WireGuard client took too long to disconnect.")


# ─── Tailscale ───


async def test_tailscale_status(
    router: GLinet,
    test_report: LiveTestReport | None,
) -> None:
    """Test retrieving the Tailscale status."""
    response = await router._tailscale_status()  # noqa: SLF001
    assert dict(response).get("status", 0) in [1, 2, 3, 4] or response == []
    if test_report is not None:
        test_report.record("test_tailscale_status", "tailscale/get_status", response)


async def test_tailscale_connection(
    router: GLinet,
    test_report: LiveTestReport | None,
) -> None:
    """Test retrieving the Tailscale connection state."""
    response = await router.tailscale_connection_state()
    assert isinstance(response, TailscaleConnection)
    if test_report is not None:
        test_report.record(
            "test_tailscale_connection",
            "tailscale/get_status (enum)",
            {"state": response.name},
        )


async def test_tailscale_configured(
    router: GLinet,
    test_report: LiveTestReport | None,
) -> None:
    """Test checking if Tailscale is configured."""
    response = await router.tailscale_configured()
    assert response in [True, False]
    if test_report is not None:
        test_report.record(
            "test_tailscale_configured",
            "tailscale/get_status+get_config",
            {"configured": response},
        )


async def test_tailscale_get_config(
    router: GLinet,
    test_report: LiveTestReport | None,
) -> None:
    """Test retrieving the Tailscale configuration."""
    response = await router._tailscale_get_config()  # noqa: SLF001
    if response is not False:
        assert response["enabled"] in [True, False]
    if test_report is not None:
        test_report.record(
            "test_tailscale_get_config", "tailscale/get_config", response
        )


async def test_tailscale_start(
    router: GLinet,
    disruptive: bool,
    test_report: LiveTestReport | None,
) -> None:
    """Test starting Tailscale (disruptive)."""
    if not disruptive:
        pytest.skip("Disruptive tests disabled (use --disruptive to enable)")
    result = await router.tailscale_start()
    assert result is True
    if test_report is not None:
        test_report.record(
            "test_tailscale_start", "tailscale/set_config", {"started": True}
        )


async def test_tailscale_stop(
    router: GLinet,
    disruptive: bool,
    test_report: LiveTestReport | None,
) -> None:
    """Test stopping Tailscale (disruptive)."""
    if not disruptive:
        pytest.skip("Disruptive tests disabled (use --disruptive to enable)")
    result = await router.tailscale_stop()
    assert result is True
    if test_report is not None:
        test_report.record(
            "test_tailscale_stop", "tailscale/set_config", {"stopped": True}
        )


# ─── Reboot (most disruptive — run last) ───


async def test_router_reboot(
    router: GLinet,
    disruptive: bool,
    test_report: LiveTestReport | None,
) -> None:
    """Test rebooting the router (most disruptive, run last)."""
    if not disruptive:
        pytest.skip("Disruptive tests disabled (use --disruptive to enable)")
    response = await router.router_reboot()
    if test_report is not None:
        test_report.record("test_router_reboot", "system/reboot", response)
    await asyncio.sleep(15)
    while not await router.router_reachable():
        await asyncio.sleep(1)
    with pytest.raises(NonZeroResponse):
        await router.router_info()
