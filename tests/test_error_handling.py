"""Unit tests for gli4py error handling and exception hierarchy."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from gli4py.error_handling import (
    APIClientError,
    AuthenticationError,
    LockoutError,
    NonZeroResponse,
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
    # Ensure TokenError is not caught as AuthenticationError
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
async def test_raise_for_status_generic_non_zero() -> None:
    """Test negative error code other than -1, -32000, -32003 raises NonZeroResponse."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(
        return_value={"error": {"code": -5, "message": "Unknown error"}}
    )

    with pytest.raises(NonZeroResponse) as exc_info:
        await raise_for_status(mock_resp)
    assert "code -5" in str(exc_info.value)
    assert not isinstance(exc_info.value, AuthenticationError)
    assert not isinstance(exc_info.value, TokenError)


@pytest.mark.asyncio
async def test_raise_for_status_unsuccessful_http_status() -> None:
    """Test non-200 HTTP status raises UnsuccessfulRequest."""
    mock_resp = MagicMock()
    mock_resp.status = 500
    mock_resp.json = AsyncMock(return_value={"error": "Internal server error"})

    with pytest.raises(UnsuccessfulRequest):
        await raise_for_status(mock_resp)
