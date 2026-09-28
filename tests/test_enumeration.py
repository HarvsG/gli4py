"""Unit tests for the enumeration utility module."""

import pytest

from gli4py.enumeration import (
    API_REGISTRY,
    _redact,
    _redact_ip_val,
    _split_args,
    filter_registry,
    normalize_url,
)
from gli4py.helpers import normalize_url as helpers_normalize_url


@pytest.mark.parametrize(
    ("input_url", "expected_url"),
    [
        ("http://192.168.8.1/rpc", "http://192.168.8.1/rpc"),
        ("http://192.168.8.1", "http://192.168.8.1/rpc"),
        ("http://192.168.8.1/", "http://192.168.8.1/rpc"),
        ("192.168.8.1", "http://192.168.8.1/rpc"),
        ("192.168.8.1/", "http://192.168.8.1/rpc"),
        ("192.168.8.1/rpc", "http://192.168.8.1/rpc"),
        ("https://192.168.8.1:8443", "https://192.168.8.1:8443/rpc"),
        ("https://192.168.8.1:8443/", "https://192.168.8.1:8443/rpc"),
        ("https://192.168.8.1:8443/rpc", "https://192.168.8.1:8443/rpc"),
        ("  http://192.168.8.1  ", "http://192.168.8.1/rpc"),
    ],
)
def test_normalize_url(input_url: str, expected_url: str) -> None:
    """Test that router URLs are normalized to end with /rpc and have a scheme."""
    assert normalize_url(input_url) == expected_url
    assert helpers_normalize_url(input_url) == expected_url


def test_split_args() -> None:
    """Test splitting comma-separated and repeated CLI argument lists."""
    assert _split_args(None) is None
    assert _split_args([]) is None
    assert _split_args([""]) is None
    assert _split_args(["system", "wifi"]) == ["system", "wifi"]
    assert _split_args(["system,wifi", "clients"]) == ["system", "wifi", "clients"]
    assert _split_args(["  system  ,  wifi  "]) == ["system", "wifi"]


def test_filter_registry_no_filter() -> None:
    """Test that filter_registry returns the full registry when no filter is provided."""
    assert filter_registry(API_REGISTRY) == API_REGISTRY


def test_filter_registry_by_module() -> None:
    """Test filtering registry by module name."""
    filtered = filter_registry(API_REGISTRY, modules=["system", "wifi"])
    assert set(filtered.keys()) == {"system", "wifi"}
    assert ("get_info", True) in filtered["system"]
    assert ("get_config", True) in filtered["wifi"]


def test_filter_registry_by_method() -> None:
    """Test filtering registry across all modules by method name."""
    filtered = filter_registry(API_REGISTRY, methods=["get_status"])
    assert "wifi" in filtered
    for methods in filtered.values():
        for meth_name, _ in methods:
            assert meth_name == "get_status"


def test_filter_registry_by_endpoint() -> None:
    """Test filtering registry by specific module.method endpoints."""
    filtered = filter_registry(
        API_REGISTRY,
        endpoints=["system.get_info", "wifi/get_config"],
    )
    assert set(filtered.keys()) == {"system", "wifi"}
    assert [m[0] for m in filtered["system"]] == ["get_info"]
    assert [m[0] for m in filtered["wifi"]] == ["get_config"]


def test_filter_registry_custom_endpoint() -> None:
    """Test filtering registry with an uncatalogued endpoint."""
    filtered = filter_registry(
        API_REGISTRY,
        endpoints=["custom_mod.check_status", "custom_mod.reboot_system"],
    )
    assert "custom_mod" in filtered
    methods_dict = dict(filtered["custom_mod"])
    assert methods_dict["check_status"] is True  # heuristic read-safe
    assert methods_dict["reboot_system"] is False  # heuristic write/unsafe


def test_redact_sensitive_keys() -> None:
    """Test that all explicitly sensitive keys are redacted unconditionally."""
    data = {
        "password": "secret_password",
        "passwd": "secret_passwd",
        "key": "super_secret_wifi_key",
        "sid": "session_id_12345",
        "nonce": "random_nonce_abc",
        "salt": "salt_xyz",
        "hash": "computed_hash_value",
        "sn": "GL123456789",
        "sn_bak": "GL123456789_BAK",
        "ddns": "myrouter.glddns.com",
        "login_name": "admin_user",
    }
    redacted = _redact(data)
    for key in data:
        assert redacted[key] == "***"


