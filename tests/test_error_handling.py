"""Unit tests for gli4py error handling and exception hierarchy."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from gli4py.error_handling import (
    APIClientError,
    AuthenticationError,
    HardwareNotFoundError,
    InvalidStateError,
    LockoutError,
    MethodNotFound,
    MethodNotFoundError,
    NonZeroResponse,
    ServerError,
    TokenError,
    UnsuccessfulRequest,
    raise_for_status,
)


def test_exception_hierarchy() -> None:
    """Test the exception hierarchy relationships."""
    # TokenError is NonZeroResponse, NOT an AuthenticationError
    assert issubclass(TokenError, NonZeroResponse)
    assert issubclass(TokenError, APIClientError)
    assert not issubclass(TokenError, AuthenticationError)

    # AuthenticationError is NonZeroResponse
    assert issubclass(AuthenticationError, NonZeroResponse)
    assert issubclass(AuthenticationError, APIClientError)

    # LockoutError is an AuthenticationError
    assert issubclass(LockoutError, AuthenticationError)
    assert issubclass(LockoutError, NonZeroResponse)

    # MethodNotFoundError is NonZeroResponse, NOT an AuthenticationError or TokenError
    assert issubclass(MethodNotFoundError, NonZeroResponse)
    assert issubclass(MethodNotFoundError, APIClientError)
    assert not issubclass(MethodNotFoundError, AuthenticationError)
    assert not issubclass(MethodNotFoundError, TokenError)
    assert MethodNotFound is MethodNotFoundError

    # ServerError subclasses both UnsuccessfulRequest and NonZeroResponse
    assert issubclass(ServerError, UnsuccessfulRequest)
    assert issubclass(ServerError, NonZeroResponse)
    assert issubclass(ServerError, APIClientError)

    # HardwareNotFoundError & InvalidStateError subclass NonZeroResponse
    assert issubclass(HardwareNotFoundError, NonZeroResponse)
    assert issubclass(InvalidStateError, NonZeroResponse)


@pytest.mark.asyncio
async def test_raise_for_status_success() -> None:
    """Test successful 200 response with result payload."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={"result": {"foo": "bar"}})

    result = await raise_for_status(mock_resp)
    assert result == {"foo": "bar"}


@pytest.mark.asyncio
async def test_raise_for_status_token_error() -> None:
    """Test code -1 raises TokenError."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(
        return_value={"error": {"code": -1, "message": "Session expired"}}
    )

    with pytest.raises(TokenError) as exc_info:
        await raise_for_status(mock_resp)
    assert "code -1" in str(exc_info.value)
    assert not isinstance(exc_info.value, AuthenticationError)


@pytest.mark.asyncio
async def test_raise_for_status_authentication_error() -> None:
    """Test code -32000 raises AuthenticationError."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(
        return_value={"error": {"code": -32000, "message": "Access denied"}}
    )

    with pytest.raises(AuthenticationError) as exc_info:
        await raise_for_status(mock_resp)
    assert "code -32000" in str(exc_info.value)
    assert not isinstance(exc_info.value, TokenError)


@pytest.mark.asyncio
async def test_raise_for_status_lockout_error() -> None:
    """Test code -32003 raises LockoutError (subclass of AuthenticationError)."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(
        return_value={
            "error": {"code": -32003, "message": "Login fail number over limit"}
        }
    )

    with pytest.raises(LockoutError) as exc_info:
        await raise_for_status(mock_resp)
    assert "code -32003" in str(exc_info.value)
    assert isinstance(exc_info.value, AuthenticationError)
    assert not isinstance(exc_info.value, TokenError)


@pytest.mark.asyncio
async def test_raise_for_status_method_not_found_error() -> None:
    """Test code -32601 raises MethodNotFoundError and alias MethodNotFound."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(
        return_value={"error": {"code": -32601, "message": "Method not found"}}
    )

    with pytest.raises(MethodNotFoundError) as exc_info:
        await raise_for_status(mock_resp)
    assert "code -32601" in str(exc_info.value)
    assert isinstance(exc_info.value, MethodNotFound)
    assert isinstance(exc_info.value, NonZeroResponse)


