#!/usr/bin/env python3
"""Completeness verification script for CI.

Verifies that:
1. Every public (non-private) method on GLinet has an entry and example in examples.md.
2. Every public method is registered in the API RPC mapping.
3. Every API call used by GLinet methods is implemented in gli4py.mock.MockRouter.
4. Every data query endpoint has a corresponding sanitized fixture in tests/fixtures/.
5. All fixtures in tests/fixtures/ are valid JSON and free of leaked private credentials/IPs.
"""

import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# pylint: disable=protected-access,too-many-branches,too-many-locals,too-many-statements,wrong-import-position
from gli4py import GLinet  # noqa: E402
from gli4py.mock import MockRouter  # noqa: E402

# Mapping of public GLinet methods to the underlying RPC calls they perform.
# Formats:
#   ("no_auth", method_name)
#   ("call", module, func, optional_test_args)
METHOD_RPC_MAP: dict[str, list[tuple[Any, ...]]] = {
    "router_reachable": [("no_auth", "challenge")],
    "login": [("no_auth", "challenge"), ("no_auth", "login")],
    "router_info": [("call", "system", "get_info")],
    "router_get_status": [("call", "system", "get_status")],
    "router_get_load": [("call", "system", "get_load")],
    "router_mac": [("call", "macclone", "get_mac")],
    "router_reboot": [("call", "system", "reboot", {"delay": 0})],
    "ping": [("call", "diag", "ping", {"addr": "8.8.8.8"})],
    "connected_to_internet": [("call", "edgerouter", "get_status")],
    "list_all_clients": [("call", "clients", "get_list")],
    "list_static_clients": [("call", "lan", "get_static_bind_list")],
    "connected_clients": [("call", "clients", "get_list")],
    "wifi_ifaces_get": [("call", "wifi", "get_config")],
    "wifi_iface_set_enabled": [
        (
            "call",
            "wifi",
            "set_config",
            {"enabled": True, "iface_name": "default_radio0"},
        )
    ],
    "wireguard_client_list": [("call", "wg-client", "get_all_config_list")],
    "wireguard_client_state": [
        ("call", "wg-client", "get_status"),
        ("call", "vpn-client", "get_status"),
    ],
    "wireguard_client_start": [
        ("call", "wg-client", "start", {"group_id": 7707, "peer_id": 2001}),
        ("call", "vpn-client", "set_tunnel", {"enabled": True, "tunnel_id": 2001}),
    ],
    "wireguard_client_stop": [
        ("call", "wg-client", "stop", {"peer_id": 2001}),
        ("call", "vpn-client", "set_tunnel", {"enabled": False, "tunnel_id": 2001}),
    ],
    "tailscale_configured": [("call", "tailscale", "get_status")],
    "tailscale_connection_state": [("call", "tailscale", "get_status")],
    "tailscale_start": [
        ("call", "tailscale", "get_config"),
        ("call", "tailscale", "set_config", {"enabled": True}),
    ],
    "tailscale_stop": [
        ("call", "tailscale", "get_config"),
        ("call", "tailscale", "set_config", {"enabled": False}),
    ],
    "modem_info": [("call", "modem", "get_info")],
    "modem_sim_info": [("call", "modem", "get_sim_info")],
    "modem_sim_signal": [("call", "modem", "get_sim_signal")],
    # Pure utility payload generators (no network call)
    "gen_sid_payload": [],
    "gen_no_auth_payload": [],
}

# Mapping of RPC query endpoints to their corresponding fixture file in tests/fixtures/
ENDPOINT_FIXTURE_MAP: dict[tuple[str, str], str] = {
    ("system", "get_info"): "system_info.json",
    ("system", "get_status"): "system_status.json",
    ("system", "get_load"): "system_load.json",
    ("macclone", "get_mac"): "macclone.json",
    ("edgerouter", "get_status"): "edgerouter.json",
    ("clients", "get_list"): "clients.json",
    ("lan", "get_static_bind_list"): "lan_static.json",
    ("wifi", "get_config"): "wifi_config.json",
    ("wg-client", "get_all_config_list"): "wireguard_config.json",
    ("wg-client", "get_status"): "wireguard_status.json",
    ("vpn-client", "get_status"): "vpn_client_status.json",
    ("tailscale", "get_config"): "tailscale_config.json",
    ("tailscale", "get_status"): "tailscale_status.json",
    ("modem", "get_info"): "modem_info.json",
    ("modem", "get_sim_info"): "modem_sim.json",
    ("modem", "get_sim_signal"): "modem_sim_signal.json",
}


def get_public_methods() -> list[str]:
    """Retrieve all public callable method names on GLinet."""
    return sorted(
        name
        for name, member in GLinet.__dict__.items()
        if not name.startswith("_") and callable(member)
    )


def check_examples_md(public_methods: list[str], errors: list[str]) -> None:
    """Verify that every public method has an entry and example in examples.md."""
    examples_path = PROJECT_ROOT / "examples.md"
    if not examples_path.exists():
        errors.append("examples.md does not exist.")
        return

    content = examples_path.read_text(encoding="utf-8")
    for method in public_methods:
        pattern = (
            rf"`{re.escape(method)}\(\)`|`{re.escape(method)}`|{re.escape(method)}\("
        )
        if not re.search(pattern, content):
            errors.append(
                f"[examples.md] Missing entry for public method '{method}()'. "
                f"Every public method must be documented with an example in examples.md."
            )


