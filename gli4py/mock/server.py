"""Mock GL.iNet JSON-RPC API server for offline testing and development."""
# pylint: disable=too-many-instance-attributes,too-many-public-methods,too-many-arguments,too-many-positional-arguments,broad-exception-caught,too-many-return-statements,too-many-branches,attribute-defined-outside-init

import asyncio
import copy
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from aiohttp import web

from gli4py.glinet import GLinet
from gli4py.mock.fixtures_loader import FixturesLoader

# Real-world timings measured on physical GL-B1300 running firmware 4.3.25
REAL_WORLD_TIMINGS: dict[str, float] = {
    "challenge": 0.063,
    "login": 0.032,
    "system.get_info": 0.071,
    "system.get_status": 0.094,
    "system.get_load": 0.051,
    "macclone.get_mac": 0.042,
    "clients.get_list": 0.283,
    "lan.get_static_bind_list": 0.056,
    "wifi.get_config": 0.466,
    "cable.get_status": 0.112,
    "dns.get_config": 0.045,
    "edgerouter.get_status": 4.57,
    "diag.ping": 3.35,
    "diag.ping_unreachable": 11.06,
    "repeater.scan": 17.99,
    "system.reboot_shutdown": 15.0,
    "system.reboot_total": 45.0,
}


class MockRouter:
    """Simulates a GL.iNet router JSON-RPC API backend over HTTP."""

    def __init__(
        self,
        username: str = "root",
        password: str = "goodlife",
        alg: int = 1,
        hash_method: str = "md5",
        max_failed_logins: int = 5,
        lockout_duration: float = 300.0,
        token_ttl: float = 1800.0,
        simulate_delays: bool = False,
        reboot_duration: float = 0.1,
        fixtures_dir: Path | str | None = None,
        host: str = "127.0.0.1",
        port: int = 0,
    ) -> None:
        """Initialize mock router instance."""
        self.username = username
        self.password = password
        self.alg = alg
        self.hash_method = hash_method
        self.max_failed_logins = max_failed_logins
        self.lockout_duration = lockout_duration
        self.token_ttl = token_ttl
        self.simulate_delays = simulate_delays
        self.reboot_duration = reboot_duration
        self.host = host
        self.port = port

        self._loader = FixturesLoader(fixtures_dir)
        self._app = web.Application()
        self._app.router.add_post("/rpc", self._handle_rpc)
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None

        self.actual_port: int | None = None
        self.url: str = ""
        self.rebooting: bool = False
        self.failed_login_count: int = 0
        self.locked_until: float = 0.0
        self.sessions: dict[str, float] = {}
        self.last_nonce: str = ""
        self.last_salt: str = ""

        self._endpoint_overrides: dict[tuple[str, str], Any] = {}
        self._background_tasks: set[asyncio.Task[Any]] = set()
        self._reset_in_memory_state()

    def _reset_in_memory_state(self) -> None:
        """Reload all mutable state from clean fixture copies."""
        self.system_info = self._loader.load("system_info")
        self.system_status = self._loader.load("system_status")
        self.system_load = self._loader.load("system_load")
        self.macclone = self._loader.load("macclone")
        self.clients = self._loader.load("clients")
        self.lan_static = self._loader.load("lan_static")
        self.lan_config = self._loader.load("lan_config")
        self.wifi_config = self._loader.load("wifi_config")
        self.edgerouter = self._loader.load("edgerouter")
        self.wireguard_config = self._loader.load("wireguard_config")
        self.wireguard_status = self._loader.load("wireguard_status")
        self.vpn_client_status = self._loader.load("vpn_client_status")
        self.tailscale_config = self._loader.load("tailscale_config")
        self.tailscale_status = self._loader.load("tailscale_status")
        self.tailscale_exit_nodes = self._loader.load("tailscale_exit_nodes")
        self.modem_info = self._loader.load("modem_info")
        self.modem_sim = self._loader.load("modem_sim")
        self.modem_sim_signal = self._loader.load("modem_sim_signal")
        self.ovpn_config = self._loader.load("ovpn_config")
        self.ovpn_status = self._loader.load("ovpn_status")
        self.repeater_config = self._loader.load("repeater_config")
        self.repeater_status = self._loader.load("repeater_status")
        self.repeater_scan = self._loader.load("repeater_scan")
        self.cable_status = self._loader.load("cable_status")
        self.dns_config = self._loader.load("dns_config")
        self.tethering_status = self._loader.load("tethering_status")
        self.adguardhome = self._loader.load("adguardhome")
        self.switch_button = self._loader.load("switch_button")
        self.vpn_policy = self._loader.load("vpn_policy")
        self.dhcp_leases = self._loader.load("dhcp_leases")
        self.arp_list = self._loader.load("arp_list")
        self.firewall_wan_access = self._loader.load("firewall_wan_access")
        self.firewall_zones = self._loader.load("firewall_zones")
        self.led_config = self._loader.load("led_config")
        self.ddns_config = self._loader.load("ddns_config")
        self.ddns_status = self._loader.load("ddns_status")
        self._initial_tailscale_status = copy.deepcopy(self.tailscale_status)

    async def start(self) -> "MockRouter":
        """Start the in-process mock HTTP server."""
        self._runner = web.AppRunner(self._app, access_log=None)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()

        # Retrieve bound port from underlying socket
        assert self._site._server is not None  # pylint: disable=protected-access
        server_sockets = getattr(self._site._server, "sockets", [])  # pylint: disable=protected-access
        if server_sockets:
            self.actual_port = server_sockets[0].getsockname()[1]
        self.url = f"http://{self.host}:{self.actual_port}/rpc"
        return self

    async def stop(self) -> None:
        """Stop server and clean up active sessions."""
        for task in list(self._background_tasks):
            task.cancel()
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
            self._background_tasks.clear()

        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
            self._site = None

    async def __aenter__(self) -> "MockRouter":
        """Context manager entry."""
        return await self.start()

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        await self.stop()

    def set_endpoint_override(
        self, module: str, method: str, response_or_callable: Any
    ) -> None:
        """Override a specific RPC endpoint response or handler."""
        self._endpoint_overrides[(module, method)] = response_or_callable

    def clear_endpoint_overrides(self) -> None:
        """Clear all active endpoint overrides."""
        self._endpoint_overrides.clear()

    def expire_session(self, sid: str) -> None:
        """Manually mark a session as expired."""
        if sid in self.sessions:
            self.sessions[sid] = 0.0

    def invalidate_all_sessions(self) -> None:
        """Clear all active sessions."""
        self.sessions.clear()

    async def _handle_rpc(self, request: web.Request) -> web.Response:
        """Handle incoming POST /rpc JSON-RPC requests."""
        if self.rebooting:
            return web.Response(status=503, text="Router Rebooting")

        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                {
                    "jsonrpc": "2.0",
                    "id": 0,
                    "error": {"code": -32700, "message": "Parse error"},
                }
            )

        req_id = body.get("id", 0)
        method = body.get("method")
        params = body.get("params")

        # Optional delay simulation
        if self.simulate_delays:
            op_key = method
            if method == "call" and isinstance(params, list) and len(params) >= 3:
                op_key = f"{params[1]}.{params[2]}"
            delay = REAL_WORLD_TIMINGS.get(op_key, 0.01)
            await asyncio.sleep(delay)

        if method == "challenge":
            return web.json_response(self._handle_challenge(req_id, params))
        if method == "login":
            return web.json_response(self._handle_login(req_id, params))
        if method == "alive":
            return web.json_response(self._handle_alive(req_id, params))
        if method == "logout":
            return web.json_response(self._handle_logout(req_id, params))
        if method == "call":
            return web.json_response(self._handle_call(req_id, params))

        return web.json_response(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": "Method not found"},
            }
        )

    def _handle_challenge(self, req_id: Any, params: Any) -> dict[str, Any]:
        """Process challenge request."""
        _ = params
        self.last_salt = uuid.uuid4().hex[:8]
        self.last_nonce = uuid.uuid4().hex[:16]
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "alg": self.alg,
                "salt": self.last_salt,
                "nonce": self.last_nonce,
                "hash-method": self.hash_method,
            },
        }

    def _handle_login(self, req_id: Any, params: Any) -> dict[str, Any]:
        """Process login request with rate limiting."""
        now = time.time()
        if now < self.locked_until:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32003,
                    "message": "Login failed too many times, please try again in 5 minutes",
                },
            }

        username = params.get("username") if isinstance(params, dict) else ""
        received_hash = params.get("hash") if isinstance(params, dict) else ""

        # Compute expected hash
        expected_hash = GLinet._compute_hash(  # pylint: disable=protected-access
            alg=self.alg,
            salt=self.last_salt,
            nonce=self.last_nonce,
            hash_method=self.hash_method,
            username=self.username,
            password=self.password,
        )

        if username == self.username and received_hash == expected_hash:
            self.failed_login_count = 0
            sid = uuid.uuid4().hex
            self.sessions[sid] = now
            return {"jsonrpc": "2.0", "id": req_id, "result": {"sid": sid}}

        self.failed_login_count += 1
        if self.failed_login_count >= self.max_failed_logins:
            self.locked_until = now + self.lockout_duration
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32003,
                    "message": "Login failed too many times, please try again in 5 minutes",
                },
            }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32000, "message": "Access denied"},
        }

    def _handle_alive(self, req_id: Any, params: Any) -> dict[str, Any]:
        """Process session keep-alive."""
        sid = params.get("sid") if isinstance(params, dict) else None
        if sid in self.sessions:
            self.sessions[sid] = time.time()
        return {"jsonrpc": "2.0", "id": req_id, "result": None}

    def _handle_logout(self, req_id: Any, params: Any) -> dict[str, Any]:
        """Process session logout."""
        sid = params.get("sid") if isinstance(params, dict) else None
        if sid in self.sessions:
            del self.sessions[sid]
        return {"jsonrpc": "2.0", "id": req_id, "result": None}

    def _handle_call(self, req_id: Any, params: Any) -> dict[str, Any]:
        """Process authenticated JSON-RPC module call."""
        if not isinstance(params, list) or len(params) < 3:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": "Invalid params"},
            }

        sid = params[0]
        module = params[1]
        func = params[2]
        opt_args = params[3] if len(params) > 3 else {}

        # Validate session
        if sid is None:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": "Invalid params"},
            }

        now = time.time()
        if sid not in self.sessions:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": "Access denied"},
            }

        if self.token_ttl > 0 and (now - self.sessions[sid] > self.token_ttl):
            del self.sessions[sid]
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -1, "message": "Token doesn't exist or has expired"},
            }

        self.sessions[sid] = now

        # Check for test overrides
        override = self._endpoint_overrides.get((module, func))
        if override is not None:
            res = override(opt_args) if callable(override) else override
            return {"jsonrpc": "2.0", "id": req_id, "result": res}

        # Dispatch module calls
        result = self._dispatch_module(module, func, opt_args)
        if result is None:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": "Method not found"},
            }

        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def _dispatch_module(self, module: str, func: str, opt_args: Any) -> Any:
        """Dispatch module function to corresponding mock handler."""
        if module == "system":
            return self._dispatch_system(func, opt_args)
        if module == "wifi":
            return self._dispatch_wifi(func, opt_args)
        if module == "macclone":
            return self.macclone if func == "get_mac" else None
        if module == "clients":
            return self.clients if func == "get_list" else None
        if module == "lan":
            if func == "get_static_bind_list":
                return copy.deepcopy(self.lan_static)
            if func == "get_config_list":
                return copy.deepcopy(self.lan_config)
            return None
        if module == "edgerouter":
            return self.edgerouter if func == "get_status" else None
        if module == "diag":
            return self._dispatch_diag(func, opt_args)
        if module == "wg-client":
            return self._dispatch_wg_client(func, opt_args)
        if module == "vpn-client":
            return self._dispatch_vpn_client(func, opt_args)
        if module == "tailscale":
            return self._dispatch_tailscale(func, opt_args)
        if module == "modem":
            return self._dispatch_modem(func)
        if module == "ovpn-client":
            return self._dispatch_ovpn(func)
        if module == "repeater":
            return self._dispatch_repeater(func)
        if module == "cable":
            return self._dispatch_cable(func)
        if module == "dns":
            return self.dns_config if func == "get_config" else None
        if module == "tethering":
            return self.tethering_status if func == "get_status" else None
        if module == "adguardhome":
            return self.adguardhome if func in ("get_config", "get_status") else None
        if module == "switch-button":
            if func == "get_config":
                return {"func": self.switch_button.get("func", "none")}
            if func == "get_funcs":
                return {"funcs": copy.deepcopy(self.switch_button.get("funcs", []))}
            return None
        if module == "vpn-policy":
            return self._dispatch_vpn_policy(func)
        if module == "network":
            if func == "get_dhcp_leases":
                return copy.deepcopy(self.dhcp_leases)
            if func == "get_arp_list":
                return copy.deepcopy(self.arp_list)
            return None
        if module == "firewall":
            if func == "get_wan_access":
                return copy.deepcopy(self.firewall_wan_access)
            if func == "get_zone_list":
                return copy.deepcopy(self.firewall_zones)
            return None
        if module == "led":
            return copy.deepcopy(self.led_config) if func == "get_config" else None
        if module == "ddns":
            if func == "get_config":
                return copy.deepcopy(self.ddns_config)
            if func == "get_status":
                return copy.deepcopy(self.ddns_status)
            return None
        return None

    def _dispatch_system(self, func: str, opt_args: Any) -> Any:
        """Handle system module calls."""
        if func == "get_info":
            return copy.deepcopy(self.system_info)
        if func == "get_status":
            return copy.deepcopy(self.system_status)
        if func == "get_load":
            return copy.deepcopy(self.system_load)
        if func == "reboot":
            delay = opt_args.get("delay", 0) if isinstance(opt_args, dict) else 0
            task = asyncio.create_task(self._simulate_reboot())
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
            return {"delay": delay}
        return None

    async def _simulate_reboot(self) -> None:
        """Simulate router downtime and session invalidation upon reboot."""
        self.rebooting = True
        await asyncio.sleep(self.reboot_duration)
        self.invalidate_all_sessions()
        self.rebooting = False

    def _dispatch_wifi(self, func: str, opt_args: Any) -> Any:
        """Handle wifi module calls with in-memory state toggle."""
        if func == "get_config":
            return copy.deepcopy(self.wifi_config)
        if func == "set_config":
            if isinstance(opt_args, dict):
                iface_name = opt_args.get("iface_name")
                enabled = opt_args.get("enabled", True)
                for dev in self.wifi_config.get("res", []):
                    for iface in dev.get("ifaces", []):
                        if iface.get("name") == iface_name:
                            iface["enabled"] = enabled
            return {}
        return None

    @staticmethod
    def _dispatch_diag(func: str, opt_args: Any) -> Any:
        """Handle diagnostic ping."""
        if func != "ping":
            return None
        addr = opt_args.get("addr", "") if isinstance(opt_args, dict) else ""
        if addr in ("0.0.0.1", "unreachable"):
            return []
        return [
            f"PING {addr} 56(84) bytes of data.",
            f"64 bytes from {addr}: icmp_seq=1 ttl=116 time=12.3 ms",
        ]

    def _dispatch_wg_client(self, func: str, opt_args: Any) -> Any:
        """Handle WireGuard client calls."""
        if func == "get_all_config_list":
            return copy.deepcopy(self.wireguard_config)
        if func == "get_status":
            return copy.deepcopy(self.wireguard_status)
        if func == "start":
            peer_id = (
                opt_args.get("peer_id", 2001) if isinstance(opt_args, dict) else 2001
            )
            self.wireguard_status["status"] = 1
            self.wireguard_status["enabled"] = True
            self.wireguard_status["peer_id"] = peer_id
            self.wireguard_status["tunnel_id"] = peer_id
            if self.vpn_client_status.get("status_list"):
                self.vpn_client_status["status_list"][0]["status"] = 1
                self.vpn_client_status["status_list"][0]["enabled"] = True
            return []
        if func == "stop":
            self.wireguard_status["status"] = 0
            self.wireguard_status["enabled"] = False
            if self.vpn_client_status.get("status_list"):
                self.vpn_client_status["status_list"][0]["status"] = 0
                self.vpn_client_status["status_list"][0]["enabled"] = False
            return []
        return None

    def _dispatch_vpn_client(self, func: str, opt_args: Any) -> Any:
        """Handle >=4.8 unified VPN client calls."""
        if func == "get_status":
            return copy.deepcopy(self.vpn_client_status)
        if func == "set_tunnel":
            tunnel_id = (
                opt_args.get("tunnel_id", 2001) if isinstance(opt_args, dict) else 2001
            )
            enabled = (
                opt_args.get("enabled", True) if isinstance(opt_args, dict) else True
            )
            for tunnel in self.vpn_client_status.get("status_list", []):
                if tunnel.get("tunnel_id") == tunnel_id:
                    tunnel["enabled"] = enabled
                    tunnel["status"] = 1 if enabled else 0
            return {"tunnel_id": tunnel_id}
        return None

    def _dispatch_tailscale(self, func: str, opt_args: Any) -> Any:
        """Handle Tailscale calls."""
        if func == "get_config":
            return copy.deepcopy(self.tailscale_config)
        if func == "set_config":
            if isinstance(opt_args, dict):
                self.tailscale_config.update(opt_args)
                if opt_args.get("enabled") is True:
                    self.tailscale_status = copy.deepcopy(
                        self._initial_tailscale_status
                    )
                elif opt_args.get("enabled") is False:
                    self.tailscale_status = []
            return {}
        if func == "get_status":
            return copy.deepcopy(self.tailscale_status)
        if func == "get_exit_node_list":
            return copy.deepcopy(self.tailscale_exit_nodes)
        if func == "get_auth_url":
            return []
        return None

    def _dispatch_modem(self, func: str) -> Any:
        """Handle modem calls."""
        if func == "get_info":
            return copy.deepcopy(self.modem_info)
        if func == "get_sim_info":
            return copy.deepcopy(self.modem_sim)
        if func == "get_sim_signal":
            return copy.deepcopy(self.modem_sim_signal)
        return None

    def _dispatch_ovpn(self, func: str) -> Any:
        """Handle OpenVPN calls."""
        if func == "get_all_config_list":
            return copy.deepcopy(self.ovpn_config)
        if func == "get_status":
            return copy.deepcopy(self.ovpn_status)
        return None

    def _dispatch_repeater(self, func: str) -> Any:
        """Handle repeater calls."""
        if func == "get_status":
            return copy.deepcopy(self.repeater_status)
        if func == "scan":
            return copy.deepcopy(self.repeater_scan)
        if func == "get_config":
            return copy.deepcopy(self.repeater_config)
        return None

    def _dispatch_cable(self, func: str) -> Any:
        """Handle cable calls."""
        if func == "get_status":
            return copy.deepcopy(self.cable_status)
        if func == "get_config":
            return {"protocol": "dhcp"}
        return None

    def _dispatch_vpn_policy(self, func: str) -> Any:
        """Handle vpn-policy calls."""
        if func == "get_domain_policy":
            return copy.deepcopy(self.vpn_policy.get("domain_policy"))
        if func == "get_global_policy":
            return copy.deepcopy(self.vpn_policy.get("global_policy"))
        if func == "get_mac_policy":
            return copy.deepcopy(self.vpn_policy.get("mac_policy"))
        if func == "get_proxy_mode":
            return copy.deepcopy(self.vpn_policy.get("proxy_mode"))
        if func == "get_vlan_policy":
            return copy.deepcopy(self.vpn_policy.get("vlan_policy"))
        return None


