import unittest
import asyncio
import pytest
from gli4py.enums import TailscaleConnection
from gli4py.error_handling import NonZeroResponse
from gli4py.glinet import GLinet

router = GLinet(base_url="http://192.168.0.1/rpc")

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
	"n300"

]


@pytest.fixture(scope="session")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()
    
@pytest.mark.asyncio
async def test_router_reachable() -> None:
	response = await router.router_reachable()
	assert(response)
	print(response)

@pytest.mark.asyncio
async def test_login() -> None:
	with open('router_pwd', 'r') as file:
		pwd = str(file.read())
	assert(not router.logged_in)
	await router.login("root", pwd)
	assert(router.logged_in)
	print(router.sid)

@pytest.mark.asyncio
async def test_router_info() -> None:
	response = await router.router_info()
	assert('model' in response)
	assert('firmware_version' in response)
	assert('mac' in response)
	print(response)

@pytest.mark.asyncio
async def test_router_get_status() -> None:
	response = await router.router_get_status()
	assert('service' in response)
	assert('network' in response)
	assert('system' in response)
	assert('wifi' in response)
	system = response.get("system")
	assert('uptime' in system)
	assert('load_average' in system)
	print(response)

@pytest.mark.asyncio
async def test_router_get_load() -> None:
	response = await router.router_get_load()
	assert('load_average' in response)
	assert('memory_free' in response)
	assert('memory_total' in response)
	print(response)

@pytest.mark.asyncio
async def test_router_mac() -> None:
	response = await router.router_mac()
	assert('factory_mac' in response)
	print(response)

@pytest.mark.asyncio
async def test_connected_clients() -> None:
	clients = await router.connected_clients()
	print(len(clients))
	assert(len(clients) > 0)

@pytest.mark.asyncio
async def test_wifi_ifaces_get() -> None:
	wifi_ifaces = await router.wifi_ifaces_get()
	print(wifi_ifaces)
	for iface in wifi_ifaces.values():
		assert('enabled' in iface)
		assert('ssid' in iface)
		assert('name' in iface)
		assert('key' in iface)

@pytest.mark.asyncio
async def test_wifi_ifaces_set_enabled() -> None:
	wifi_ifaces = await router.wifi_ifaces_get()
	iface = next(iter(wifi_ifaces.values()))
	iface_enabled = iface.get("enabled")

	response = await router.wifi_iface_set_enabled(iface.get("name"), not iface_enabled)
	print(response)
	await asyncio.sleep(1)

	wifi_ifaces2 = await router.wifi_ifaces_get()
	iface_enabled_after = wifi_ifaces2.get(iface.get("name")).get("enabled")
	assert(iface_enabled_after != iface_enabled)

@pytest.mark.asyncio
async def test_wireguard_client_list() -> None:
	response = await router.wireguard_client_list()
	print(response)
	#assert(response['enable'] in [True,False])

@pytest.mark.asyncio
async def test_wireguard_client_state() -> None:
	response = await router.wireguard_client_state()
	print(response)
	assert(response['status'] in [0,1,2])

@pytest.mark.asyncio
async def test_tailscale_status() -> None:
	response = await router._tailscale_status()
	print(response)
	assert(dict(response).get('status', 0) in [1,2,3,4] or response == [])

@pytest.mark.asyncio
async def test_tailscale_connection() -> None:
	response = await router.tailscale_connection_state()
	print(response)
	assert(response in [TailscaleConnection.Disconnected, TailscaleConnection.Connected])

@pytest.mark.asyncio
async def test_tailscale_configured() -> None:
	response = await router.tailscale_configured()
	print("Tailscale configured:", response)
	assert(response in [True, False])

@pytest.mark.asyncio
async def test_tailscale_get_config() -> None:
	response = await router._tailscale_get_config()
	print(response['enabled'])
	assert(response['enabled'] in [True, False])

@pytest.mark.asyncio
async def test_tailscale_start() -> None:
	result = await router.tailscale_start()
	print(result)
	assert(result in [True, False])

@pytest.mark.asyncio
async def test_tailscale_stop() -> None:
	result = await router.tailscale_stop()
	print(result)
	assert(result in [True, False])

@pytest.mark.asyncio
async def test_connected_to_internet() -> None:
	response = await router.connected_to_internet()
	print(response)
	#assert(response['detected'] in [0,1,2,3])
	#assert('ip' in response)

@pytest.mark.asyncio
async def test_ping() -> None:
	response = await router.ping("google.com") 
	assert(response)
	response = await router.ping("8.8.8.8")
	assert(response)
	response = await router.ping("0.0.0.1")
	assert(not response)

@pytest.mark.asyncio
async def test_router_reboot() -> None:
	response = await router.router_reboot()
	print(response)
	print("waiting `15s` for router to shutdown")
	await asyncio.sleep(15)
	while not await router.router_reachable():
		print("waiting for router to wake")
		await asyncio.sleep(1)
	with pytest.raises(NonZeroResponse):
		await router.router_info()