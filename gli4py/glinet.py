from typing import Optional, Self
from requests import Response, exceptions
import requests
import json as JSON
from uplink import (
    Consumer,
    get,
    json,
    post,
    response_handler,
    Field,
    AiohttpClient,
    timeout,
    error_handler,
    Body)
import hashlib
from passlib.hash import md5_crypt, sha256_crypt, sha512_crypt

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
            
    async def router_mac(self) -> dict:
        return await self._request(self.gen_sid_payload('call', ['macclone', 'get_mac'], self.sid))

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

    async def wireguard_client_stop(self, group_id: int, peer_id: int) -> dict:
        return await self._request(self.gen_sid_payload('call', ['wg-client', 'stop', {"group_id":group_id,"peer_id":peer_id}], self.sid))

    @property
    def logged_in(self) -> bool:
        return self._logged_in

