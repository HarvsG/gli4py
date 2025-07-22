"""This module contains custom exceptions and a function to handle API response status codes."""
from json import loads
from requests import Response

class APIClientError(Exception):
    '''Base class for all exceptions raised by the API client'''

class UnsuccessfulRequest(APIClientError):
    '''raised when the status code is not 200'''

class NonZeroResponse(APIClientError):
    '''raised when the router responds but with a non 0 code'''

class AuthenticationError(NonZeroResponse):
    '''raised when for authentication errors, such as invalid token or password'''

class TokenError(AuthenticationError):
    '''Should be raised when the token is invalid or expired'''

def raise_for_status(response: Response) -> dict:
    """Checks whether or not the response was successful."""
    if 200 <= response.status < 300:
        res: dict = loads(response.text())
        if 'result' in res:
            return res['result']
        # Gl-inet's api uses its own error codes that are returned in
        # status 200 messages - this is out of spec so we must handle it
        if 'error' not in res:
            raise ConnectionError(f"Unexpected response from GLinet router {res}")
        if 'message' not in res['error']:
            res['error']['message'] = "null"
        if res['error']['code'] == -1:
            raise TokenError(f"Request returned error code -1 ({res['error']['message']}), is the token expired or the password wrong?")
        if res['error']['code'] == -32000:
            raise AuthenticationError(f"Request returned error code -32000 ({res['error']['message']}), is password wrong or the hashing process incorrect?")
        if res['error']['code'] < 0:
            raise NonZeroResponse(f"Request returned error code {res['error']['code']} with message: {res['error']['message']}. Full response: {res}")

    raise UnsuccessfulRequest(response.status_code, response.url)
