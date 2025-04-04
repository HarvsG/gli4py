import asyncio
from typing import Any, Optional
from requests import Response, exceptions
from uplink import (
    Consumer,
    json,
    post,
    response_handler,
    AiohttpClient,
    timeout,
    Body)
import hashlib
from passlib.hash import md5_crypt, sha256_crypt, sha512_crypt

from gli4py.enums import TailscaleConnection

# , Path, clients, RequestsClient, Query, headers,response,handler,
# import cache

from .error_handling import raise_for_status#, timeout_error
# from json import loads




# typical base url http://192.168.8.1/rpc


@response_handler(raise_for_status)
@json
class GLinet(Consumer):
    """A Python Client for the GL-inet API."""
    def __init__(
        self,
        sid: Optional[str] = None,
        **kwargs
    ):
        self.sid: str = sid
        self._logged_in = (self.sid is not None)

        # initialise the super class
        super(GLinet, self).__init__(client=AiohttpClient(), **kwargs)

    @staticmethod
    def gen_sid_payload(method: str, params: list, sid: str = None) -> dict:
        #headers = {'glinet': 1}
        params.insert(0, sid)
        payload = {
            "method": method,
            "jsonrpc": "2.0",
            'params': params,
            "id": 0,
            }
        return payload

    @staticmethod
    def gen_no_auth_payload(method: str, params: dict) -> dict:
        #headers = {'glinet': 1}
        payload = {
            "method": method,
            "jsonrpc": "2.0",
            'params': params,
            "id": 0,
            }
        return payload
    
    @post("")
    @timeout(2)
    async def _request(self, data: Body) -> Response:
        """challenges the router for password hashing config"""
    @post("")
    @timeout(5)
    async def _request_long_timeout(self, data: Body) -> Response:
        """challenges the router for password hashing config"""

    async def _challenge(self, username) -> dict:
        challenge_data = self.gen_no_auth_payload('challenge', {'username': username})
        return await self._request(challenge_data)
        
    async def _get_sid(self, username: str, hash) -> dict:
        login_data = self.gen_no_auth_payload(
            "login", 
            {
                'username': username,
                'hash': hash
            }
            )
        return await self._request(login_data)
    
    async def router_reachable(self, username:str = 'root') -> bool:
        try:
            res = await self._challenge(username)
            if res:
                return True
        except:
            return False
        return False

    async def login(self, username: str, password: str) -> None:
        
        try: 
            res = await self._challenge(username)

            alg = res['alg']
            salt = res['salt']
            nonce = res['nonce']

            # Step2: Generate cipher text using openssl algorithm
            if alg == 1:  # MD5
                cipher_password = md5_crypt.using(salt=salt).hash(password)
            elif alg == 5:  # SHA-256
                cipher_password = sha256_crypt.using(salt=salt, rounds=5000).hash(password)
            elif alg == 6:  # SHA-512
                cipher_password = sha512_crypt.using(salt=salt, rounds=5000).hash(password)
            else:
                raise ValueError('Router requested unsupported hashing algorithm')

            # Step3: Generate hash values for login
            data = f"{username}:{cipher_password}:{nonce}"
            hash = hashlib.md5(data.encode()).hexdigest()

            # Step4: Get sid by login
            res = await self._get_sid(username, hash)
            if 'sid' in res:
                self.sid = res['sid']
                self._logged_in = True

        except exceptions.RequestException as e:
            raise exceptions.RequestException(e)
        except (KeyError, ValueError) as e:
            raise KeyError("Parameter Exception:", e)
        except Exception as e:
            raise Exception("An unexpected error has occurred:", e)

    async def router_info(self) -> dict:
        return await self._request(self.gen_sid_payload('call', ['system', 'get_info'], self.sid))

    async def router_get_status(self) -> dict:
        return await self._request(self.gen_sid_payload('call', ['system', 'get_status'], self.sid))

    async def router_get_load(self) -> dict:
        return await self._request(self.gen_sid_payload('call', ['system', 'get_load'], self.sid))

    async def router_mac(self) -> dict:
        return await self._request(self.gen_sid_payload('call', ['macclone', 'get_mac'], self.sid))

    async def router_reboot(self, delay: int = 0) -> dict:
        return await self._request(self.gen_sid_payload('call', ['system', 'reboot',  {'delay': delay}], self.sid))

    async def ping(self, address) -> bool:
        """
        returns the stdout of the ping command if successful or "[]" if not successful
        """
        result = await self._request_long_timeout(self.gen_sid_payload('call', ['diag', 'ping', {"addr":address}], self.sid))
        return (not result == [])
    
    async def connected_to_internet(self) -> dict:
        """Is the internet reachable
        {"detected":2,"dns":["82.15.176.1"],"gateway":"82.15.178.1","valid":false,"netmask":"255.255.254.0","ip":"82.15.178.44"}
        upper-level DHCP server status [0: disable; 1:enabled and have pointed the gateway to the bypass route; 2: enabled; 3：the cable is not connected]
        """
        return await self._request(self.gen_sid_payload('call', ['edgerouter', 'get_status'], self.sid))

    async def list_all_clients(self) -> dict:
        return await self._request(self.gen_sid_payload('call', ['clients', 'get_list'], self.sid))

    async def list_static_clients(self) -> dict:
        return await self._request(self.gen_sid_payload('call', ['lan', 'get_static_bind_list'], self.sid))

    async def connected_clients(self) -> dict:
        """gets all connected clients asyncronously.
        Returns a list of dictionaries with key being the mac addr and the dictionary
        being client data
        """
        clients = {}
        all_clients = await self.list_all_clients()
        for client in all_clients["clients"]:
            if client['online'] is True:
                clients[client['mac']] = client
        return clients

    async def _wifi_config_get(self) -> dict:
        return await self._request(self.gen_sid_payload('call', ['wifi', 'get_config'], self.sid))

    async def _wifi_config_set(self, config: dict) -> dict:
        return await self._request(self.gen_sid_payload('call', ['wifi', 'set_config', config], self.sid))
    
    async def wifi_ifaces_get(self) -> dict:
        wifi_config = await self._wifi_config_get()
        return {iface.get('name'):iface for dev in wifi_config.get('res', []) for iface in dev.get('ifaces')}
    
    async def wifi_iface_set_enabled(self, iface_name: str, enabled: bool) -> dict:
        ifaces = await self.wifi_ifaces_get()
        if iface_name in ifaces:
            return await self._wifi_config_set({'enabled': enabled, 'iface_name': iface_name})
        else:
            raise ValueError('iface_name does not exist')    

    # VPN information

    async def wireguard_client_list(self) -> dict:
        response: dict = await self._request(self.gen_sid_payload('call', ['wg-client', 'get_all_config_list'], self.sid))
        configs: list[dict[str,any]] = []
        for item in response['config_list']:
            if item['peers'] == []:
                continue
            for peer in item['peers']:
                configs.append(
                    {
                        "name":f'{item["group_name"]}/{peer["name"]}',
                        "group_id":item['group_id'],
                        "peer_id":peer['peer_id']
                     }
                )
        return configs
            

    async def wireguard_client_state(self) -> dict:
        """
        {"rx_bytes":0,"ipv6":"","tx_bytes":0,"domain":"vpn.example.com","group_id":7707,"port":51820,"name":"TheOracle","peer_id":1341,"status":0,"proxy":true,"log":"","ipv4":""}
        status 0:not start 1:connected 2:connecting
        """
        return await self._request(self.gen_sid_payload('call', ['wg-client', 'get_status'], self.sid))

    async def wireguard_client_start(self, group_id: int, peer_id: int) -> dict:
        return await self._request(self.gen_sid_payload('call', ['wg-client', 'start', {"group_id":group_id,"peer_id":peer_id}], self.sid))

    async def wireguard_client_stop(self) -> dict:
        return await self._request(self.gen_sid_payload('call', ['wg-client', 'stop'], self.sid))

    async def _tailscale_get_config(self) -> dict | bool:
        """
        {'wan_enabled': False, 'lan_ip': '192.168.0.0/24', 'enabled': False, 'lan_enabled': True}
        {'detected': 2, 'dns': ['88.88.88.88'], 'gateway': '88.88.88.88', 'valid': False, 'netmask': '255.255.254.0', 'ip': '88.88.88.88'}
        If tailscale is not available on the the device this will error.
        """
        try:
            result = await self._request(self.gen_sid_payload('call', ['tailscale', 'get_config'], self.sid))
        except:
            return False
        return result
    
    async def _tailscale_set_config(self, config_updates: dict[str, Any]) -> dict:
        current_config: dict[str, Any] = await self._request(self.gen_sid_payload('call', ['tailscale', 'get_config'], self.sid))
        new_config = current_config | config_updates
        return await self._request(self.gen_sid_payload('call', ['tailscale', 'set_config', new_config], self.sid))

    async def _tailscale_status(self) -> dict:
        """
        {'login_name': 'HarvsG@github', 'status': 3, 'address_v4': '100.92.1.100'}
        {'detected': 2, 'dns': ['88.88.88.89'], 'gateway': '88.88.88.88', 'valid': False, 'netmask': '255.255.254.0', 'ip': '88.88.88.88'}
        If disconnected or not configured, returns []
        """
        return await self._request(self.gen_sid_payload('call', ['tailscale', 'get_status'], self.sid))

    async def tailscale_connection_state(self) -> TailscaleConnection:
        state: dict = dict(await self._tailscale_status())
        if state == {}:
            return TailscaleConnection.Disconnected
        return TailscaleConnection(state.get('status',0))

    async def tailscale_configured(self) -> bool:
        try:
            if await self._tailscale_status() != []:
                return True
        #TODO make this catch less broad and put some logs in
        except Exception:
            return False
        if await self._tailscale_get_config() == False:
            return False
        return True

    async def tailscale_start(self, depth: int = 0) -> True:
        if depth > 10:
            raise ConnectionError("Tailscale attempted to connect 10 times with no success")
        response: dict | list = await self._tailscale_status()
        if type(response) is list and response == []:
            await self._tailscale_set_config({'enabled':True})
            if depth > 0:
                await asyncio.sleep(0.3)
            depth += 1
            return await self.tailscale_start(depth)
        else:
            status: int = response.get('status',0)
        if status == 3:
            return True
        if status == 4:
            await asyncio.sleep(3)
            status = (await self._tailscale_status())['status']
            if status != 3:
                raise ConnectionError("Did not try to start tailscale as device reported 'Connecting' and then 3 seconds later '%s'", TailscaleConnection[status].name)
            return True
        if status in [1,2]:
            raise ConnectionAbortedError("Connection not attempted as authorisation is not complete, due to '%s'", TailscaleConnection[status].name)

        raise ConnectionError ("Unkown conenction status: '%s'", status) 

    async def tailscale_stop(self, depth: int = 0) -> True:
        if depth > 10:
            raise ConnectionError("Tailscale attempted to disconnect 10 times with no success")
        response: dict | list = await self._tailscale_status()
        if type(response) is list and response == []:
            return True
        else:
            status: int = response.get('status',0)
        if status in [3,4]:
            await self._tailscale_set_config({'enabled':False})
            if depth > 0:
                await asyncio.sleep(0.3)
            depth += 1
            return await self.tailscale_stop(depth)
        if status in [1,2]:
            raise ConnectionAbortedError("Disconnection not attempted as tailscale authorisation is not complete, due to '%s'. Therefore tailscale was already not connected", TailscaleConnection[status].name)

    @property
    def logged_in(self) -> bool:
        return self._logged_in

