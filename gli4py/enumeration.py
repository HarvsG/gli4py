#!/usr/bin/env python3
# pylint: disable=too-many-lines
"""GL.iNet Router API Enumeration Script.

Probes a GL.iNet router to discover which API modules and methods are
supported by the device's firmware. Produces a JSON report that can be
contributed to build a model→feature-set registry.

Usage:
    python3 enumeration.py --url 192.168.8.1 --password your_password
    python3 enumeration.py --url 192.168.8.1 -p your_password --module system
    python3 enumeration.py --url 192.168.8.1 -p your_password --endpoint system.get_info
    python3 enumeration.py --url 192.168.8.1 -p your_password --output report.json
    python3 enumeration.py --url 192.168.8.1 -p your_password --no-read-only
    python3 enumeration.py --url 192.168.8.1 -p your_password --disable-deep-redact
"""

import argparse
import asyncio
import getpass
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from uplink import AiohttpClient

from gli4py.glinet import GLinet
from gli4py.helpers import normalize_url

# Workarounds for older GL.iNet firmware and uplink deallocator during standalone script execution
try:
    from aiohttp import client_proto, http_parser

    client_proto.HttpResponseParser = http_parser.HttpResponseParserPy  # type: ignore[misc]
    http_parser.SINGLETON_HEADERS = frozenset(  # type: ignore[misc]
        h for h in http_parser.SINGLETON_HEADERS if h != "content-type"
    )
except (ImportError, AttributeError):
    pass

# Suppress bug in uplink's AiohttpClient.__del__ during Python shutdown
AiohttpClient.__del__ = lambda self: None

# ─── Complete API registry from GL.iNet SDK 4.0 API-DOCS.html ───
# Each module maps to a list of (method, is_safe_to_modify) tuples.

