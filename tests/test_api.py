"""Integration tests for the GLinet router API.

These tests execute against a mock router server by default, or against a physical
GL.iNet router when invoked with --live.
"""
# pylint: disable=protected-access,redefined-outer-name

import asyncio

import pytest
from semver import Version

from gli4py.enums import TailscaleConnection
from gli4py.error_handling import NonZeroResponse
from gli4py.glinet import NEW_VPN_CLIENT_VERSION, GLinet

# All tests in this module share one GLinet client (and aiohttp session),
# running on a module-scoped event loop.
pytestmark = [
    pytest.mark.asyncio(loop_scope="module"),
]

models = [
    "mt1300",
    "x3000",
    "mt2500",
    "mt2500a",
    "axt1800",
    "a1300",
    "ax1800",
    "sft1200",
    "e750",
    "mv100",
    "mv1000w",
    "s10",
    "s200",
    "s1300",
    "sf1200",
    "b1300",
    "b2200",
    "ap1300",
    "ap1300lte",
    "x1200",
    "x750",
    "x300b",
    "xe300",
    "ar750s",
    "ar750",
    "ar300m",
    "n300",
]


async def test_router_reachable(router: GLinet) -> None:
    """Test if the router is reachable."""
    response = await router.router_reachable()
    assert response
    print(response)


async def test_login(router: GLinet, router_password: str | None) -> None:
    """Test logging into the router."""
    if not router_password:
        pytest.skip(
            "Router password not provided (pass --password or create router_pwd file)."
        )
    assert not router.logged_in
    await router.login("root", router_password)
    assert router.logged_in
    print(router.sid)


async def test_router_info(router: GLinet) -> None:
    """Test retrieving router information."""
    if not router.logged_in:
        pytest.skip("Router not logged in")
    response = await router.router_info()
    assert "model" in response
    assert "firmware_version" in response
    assert "mac" in response
    print(response)


async def test_router_get_status(router: GLinet) -> None:
    """Test retrieving router status."""
    if not router.logged_in:
        pytest.skip("Router not logged in")
    response = await router.router_get_status()
    assert "service" in response
    assert "network" in response
    assert "system" in response
    assert "wifi" in response
    system = response.get("system")
    assert "uptime" in system
    assert "load_average" in system
    print(response)


async def test_router_get_load(router: GLinet) -> None:
    """Test retrieving router load information."""
    if not router.logged_in:
        pytest.skip("Router not logged in")
    response = await router.router_get_load()
    assert "load_average" in response
    assert "memory_free" in response
    assert "memory_total" in response
    print(response)


async def test_router_mac(router: GLinet) -> None:
    """Test retrieving the router's MAC address."""
    if not router.logged_in:
        pytest.skip("Router not logged in")
    response = await router.router_mac()
    assert "factory_mac" in response
    print(response)


async def test_connected_clients(router: GLinet) -> None:
    """Test retrieving connected clients."""
    if not router.logged_in:
        pytest.skip("Router not logged in")
    clients = await router.connected_clients()
    print(len(clients))
    assert len(clients) > 0


async def test_wifi_ifaces_get(router: GLinet) -> None:
    """Test retrieving WiFi interfaces."""
    if not router.logged_in:
        pytest.skip("Router not logged in")
    wifi_ifaces = await router.wifi_ifaces_get()
    print(wifi_ifaces)
    for iface in wifi_ifaces.values():
        assert "enabled" in iface
        assert "ssid" in iface
        assert "name" in iface
        assert "key" in iface