@pytest.mark.asyncio
async def test_raise_for_status_hardware_not_found_error() -> None:
    """Test codes -2 and -250 raise HardwareNotFoundError."""
    for code in (-2, -250, -251):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(
            return_value={"error": {"code": code, "message": "Hardware missing"}}
        )

        with pytest.raises(HardwareNotFoundError) as exc_info:
            await raise_for_status(mock_resp)
        assert f"code {code}" in str(exc_info.value)
        assert isinstance(exc_info.value, NonZeroResponse)


@pytest.mark.asyncio
async def test_raise_for_status_invalid_state_error() -> None:
    """Test codes -200, -204, -260, and -261 raise InvalidStateError."""
    for code in (-200, -204, -260, -261):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(
            return_value={
                "error": {
                    "code": code,
                    "message": "Invalid state or missing required field",
                }
            }
        )

        with pytest.raises(InvalidStateError) as exc_info:
            await raise_for_status(mock_resp)
        assert f"code {code}" in str(exc_info.value)
        assert isinstance(exc_info.value, NonZeroResponse)


@pytest.mark.asyncio
async def test_raise_for_status_server_error_http_500_html() -> None:
    """Test HTTP 500 with Nginx HTML body raises ServerError (resolving Issue #72)."""
    mock_resp = MagicMock()
    mock_resp.status = 500
    mock_resp.json = AsyncMock(side_effect=Exception("Invalid JSON"))
    mock_resp.text = AsyncMock(
        return_value="<html><head><title>500 Internal Server Error</title></head><body><center><h1>500 Internal Server Error</h1></center></body></html>"
    )

    with pytest.raises(ServerError) as exc_info:
        await raise_for_status(mock_resp)
    assert "500 Internal Server Error" in str(exc_info.value)
    assert isinstance(exc_info.value, UnsuccessfulRequest)
    assert isinstance(exc_info.value, NonZeroResponse)
    assert isinstance(exc_info.value, APIClientError)


@pytest.mark.asyncio
async def test_raise_for_status_server_error_rpc_code() -> None:
    """Test RPC code -32603 raises ServerError."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(
        return_value={"error": {"code": -32603, "message": "Internal error"}}
    )

    with pytest.raises(ServerError) as exc_info:
        await raise_for_status(mock_resp)
    assert "code -32603" in str(exc_info.value)
    assert isinstance(exc_info.value, NonZeroResponse)
    assert isinstance(exc_info.value, UnsuccessfulRequest)


@pytest.mark.asyncio
async def test_raise_for_status_generic_non_zero() -> None:
    """Test unmapped negative error code raises NonZeroResponse."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(
        return_value={"error": {"code": -5, "message": "Unknown error"}}
    )

    with pytest.raises(NonZeroResponse) as exc_info:
        await raise_for_status(mock_resp)
    assert "code -5" in str(exc_info.value)
    assert "previously unknown" in str(exc_info.value)
    assert "https://github.com/HarvsG/gli4py/issues" in str(exc_info.value)


@pytest.mark.asyncio
async def test_raise_for_status_unsuccessful_http_404() -> None:
    """Test non-500 non-200 HTTP status (e.g. 404) raises UnsuccessfulRequest."""
    mock_resp = MagicMock()
    mock_resp.status = 404
    mock_resp.json = AsyncMock(side_effect=Exception("Not JSON"))
    mock_resp.text = AsyncMock(return_value="Not Found")

    with pytest.raises(UnsuccessfulRequest) as exc_info:
        await raise_for_status(mock_resp)
    assert not isinstance(exc_info.value, ServerError)


@pytest.mark.asyncio
async def test_raise_for_status_non_utf8_json_decoding() -> None:
    """Test that raise_for_status gracefully decodes non-UTF-8 responses rather than failing."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(
        side_effect=UnicodeDecodeError(
            "utf-8", b"\xe1", 0, 1, "invalid continuation byte"
        )
    )
    mock_resp.text = AsyncMock(return_value='{"result": {"foo": "bar"}}')

    result = await raise_for_status(mock_resp)
    assert result == {"foo": "bar"}
