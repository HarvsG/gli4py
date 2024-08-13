import unittest
import asyncio
import pytest
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
async def test_connected_to_internet() -> None:
	response = await router.connected_to_internet()
	print(response)
	assert(response['detected'] in [0,1,2,3])
	assert('ip' in response)

@pytest.mark.asyncio
async def test_ping() -> None:
	response = await router.ping("google.com")
	assert(response)
	response = await router.ping("8.8.8.8")
	assert(response)
	response = await router.ping("0.0.0.1")
	assert(not response)

@pytest.mark.asyncio
async def test_tailscale_connection_state() -> None:
	response = await router.tailscale_connection_state()
	print(response)
	assert(response['status'] in [0,1,2,3,4])
	