API_REGISTRY: dict[str, list[tuple[str, bool]]] = {
    "acl": [
        ("add_group", False),
        ("add_acl", False),
        ("add_user", False),
        ("remove_group", False),
        ("remove_acl", False),
        ("remove_user", False),
        ("get_group_list", True),
        ("get_acl_list", True),
    ],
    "adguardhome": [
        ("get_config", True),
        ("set_config", False),
    ],
    "bark": [
        ("get_status", True),
        ("get_config", True),
        ("set_config", False),
        ("logout", False),
    ],
    "black_white_list": [
        ("get_config", True),
        ("set_single_mac", False),
        ("set_config", False),
    ],
    "cable": [
        ("set_config", False),
        ("change_interface", False),
        ("get_status", True),
        ("get_config", True),
    ],
    "clients": [
        ("get_list", True),
        ("remove_offline", False),
        ("block_client", False),
        ("get_status", True),
        ("set_info", False),
        ("clean_traffic", False),
    ],
    "cloud": [
        ("bind_info", True),
        ("get_batch_config", True),
        ("get_config", True),
        ("set_batch_config", False),
        ("set_config", False),
        ("unbind", False),
    ],
    "cloud-batch-manage": [
        ("bind_info", True),
        ("designated_customer", False),
        ("get_2b_config", True),
        ("get_batch_config", True),
        ("send_router_info", False),
        ("set_2b_config", False),
        ("set_batch_config", False),
    ],
    "ddns": [
        ("get_config", True),
        ("get_status", True),
        ("set_config", False),
    ],
    "diag": [
        ("ping", True),
        ("traceroute", True),
    ],
    "dlna": [
        ("get_config", True),
        ("set_config", False),
    ],
    "dns": [
        ("get_config", True),
        ("get_host", True),
        ("get_info", True),
        ("set_config", False),
        ("set_host", False),
    ],
    "edgerouter": [
        ("get_config", True),
        ("get_status", True),
        ("set_config", False),
    ],
    "fan": [
        ("get_config", True),
        ("get_status", True),
        ("set_config", False),
        ("set_test", False),
    ],
    "firewall": [
        ("add_port_forward", False),
        ("add_rule", False),
        ("get_dmz", True),
        ("get_port_forward_list", True),
        ("get_rule_list", True),
        ("get_wan_access", True),
        ("get_zone_list", True),
        ("remove_port_forward", False),
        ("remove_rule", False),
        ("set_dmz", False),
        ("set_port_forward", False),
        ("set_rule", False),
        ("set_wan_access", False),
    ],
    "igmp": [
        ("get_config", True),
        ("set_config", False),
    ],
    "ipv6": [
        ("get_ipv6", True),
        ("set_ipv6", False),
    ],
    "kmwan": [
        ("get_config", True),
        ("get_status", True),
        ("set_config", False),
        ("set_interface", False),
        ("set_sensitivity", False),
    ],
    "lan": [
        ("add_static_bind", False),
        ("get_config_list", True),
        ("get_static_bind_list", True),
        ("remove_static_bind", False),
        ("set_config", False),
        ("set_static_bind", False),
    ],
    "led": [
        ("get_config", True),
        ("set_config", False),
    ],
    "local-access": [
        ("get_config", True),
        ("set_config", False),
    ],
    "logread": [
        ("export_logs", True),
        ("get_config", True),
        ("get_crash_log", True),
        ("get_kernel_log", True),
        ("get_nginx_log", True),
        ("get_system_log", True),
        ("remove_crash_log", False),
        ("set_config", False),
    ],
    "macclone": [
        ("get_mac", True),
        ("set_mac", False),
    ],
    "mcu": [
        ("get_battery_config", True),
        ("get_oled_config", True),
        ("set_battery_config", False),
        ("set_oled_config", False),
    ],
    "modem": [
        ("disconnect", False),
        ("get_cell_tower", True),
        ("get_cells_info", True),
        ("get_config", True),
        ("get_debug_msg", True),
        ("get_info", True),
        ("get_name", True),
        ("get_profile_list", True),
        ("get_signals", True),
        ("get_sim_info", True),
        ("get_sim_signal", True),
        ("get_slot_config", True),
        ("get_sms_list", True),
        ("get_status", True),
        ("get_traffic_config", True),
        ("reboot_modem", False),
        ("remove_profile", False),
        ("remove_sms", False),
        ("reset_traffic_count", False),
        ("scan_cell_tower", False),
        ("send_at_command", False),
        ("send_sms", False),
        ("set_auto_connect", False),
        ("set_cell_tower", False),
        ("set_connect", False),
        ("set_slot_config", False),
        ("set_sms", False),
        ("set_traffic_auto_save", False),
        ("set_upgrade", False),
    ],
    "mwan3": [
        ("get_config", True),
        ("get_status", True),
        ("set_config", False),
        ("set_interface", False),
    ],
    "nas-web": [
        ("add_share", False),
        ("add_user", False),
        ("eject_disk", False),
        ("get_disk_list", True),
        ("get_file_list", True),
        ("get_nas_ser", True),
        ("get_proto_config", True),
        ("get_share_list", True),
        ("get_status", True),
        ("get_user_list", True),
        ("remove_share", False),
        ("remove_user", False),
        ("set_nas_ser", False),
        ("set_proto_config", False),
        ("set_share", False),
        ("set_user_pwd", False),
        ("start", False),
    ],
    "netmode": [
        ("get_mode", True),
        ("set_mode", False),
    ],
    "network": [
        ("check_wan_cable", True),
        ("get_arp_list", True),
        ("get_dhcp_leases", True),
        ("get_hwnat_config", True),
        ("get_netnat_config", True),
        ("routes", True),
        ("routes6", True),
        ("set_hwnat_config", False),
        ("set_netnat_config", False),
    ],
    "otbr": [
        ("add_joiner", False),
        ("export_joiner_list", True),
        ("export_network_data", True),
        ("export_thread_network", True),
        ("generate_thread_network", False),
        ("get_bbr_status", True),
        ("get_joiner_list", True),
        ("get_neighbor_list", True),
        ("get_network_data", True),
        ("get_srp_server_config", True),
        ("get_srp_server_service", True),
        ("get_status", True),
        ("import_joiner_list", False),
        ("import_thread_network", False),
        ("join", False),
        ("rejoin_all", False),
        ("remove_joiner_list", False),
        ("scan", True),
        ("set_bbr_config", False),
        ("set_commissioning", False),
        ("set_config", False),
        ("set_srp_server_config", False),
        ("set_txpower", False),
        ("start", False),
        ("stop", False),
    ],
    "ovpn-client": [
        ("add_config", False),
        ("add_group", False),
        ("add_route", False),
        ("check_config", True),
        ("clear_config_list", False),
        ("confirm_config", False),
        ("get_all_config_list", True),
        ("get_config_list", True),
        ("get_group_list", True),
        ("get_recommend_config", True),
        ("get_route_list", True),
        ("get_setting", True),
        ("get_status", True),
        ("get_third_config", True),
        ("remove_config", False),
        ("remove_group", False),
        ("remove_route", False),
        ("set_config", False),
        ("set_group", False),
        ("set_route", False),
        ("set_setting", False),
        ("start", False),
        ("stop", False),
    ],
    "ovpn-server": [
        ("add_route", False),
        ("add_user", False),
        ("export_config", True),
        ("generate_certificate", False),
        ("get_config", True),
        ("get_route_list", True),
        ("get_setting", True),
        ("get_status", True),
        ("get_user_list", True),
        ("remove_route", False),
        ("remove_user", False),
        ("set_config", False),
        ("set_route", False),
        ("set_setting", False),
        ("start", False),
        ("stop", False),
    ],
    "parental-control": [
        ("add_group", False),
        ("add_rule", False),
        ("get_app_list", True),
        ("get_brief", True),
        ("get_config", True),
        ("get_status", True),
        ("remove_group", False),
        ("remove_rule", False),
        ("set_brief", False),
        ("set_config", False),
        ("set_group", False),
        ("set_rule", False),
        ("update", False),
    ],
    "plugins": [
        ("get_config", True),
        ("get_list", True),
        ("get_package_info", True),
        ("get_repository_status", True),
        ("install_package", False),
        ("remove_package", False),
        ("set_config", False),
        ("update_repository", False),
    ],
    "qos": [
        ("add_device_group", False),
        ("delete_device_group", False),
        ("enable_qos", False),
        ("get_bandwidth_config", True),
        ("get_channel_bandwidth_ratio", True),
        ("get_client_list", True),
        ("get_config", True),
        ("get_device_group", True),
        ("modify_device_group", False),
        ("remove_speed_limit_rule", False),
        ("set_bandwidth_config", False),
        ("set_channel_bandwidth_ratio", False),
        ("set_config", False),
        ("set_default_priority", False),
        ("set_model", False),
        ("set_other_client_priority", False),
        ("set_packet_priority", False),
        ("set_speed_limit_rule", False),
        ("set_work_mode", False),
    ],
    "reboot": [
        ("get_config", True),
        ("set_config", False),
    ],
    "repeater": [
        ("connect", False),
        ("disconnect", False),
        ("get_config", True),
        ("get_saved_ap_list", True),
        ("get_status", True),
        ("remove_saved_ap", False),
        ("scan", True),
        ("set_config", False),
    ],
    "rs485": [
        ("debug_mqtt", False),
        ("debug_socket", False),
        ("get_config", True),
        ("get_connect_status", True),
        ("get_forward_config", True),
        ("get_forward_log", True),
        ("get_tcp_clients", True),
        ("glcould_tool", False),
        ("read_modbus_data", True),
        ("set_config", False),
        ("set_forward_config", False),
        ("terminal", False),
        ("write_modbus_data", False),
    ],
    "rtty": [
        ("get_config", True),
        ("run", False),
        ("set_config", False),
        ("stop", False),
    ],
    "s2s": [
        ("enable_echo_server", False),
        ("generate_wg_genkey", False),
        ("get_status", True),
        ("remove_config", False),
        ("set_config", False),
        ("start_wg", False),
        ("stop_wg", False),
    ],
    "samba": [
        ("get_config", True),
        ("set_config", False),
    ],
    "sms-forward": [
        ("get_config", True),
        ("set_email", False),
        ("set_phone_number", False),
    ],
    "switch-button": [
        ("get_config", True),
        ("get_funcs", True),
        ("set_config", False),
    ],
    "system": [
        ("add_user", False),
        ("disk_info", True),
        ("get_httpd_mem_status", True),
        ("get_info", True),
        ("get_load", True),
        ("get_security_policy", True),
        ("get_status", True),
        ("get_timezone_config", True),
        ("get_unixtime", True),
        ("reboot", False),
        ("remove_user", False),
        ("reset_firmware", False),
        ("set_password", False),
        ("set_security_policy", False),
        ("set_timezone_config", False),
    ],
    "tailscale": [
        ("get_auth_url", True),
        ("get_config", True),
        ("get_exit_node_list", True),
        ("get_status", True),
        ("logout", False),
        ("set_config", False),
    ],
    "tethering": [
        ("disconnect", False),
        ("get_status", True),
        ("set_connect", False),
    ],
    "timer": [
        ("get_disk", True),
        ("get_led", True),
        ("get_reboot", True),
        ("get_wifi", True),
        ("set_disk", False),
        ("set_led", False),
        ("set_reboot", False),
        ("set_wifi", False),
    ],
    "tor": [
        ("get_config", True),
        ("get_status", True),
        ("set_config", False),
    ],
    "ui": [
        ("check_initialized", True),
        ("get_lang", True),
        ("get_menu_list", True),
        ("init", False),
        ("load_locales", True),
        ("set_lang", False),
    ],
    "upgrade": [
        ("check_firmware_local", True),
        ("check_firmware_online", True),
        ("get_config", True),
        ("get_online_upgrade_status", True),
        ("upgrade_local", False),
        ("upgrade_online", False),
        ("set_config", False),
    ],
    "vpn-client": [
        ("get_status", True),
        ("set_tunnel", False),
    ],
    "vpn-policy": [
        ("get_domain_policy", True),
        ("get_global_policy", True),
        ("get_mac_policy", True),
        ("get_proxy_mode", True),
        ("get_vlan_policy", True),
        ("set_domain_policy", False),
        ("set_global_policy", False),
        ("set_mac_policy", False),
        ("set_proxy_mode", False),
        ("set_vlan_policy", False),
    ],
    "wg-client": [
        ("add_config", False),
        ("add_group", False),
        ("add_route", False),
        ("check_config", True),
        ("clear_config_list", False),
        ("confirm_config", False),
        ("get_all_config_list", True),
        ("get_config_list", True),
        ("get_group_list", True),
        ("get_recommend_config", True),
        ("get_route_list", True),
        ("get_setting", True),
        ("get_status", True),
        ("get_third_config", True),
        ("remove_config", False),
        ("remove_group", False),
        ("remove_route", False),
        ("set_config", False),
        ("set_group", False),
        ("set_proxy", False),
        ("set_route", False),
        ("set_setting", False),
        ("start", False),
        ("stop", False),
    ],
    "wg-server": [
        ("add_peer", False),
        ("add_route", False),
        ("generate_key", False),
        ("generate_peer", False),
        ("generate_publickey", False),
        ("get_config", True),
        ("get_peer_list", True),
        ("get_route_list", True),
        ("get_setting", True),
        ("get_status", True),
        ("remove_peer", False),
        ("remove_route", False),
        ("set_config", False),
        ("set_peer", False),
        ("set_route", False),
        ("set_setting", False),
        ("start", False),
        ("stop", False),
    ],
    "wifi": [
        ("get_config", True),
        ("get_status", True),
        ("set_config", False),
        ("set_txpower", False),
    ],
    "zerotier": [
        ("get_config", True),
        ("get_status", True),
        ("set_config", False),
    ],
}