def test_redact_ip_val() -> None:
    """Test IP redaction helper with IPv4, IPv6, lists, and invalid values."""
    # IPv4 standard 4 octets
    assert _redact_ip_val("192.168.8.1") == "192.168.*.*"
    assert _redact_ip_val("10.0.0.1") == "10.0.*.*"
    # Malformed IPv4
    assert _redact_ip_val("192.168.1") == "***"

    # IPv6
    assert _redact_ip_val("fe80:1234:5678::1") == "fe80:1234::*"
    assert _redact_ip_val("2001:db8:85a3::8a2e") == "2001:db8::*"
    # Malformed IPv6
    assert _redact_ip_val("fe80:1") == "***"

    # List of IPs
    assert _redact_ip_val(["1.1.1.1", "8.8.8.8"]) == ["1.1.*.*", "8.8.*.*"]

    # Non-string, non-list
    assert _redact_ip_val(12345) == "***"


def test_redact_mac_and_bssid() -> None:
    """Test MAC and BSSID redaction retains first 3 octets and masks the rest."""
    data = {
        "mac": "94:83:C4:14:73:76",
        "bssid": "aa:bb:cc:dd:ee:ff",
        "invalid_mac": "invalid:mac",
    }
    redacted = _redact(data)
    assert redacted["mac"] == "94:83:C4:**:**:**"
    assert redacted["bssid"] == "aa:bb:cc:**:**:**"

    data_malformed = {"mac": "malformed_mac"}
    assert _redact(data_malformed)["mac"] == "***"


def test_redact_ssid() -> None:
    """Test SSID redaction preserves first 2 chars or masks entirely if short."""
    assert _redact({"ssid": "MyHomeNetwork"})["ssid"] == "My***"
    assert _redact({"ssid": "GL-Router"})["ssid"] == "GL***"
    assert _redact({"ssid": "AB"})["ssid"] == "***"
    assert _redact({"ssid": "A"})["ssid"] == "***"
    assert _redact({"ssid": ""})["ssid"] == "***"


def test_redact_traffic_and_metrics() -> None:
    """Test traffic counters are masked in deep redact mode."""
    data = {
        "last_tx": 1234567,
        "last_rx": [100, 200, 300],
    }
    redacted = _redact(data)
    assert redacted["last_tx"] == "***"
    assert redacted["last_rx"] == ["***"]


def test_redact_nested_structures() -> None:
    """Test recursive redaction across nested dictionaries and lists."""
    data = {
        "device": "radio0",
        "interfaces": [
            {
                "name": "guest",
                "ssid": "GuestNetwork",
                "key": "guest_password",
                "mac": "11:22:33:44:55:66",
                "ip": "192.168.9.1",
            }
        ],
        "system": {
            "sn": "SN999999",
            "dns": ["1.1.1.1", "9.9.9.9"],
        },
    }
    redacted = _redact(data)
    assert redacted["device"] == "radio0"
    iface = redacted["interfaces"][0]
    assert iface["name"] == "guest"
    assert iface["ssid"] == "Gu***"
    assert iface["key"] == "***"
    assert iface["mac"] == "11:22:33:**:**:**"
    assert iface["ip"] == "192.168.*.*"
    assert redacted["system"]["sn"] == "***"
    assert redacted["system"]["dns"] == ["1.1.*.*", "9.9.*.*"]


def test_redact_deep_redact_disabled() -> None:
    """Test that when deep_redact=False, sensitive keys are masked but MAC/gateway/SSID are preserved."""
    data = {
        "password": "secret_password",
        "key": "wifi_key",
        "ip": "192.168.8.1",
        "gateway": "192.168.8.1",
        "mac": "94:83:C4:14:73:76",
        "ssid": "MyHomeNetwork",
        "last_tx": 99999,
    }
    redacted = _redact(data, deep_redact=False)
    # Explicit sensitive keys are ALWAYS masked (including 'ip' and 'key')
    assert redacted["password"] == "***"
    assert redacted["key"] == "***"
    assert redacted["ip"] == "***"
    # Network metrics / hardware identifiers are kept intact when deep redaction is disabled
    assert redacted["gateway"] == "192.168.8.1"
    assert redacted["mac"] == "94:83:C4:14:73:76"
    assert redacted["ssid"] == "MyHomeNetwork"
    assert redacted["last_tx"] == 99999
