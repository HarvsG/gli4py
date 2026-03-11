"""This module contains custom exceptions and a function to handle API response status codes."""

from aiohttp import ClientResponse


class APIClientError(Exception):
    """Base class for all exceptions raised by the API client"""


class UnsuccessfulRequest(APIClientError):
    """raised when the status code is not 200"""


class NonZeroResponse(APIClientError):
    """raised when the router responds but with a non 0 code"""


class AuthenticationError(NonZeroResponse):
    """raised when for authentication errors, such as invalid token or password"""


class TokenError(AuthenticationError):
    """Should be raised when the token is invalid or expired"""

async def raise_for_status(response: ClientResponse) -> dict:
    """Checks whether or not the response was successful."""

    # 1. Safely read the body as JSON, falling back to text if it's HTML
    try:
        # content_type=None forces aiohttp to parse it even if the router sends the wrong headers
        res = await response.json(content_type=None)
    except Exception as exc:
        text = await response.text()
        raise UnsuccessfulRequest(f"Request failed or returned invalid JSON (Status {response.status}): {text}") from exc

    # 2. Process the GL-iNet logic
    if 200 <= response.status < 300:
        if "result" in res:
            return res["result"]

        if "error" not in res:
            raise ConnectionError(f"Unexpected response from GLinet router {res}")

        if "message" not in res["error"]:
            res["error"]["message"] = "null"

        code = res["error"].get("code", 0)
        if code == -1:
            raise TokenError(f"Request returned error code -1 ({res['error']['message']})")
        if code == -32000:
            raise AuthenticationError(f"Request returned error code -32000 ({res['error']['message']})")
        if code < 0:
            raise NonZeroResponse(f"Request returned error code {code} with message: {res['error']['message']}")

        return res

    raise UnsuccessfulRequest(f"Request failed with status {response.status}: {res}")
