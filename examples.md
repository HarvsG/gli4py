# GL.iNet API & gli4py Reference Examples

This document serves as a reference for the low-level GL.iNet JSON-RPC 2.0 API and the high-level `gli4py` Python library.

> [!IMPORTANT]
> **gli4py Method Outputs vs. Raw API Fixtures**
>
> The examples in the [gli4py Method Output Examples](#5-gli4py-method-output-examples) section represent the **processed Python return values from `gli4py` methods** (e.g., `await router.connected_clients()`, `await router.wifi_ifaces_get()`).
>
> Depending on the method, `gli4py` performs varying degrees of client-side processing:
> - **Indexing & Filtering**: `connected_clients()` filters online clients and indexes them by MAC address as a dictionary (`{mac: client_info}`); `wifi_ifaces_get()` extracts interfaces across all radio devices and indexes them by interface name.
> - **Redaction**: `wifi_ifaces_get()` redacts Wi-Fi passwords to `None` by default; `router_get_status()` strips Wi-Fi network passwords.
> - **Schema Normalization**: `wireguard_client_state()` wraps legacy single-object responses from firmware <4.8 into a list to match the modern firmware >=4.8 `status_list` structure.
> - **Direct Passthrough**: Methods like `router_info()`, `router_get_load()`, and `router_mac()` return the router's JSON-RPC dictionary payload directly without alteration.
>
> For the **exact, unadulterated raw JSON-RPC response payloads** returned directly by GL.iNet router firmware across all endpoints, refer to the [Raw API Fixtures Reference](#4-raw-api-fixtures-reference) below and the JSON files in [`tests/fixtures/`](tests/fixtures/).

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

## 3. Raw API Fixtures Reference

The test suite and mock router maintain 36 sanitized offline fixtures in [`tests/fixtures/`](tests/fixtures/) captured directly from physical GL.iNet routers (`GL-B1300` and `GL-MT1300`).

| Endpoint / Method | Fixture File | Corresponding `gli4py` Method | Raw vs. `gli4py` Transformation |
|:---|:---|:---|:---|
| `system/get_info` | [`system_info.json`](tests/fixtures/system_info.json) | `router_info()` | Direct passthrough |
| `system/get_status` | [`system_status.json`](tests/fixtures/system_status.json) | `router_get_status()` | WiFi passwords redacted to `None` |
| `system/get_load` | [`system_load.json`](tests/fixtures/system_load.json) | `router_get_load()` | Direct passthrough |
| `macclone/get_mac` | [`macclone.json`](tests/fixtures/macclone.json) | `router_mac()` | Direct passthrough |
| `clients/get_list` | [`clients.json`](tests/fixtures/clients.json) | `connected_clients()` / `list_all_clients()` | `connected_clients()` filters `online: true` and indexes by MAC; `list_all_clients()` is passthrough |
| `lan/get_static_bind_list` | [`lan_static.json`](tests/fixtures/lan_static.json) | `list_static_clients()` | Direct passthrough |
| `wifi/get_config` | [`wifi_config.json`](tests/fixtures/wifi_config.json) | `wifi_ifaces_get()` | Flattened into interface dict keyed by `name`, keys redacted |
| `cable/get_status` | [`cable_status.json`](tests/fixtures/cable_status.json) | *Underlying API* | Cable WAN link state |
| `edgerouter/get_status` | [`edgerouter.json`](tests/fixtures/edgerouter.json) | `connected_to_internet()` | Direct passthrough |
| `wg-client/get_all_config_list` | [`wireguard_config.json`](tests/fixtures/wireguard_config.json) | `wireguard_client_list()` | Extracts peers into `{name: "group/peer", group_id, peer_id}` |
| `wg-client/get_status` | [`wireguard_status.json`](tests/fixtures/wireguard_status.json) | `wireguard_client_state()` | Wrapped in a list on fw < 4.8 to match fw >= 4.8 |
| `vpn-client/get_status` | [`vpn_client_status.json`](tests/fixtures/vpn_client_status.json) | `wireguard_client_state()` | Extracts `status_list` on fw >= 4.8 |
| `tailscale/get_config` | [`tailscale_config.json`](tests/fixtures/tailscale_config.json) | *Underlying API* | Tailscale client configuration |
| `tailscale/get_status` | [`tailscale_status.json`](tests/fixtures/tailscale_status.json) | *Underlying API* | Tailscale connection status |
| `tailscale/get_exit_node_list` | [`tailscale_exit_nodes.json`](tests/fixtures/tailscale_exit_nodes.json) | *Underlying API* | Exit node IP list |
| `switch-button/get_config`, `get_funcs` | [`switch_button.json`](tests/fixtures/switch_button.json) | *Underlying API* | Physical toggle switch configuration & supported functions |
| `vpn-policy/*` | [`vpn_policy.json`](tests/fixtures/vpn_policy.json) | *Underlying API* | Domain, MAC, VLAN, global policies & proxy mode |
| `network/get_dhcp_leases` | [`dhcp_leases.json`](tests/fixtures/dhcp_leases.json) | *Underlying API* | Active DHCP leases |
| `network/get_arp_list` | [`arp_list.json`](tests/fixtures/arp_list.json) | *Underlying API* | Kernel ARP table entries |
| `firewall/get_wan_access` | [`firewall_wan_access.json`](tests/fixtures/firewall_wan_access.json) | *Underlying API* | Remote WAN management settings (SSH/HTTPS/ping) |
| `firewall/get_zone_list` | [`firewall_zones.json`](tests/fixtures/firewall_zones.json) | *Underlying API* | Internal and external zone interfaces |
| `lan/get_config_list` | [`lan_config.json`](tests/fixtures/lan_config.json) | *Underlying API* | LAN and guest subnet/DHCP IP ranges |
| `led/get_config` | [`led_config.json`](tests/fixtures/led_config.json) | *Underlying API* | LED status light configuration |
| `ddns/get_config` | [`ddns_config.json`](tests/fixtures/ddns_config.json) | *Underlying API* | Dynamic DNS client configuration |
| `ddns/get_status` | [`ddns_status.json`](tests/fixtures/ddns_status.json) | *Underlying API* | DDNS WAN IP resolution status |
| `repeater/get_config` | [`repeater_config.json`](tests/fixtures/repeater_config.json) | *Underlying API* | Repeater auto/antijam/dfs configuration |
| `repeater/get_status` | [`repeater_status.json`](tests/fixtures/repeater_status.json) | *Underlying API* | Repeater connection status |
| `repeater/scan` | [`repeater_scan.json`](tests/fixtures/repeater_scan.json) | *Underlying API* | Scanned nearby SSIDs and signal strengths |
| `ovpn-client/get_config` | [`ovpn_config.json`](tests/fixtures/ovpn_config.json) | *Underlying API* | OpenVPN client configurations |
| `ovpn-client/get_status` | [`ovpn_status.json`](tests/fixtures/ovpn_status.json) | *Underlying API* | OpenVPN client status |
| `dns/get_config` | [`dns_config.json`](tests/fixtures/dns_config.json) | *Underlying API* | Upstream DNS configuration |
| `tethering/get_status` | [`tethering_status.json`](tests/fixtures/tethering_status.json) | *Underlying API* | USB / mobile tethering status |
| `modem/get_modem_info` | [`modem_info.json`](tests/fixtures/modem_info.json) | `modem_info()` | Direct passthrough |
| `modem/get_sim_info` | [`modem_sim.json`](tests/fixtures/modem_sim.json) | `modem_sim_info()` | Direct passthrough |
| `modem/get_sim_signal` | [`modem_sim_signal.json`](tests/fixtures/modem_sim_signal.json) | `modem_sim_signal()` | Direct passthrough |
| `adguardhome/get_config` | [`adguardhome.json`](tests/fixtures/adguardhome.json) | *Underlying API* | AdGuard Home configuration |

---

## 4. `gli4py` Method Output Examples

The examples below demonstrate the processed Python dictionary / list structures returned by high-level `gli4py` methods. Sensitive values (passwords, MACs, SSIDs) have been sanitized.

### `connected_clients()`
Invocation: `await router.connected_clients()` (tested in `tests/test_api.py::test_connected_clients`)

Returns online clients filtered from `clients/get_list` and indexed by MAC address:
```json
{
   "e6:bb:ea:4b:11:f7":{
      "remote":true,
      "mac":"e6:bb:ea:4b:11:f7",
      "ip":"192.168.0.230",
      "up":"0",
      "down":"0",
      "total_up":"0",
      "total_down":"0",
      "qos_up":"0",
      "qos_down":"0",
      "blocked":false,
      "iface":"cable",
      "name":"pop-os",
      "online_time":"1623744560",
      "alive":"2793277",
      "new_online":false,
      "online":true,
      "vendor":"Liteon Technology Corporation",
      "node":"0"
   },
   "11:f6:43:48:ae:04":{
      "remote":false,
      "mac":"11:f6:43:48:ae:04",
      "ip":"192.168.0.167",
      "up":"0",
      "down":"0",
      "total_up":"0",
      "total_down":"0",
      "qos_up":"0",
      "qos_down":"0",
      "blocked":false,
      "iface":"cable",
      "name":"Google-Home-Mini",
      "online_time":"1623774267",
      "alive":"2763570",
      "new_online":false,
      "online":true,
      "vendor":"Google, Inc.",
      "node":"0"
   }
}
```

### `router_info()`
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

### `router_get_status()`
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

### `router_get_load()`
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

### `router_mac()`
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

### `wifi_ifaces_get()`
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

### `wireguard_client_state()`
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
