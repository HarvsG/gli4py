import traceback
from requests import Response
from json import loads
import asyncio
import uplink
class UnsuccessfulRequest(Exception):
    '''raised when the status code is not 200'''


class NonZeroResponse(Exception):
    '''raised when the router responds but with a non O code'''

class TokenError(Exception):
    '''raised when the router responds but with a -1 code'''


def raise_for_status(response: Response) -> dict:
    """Checks whether or not the response was successful."""
    if 200 <= response.status < 300:
        res: dict = loads(response.text())
        if 'result' in res:
            return res['result']
        # Gl-inet's api uses its own error codes that are returned in
        # status 200 messages - this is out of spec so we must handle it
        if 'error' not in res:
            raise ConnectionError("Unexpected response from GLinet router %s" % res)
        if res['error']['code'] == -1:
            raise TokenError("Request returned error code -1 (InvalidAuth), is the token expired or the passowrd wrong?")
        if res['error']['code'] < 0:
            if 'message' not in res['error']:
                res['error']['message'] = "null"

            raise NonZeroResponse("Request returned error code %s with message:' %s'. Full response %s" % (res['error']['code'], res['error']['message'],res))

    raise UnsuccessfulRequest(response.status_code, response.url)

#TODO
# @uplink.error_handler
# def timeout_error(exc_type: Exception, exc_val: TimeoutError, exc_tb: traceback):
#     # wrap client error with custom API error
#     print("some error")
#     print(exc_type)
#     print("some val")
#     print(exc_val)
#     print("some tb")
#     print(exc_tb)
#     print("-----------------")
#     if isinstance(exc_val, asyncio.exceptions.TimeoutError):
#         print("timeout error")
#         return {"code":408}
#     raise exc_val