@pytest.mark.disruptive
async def test_wifi_ifaces_set_enabled(router: GLinet, disruptive_tests: bool) -> None:
    """Test enabling/disabling a WiFi interface."""
    if not disruptive_tests:
        pytest.skip("Disruptive tests are disabled (pass --disruptive-tests to run)")
    if not router.logged_in:
        pytest.skip("Router not logged in")

    wifi_ifaces = await router.wifi_ifaces_get()
    iface = next(iter(wifi_ifaces.values()))
    iface_enabled = iface.get("enabled")

    try:
        response = await router.wifi_iface_set_enabled(
            iface.get("name"), not iface_enabled
        )
        print(response)
        await asyncio.sleep(1)

        wifi_ifaces2 = await router.wifi_ifaces_get()
        iface_enabled_after = wifi_ifaces2.get(iface.get("name")).get("enabled")
        assert iface_enabled_after != iface_enabled
    finally:
        await router.wifi_iface_set_enabled(iface.get("name"), iface_enabled)


async def test_connected_to_internet(router: GLinet) -> None:
    """Test checking if the router is connected to the internet."""
    if not router.logged_in:
        pytest.skip("Router not logged in")
    response = await router.connected_to_internet()
    print(response)
    assert response["detected"] in [0, 1, 2, 3]
    if response["detected"] in (1, 2):
        assert "ip" in response


async def test_ping(router: GLinet) -> None:
    """Test pinging a host."""
    if not router.logged_in:
        pytest.skip("Router not logged in")
    response = await router.ping("google.com")
    assert response
    print(response)
    response = await router.ping("8.8.8.8")
    assert response
    response = await router.ping("0.0.0.1")
    assert not response


async def test_wireguard_client_list(router: GLinet) -> None:
    """Test retrieving the list of WireGuard clients."""
    if not router.logged_in:
        pytest.skip("Router not logged in")
    response = await router.wireguard_client_list()
    print(response)


async def test_wireguard_client_state(router: GLinet) -> None:
    """Test retrieving the state of the WireGuard client."""
    if not router.logged_in:
        pytest.skip("Router not logged in")
    info_response = await router.router_info()
    firmware_version = info_response["firmware_version"]
    parsed_version = Version.parse(firmware_version)
    response = await router.wireguard_client_state()
    print(response)
    if not response:
        pytest.skip("No WireGuard client status available.")
    first_status = response[0]
    # In newer version, status only exists when enabled is True
    # In older versions, status is always present
    if parsed_version >= NEW_VPN_CLIENT_VERSION:
        assert first_status["enabled"] in [True, False]
    else:
        assert first_status["status"] in [0, 1, 2]


@pytest.mark.disruptive
async def test_wireguard_start(router: GLinet, disruptive_tests: bool) -> None:
    """Test starting the WireGuard client."""
    if not disruptive_tests:
        pytest.skip("Disruptive tests are disabled (pass --disruptive-tests to run)")
    if not router.logged_in:
        pytest.skip("Router not logged in")

    status_list = await router.wireguard_client_state()
    if status_list is None or len(status_list) == 0:
        pytest.skip("No WireGuard client configured, skipping test.")
        return

    first_status = status_list[0]
    group_id = first_status["group_id"]
    peer_id = first_status["peer_id"]
    tunnel_id = first_status.get("tunnel_id")

    result = await router.wireguard_client_start(group_id, tunnel_id or peer_id)
    print("RESULT: ", result)
    assert result["tunnel_id"] == tunnel_id

    # Wait for the client to connect or timeout with 10 seconds
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


