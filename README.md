# gli4py

[![Tests](https://github.com/HarvsG/gli4py/actions/workflows/tests.yml/badge.svg)](https://github.com/HarvsG/gli4py/actions/workflows/tests.yml)
[![Pylint](https://github.com/HarvsG/gli4py/actions/workflows/pylint.yml/badge.svg)](https://github.com/HarvsG/gli4py/actions/workflows/pylint.yml)
[![CodeQL](https://github.com/HarvsG/gli4py/actions/workflows/codeql.yml/badge.svg)](https://github.com/HarvsG/gli4py/actions/workflows/codeql.yml)
[![PyPI Version](https://img.shields.io/pypi/v/gli4py.svg?color=blue)](https://pypi.org/project/gli4py/)
[![Python Versions](https://img.shields.io/pypi/pyversions/gli4py.svg)](https://pypi.org/project/gli4py/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![Home Assistant Integration](https://img.shields.io/badge/Home%20Assistant-GL--iNet%20Integration-41BDF5?logo=home-assistant&logoColor=white)](https://github.com/HarvsG/ha-glinet4-integration)

An asynchronous Python 3 API wrapper for [GL.iNet](https://www.gl-inet.com/) routers running firmware version 4.x.

GL.iNet routers are built on [OpenWrt](https://openwrt.org/), providing extensive customization combined with a user-friendly web interface and a [locally accessible JSON-RPC API](https://web.archive.org/web/20240121142533/https://dev.gl-inet.com/router-4.x-api/). `gli4py` provides a native, non-blocking Python interface to query and manage these devices.

> **Home Assistant Integration**: `gli4py` is the core library powering the [Home Assistant GL-iNet v4 Integration (`ha-glinet4-integration`)](https://github.com/HarvsG/ha-glinet4-integration).

---

## Features

- **Authentication & Security**
  - Asynchronous challenge-response authentication supporting `MD5`, `SHA-256`, and `SHA-512` hashing algorithms computed off the main thread.
  - Dedicated exception hierarchy differentiating session expiry (`TokenError`), invalid credentials (`AuthenticationError`), and login rate-limiting (`LockoutError`).
  - Fast reachability check and login state tracking.

- **System Diagnostics & Control**
  - Retrieve router model, MAC address, and firmware version.
  - Query CPU load, free memory, and real-time network traffic status.
  - Trigger graceful router reboot with optional delay.

- **Network & Client Monitoring**
  - List active connected clients with real-time bandwidth and signal stats.
  - Query DHCP leases (active and static clients).
  - Internet reachability verification and ping diagnostics.

- **Cellular / Modem (LTE & 5G)**
  - Query modem hardware status and capabilities.
  - Retrieve SIM card details (IMEI, IMSI, ICCID).
  - Inspect cellular signal strength and carrier connection status.

- **Wi-Fi Management**
  - Inspect 2.4 GHz and 5 GHz radio interfaces with optional key/credential redaction.
  - Enable or disable individual Wi-Fi interfaces.

- **VPN Management**
  - **WireGuard**: List client configurations, retrieve active connection status, and start/stop WireGuard clients with automated schema adaptation across firmware versions (< 4.8 and >= 4.8).
  - **Tailscale**: Check Tailscale connection state, configuration, and start or stop the Tailscale service.

---

## Installation

```bash
pip install gli4py
```

For development or test environments requiring the in-process mock router and fixtures:

```bash
pip install "gli4py[mock]"
```

---

## Quick Start

```python
import asyncio
from gli4py import GLinet


async def main() -> None:
    # Initialize the client (default base URL is typically http://192.168.8.1/rpc)
    router = GLinet(base_url="http://192.168.8.1/rpc")

    # Check if the router is reachable
    if not await router.router_reachable():
        print("Router is not reachable.")
        return

    # Authenticate
    await router.login("root", "your_router_password")
    print(f"Logged in successfully. Session ID: {router.sid}")

    # Query system information
    info = await router.router_info()
    print(f"Device: {info.get('model')} (Firmware {info.get('firmware_version')})")

    # Query connected clients
    clients = await router.connected_clients()
    print(f"\nConnected clients ({len(clients)}):")
    for client in clients:
        print(f" - {client.get('name', 'Unknown')} ({client.get('ip')})")


if __name__ == "__main__":
    asyncio.run(main())
```

See [examples.md](examples.md) for sample API payloads and responses.

---

## Development Setup

### Local Development

1. **Clone the repository**:
```bash
git clone https://github.com/HarvsG/gli4py.git
cd gli4py
```


2. **Ensure Python 3.11+ is installed**:
```bash
python3 -V
```

3. **Install Poetry** (if not already installed):
```bash
pipx install poetry
# Or via official installer: curl -sSL https://install.python-poetry.org | python3 -
```

4. **Install dependencies with Poetry**:
```bash
poetry install
```

5. **Install pre-commit hooks**:
```bash
poetry run pre-commit install
```

### Running Tests

* **Unit Tests** (no router required, runs offline and in CI by default):
```bash
poetry run pytest
```

* **Live Hardware Tests** (requires a physical GL.iNet router):
Run live API tests by passing the `--live` flag, with target URL and password arguments:
```bash
# Using a password file (router_pwd in root or tests/):
poetry run pytest --live --url 192.168.8.1

# Or passing credentials directly:
poetry run pytest --live --url 192.168.8.1 --password your_password

# Enable disruptive tests (WiFi toggling, VPN toggling, reboot):
poetry run pytest --live --url 192.168.8.1 --disruptive-tests
```
> **Note**: Router URL and password can also be configured via environment variables (`ROUTER_URL`, `ROUTER_PASSWORD`). In most development environments where `PYTHONASYNCIODEBUG` or `PYTHONDEVMODE` is set, prefix with `PYTHONDEVMODE="" PYTHONASYNCIODEBUG=""`.

### Code Formatting & Linting

```bash
# Run pre-commit checks on all files
poetry run pre-commit run --all-files

# Or run tools directly
poetry run ruff check .
poetry run ruff format --check .
poetry run pylint $(git ls-files '*.py')
```

---

## Dev Setup Alongside Home Assistant & Custom Component

To test `gli4py` locally within a Home Assistant development container alongside the custom component:

1. Clone `gli4py` into your VS Code `/workspaces/` directory alongside `core` and `glinet`.
   > **Tip**: In VS Code, press `Ctrl` + `Shift` + `P` (or `Cmd` + `Shift` + `P` on macOS) and choose **Workspaces: Add Folder to Workspace...** to add `/workspaces/gli4py` directly to your multi-root workspace alongside `core` and `glinet`.
2. Inside your Home Assistant virtual environment (`ha-env`), install the editable package:
```bash
pip install -e /workspaces/gli4py
```
3. Ensure the custom component has `"/workspaces/gli4py/"` in `"python.analysis.extraPaths"` in `.vscode/settings.json`.

---

## API Enumeration

The repository includes `gli-enumerate` (or `python3 -m gli4py.enumeration`), a utility to probe a GL.iNet router to discover which API modules and methods are supported by the device's firmware and produce a JSON report.

Sensitive information (passwords, Wi-Fi keys, session tokens, serial numbers, and IP/MAC addresses) is automatically redacted from the output. By default, enumeration runs in a safe, read-only mode by skipping methods that alter router configuration or state.

### Examples

**Basic read-only probe:**

```bash
gli-enumerate -u 192.168.8.1 -p your_router_password
```

**Target a specific module or endpoint:**

```bash
gli-enumerate -u 192.168.8.1 -p your_router_password -m wifi
gli-enumerate -u 192.168.8.1 -p your_router_password -e system.get_info
```

**Share report or subsection via pastebin:**

```bash
# Upload full report to paste.rs:
gli-enumerate -u 192.168.8.1 -p your_router_password --quiet | curl --data-binary @- https://paste.rs

# Or pipe a specific subsection using jq:
gli-enumerate -u 192.168.8.1 -p your_router_password --quiet | jq '.modules.wifi' | curl --data-binary @- https://paste.rs
```

**Probe all endpoints (including write methods):**

> **Caution:** Probing write methods *will* alter the router's configuration or state.

```bash
gli-enumerate -u 192.168.8.1 -p your_router_password --no-read-only
```

For all available flags and options, run:

```bash
gli-enumerate --help
# or from a repository checkout:
python3 -m gli4py.enumeration --help
```

---

## Related Projects

* [Home Assistant GL-iNet v4 Integration (`ha-glinet4-integration`)](https://github.com/HarvsG/ha-glinet4-integration) - Custom component integrating GL.iNet firmware 4.x routers into Home Assistant.

---

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).
