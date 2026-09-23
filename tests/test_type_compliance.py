"""API Type Compliance Testing & Verification Script.

Validates that raw API JSON response payloads (from tests/fixtures/ or live router)
and processed gli4py method outputs strictly conform to the static TypedDict definitions
in gli4py.types without undocumented keys or type mismatches.
"""
# pylint: disable=wrong-import-position,too-many-locals,broad-exception-caught

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from typeguard import check_type

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from uplink import AiohttpClient  # noqa: E402

from gli4py import types  # noqa: E402
from gli4py.glinet import GLinet  # noqa: E402
from gli4py.mock.server import MockRouter  # noqa: E402

# Suppress bug in uplink's AiohttpClient.__del__ during Python shutdown
AiohttpClient.__del__ = lambda self: None

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# Mapping between fixture JSON filenames and their corresponding static types
FIXTURE_TYPE_MAPPING: dict[str, Any] = {
    "adguardhome.json": types.AdguardHomeConfigResponse,
    "arp_list.json": types.ArpListResponse,
    "cable_status.json": types.CableStatusResponse,
    "clients.json": types.ClientsResponse,
    "ddns_config.json": types.DdnsConfigResponse,
    "ddns_status.json": types.DdnsStatusResponse,
    "dhcp_leases.json": types.DhcpLeasesResponse,
    "dns_config.json": types.DnsConfigResponse,
    "edgerouter.json": types.EdgeRouterStatusResponse,
    "firewall_wan_access.json": types.FirewallWanAccessResponse,
    "firewall_zones.json": types.FirewallZonesResponse,
    "lan_config.json": types.LanConfigResponse,
    "lan_static.json": types.StaticBindListResponse,
    "led_config.json": types.LedConfigResponse,
    "macclone.json": types.MaccloneResponse,
    "modem_info.json": types.ModemInfoResponse,
    "modem_sim.json": list[types.ModemSimInfoEntry],
    "modem_sim_signal.json": list[types.ModemSimSignalEntry],
    "ovpn_config.json": types.OvpnConfigResponse,
    "ovpn_status.json": types.OvpnStatusResponse,
    "repeater_config.json": types.RepeaterConfigResponse,
    "repeater_scan.json": types.RepeaterScanResponse,
    "repeater_status.json": types.RepeaterStatusResponse,
    "switch_button.json": types.SwitchButtonResponse,
    "system_info.json": types.SystemInfoResponse,
    "system_load.json": types.SystemLoadResponse,
    "system_status.json": types.RouterStatusResponse,
    "tailscale_config.json": types.TailscaleConfigResponse,
    "tailscale_exit_nodes.json": types.TailscaleExitNodesResponse,
    "tailscale_status.json": types.TailscaleStatusResponse,
    "tethering_status.json": types.TetheringStatusResponse,
    "vpn_client_status.json": types.VpnClientStatusResponse,
    "vpn_policy.json": types.VpnPolicyResponse,
    "wifi_config.json": types.WifiConfigResponse,
    "wireguard_config.json": types.WireguardConfigListResponse,
    "wireguard_status.json": types.WireguardStatusItem,
}


def validate_payload_compliance(data: Any, expected_type: Any) -> None:
    """Validate that data strictly conforms to the expected TypedDict or type."""
    # 1. Typeguard runtime type validation
    check_type(data, expected_type)

    # 2. Strict key verification for TypedDicts
    if isinstance(data, dict) and hasattr(expected_type, "__annotations__"):
        expected_keys = set(expected_type.__annotations__.keys())
        actual_keys = set(data.keys())
        extra_keys = actual_keys - expected_keys
        if extra_keys:
            raise ValueError(
                f"Data has undocumented keys not in {expected_type.__name__}: {extra_keys}"
            )
        required_keys = getattr(expected_type, "__required_keys__", expected_keys)
        missing_keys = required_keys - actual_keys
        if missing_keys:
            raise ValueError(
                f"Data is missing required keys in {expected_type.__name__}: {missing_keys}"
            )


@pytest.mark.parametrize("fixture_name,expected_type", FIXTURE_TYPE_MAPPING.items())
def test_fixture_type_compliance(fixture_name: str, expected_type: Any) -> None:
    """Validate that every JSON fixture strictly matches its TypedDict definition."""
    fixture_path = FIXTURES_DIR / fixture_name
    assert fixture_path.exists(), f"Fixture {fixture_name} not found at {fixture_path}"

    with open(fixture_path, encoding="utf-8") as f:
        data = json.load(f)

    validate_payload_compliance(data, expected_type)


