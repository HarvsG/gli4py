"""Pytest configuration and shared fixtures for gli4py."""
# pylint: disable=wrong-import-position,redefined-outer-name,broad-exception-caught,protected-access,no-member,duplicate-code

import os
from collections.abc import AsyncGenerator
from pathlib import Path

# Ensure development mode environment variables are cleared so dev environments
# do not trigger strict duplicate header errors on older GL.iNet firmware.
os.environ["PYTHONASYNCIODEBUG"] = ""
os.environ["PYTHONDEVMODE"] = ""

# If python was started with PYTHONASYNCIODEBUG, ensure aiohttp permits duplicate
# Content-Type headers returned by older GL.iNet nginx servers.
try:
    from aiohttp import client_proto, http_parser

    client_proto.HttpResponseParser = http_parser.HttpResponseParserPy
    http_parser.SINGLETON_HEADERS = frozenset(
        h for h in http_parser.SINGLETON_HEADERS if h != "content-type"
    )
except (ImportError, AttributeError):
    pass

import pytest
from uplink import AiohttpClient

from gli4py.glinet import GLinet
from gli4py.helpers import normalize_url

# Suppress bug in uplink's AiohttpClient.__del__ during Python shutdown
AiohttpClient.__del__ = lambda self: None


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register custom CLI options for gli4py test suite."""
    parser.addoption(
        "--live",
        "--with-live",
        action="store_true",
        default=False,
        help="Run live tests against a physical GL.iNet router (skipped by default).",
    )
    parser.addoption(
        "--url",
        "--router-url",
        dest="router_url",
        default=os.getenv(
            "ROUTER_URL", os.getenv("GLINET_ROUTER_URL", "http://192.168.8.1/rpc")
        ),
        help="GL.iNet router URL or IP address (e.g. 192.168.0.4 or http://192.168.8.1/rpc).",
    )
    parser.addoption(
        "--password",
        "--router-password",
        dest="router_password",
        default=os.getenv("ROUTER_PASSWORD", os.getenv("GLINET_ROUTER_PASSWORD", None)),
        help="GL.iNet router password.",
    )
    parser.addoption(
        "--pwd-file",
        dest="pwd_file",
        default=None,
        help="Path to file containing the router password.",
    )
    parser.addoption(
        "--disruptive-tests",
        "--disruptive",
        dest="disruptive_tests",
        action="store_true",
        default=False,
        help="Run disruptive tests that modify router state or reboot.",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip live tests by default unless --live is specified."""
    if not config.getoption("live"):
        skip_live = pytest.mark.skip(reason="Live tests disabled (pass --live to run)")
        for item in items:
            if "live" in item.keywords:
                item.add_marker(skip_live)


@pytest.fixture(scope="session")
def router_url(request: pytest.FixtureRequest) -> str:
    """Return normalized router URL from CLI options or environment."""
    raw_url: str = request.config.getoption("router_url")
    return normalize_url(raw_url)


@pytest.fixture(scope="session")
def router_password(request: pytest.FixtureRequest) -> str | None:
    """Return router password from CLI options, env var, or password file."""
    # 1. Explicit CLI option or env var
    cli_pwd = request.config.getoption("router_password")
    if cli_pwd is not None:
        return cli_pwd if cli_pwd != "" else None

    # 2. Explicit --pwd-file option
    pwd_file = request.config.getoption("pwd_file")
    if pwd_file:
        path = Path(pwd_file)
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
        pytest.fail(f"Password file '{pwd_file}' does not exist.")

    # 3. Standard default password file locations
    for default_path in (Path("router_pwd"), Path("tests/router_pwd")):
        if default_path.exists():
            return default_path.read_text(encoding="utf-8").strip()

    return None


@pytest.fixture(scope="session")
def disruptive_tests(request: pytest.FixtureRequest) -> bool:
    """Return whether disruptive tests are enabled."""
    return bool(request.config.getoption("disruptive_tests"))


@pytest.fixture(scope="module")
async def router(router_url: str) -> AsyncGenerator[GLinet, None]:
    """Yield a module-scoped GLinet client connected to the target router URL."""
    client = GLinet(base_url=router_url)
    yield client
    try:
        session = await client._client.session()
        await session.close()
    except Exception:
        pass