class MockRouterServer:
    """Threaded manager for MockRouter to operate independently of pytest loop scope."""

    def __init__(self, **router_kwargs: Any) -> None:
        """Initialize threaded mock server with router configuration."""
        self.router = MockRouter(**router_kwargs)
        self.thread: threading.Thread | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self._ready = threading.Event()

    @property
    def url(self) -> str:
        """Return the mock server URL."""
        return self.router.url

    def _run_server(self) -> None:
        """Run the asyncio event loop inside the dedicated server thread."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.router.start())
        self._ready.set()
        self.loop.run_forever()

    def start(self) -> "MockRouterServer":
        """Start mock server thread and block until TCP socket is listening."""
        self.thread = threading.Thread(target=self._run_server, daemon=True)
        self.thread.start()
        self._ready.wait(timeout=5.0)
        return self

    def stop(self) -> None:
        """Stop mock server and shut down server loop cleanly."""
        if self.loop is not None and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.router.stop(), self.loop).result(
                timeout=5.0
            )
            self.loop.call_soon_threadsafe(self.loop.stop)
            if self.thread is not None:
                self.thread.join(timeout=2.0)
        self.loop = None
        self.thread = None

    def __enter__(self) -> "MockRouterServer":
        """Synchronous context manager entry."""
        return self.start()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Synchronous context manager exit."""
        self.stop()