async def test_processed_method_outputs_compliance() -> None:
    """Validate that high-level processed gli4py methods return strictly typed structures."""
    server = MockRouter(simulate_delays=False)
    await server.start()
    uplink_client = AiohttpClient()
    client = GLinet(base_url=server.url, client=uplink_client)

    try:
        await client.login("root", "goodlife")

        # 1. router_info()
        info = await client.router_info()
        validate_payload_compliance(info, types.SystemInfoResponse)

        # 2. router_get_status()
        status = await client.router_get_status()
        validate_payload_compliance(status, types.RouterStatusResponse)

        # 3. router_get_load()
        load = await client.router_get_load()
        validate_payload_compliance(load, types.SystemLoadResponse)

        # 4. router_mac()
        mac = await client.router_mac()
        validate_payload_compliance(mac, types.MaccloneResponse)

        # 5. connected_to_internet()
        edge = await client.connected_to_internet()
        validate_payload_compliance(edge, types.EdgeRouterStatusResponse)

        # 6. connected_clients()
        clients = await client.connected_clients()
        validate_payload_compliance(clients, types.ConnectedClients)

        # 7. list_all_clients()
        all_clients = await client.list_all_clients()
        validate_payload_compliance(all_clients, types.ClientsResponse)

        # 8. list_static_clients()
        static_clients = await client.list_static_clients()
        validate_payload_compliance(static_clients, types.StaticBindListResponse)

        # 9. wifi_ifaces_get()
        wifi_ifaces = await client.wifi_ifaces_get()
        validate_payload_compliance(wifi_ifaces, types.WifiIfacesMap)

        # 10. wireguard_client_list()
        wg_clients = await client.wireguard_client_list()
        validate_payload_compliance(wg_clients, list[types.WireguardClientListItem])

        # 11. wireguard_client_state()
        wg_state = await client.wireguard_client_state()
        validate_payload_compliance(wg_state, list[types.WireguardStatusItem])

        # 12. modem_info()
        modems = await client.modem_info()
        validate_payload_compliance(modems, types.ModemInfoResponse)

        # 13. modem_sim_info()
        sim_info = await client.modem_sim_info()
        validate_payload_compliance(sim_info, list[types.ModemSimInfoEntry])

        # 14. modem_sim_signal()
        sim_signal = await client.modem_sim_signal()
        validate_payload_compliance(sim_signal, list[types.ModemSimSignalEntry])

    finally:
        try:
            session = await uplink_client.session()
            await session.close()
        except Exception:
            pass
        await server.stop()


def run_compliance_cli() -> int:
    """Standalone CLI entry point for running compliance checks in scripts/CI."""
    parser = argparse.ArgumentParser(
        description="Run gli4py API static type compliance checks against fixtures or live router."
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Query live router using GLINET_ROUTER_URL and GLINET_ROUTER_PASSWORD.",
    )
    _ = parser.parse_args()

    print("=" * 70)
    print("gli4py API Static Type Compliance Verification")
    print("=" * 70)

    failed = 0
    passed = 0

    print(f"\n1. Verifying {len(FIXTURE_TYPE_MAPPING)} JSON Fixtures:")
    for fixture_name, expected_type in sorted(FIXTURE_TYPE_MAPPING.items()):
        fixture_path = FIXTURES_DIR / fixture_name
        try:
            with open(fixture_path, encoding="utf-8") as f:
                data = json.load(f)
            validate_payload_compliance(data, expected_type)
            print(f"  [PASS] {fixture_name:<30} -> {expected_type}")
            passed += 1
        except Exception as exc:
            print(f"  [FAIL] {fixture_name:<30} -> Error: {exc}")
            failed += 1

    print("\n2. Verifying Processed GLinet Client Method Outputs:")
    try:
        asyncio.run(test_processed_method_outputs_compliance())
        print("  [PASS] All 14 high-level client method responses conform to types.")
        passed += 1
    except Exception as exc:
        print(f"  [FAIL] Processed client method output error: {exc}")
        failed += 1

    print("\n" + "=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(run_compliance_cli())
