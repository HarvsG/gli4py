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


def raise_for_status(response: Response):
    """Checks whether or not the response was successful."""
    if 200 <= response.status < 300:
        # Pass through the response.
        res = loads(response.text())
        # Gl-inet's api uses its own error codes that are returned in
        # status 200 messages - this is out of spec so we must handle it
        if res['code'] == -1:
            raise TokenError("Request returned error code -1 (InvalidAuth), is the token expired or the passowrd wrong?")
        if res['code'] in [-204,-203, -200]: # these error codes represent non-error off states of some endpoints
            return res
        if res['code'] < 0:
            if 'msg' not in res:
                res['msg'] = "null"

            raise NonZeroResponse("Request returned error code %s with message:' %s'. Full response %s" % (res['code'], res['msg'],res))
        return res

    raise UnsuccessfulRequest(response.url)

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