@pytest.mark.disruptive
async def test_wireguard_stop(router: GLinet, disruptive_tests: bool) -> None:
    """Test stopping the WireGuard client."""
    if not disruptive_tests:
        pytest.skip("Disruptive tests are disabled (pass --disruptive-tests to run)")
    if not router.logged_in:
        pytest.skip("Router not logged in")

    info_response = await router.router_info()
    firmware_version = info_response["firmware_version"]
    status_list = await router.wireguard_client_state()
    if status_list is None or len(status_list) == 0:
        pytest.skip("No WireGuard client configured, skipping test.")
        return

    first_status = status_list[0]
    tunnel_id = first_status["tunnel_id"]

    result = await router.wireguard_client_stop(tunnel_id)
    print("RESULT: ", result)
    assert result["tunnel_id"] == tunnel_id

    parsed_version = Version.parse(firmware_version)

    # Wait for the client to disconnect or timeout with 10 seconds
    for i in range(10):
        status_list = await router.wireguard_client_state()
        first_status = status_list[0]
        # In newer version, status only exists when enabled is True
        # In older versions, status is always present
        if parsed_version >= NEW_VPN_CLIENT_VERSION:
            if "enabled" in first_status and not first_status["enabled"]:
                break
        else:
            if "status" in first_status and first_status["status"] == 0:
                break

        await asyncio.sleep(1)

        if i == 9:
            pytest.fail("WireGuard client took too long to disconnect.")


async def test_tailscale_status(router: GLinet) -> None:
    """Test retrieving the Tailscale status."""
    if not router.logged_in:
        pytest.skip("Router not logged in")
    if not await router.tailscale_configured():
        pytest.skip("Tailscale is not configured or supported on this device")
    response = await router._tailscale_status()  # pylint: disable=protected-access
    print(response)
    assert dict(response).get("status", 0) in [1, 2, 3, 4] or response == []


async def test_tailscale_connection(router: GLinet) -> None:
    """Test retrieving the Tailscale connection state."""
    if not router.logged_in:
        pytest.skip("Router not logged in")
    if not await router.tailscale_configured():
        pytest.skip("Tailscale is not configured or supported on this device")
    response = await router.tailscale_connection_state()
    print(response)
    assert response in [TailscaleConnection.DISCONNECTED, TailscaleConnection.CONNECTED]


async def test_tailscale_configured(router: GLinet) -> None:
    """Test checking if Tailscale is configured."""
    if not router.logged_in:
        pytest.skip("Router not logged in")
    response = await router.tailscale_configured()
    print("Tailscale configured:", response)
    assert response in [True, False]


async def test_tailscale_get_config(router: GLinet) -> None:
    """Test retrieving the Tailscale configuration."""
    if not router.logged_in:
        pytest.skip("Router not logged in")
    response = await router._tailscale_get_config()  # pylint: disable=protected-access
    if response is False:
        pytest.skip("Tailscale is not available on this device")
    print(response["enabled"])
    assert response["enabled"] in [True, False]


@pytest.mark.disruptive
async def test_tailscale_start(router: GLinet, disruptive_tests: bool) -> None:
    """Test starting Tailscale."""
    if not disruptive_tests:
        pytest.skip("Disruptive tests are disabled (pass --disruptive-tests to run)")
    if not router.logged_in:
        pytest.skip("Router not logged in")
    result = await router.tailscale_start()
    print(result)
    assert result in [True, False]


@pytest.mark.disruptive
async def test_tailscale_stop(router: GLinet, disruptive_tests: bool) -> None:
    """Test stopping Tailscale."""
    if not disruptive_tests:
        pytest.skip("Disruptive tests are disabled (pass --disruptive-tests to run)")
    if not router.logged_in:
        pytest.skip("Router not logged in")
    result = await router.tailscale_stop()
    print(result)
    assert result in [True, False]


@pytest.mark.disruptive
async def test_router_reboot(
    router: GLinet, disruptive_tests: bool, reboot_wait_time: float
) -> None:
    """Test rebooting the router."""
    if not disruptive_tests:
        pytest.skip("Disruptive tests are disabled (pass --disruptive-tests to run)")
    if not router.logged_in:
        pytest.skip("Router not logged in")
    response = await router.router_reboot()
    print(response)
    print(f"waiting `{reboot_wait_time}s` for router to shutdown")
    await asyncio.sleep(reboot_wait_time)
    while not await router.router_reachable():
        print("waiting for router to wake")
        await asyncio.sleep(0.05)
    with pytest.raises(NonZeroResponse):
        await router.router_info()
