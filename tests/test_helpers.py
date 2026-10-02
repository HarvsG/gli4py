"""Unit tests for gli4py.helpers module."""

import pytest

from gli4py.helpers import format_mac, normalize_url


def test_normalize_url() -> None:
    """Test URL normalization."""
    assert normalize_url("192.168.8.1") == "http://192.168.8.1/rpc"
    assert normalize_url("http://192.168.8.1") == "http://192.168.8.1/rpc"
    assert normalize_url("https://192.168.8.1/rpc") == "https://192.168.8.1/rpc"
    assert normalize_url("192.168.8.1/") == "http://192.168.8.1/rpc"


def test_format_mac_valid() -> None:
    """Test formatting valid MAC addresses in various formats."""
    # Standard uppercase colons
    assert format_mac("28:CD:C1:06:77:67") == "28:CD:C1:06:77:67"

    # Lowercase colons -> converted to uppercase by default
    assert format_mac("28:cd:c1:06:77:67") == "28:CD:C1:06:77:67"
    assert format_mac("28:cd:c1:06:77:67", uppercase=False) == "28:cd:c1:06:77:67"

    # Hyphenated
    assert format_mac("28-CD-C1-06-77-67") == "28:CD:C1:06:77:67"
    assert format_mac("28-cd-c1-06-77-67") == "28:CD:C1:06:77:67"

    # Raw 12 hex digits (no separators)
    assert format_mac("28CDC1067767") == "28:CD:C1:06:77:67"
    assert format_mac("28cdc1067767") == "28:CD:C1:06:77:67"

    # Dot notation
    assert format_mac("28cd.c106.7767") == "28:CD:C1:06:77:67"

    # Test alias
    assert format_mac("b8-27-eb-44-55-66") == "B8:27:EB:44:55:66"


def test_format_mac_invalid() -> None:
    """Test that invalid MAC inputs raise ValueError."""
    with pytest.raises(ValueError, match="Invalid MAC address"):
        format_mac("invalid")

    with pytest.raises(ValueError, match="Invalid MAC address"):
        format_mac("28:CD:C1:06:77")  # too short

    with pytest.raises(ValueError, match="Invalid MAC address"):
        format_mac("28:CD:C1:06:77:67:88")  # too long

    with pytest.raises(ValueError, match="Invalid MAC address"):
        format_mac("28:ZZ:C1:06:77:67")  # non-hex
