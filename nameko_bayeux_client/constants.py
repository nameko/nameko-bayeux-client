from enum import Enum


class Reconnection(Enum):
    """
    Reconnection options

    Indicates how the client should act in the case of a failure to connect.

    """

    retry = 'retry'
    """
    Reconnect with a connection request

    A client MAY attempt to reconnect with a /meta/connect message after
    the interval (as defined by interval advice field or client-default
    backoff), and with the same credentials.

    """

    handshake = 'handshake'
    """
    Reconnect with a handshake request

    The server has terminated any prior connection status and the client
    MUST reconnect with a /meta/handshake message. A client MUST NOT
    automatically retry when a reconnect advice handshake has been received.

    """

    none = 'none'
    """
    Do NOT reconnect

    Indicates a hard failure for the connect attempt. A client MUST respect
    reconnect advice none and MUST NOT automatically retry or handshake.

    """
