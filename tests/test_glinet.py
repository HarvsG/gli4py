import unittest
import asyncio
import pytest
from gli4py import GLinet

router = GLinet(base_url="http://192.168.0.1/cgi-bin/api/")

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
async def test_router_model() -> None:
	response = await router.router_model()
	assert(response['code']==0)
	assert(response['model'] in models)
	print(response)

@pytest.mark.asyncio
async def test_router_hello() -> None:
	response = await router.router_hello()
	assert(response['code']==0)
	assert(response['model'] in models)
	print(response)


@pytest.mark.asyncio
async def test_login() -> None:
	with open('router_pwd', 'r') as file:
		pwd = str(file.read())
	assert(not router.logged_in)
	await router.login(pwd)
	assert(router.logged_in)
	print("router.token")
	print(router.token)
	print("-----------------")
		
@pytest.mark.asyncio
async def test_router_mac() -> None:
	response = await router.router_mac()
	print(response)

@pytest.mark.asyncio
async def test_connected_clients() -> None:
	clients = await router.connected_clients()
	print(len(clients))
	assert(len(clients) > 0)

@pytest.mark.asyncio
async def test_client_vpn_status() -> None:
	response = await router.client_vpn_status()
	print("vpn status")
	print(response)

@pytest.mark.asyncio
async def test_wireguard_client_list() -> None:
	response = await router.wireguard_client_list()
	print(response)
	#assert(response['enable'] in [True,False])

@pytest.mark.asyncio
async def test_wireguard_client_states() -> None:
	response = await router.wireguard_client_state()
	print(response)
	assert(response['enable'] in [True,False])
	
# @pytest.mark.asyncio
# async def test_wireguard_client_stop() -> None:
# 	response = await router.wireguard_client_stop()
# 	print("stoping wg client")
# 	print(response)
# 	#assert(response['code'] == 0)

# @pytest.mark.asyncio
# async def test_wireguard_client_start() -> None:
# 	response = await router.wireguard_client_state()
# 	wg_server_name = response['main_server']
# 	response = await router.wireguard_client_start(wg_server_name)
# 	print("starting wg client")
# 	print(response)
# 	#assert(response['code'] == 0)


@pytest.mark.asyncio
async def test_wan_ip() -> None:
	response = await router.wan_ip()
	print(response)
	assert(response['online'] in [True,False])

@pytest.mark.asyncio
async def test_connected_to_internet() -> None:
	response = await router.connected_to_internet()
	print(response)
	assert(response['reachable'] in [True,False])

@pytest.mark.asyncio
async def test_ping() -> None:
	response = await router.ping("google.com")
	print(response)
	response = await router.ping("10.0.0.10")
	print(response)
	#assert(response['reachable'] in [True,False])