This file is used to document the various API calls and typical responses
`my_router.connected_clients()` or `asyncio.run(my_router.async_connected_clients())`
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

tests/test_api.py::test_router_info
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
tests/test_api.py::test_router_get_status
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

tests/test_api.py::test_router_get_load
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

tests/test_api.py::test_router_mac
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

tests/test_api.py::test_wifi_ifaces_get
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
```

## Measured Real-World API Timings

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

## API Documentation Discrepancies

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

## Hardware Differences (GL-MT1300 vs GL-B1300)

Enumeration across physical models (`GL-B1300` vs `GL-MT1300`) revealed model-specific capabilities:

- **Hardware Toggle Switch (`switch-button`)**: Present on GL-MT1300 (`switch-button/get_config`, `switch-button/get_funcs`) supporting modes such as `openvpn` or `wireguard` toggles. Absent on GL-B1300 (returns `-32601 Method not found`).
- **Tailscale**: Available on GL-MT1300 (`tailscale/get_status`, `tailscale/get_exit_node_list`, `tailscale/set_config`).
- **VPN Policies (`vpn-policy`)**: Granular policy routing available on GL-MT1300 (`domain_policy`, `global_policy`, `mac_policy`, `vlan_policy`, `proxy_mode`).
- **Network Leases & ARP (`network`)**: `network/get_dhcp_leases` and `network/get_arp_list` provide real-time ARP and DHCP state.
- **Firewall Controls (`firewall`)**: `firewall/get_wan_access` manages remote admin access (SSH, HTTPS, ping), while `firewall/get_zone_list` enumerates firewall zone mappings.
- **LAN Configuration (`lan`)**: `lan/get_config_list` reports IP ranges, subnet masks, and DHCP lease times for LAN and guest interfaces.
- **Status LED (`led`)**: `led/get_config` toggles router LED status lights.
- **DDNS (`ddns`)**: `ddns/get_config` and `ddns/get_status` configure and report dynamic DNS status.