_SENSITIVE_KEYS = frozenset(
    {
        "key",
        "passwd",
        "password",
        "sid",
        "nonce",
        "salt",
        "hash",
        "sn",
        "sn_bak",
        "ddns",
        "login_name",
        "address_v4",
        "ip",
    }
)


def _redact_ip_val(val: object) -> object:
    """Helper to partially redact IPs and lists of IPs."""
    if isinstance(val, str):
        if "." in val:
            parts = val.split(".")
            return f"{parts[0]}.{parts[1]}.*.*" if len(parts) == 4 else "***"
        if ":" in val:
            parts = val.split(":")
            return f"{parts[0]}:{parts[1]}::*" if len(parts) >= 3 else "***"
        return "***"
    if isinstance(val, list):
        return [_redact_ip_val(i) for i in val]
    return "***"


def _redact(obj: object, deep_redact: bool = True) -> object:
    """Recursively redact sensitive values."""
    if isinstance(obj, dict):
        res: dict[Any, Any] = {}
        for k, v in obj.items():
            if deep_redact:
                if k in ("last_tx", "last_rx"):
                    res[k] = ["***"] if isinstance(v, list) else "***"
                elif k in ("mac", "bssid") and isinstance(v, str):
                    parts = v.split(":")
                    res[k] = (
                        f"{parts[0]}:{parts[1]}:{parts[2]}:**:**:**"
                        if len(parts) == 6
                        else "***"
                    )
                elif k in ("ip", "address_v4", "gateway", "dns"):
                    res[k] = _redact_ip_val(v)
                elif k == "ssid" and isinstance(v, str):
                    res[k] = f"{v[:2]}***" if len(v) > 2 else "***"
                elif k in _SENSITIVE_KEYS:
                    res[k] = "***"
                else:
                    res[k] = _redact(v, deep_redact)
            else:
                if k in _SENSITIVE_KEYS:
                    res[k] = "***"
                else:
                    res[k] = _redact(v, deep_redact)
        return res
    if isinstance(obj, list):
        return [_redact(item, deep_redact) for item in obj]
    return obj


