from typing import Optional
from requests import Response
from uplink import (
    Consumer,
    get,
    post,
    response_handler,
    Field,
    AiohttpClient,
    timeout,
    error_handler)

# , Path, clients, RequestsClient, Query, headers,response,handler,
# import cache

from .error_handling import raise_for_status, timeout_error
# from json import loads




# typical base url http://192.168.8.1/cgi-bin/api/
@timeout(2)
@response_handler(raise_for_status)
class GLinet(Consumer):
    """A Python Client for the GL-inet API."""
    def __init__(
        self,
        token: Optional[str] = None,
        **kwargs
    ):
        self.token = token

        # initialise the super class
        super(GLinet, self).__init__(client=AiohttpClient(), **kwargs)

        self._logged_in: bool = False
        if self.token is not None:
            self._logged_in = True
            self.session.headers["Authorization"] = self.token

    @post("router/login")
    def _login(self, pwd: Field) -> Response:
        """fetches token"""

    async def login(self, password: str) -> None:
        try:
            # use the token for auth for all requests henceforth
            res = await self._login(password)
            self.token = res['token']
            self.session.headers["Authorization"] = self.token
            self._logged_in = True
        except Exception as err:
            self._logged_in = False
            raise ConnectionRefusedError("Failed to authenticate with GL-inet. Error %s", err)

    @get("router/hello")
    def router_hello(self) -> Response:  
        """Gets a vrariety of basic router info, no login required
        {'init': True, 'connected': True, 'configured': True, 'version': '3.215', 'firmware_user': '', 'firmware_type': '', 'model': 'mt1300', 'mac': '94:83:c4:11:44:76', 'type': 'router', 'name': '', 'code': 0}
        """

    @get("router/model")
    def router_model(self) -> Response:
        """Retrieves the router's model, no auth required
        {'internal_version': 'VC1D020ER22092110101', 'model': 'mt1300', 'code': 0}
        """

    @get("router/mac/get")
    def router_mac(self) -> Response:
        """Retrieves the router's mac address"""

    @get("router/status")
    def router_status(self) -> Response:
        """router status"""

    @get("firmware/onlinecheck")
    def new_firmware(self) -> Response:
        """whether there is new firmware to upgrade"""

    @get("router/reboot")
    def reboot(self) -> Response:
        """reboot router"""

    # Basic WAN interaction

    @get("wan/info")
    def wan_ip(self) -> Response:
        """Retrieves the router's wan ip
        connected
        {'macclone': False, 'up': True, 'cableinwan': True, 'online': True, 'ip': '432.653.65.6', 'mask': '0.0.0.0', 'proto': 'dhcp', 'gateway': 'xxx.xxx.xxx.xxx', 'dns': ['8.8.8.8'], 'device': 'eth0.2', 'passthrough': False, 'code': 0}
        disconnected
        {'macclone': False, 'up': True, 'cableinwan': True, 'online': False, 'proto': 'dhcp', 'device': 'eth0.2', 'passthrough': False, 'code': 0}
        """

    @get("internet/public_ip/get")
    def public_ip(self) -> Response:
        """Retrieves the router's public ip. Will give VPN IP is connected
        timesout
        """
    @timeout_error
    @timeout(5)
    @post("internet/ping")
    def ping(self, ping_addr: Field) -> Response:
        """Pings an addresss"""

    @get("internet/reachable")
    def connected_to_internet(self) -> Response:
        """Is the internet reachable
        *WARNING* sometimes timesout when internet is reachable
        e.g when a VPN client is connecting
        Connected
        {'reachable': True, 'code': 0}
        Disconnected
        timesout
        """

    # Client information

    @get("client/list")
    def list_all_clients(self) -> Response:
        """gets all clients"""

    @get("router/static_leases/list")
    def list_static_clients(self) -> Response:
        """gets all static clients"""

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

    @get("router/vpn/status")
    def client_vpn_status(self) -> Response:
        """Retrieves all the VPN statuses
        Connected
        """

    @get("wireguard/client/list")
    def wireguard_client_list(self) -> Response:
        """Retrieves the different WG client configurations
        Does *NOT* return the list of clients connected to 
        the WG server.
        """

    @get("wireguard/client/status")
    def wireguard_client_state(self) -> Response:
        """Retrieves the wireguard status
        Connected
        {'code': 0, 'download_config': False, 'enable': True, 'access': True, 'mode6': 'Native', 'ipaddr': '10.0.0.7', 'ipaddrv6': '', 'main_server': 'ServerName', 'rx': '65.15 KB', 'tx': '13.08 KB'}
        disconnected
        {'code': -204, 'download_config': False, 'enable': False, 'access': True, 'main_server': 'ServerName', 'rx': 'Unknown', 'tx': 'Unknown'}
        """

    @post("wireguard/client/stop")
    def wireguard_client_stop(self) -> Response:
        """Stops the wireguard client"""

    @post("wireguard/client/start")
    def wireguard_client_start(self, name:Field) -> Response:
        """Stops the wireguard client"""

    @post("openvpn/client/stop")
    def openvpn_client_stop(self) -> Response:
        """Stops the wireguard client"""

    @post("openvpn/client/start")
    def openvpn_client_start(self, name:Field) -> Response:
        """Stops the wireguard client"""
    # SMS stuff

    # TODO untested
    @get("modem/info")
    def _get_modems(self) -> Response:
        """Returns a list of modems"""

    # TODO untested
    def count_modems(self) -> int:
        return len(self._get_modems())

    # TODO untested
    @get("modem/sms/status")
    def sms_status(self, modem_id: Field) -> Response:
        """Retrieves the status of the SMS modem"""

    # TODO untested
    @post("modem/sms/send")
    def _send_sms(self, modem_id: Field, message: Field, number: Field) -> Response:
        """send an SMS"""

    # TODO untested
    async def send_sms(self, number: str, message: str) -> Response:
        modems = await self._get_modems()
        # if there are no modems raise exception
        if len(modems) == 0:
            raise Exception("No modems found")
        # if there is only one modem try and send the message
        elif len(modems) == 1:
            return await self._send_sms(modems[0]["modem_id"], message, number)
        elif len(modems) > 1:
            for modem in modems:
                if modem["SIM_status"] == 0:
                    return await self._send_sms(modem["modem_id"], message, number)

    @property
    def logged_in(self) -> bool:
        return self._logged_in
