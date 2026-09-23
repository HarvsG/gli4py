"""This module contains custom exceptions and a function to handle API response status codes."""

from typing import cast

from aiohttp import ClientResponse


class APIClientError(Exception):
    """Base class for all exceptions raised by the API client."""


class UnsuccessfulRequest(APIClientError):
    """Raised when the status code is not 200."""


class NonZeroResponse(APIClientError):
    """Raised when the router responds but with a non-zero code."""


class TokenError(NonZeroResponse):
    """Raised when the session token is invalid or expired."""


class AuthenticationError(NonZeroResponse):
    """Raised for authentication errors, such as invalid credentials or password."""


class LockoutError(AuthenticationError):
    """Raised when login is locked out due to exceeding failed login limit."""


async def raise_for_status(response: ClientResponse) -> object:
    """Checks whether or not the response was successful."""
    # 1. Safely read the body as JSON, falling back to text if it's HTML
    try:
        # content_type=None forces aiohttp to parse it even if the router sends the wrong headers
        raw_res = await response.json(content_type=None)
    except Exception as exc:
        text = await response.text()
        raise UnsuccessfulRequest(
            f"Request failed or returned invalid JSON (Status {response.status}): {text}"
        ) from exc

    # 2. Process the GL-iNet logic
    if 200 <= response.status < 300:
        if isinstance(raw_res, dict):
            res_dict = cast(dict[str, object], raw_res)
            if "result" in res_dict:
                return res_dict["result"]

            if "error" not in res_dict:
                raise ConnectionError(
                    f"Unexpected response from GLinet router {res_dict}"
                )

            error_obj = res_dict.get("error")
            if isinstance(error_obj, dict):
                error_dict = cast(dict[str, object], error_obj)
                if "message" not in error_dict:
                    error_dict["message"] = "null"

                code_val = error_dict.get("code", 0)
                code = int(code_val) if isinstance(code_val, int | str) else 0
                msg = str(error_dict.get("message", "null"))

                if code == -1:
                    raise TokenError(f"Request returned error code -1 ({msg})")
                if code == -32000:
                    raise AuthenticationError(
                        f"Request returned error code -32000 ({msg})"
                    )
                if code == -32003:
                    raise LockoutError(f"Request returned error code -32003 ({msg})")
                if code < 0:
                    raise NonZeroResponse(
                        f"Request returned error code {code} with message: {msg}"
                    )

        return raw_res

    raise UnsuccessfulRequest(
        f"Request failed with status {response.status}: {raw_res}"
    )


__all__ = [
    "APIClientError",
    "AuthenticationError",
    "LockoutError",
    "NonZeroResponse",
    "TokenError",
    "UnsuccessfulRequest",
    "raise_for_status",
]