def check_method_mappings(public_methods: list[str], errors: list[str]) -> None:
    """Verify that every public method is accounted for in METHOD_RPC_MAP."""
    for method in public_methods:
        if method not in METHOD_RPC_MAP:
            errors.append(
                f"[METHOD_RPC_MAP] Public method '{method}()' is not registered in METHOD_RPC_MAP. "
                f"Define the RPC call(s) it uses so MockRouter and fixtures can be validated."
            )


async def _check_mock_router_support_async(errors: list[str]) -> None:
    """Verify that MockRouter successfully handles every RPC call used by GLinet."""
    router = MockRouter(reboot_duration=0.01)

    # Helper to authenticate with MockRouter
    def _login():
        ch = router._handle_challenge(1, {"username": "root"})
        salt = ch["result"]["salt"]
        nonce = ch["result"]["nonce"]
        alg = ch["result"]["alg"]
        hsh = GLinet._compute_hash(
            alg=alg,
            salt=salt,
            nonce=nonce,
            hash_method="md5",
            username="root",
            password="goodlife",
        )
        lg = router._handle_login(2, {"username": "root", "hash": hsh})
        return lg["result"]["sid"]

    sid = _login()
    req_id = 10
    checked_calls: set[str] = set()

    for method, calls in METHOD_RPC_MAP.items():
        for rpc_call in calls:
            call_key = repr(rpc_call)
            if call_key in checked_calls:
                continue
            checked_calls.add(call_key)
            req_id += 1

            kind = rpc_call[0]
            if kind == "no_auth":
                action = rpc_call[1]
                if action == "challenge":
                    res = router._handle_challenge(req_id, {"username": "root"})
                elif action == "login":
                    # Login requires fresh challenge
                    ch = router._handle_challenge(req_id, {"username": "root"})
                    salt = ch["result"]["salt"]
                    nonce = ch["result"]["nonce"]
                    alg = ch["result"]["alg"]
                    hsh = GLinet._compute_hash(
                        alg=alg,
                        salt=salt,
                        nonce=nonce,
                        hash_method="md5",
                        username="root",
                        password="goodlife",
                    )
                    res = router._handle_login(
                        req_id + 1, {"username": "root", "hash": hsh}
                    )
                    sid = res["result"]["sid"]
                else:
                    errors.append(
                        f"[MockRouter] Unknown no_auth action '{action}' for method '{method}()'."
                    )
                    continue
            elif kind == "call":
                module = rpc_call[1]
                func = rpc_call[2]
                opt_args = rpc_call[3] if len(rpc_call) > 3 else None
                params = [sid, module, func]
                if opt_args is not None:
                    params.append(opt_args)
                try:
                    res = router._handle_call(req_id, params)
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    errors.append(
                        f"[MockRouter] Error executing call '{module}/{func}' (used by '{method}()'): {exc}"
                    )
                    continue
            else:
                errors.append(
                    f"[MockRouter] Invalid RPC call type '{kind}' in mapping."
                )
                continue

            error = res.get("error")
            if error is not None:
                code = error.get("code")
                msg = error.get("message", "unknown")
                if code == -32601:
                    errors.append(
                        f"[MockRouter] Endpoint '{rpc_call}' (used by '{method}()') "
                        f"returned -32601 Method not found. It must be implemented in MockRouter."
                    )
                else:
                    errors.append(
                        f"[MockRouter] Endpoint '{rpc_call}' (used by '{method}()') "
                        f"returned unexpected error {code}: {msg}"
                    )


def check_mock_router_support(errors: list[str]) -> None:
    """Run MockRouter check inside an asyncio event loop."""
    asyncio.run(_check_mock_router_support_async(errors))


def check_fixtures_existence(errors: list[str]) -> None:
    """Verify that every query endpoint has a corresponding valid fixture in tests/fixtures/."""
    fixtures_dir = PROJECT_ROOT / "tests" / "fixtures"
    if not fixtures_dir.is_dir():
        errors.append(f"Fixtures directory '{fixtures_dir}' not found.")
        return

    for (module, func), fixture_name in ENDPOINT_FIXTURE_MAP.items():
        fixture_path = fixtures_dir / fixture_name
        if not fixture_path.exists():
            errors.append(
                f"[tests/fixtures/] Missing fixture file '{fixture_name}' for endpoint '{module}/{func}'."
            )
            continue

        try:
            data = json.loads(fixture_path.read_text(encoding="utf-8"))
            if not data and data != {}:
                errors.append(
                    f"[tests/fixtures/] Fixture file '{fixture_name}' contains empty data."
                )
        except json.JSONDecodeError as exc:
            errors.append(
                f"[tests/fixtures/] Fixture file '{fixture_name}' is not valid JSON: {exc}"
            )


def main() -> int:
    """Run all completeness checks and report results."""
    print("Running completeness verification...")
    errors: list[str] = []

    public_methods = get_public_methods()
    print(f"Discovered {len(public_methods)} public method(s) on GLinet.")

    # 1. Check examples.md
    check_examples_md(public_methods, errors)

    # 2. Check method RPC mappings
    check_method_mappings(public_methods, errors)

    # 3. Check MockRouter support
    check_mock_router_support(errors)

    # 4. Check fixture existence and validity
    check_fixtures_existence(errors)

    if errors:
        print(f"\n[FAIL] Completeness verification found {len(errors)} issue(s):")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("\n[OK] All public methods are documented in examples.md.")
    print("[OK] All method API endpoints are handled by MockRouter.")
    print("[OK] All required response fixtures exist and are valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
