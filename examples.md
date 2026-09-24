# GL.iNet API & gli4py Reference Examples

This document serves as a reference for the low-level GL.iNet JSON-RPC 2.0 API and the high-level `gli4py` Python library.

> [!IMPORTANT]
> **gli4py Method Outputs vs. Raw API Fixtures**
>
> The examples in the [gli4py Method Output Examples](#3-gli4py-method-output-examples) section represent the **processed Python return values from `gli4py` methods** (e.g., `await router.connected_clients()`, `await router.wifi_ifaces_get()`).
>
> Depending on the method, `gli4py` performs varying degrees of client-side processing:
> - **Indexing & Filtering**: `connected_clients()` filters online clients and indexes them by MAC address as a dictionary (`{mac: client_info}`); `wifi_ifaces_get()` extracts interfaces across all radio devices and indexes them by interface name.
> - **Redaction**: `wifi_ifaces_get()` redacts Wi-Fi passwords to `None` by default; `router_get_status()` strips Wi-Fi network passwords.
> - **Schema Normalization**: `wireguard_client_state()` wraps legacy single-object responses from firmware <4.8 into a list to match the modern firmware >=4.8 `status_list` structure.
> - **Direct Passthrough**: Methods like `router_info()`, `router_get_load()`, and `router_mac()` return the router's JSON-RPC dictionary payload directly without alteration.
>
> For the **exact, unadulterated raw JSON-RPC response payloads** returned directly by GL.iNet router firmware across all endpoints, refer to the offline JSON fixtures in [`tests/fixtures/`](tests/fixtures/).

---

## 1. Measured Real-World API Timings

Measured against a physical GL.iNet GL-B1300 running firmware 4.3.25:

| Operation | Method / Endpoint | Real-World Timing | Notes |
|:---|:---|:---|:---|
| **Challenge** | `challenge` | ~63 ms | Alg=1 (MD5 crypt), returns salt & nonce |
| **Login** | `login` | ~32 ms | Verifies hash, issues session token `sid` |
| **Router Info** | `system/get_info` | ~71 ms | Returns firmware, model, features, board info |
| **Router Status** | `system/get_status` | ~94 ms | Network, wifi, service, system metrics |
| **Router Load** | `system/get_load` | ~51 ms | Memory, buff/cache, load average |
| **Router MAC** | `macclone/get_mac` | ~42 ms | Factory and cloned MAC addresses |
| **Connected Clients** | `clients/get_list` | ~283 ms | Full list of connected & offline clients with traffic stats |
| **Static Leases** | `lan/get_static_bind_list` | ~56 ms | DHCP static bindings |
| **WiFi Config** | `wifi/get_config` | ~466 ms | Queries radio0 and radio1 interfaces |
| **Cable Status** | `cable/get_status` | ~112 ms | WAN cable connection & DHCP status |
| **DNS Config** | `dns/get_config` | ~45 ms | DNS servers and rebind protection |
| **Edge Router Status** | `edgerouter/get_status` | ~4.57 s | Probes upstream DHCP / bypass routing status |
| **Ping (Reachable)** | `diag/ping` (`8.8.8.8`) | ~3.35 s | Runs 4 ICMP echo probes on device |
| **Ping (Unreachable)**| `diag/ping` (`0.0.0.1`) | ~11.06 s | Times out across 4 failed probe attempts |
| **Repeater Scan** | `repeater/scan` | ~17.99 s | Full channel scan across 2.4 GHz and 5 GHz radios |
| **WireGuard Config** | `wg-client/get_all_config_list` | ~60 ms | Lists WireGuard client peer configurations |
| **WireGuard Status** | `wg-client/get_status` | ~68 ms | Firmware <4.8 returns single status object |
| **OpenVPN Status** | `ovpn-client/get_status` | ~62 ms | OpenVPN client status |
| **Repeater Status** | `repeater/get_status` | ~40 ms | Repeater connection state |
| **Router Reboot** | `system/reboot` | ~15 s shutdown, ~45-60 s full reboot | Shuts down after ~15s, total reboot ~45-60s |

These timings are exported as `REAL_WORLD_TIMINGS` in `gli4py.mock`. By default, tests run with `simulate_delays=False` to execute in sub-second time.

---

## 2. API Documentation Discrepancies

Observed discrepancies between `GL.iNet SDK4.0 API-DOCS.html` and real router responses:

1. **`clients/get_list`**: The HTML documentation shows minimal client properties (`mac`, `ip`, `name`, `online`), but real GL.iNet firmware returns rich per-client telemetry:
   - `limit_tx`, `limit_rx`: bandwidth throttling limits (0 if unthrottled).
   - `last_rx`, `last_tx`: recent transfer rates.
   - `total_tx_init`, `total_rx_init`: cumulative byte counters.
   - `online_time`, `alive`: connection timestamps and elapsed seconds.
   - `vendor`, `iface`: OUI lookup vendor name and interface (`cable`, `wifi2g`, `wifi5g`).

2. **`repeater/scan`**: Documentation indicates a flat structure, but real firmware returns:
   - Nested encryption dictionary: `{"enabled": bool, "description": "WPA2 PSK (CCMP)", "uci": "psk2"}`.
   - Band identifier as `"2g"` or `"5g"` (lowercase).
   - Signal strength as integer dBm (e.g. `-74`).

3. **`cable/get_status`**: Real firmware returns a nested `secondwan` dictionary (`{"mode": 1}`) and nested `ipv4` dictionary containing `ip`, `gateway`, `mask`, `dns` rather than top-level fields.

4. **Model/Firmware Feature Gating**: The documentation lists endpoints like `adguardhome/*`, `tailscale/*`, and `bark/*` globally. However, on models like GL-B1300 without these software features enabled, calling these endpoints returns JSON-RPC error code `-32601 Method not found`.

5. **VPN Client API Evolution**:
   - Firmware < 4.8.0: WireGuard client state is queried via `wg-client/get_status`, returning a single dictionary object.
   - Firmware >= 4.8.0: Replaced by unified `vpn-client/get_status`, which returns a `status_list` array allowing multiple concurrent tunnels.

---

## 3. `gli4py` Method Output Examples

The examples below demonstrate the processed Python dictionary / list structures returned by high-level `gli4py` methods. Sensitive values (passwords, MACs, SSIDs) have been sanitized.

### 3.1 Authentication & Connectivity

#### `router_reachable()`
Invocation: `await router.router_reachable()` (tested in `tests/test_api.py::test_router_reachable`)

Returns `bool` indicating whether the router responds to challenge probes without requiring authentication:
```python
True
```

#### `login()`
Invocation: `await router.login("root", "goodlife")` (tested in `tests/test_api.py::test_login`)

Performs challenge-response authentication and returns the session ID (`str`):
```python
"c4b8e1f0a2d3e4b5c6d7e8f9a0b1c2d3"
```

#### `connected_to_internet()`
Invocation: `await router.connected_to_internet()` (tested in `tests/test_api.py::test_connected_to_internet`)

Checks upper-level DHCP / bypass router status (`edgerouter/get_status`):
```json
{
   "detected": 2,
   "dns": [
      "8.8.8.8",
      "1.1.1.1"
   ],
   "gateway": "192.168.1.1",
   "ip": "192.168.1.150",
   "netmask": "255.255.255.0",
   "valid": true
}
```

#### `ping()`
Invocation: `await router.ping("8.8.8.8")` (tested in `tests/test_api.py::test_ping`)

Returns `bool` indicating whether the ICMP echo ping probe succeeded:
```python
True  # Host is reachable
False  # Host is unreachable or timed out
```

---

### 3.2 System & Hardware

#### `router_info()`
Invocation: `await router.router_info()` (tested in `tests/test_api.py::test_router_info`)

Direct passthrough of `system/get_info`:
```json
{
   "mac":"94:83:C4:00:00:00",
   "disable_guest_during_scan_wifi":false,
   "hardware_version":"",
   "country_code":"",
   "sn_bak":"d8c8321000000",
   "software_feature":{
      "ipv6":true,
      "adguard":false,
      "passthrough":false,
      "repeater_eap":true,
      "vpn":true,
      "ids_ips":false,
      "bark":false,
      "tor":false,
      "secondwan":false,
      "sms_forward":false,
      "nas":false
   },
   "vendor":"GL.iNet",
   "hardware_feature":{
      "reset_button":"gpio-63",
      "nand":false,
      "bluetooth":false,
      "wan":"eth1",
      "usb_reset":"",
      "switch_button":"",
      "radio":"radio0 radio1",
      "lan":"eth0",
      "usb":"1-1,2-1",
      "build_in_modem":"",
      "noled":false,
      "hwnat":false,
      "microsd":"",
      "modem_reset":2,
      "fan":false,
      "mcu":false,
      "nowds":false
   },
   "cpu_num":4,
   "board_info":{
      "architecture":"ARMv7 Processor rev 5 (v7l)",
      "hostname":"GL-B1300",
      "kernel_version":"5.4.179",
      "openwrt_version":"OpenWrt 21.02.2 r16495-bf0c965af0",
      "model":"GL.iNet GL-B1300"
   },
   "firmware_date":"2025-03-31 20:12:50",
   "model":"b1300",
   "ddns":"eg0fd66",
   "sn":"36aea4a340000000",
   "firmware_type":"release1",
   "firmware_version":"4.3.25"
}
```

#### `router_get_status()`
Invocation: `await router.router_get_status()` (tested in `tests/test_api.py::test_router_get_status`)

Retrieves `system/get_status` with Wi-Fi passwords redacted to `None`:
```json
{
   "network":[
      {
         "online":true,
         "up":true,
         "interface":"wan"
      },
      {
         "online":false,
         "up":false,
         "interface":"wwan"
      },
      {
         "online":false,
         "up":false,
         "interface":"tethering"
      },
      {
         "online":false,
         "up":false,
         "interface":"wan6"
      },
      {
         "online":false,
         "up":false,
         "interface":"wwan6"
      },
      {
         "online":false,
         "up":false,
         "interface":"tethering6"
      }
   ],
   "wifi":[
      {
         "guest":false,
         "ssid":"MYSSID-2.4G",
         "up":true,
         "channel":1,
         "band":"2G",
         "name":"default_radio0",
         "passwd":"None"
      },
      {
         "guest":false,
         "ssid":"MYSSID-5G",
         "up":true,
         "channel":48,
         "band":"5G",
         "name":"default_radio1",
         "passwd":"None"
      },
      {
         "guest":true,
         "ssid":"GL-B1300-000-Guest",
         "up":false,
         "channel":1,
         "band":"2G",
         "name":"guest2g",
         "passwd":"None"
      },
      {
         "guest":true,
         "ssid":"GL-B1300-000-5G-Guest",
         "up":false,
         "channel":48,
         "band":"5G",
         "name":"guest5g",
         "passwd":"None"
      }
   ],
   "service":[
      {
         "name":"wgclient",
         "status":0
      },
      {
         "name":"wgserver",
         "status":0
      },
      {
         "name":"ovpnclient",
         "status":0
      },
      {
         "name":"ovpnserver",
         "status":0
      }
   ],
   "client":[
      {
         "cable_total":12,
         "wireless_total":5
      }
   ],
   "system":{
      "netnat_enabled":false,
      "ddns_enabled":false,
      "tzoffset":"+0100",
      "guest_ip":"192.168.9.1",
      "flash_app":610304,
      "flash_total":33554432,
      "memory_total":254586880,
      "memory_free":137543680,
      "ipv6_enabled":false,
      "memory_buff_cache":33550336,
      "uptime":31287.02,
      "load_average":[
         0.2,
         0.2,
         0.18
      ],
      "guest_netmask":"255.255.255.0",
      "mode":4,
      "flash_free":14135296,
      "timestamp":1753189931
   }
}
```

#### `router_get_load()`
Invocation: `await router.router_get_load()` (tested in `tests/test_api.py::test_router_get_load`)

Direct passthrough of `system/get_load`:
```json
{
   "memory_free":137641984,
   "memory_buff_cache":33554432,
   "memory_total":254586880,
   "load_average":[
      0.2,
      0.2,
      0.18
   ]
}
```

#### `router_mac()`
Invocation: `await router.router_mac()` (tested in `tests/test_api.py::test_router_mac`)

Direct passthrough of `macclone/get_mac`:
```json
{
   "mac":"94:83:C4:00:00:00",
   "secondwan_mac":"",
   "repeater_mac":"",
   "mode":0,
   "remote_mac":"A8:A1:59:00:00:00",
   "factory_mac":"94:83:C4:00:00:00"
}
```

#### `router_reboot()`
Invocation: `await router.router_reboot(delay=0)` (tested in `tests/test_api.py::test_router_reboot`)

Triggers a system restart (`system/reboot`):
```json
{}
```

---

### 3.3 Clients & Static Bindings

#### `connected_clients()`
Invocation: `await router.connected_clients()` (tested in `tests/test_api.py::test_connected_clients`)

Returns online clients filtered from `clients/get_list` and indexed by MAC address:
```json
{
  "A1:B2:C3:D4:E5:F6": {
    "mac": "A1:B2:C3:D4:E5:F6",
    "ip": "192.168.0.50",
    "name": "Gaming-Desktop",
    "online": false,
    "iface": "cable",
    "type": 2,
    "online_time": 0,
    "blocked": false,
    "total_tx": 45039485,
    "total_rx": 120938475,
    "total_tx_init": 45000000,
    "total_rx_init": 120000000,
    "limit_tx": 0,
    "limit_rx": 0,
    "tx": 0,
    "rx": 0,
    "last_update_rate": 1790253800,
    "last_rx": [
      0, 0, 0, 0
    ],
    "last_tx": [
      0, 0, 0, 0
    ]
  },
  "11:22:33:44:55:66": {
    "mac": "11:22:33:44:55:66",
    "ip": "192.168.0.120",
    "name": "LivingRoom-TV",
    "online": true,
    "iface": "5G",
    "type": 1,
    "online_time": 1790270000,
    "blocked": false,
    "total_tx": 53409,
    "total_rx": 894032,
    "total_tx_init": 50000,
    "total_rx_init": 890000,
    "limit_tx": 0,
    "limit_rx": 0,
    "tx": 15,
    "rx": 250,
    "last_update_rate": 1790253817,
    "alias": "Main TV",
    "class": "smartappliances",
    "last_rx": [
      250, 250, 300, 350
    ],
    "last_tx": [
      15, 15, 20, 25
    ]
  },
  "AA:BB:CC:DD:EE:FF": {
    "mac": "AA:BB:CC:DD:EE:FF",
    "ip": "192.168.0.210",
    "name": "Alice-iPhone",
    "online": true,
    "iface": "2.4G",
    "type": 0,
    "online_time": 1790273500,
    "blocked": false,
    "total_tx": 948573,
    "total_rx": 2049583,
    "total_tx_init": 940000,
    "total_rx_init": 2040000,
    "limit_tx": 0,
    "limit_rx": 0,
    "tx": 45,
    "rx": 12,
    "last_update_rate": 1790253817,
    "last_rx": [
      12, 12, 12, 25, 40, 40, 120, 120
    ],
    "last_tx": [
      45, 45, 45, 90, 90, 150, 150, 200
    ],
    // The keys below have been spotted on some specific devices/firmwares
    // but are not guaranteed to be present across all clients.
    "remote": false,
    "vendor": "Apple",
    "alive": 1,
    "new_online": true,
    "qos_up": "0",
    "qos_down": "0",
    "node": "Main-Router"
  }
}
```

#### `list_all_clients()`
Invocation: `await router.list_all_clients()` (tested in `tests/test_api.py::test_clients`)

Unfiltered list of all clients (online and offline) from `clients/get_list`:
```json
{
   "clients": [
      {
         "mac": "00:11:22:33:44:01",
         "ip": "192.168.8.101",
         "name": "MockPhone",
         "online": true,
         "iface": "wifi2g",
         "vendor": "MockVendor Technologies",
         "online_time": "1623744560",
         "alive": "86400",
         "new_online": false,
         "blocked": false,
         "qos_up": "0",
         "qos_down": "0",
         "up": "1024",
         "down": "2048",
         "total_up": "1048576",
         "total_down": "2097152",
         "total_tx_init": 1048576,
         "total_rx_init": 2097152,
         "limit_tx": 0,
         "limit_rx": 0,
         "last_rx": ["1024"],
         "last_tx": ["512"],
         "node": "0",
         "remote": false
      },
      {
         "mac": "00:11:22:33:44:02",
         "ip": "192.168.8.102",
         "name": "MockLaptop",
         "online": true,
         "iface": "cable",
         "vendor": "MockLaptop Inc",
         "online_time": "1623754560",
         "alive": "76400",
         "new_online": false,
         "blocked": false,
         "qos_up": "0",
         "qos_down": "0",
         "up": "4096",
         "down": "8192",
         "total_up": "10485760",
         "total_down": "20971520",
         "total_tx_init": 10485760,
         "total_rx_init": 20971520,
         "limit_tx": 0,
         "limit_rx": 0,
         "last_rx": ["4096"],
         "last_tx": ["2048"],
         "node": "0",
         "remote": false
      },
      {
         "mac": "00:11:22:33:44:03",
         "ip": "192.168.8.103",
         "name": "MockOfflineDevice",
         "online": false,
         "iface": "wifi5g",
         "vendor": "MockVendor Corp",
         "online_time": "1623700000",
         "alive": "0",
         "new_online": false,
         "blocked": false,
         "qos_up": "0",
         "qos_down": "0",
         "up": "0",
         "down": "0",
         "total_up": "512000",
         "total_down": "1024000",
         "total_tx_init": 512000,
         "total_rx_init": 1024000,
         "limit_tx": 0,
         "limit_rx": 0,
         "last_rx": ["0"],
         "last_tx": ["0"],
         "node": "0",
         "remote": false
      }
   ]
}
```

#### `list_static_clients()`
Invocation: `await router.list_static_clients()` (tested in `tests/test_api.py::test_static_clients`)

Returns static DHCP reservations from `lan/get_static_bind_list`:
```json
{
   "static_bind_list": [
      {
         "ip": "192.168.8.102",
         "mac": "00:11:22:33:44:02",
         "name": "HomeAssistant"
      },
      {
         "ip": "192.168.8.110",
         "mac": "00:11:22:33:44:10",
         "name": "MockNAS"
      },
      {
         "ip": "192.168.8.120",
         "mac": "00:11:22:33:44:20",
         "name": "MockAP"
      },
      {
         "ip": "192.168.8.130",
         "mac": "00:11:22:33:44:30",
         "name": "MockVacuum"
      }
   ]
}
```

---

### 3.4 Wi-Fi Management

#### `wifi_ifaces_get()`
Invocation: `await router.wifi_ifaces_get()` (tested in `tests/test_api.py::test_wifi_ifaces_get`)

Iterates through all Wi-Fi radio devices returned by `wifi/get_config`, indexes by interface name, and redacts keys to `None`:
```json
{
   "default_radio0":{
      "enabled":true,
      "ssid":"MYSSID-2.4G",
      "encryption":"psk2",
      "name":"default_radio0",
      "guest":false,
      "hidden":false,
      "key":"None"
   },
   "guest2g":{
      "enabled":false,
      "ssid":"GL-B1300-000-Guest",
      "encryption":"psk2",
      "name":"guest2g",
      "guest":true,
      "hidden":false,
      "key":"None"
   },
   "default_radio1":{
      "enabled":true,
      "ssid":"MYSSID-5G",
      "encryption":"sae-mixed",
      "name":"default_radio1",
      "guest":false,
      "hidden":false,
      "key":"None"
   },
   "guest5g":{
      "enabled":false,
      "ssid":"GL-B1300-000-5G-Guest",
      "encryption":"psk2",
      "name":"guest5g",
      "guest":true,
      "hidden":false,
      "key":"None"
   }
}
```

#### `wifi_iface_set_enabled()`
Invocation: `await router.wifi_iface_set_enabled("default_radio0", False)` (tested in `tests/test_api.py::test_wifi_ifaces_set_enabled`)

Enables or disables an interface by name via `wifi/set_config`:
```json
{}
```

---

### 3.5 WireGuard Client

#### `wireguard_client_state()`
Invocation: `await router.wireguard_client_state()` (tested in `tests/test_api.py::test_wireguard_client_state`)

Returns a list of status objects. On firmware <4.8, `gli4py` wraps the single `wg-client/get_status` dictionary in a list `[status]` to match the firmware >=4.8 `vpn-client` `status_list` structure:
```json
[
   {
      "rx_bytes":0,
      "ipv6":"",
      "tx_bytes":0,
      "domain":"",
      "group_id":0,
      "port":0,
      "name":"",
      "peer_id":0,
      "status":0,
      "proxy":true,
      "log":"",
      "ipv4":""
   }
]
```

#### `wireguard_client_list()`
Invocation: `await router.wireguard_client_list()` (tested in `tests/test_api.py::test_wireguard_client_list`)

Flattens and extracts client peers from `wg-client/get_all_config_list`:
```json
[
   {
      "name": "MockVPN/MockTunnel",
      "group_id": 7707,
      "peer_id": 2001
   },
   {
      "name": "MockVPN/MockSplitTunnel",
      "group_id": 7707,
      "peer_id": 2002
   }
]
```

#### `wireguard_client_start()` / `wireguard_client_stop()`
Invocation: `await router.wireguard_client_start(7707, 2001)` / `await router.wireguard_client_stop(2001)` (tested in `tests/test_api.py::test_wireguard_client_start_stop`)

Starts or stops a WireGuard tunnel peer. Returns a dictionary with `tunnel_id` on firmware >= 4.8 (`vpn-client`), or an empty list `[]` on older firmware (< 4.8 `wg-client`):
```json
{"tunnel_id": 2001}
```
or
```json
[]
```

---

### 3.6 Tailscale

#### `tailscale_configured()`
Invocation: `await router.tailscale_configured()` (tested in `tests/test_api.py::test_tailscale_configured`)

Returns `bool` indicating whether Tailscale is installed and configured:
```python
True
```

#### `tailscale_connection_state()`
Invocation: `await router.tailscale_connection_state()` (tested in `tests/test_api.py::test_tailscale_connection_state`)

Maps `tailscale/get_status` state codes to `gli4py.models.TailscaleConnection`:
```python
TailscaleConnection.CONNECTED  # status == 3
# Other states:
# TailscaleConnection.UNKNOWN   (0)
# TailscaleConnection.STARTING  (1)
# TailscaleConnection.STOPPED   (2)
```

#### `tailscale_start()` / `tailscale_stop()`
Invocation: `await router.tailscale_start()` / `await router.tailscale_stop()` (tested in `tests/test_api.py::test_tailscale_start_stop`)

Starts or stops the Tailscale daemon via `tailscale/set_config`:
```json
{}
```

---

### 3.7 Cellular / Modem

#### `modem_info()`
Invocation: `await router.modem_info()` (tested in `tests/test_api.py::test_modem_info`)

Direct passthrough of `modem/get_modem_info`:
```json
{
   "modems": [
      {
         "carrier": "MockCarrier",
         "imei": "123456789012345",
         "modem_id": 1,
         "model": "MockModem-EC25",
         "status": "registered"
      }
   ]
}
```

#### `modem_sim_info()`
Invocation: `await router.modem_sim_info()` (tested in `tests/test_api.py::test_modem_sim_info`)

Direct passthrough of `modem/get_sim_info`:
```json
[
   {
      "iccid": "89012345678901234567",
      "imsi": "123456789012345",
      "sim_state": "ready"
   }
]
```

#### `modem_sim_signal()`
Invocation: `await router.modem_sim_signal()` (tested in `tests/test_api.py::test_modem_sim_signal`)

Direct passthrough of `modem/get_sim_signal`:
```json
[
   {
      "rsrp": -95,
      "rsrq": -10,
      "rssi": -65,
      "sinr": 15
   }
]
```

---

### 3.8 Low-Level Payload Utilities

#### `gen_sid_payload()`
Invocation: `GLinet.gen_sid_payload("call", ["system", "get_info"], sid="c4b8e1f0a2d3e4b5c6d7e8f9a0b1c2d3")`

Generates an authenticated JSON-RPC 2.0 request payload with a session ID:
```json
{
   "method": "call",
   "jsonrpc": "2.0",
   "params": [
      "c4b8e1f0a2d3e4b5c6d7e8f9a0b1c2d3",
      "system",
      "get_info"
   ],
   "id": 0
}
```

#### `gen_no_auth_payload()`
Invocation: `GLinet.gen_no_auth_payload("challenge", {"username": "root"})`

Generates an unauthenticated JSON-RPC 2.0 request payload without a session ID:
```json
{
   "method": "challenge",
   "jsonrpc": "2.0",
   "params": {
      "username": "root"
   },
   "id": 0
}
```