def _split_args(values: list[str] | None) -> list[str] | None:
    """Split comma-separated CLI argument values into a clean list."""
    if not values:
        return None
    result: list[str] = []
    for item in values:
        for part in item.split(","):
            part = part.strip()
            if part:
                result.append(part)
    return result or None


# pylint: disable=too-many-nested-blocks
def filter_registry(
    registry: dict[str, list[tuple[str, bool]]],
    *,
    modules: list[str] | None = None,
    methods: list[str] | None = None,
    endpoints: list[str] | None = None,
) -> dict[str, list[tuple[str, bool]]]:
    """Filter API registry by modules, methods, and/or specific endpoints."""
    targets: dict[str, list[tuple[str, bool]]] = {}

    if endpoints:
        for ep in endpoints:
            ep = ep.replace("/", ".")
            if "." not in ep:
                continue
            mod, meth = ep.split(".", 1)
            is_safe = True
            if mod in registry:
                for reg_meth, reg_safe in registry[mod]:
                    if reg_meth == meth:
                        is_safe = reg_safe
                        break
                else:
                    is_safe = meth.startswith(
                        ("get_", "is_", "check_", "list_", "ping", "status", "info")
                    )
            else:
                is_safe = meth.startswith(
                    ("get_", "is_", "check_", "list_", "ping", "status", "info")
                )

            if mod not in targets:
                targets[mod] = []
            if not any(m == meth for m, _ in targets[mod]):
                targets[mod].append((meth, is_safe))

    if modules or methods:
        target_mods = set(modules) if modules else set(registry.keys())
        target_meths = set(methods) if methods else None

        for mod in target_mods:
            if mod in registry:
                matching_methods = [
                    (meth, is_safe)
                    for meth, is_safe in registry[mod]
                    if target_meths is None or meth in target_meths
                ]
                if matching_methods:
                    if mod not in targets:
                        targets[mod] = []
                    for item in matching_methods:
                        if not any(m == item[0] for m, _ in targets[mod]):
                            targets[mod].append(item)
            else:
                if target_meths:
                    if mod not in targets:
                        targets[mod] = []
                    for meth in target_meths:
                        is_safe = meth.startswith(
                            ("get_", "is_", "check_", "list_", "ping", "status", "info")
                        )
                        if not any(m == meth for m, _ in targets[mod]):
                            targets[mod].append((meth, is_safe))

    if not endpoints and not modules and not methods:
        return registry

    return targets


