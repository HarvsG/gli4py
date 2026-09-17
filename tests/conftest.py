"""Pytest configuration and fixtures for gli4py tests."""

import json
import pathlib
from datetime import datetime, timezone

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register custom CLI options for live router tests."""
    parser.addoption(
        "--router-url",
        default="http://192.168.0.1/rpc",
        help="Base URL of the GL.iNet router RPC endpoint (default: http://192.168.0.1/rpc)",
    )
    parser.addoption(
        "--router-pwd-file",
        default="router_pwd",
        help="Path to file containing the router password (default: router_pwd)",
    )
    parser.addoption(
        "--disruptive",
        action="store_true",
        default=False,
        help="Enable disruptive tests (WiFi toggle, WireGuard start/stop, reboot)",
    )
    parser.addoption(
        "--test-report",
        default=None,
        help="Path to write a JSON test report of API responses (for contributor uploads)",
    )


@pytest.fixture(scope="module")
def router_url(request: pytest.FixtureRequest) -> str:
    """The GL.iNet router RPC URL."""
    return request.config.getoption("--router-url")


@pytest.fixture(scope="module")
def router_pwd(request: pytest.FixtureRequest) -> str:
    """The router password, read from the file specified by --router-pwd-file."""
    pwd_file = request.config.getoption("--router-pwd-file")
    pwd_path = pathlib.Path(pwd_file)
    if not pwd_path.exists():
        pytest.skip(f"Password file '{pwd_file}' not found")
    return pwd_path.read_text(encoding="utf-8").strip()


@pytest.fixture(scope="module")
def disruptive(request: pytest.FixtureRequest) -> bool:
    """Whether disruptive tests are enabled via --disruptive flag."""
    return request.config.getoption("--disruptive")


class LiveTestReport:
    """Collects API responses during live tests for contributor reports."""

    def __init__(self) -> None:
        self.entries: list[dict] = []
        self.router_info: dict = {}
        self.start_time: str = datetime.now(tz=timezone.utc).isoformat()

    def record(
        self,
        test_name: str,
        endpoint: str,
        response: object,
        *,
        error: str | None = None,
    ) -> None:
        """Record an API response."""
        entry: dict = {
            "test": test_name,
            "endpoint": endpoint,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
        if error is not None:
            entry["error"] = error
        else:
            entry["response"] = _redact_sensitive(response)
        self.entries.append(entry)

    def to_dict(self) -> dict:
        """Serialize the report to a dictionary."""
        return {
            "generated_at": self.start_time,
            "router_info": _redact_sensitive(self.router_info),
            "results": self.entries,
        }


def _redact_sensitive(obj: object) -> object:
    """Recursively redact sensitive keys from API responses."""
    sensitive_keys = {
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
    }
    if isinstance(obj, dict):
        return {
            k: "***REDACTED***" if k in sensitive_keys else _redact_sensitive(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_redact_sensitive(item) for item in obj]
    return obj


@pytest.fixture(scope="session")
def test_report(request: pytest.FixtureRequest) -> LiveTestReport | None:
    """Session-scoped test report collector. Returns None if --test-report not specified."""
    report_path = request.config.getoption("--test-report")
    if report_path is None:
        yield None
        return

    report = LiveTestReport()
    yield report

    # Write the report at session end
    output = pathlib.Path(report_path)
    output.write_text(
        json.dumps(report.to_dict(), indent=2, default=str),
        encoding="utf-8",
    )
