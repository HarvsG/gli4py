"""A module containing error codes and their corresponding messages for the GL-inet API."""

ERROR_CODES = {
    # This is a copy of the error codes and their messages from the GL-inet API discovered during testing
    # It should be based on the JSON-RPC error codes https://www.jsonrpc.org/specification#error_object
    "-1": "Invalid user, permission denied or not logged in!",
    "-250": "Modem not found",
    "-251": "modem_id missing",
    "-260": "Destination phone number missing",
    "-261": "Message content missing",
    "-204": "Null",
    "-200": "Server must be stopped server before starting client!!!",
    "-32000": "Access denied",  # Seems to be the code for invalid password during authentication, and perhaps has other causes when the password is correct
    "-32601": "Method not found",
}