# pylint: disable=too-many-arguments,too-many-locals,too-many-positional-arguments,protected-access,broad-exception-caught
async def enumerate_router(
    url: str,
    password: str,
    *,
    username: str = "root",
    read_only: bool = True,
    verbose: bool = False,
    deep_redact: bool = True,
    modules: list[str] | None = None,
    methods: list[str] | None = None,
    endpoints: list[str] | None = None,
) -> dict[str, Any]:
    """Enumerate supported API endpoints on a GL.iNet router.

    Args:
        url: Router URL or IP (e.g. http://192.168.8.1 or 192.168.8.1; /rpc is appended automatically)
        password: Router admin password
        username: Router admin username (default: root)
        read_only: If True, only probe read-safe (get_*) endpoints
        verbose: Print progress to stderr
        deep_redact: If True, redacts extended sensitive fields (MACs, IPs, etc.)
        modules: Optional list of module names to probe
        methods: Optional list of method names to probe
        endpoints: Optional list of specific endpoints ('module.method') to probe

    Returns:
        dict with model, firmware, and per-module enumeration results
    """
    url = normalize_url(url)
    client = AiohttpClient()
    router = GLinet(client=client, base_url=url)

    targets = filter_registry(
        API_REGISTRY,
        modules=modules,
        methods=methods,
        endpoints=endpoints,
    )

    try:
        if verbose:
            print("Logging in...", file=sys.stderr)
        await router.login(username, password)

        if verbose:
            print("Getting router info...", file=sys.stderr)
        info = await router.router_info()

        report: dict[str, Any] = {
            "generated_at": datetime.now(tz=UTC).isoformat(),
            "model": info.get("model", "unknown"),
            "firmware_version": info.get("firmware_version", "unknown"),
            "firmware_date": info.get("firmware_date", "unknown"),
            "board_info": info.get("board_info", {}),
            "software_feature": info.get("software_feature", {}),
            "hardware_feature": info.get("hardware_feature", {}),
            "modules": {},
        }

        total_modules = len(targets)
        for i, (module, target_methods) in enumerate(sorted(targets.items()), 1):
            if verbose:
                print(f"[{i}/{total_modules}] Probing {module}...", file=sys.stderr)

            module_result: dict[str, Any] = {
                "supported": False,
                "methods": {},
            }

            for method_name, is_safe in target_methods:
                if not is_safe and read_only:
                    module_result["methods"][method_name] = {
                        "status": "skipped",
                        "reason": "write method (use --no-read-only to probe)",
                    }
                    continue

                try:
                    payload = router.gen_sid_payload(
                        "call", [module, method_name], router.sid
                    )
                    result = await router._request(payload)
                    module_result["supported"] = True
                    module_result["methods"][method_name] = {
                        "status": "ok",
                        "response": _redact(result, deep_redact=deep_redact),
                    }
                except Exception as exc:
                    error_msg = str(exc)
                    status = "error"

                    if "Method not found" in error_msg or "-32601" in error_msg:
                        status = "method_not_found"
                    elif "-1" in error_msg and "permission" in error_msg.lower():
                        status = "permission_denied"
                    elif "-250" in error_msg:
                        # Module exists but hardware not available (e.g. modem)
                        module_result["supported"] = True
                        status = "hardware_not_available"

                    module_result["methods"][method_name] = {
                        "status": status,
                        "error": error_msg,
                    }

            report["modules"][module] = module_result

        # Summary statistics
        supported_modules = [m for m, r in report["modules"].items() if r["supported"]]
        report["summary"] = {
            "total_modules_probed": total_modules,
            "supported_modules": len(supported_modules),
            "supported_module_names": sorted(supported_modules),
            "total_methods_in_registry": sum(
                len(methods_list) for methods_list in targets.values()
            ),
            "methods_probed": sum(
                1
                for mod in report["modules"].values()
                for m in mod["methods"].values()
                if m["status"] != "skipped"
            ),
            "methods_ok": sum(
                1
                for mod in report["modules"].values()
                for m in mod["methods"].values()
                if m["status"] == "ok"
            ),
        }

        return report
    finally:
        try:
            session = await client.session()
            await session.close()
        except Exception:
            pass


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Enumerate GL.iNet router API endpoints",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Read-only probe with password argument (safe, won't change router state):
  python3 enumeration.py --url 192.168.8.1 --password your_password

  # Short flags (-u, -p):
  python3 enumeration.py -u 192.168.8.1 -p your_password

  # Only check a specific module (e.g. system or clients):
  python3 enumeration.py -u 192.168.8.1 -p your_password --module system

  # Only check a specific endpoint:
  python3 enumeration.py -u 192.168.8.1 -p your_password --endpoint system.get_info

  # Probe all endpoints including write methods (CAUTION):
  python3 enumeration.py -u 192.168.8.1 -p your_password --no-read-only

  # Save report to file:
  python3 enumeration.py -u 192.168.8.1 -p your_password --output report.json

  # Disable deep redaction of sensitive tracking metrics:
  python3 enumeration.py -u 192.168.8.1 -p your_password --disable-deep-redact

  # Quiet mode (JSON only, no progress):
  python3 enumeration.py -u 192.168.8.1 -p your_password --quiet
        """,
    )
    parser.add_argument(
        "--url",
        "-u",
        required=True,
        help="Router URL or IP (e.g. http://192.168.8.1 or 192.168.8.1; /rpc is appended automatically)",
    )
    pwd_group = parser.add_mutually_exclusive_group()
    pwd_group.add_argument(
        "--password",
        "-p",
        help="Router admin password",
    )
    pwd_group.add_argument(
        "--pwd-file",
        help="Path to file containing the router password (alternative to --password)",
    )
    parser.add_argument(
        "--username",
        default="root",
        help="Router admin username (default: root)",
    )
    parser.add_argument(
        "--module",
        "-m",
        action="append",
        dest="modules",
        help="Only probe specified module(s) (can be repeated or comma-separated, e.g. -m system,wifi)",
    )
    parser.add_argument(
        "--method",
        action="append",
        dest="methods",
        help="Only probe specified method(s) (can be repeated or comma-separated, e.g. --method get_status)",
    )
    parser.add_argument(
        "--endpoint",
        "-e",
        action="append",
        dest="endpoints",
        help="Only probe specific endpoint(s) in 'module.method' or 'module/method' format (can be repeated)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Write JSON report to file (default: stdout)",
    )
    parser.add_argument(
        "--no-read-only",
        action="store_true",
        help="Also probe write endpoints (CAUTION: may change router state)",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress progress messages (JSON output only)",
    )
    parser.add_argument(
        "--disable-deep-redact",
        action="store_true",
        help="Disable deep redaction of extended sensitive fields (MACs, IPs, SSIDs, traffic logs)",
    )

    args = parser.parse_args()

    password: str = ""
    if args.password:
        password = args.password
    elif args.pwd_file:
        pwd_path = Path(args.pwd_file)
        if not pwd_path.exists():
            print(f"Error: Password file '{args.pwd_file}' not found", file=sys.stderr)
            sys.exit(1)
        password = pwd_path.read_text(encoding="utf-8").strip()
    elif sys.stdin.isatty():
        try:
            password = getpass.getpass("Enter router password: ")
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.", file=sys.stderr)
            sys.exit(1)
    else:
        parser.error("Either --password or --pwd-file must be provided.")

    modules = _split_args(args.modules)
    methods = _split_args(args.methods)
    endpoints = _split_args(args.endpoints)

    report = asyncio.run(
        enumerate_router(
            url=args.url,
            password=password,
            username=args.username,
            read_only=not args.no_read_only,
            verbose=not args.quiet,
            deep_redact=not args.disable_deep_redact,
            modules=modules,
            methods=methods,
            endpoints=endpoints,
        )
    )

    output_json = json.dumps(report, indent=2, default=str)

    if args.output:
        Path(args.output).write_text(output_json, encoding="utf-8")
        if not args.quiet:
            print(f"\nReport written to {args.output}", file=sys.stderr)
            print(f"Model: {report['model']}", file=sys.stderr)
            print(f"Firmware: {report['firmware_version']}", file=sys.stderr)
            summary = report["summary"]
            print(
                f"Supported modules: {summary['supported_modules']}/{summary['total_modules_probed']}",
                file=sys.stderr,
            )
            print(
                f"Methods OK: {summary['methods_ok']}/{summary['methods_probed']} probed",
                file=sys.stderr,
            )
    else:
        print(output_json)


if __name__ == "__main__":
    main()
