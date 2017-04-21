import logging

from nameko_bayeux_client.exceptions import BayeuxError, Reconnect
from nameko_bayeux_client.constants import Reconnection


logger = logging.getLogger(__name__)


class Channel:
    """
    Bayeux channel base class

    Only long-polling connection type is supported by this implementation.

    """

    name = NotImplemented

    def __init__(self, client):
        self.client = client

    def compose(self, **fields):
        """
        Compose channel specific request message

        Returns a dictionary representing the channel request message.

        """
        return dict(
            id=self.client.get_next_message_id(),
            channel=self.name,
            clientId=self.client.client_id,
            **fields
        )

    def handle(self, message):
        """ Handle channel specific response message
        """


class Handshake(Channel):
    """
    Handshake channel for connection negotiation

    A client SHOULD NOT send any other message in the request with
    a handshake message. A server MUST ignore any other message sent
    in the same request as a handshake message.

    """

    name = '/meta/handshake'

    def compose(self):
        """ Compose a handshake request message """
        return dict(
            id=self.client.get_next_message_id(),
            channel=self.name,
            version=self.client.version,
            minimumVersion=self.client.minimum_version,
            supportedConnectionTypes=['long-polling'],
        )

    def handle(self, message):
        """
        Handle handshake response message

        Does not support renegotiating - expects the client ID to be sent
        back with the first handshake response. Ignores advices on handshake
        level.

        """
        if not message['successful']:
            raise BayeuxError(
                'Unsuccessful handshake response: {}'
                .format(message.get('error')))
        else:
            logger.info('Hand shook client ID %s', message['clientId'])
            self.client.client_id = message['clientId']


class Connect(Channel):
    """
    Connect channel

    After a Bayeux client has discovered the server’s capabilities with
    a handshake exchange, a connection is established by sending a message
    to the /meta/connect channel. A client MAY send other messages in the same
    HTTP request with a connection message.

    """

    name = '/meta/connect'

    def compose(self):
        """ Compose a connection request message """
        return super().compose(connectionType='long-polling')

    def handle(self, message):
        """ Handle connection response message """

        self._set_timeout(message)
        self._set_interval(message)
        self._set_reconnect(message)

        if not message['successful']:
            raise Reconnect(
                'Unsuccessful connect response: {}'
                .format(message.get('error')))

    def _set_timeout(self, message):
        timeout = message.get('advice', {}).get('timeout')
        if timeout is not None:
            logger.info('Taking advice timeout=%s', timeout)
            self.client.timeout = timeout

    def _set_interval(self, message):
        interval = message.get('advice', {}).get('interval')
        if interval is not None:
            logger.info('Taking advice interval=%s', interval)
            self.client.interval = interval

    def _set_reconnect(self, message):
        reconnect = message.get('advice', {}).get('reconnect')
        if reconnect is not None:
            logger.info('Taking advice reconnect=%s', reconnect)
            self.client.reconnection = Reconnection(reconnect)


class Disconnect(Channel):
    """
    Disconnect channel

    When a connected client wishes to cease operation it should send
    a request to the /meta/disconnect channel for the server to remove
    any client-related state.

    """

    name = '/meta/disconnect'

    def handle(self, message):
        """ Handle disconnect response message """
        if not message['successful']:
            raise BayeuxError(
                'Unsuccessful disconnect response: {}'
                .format(message.get('error')))


class Subscribe(Channel):
    """
    Subscribe channel

    A connected Bayeux client may send subscribe messages to register
    interest in a channel and to request that messages published to that
    channel are delivered to itself. A Bayeux server MUST respond to
    a subscribe response message. A Bayeux server MAY send event messages
    for the client in the same HTTP response as the subscribe response,
    including events for the channels just subscribed to.

    """

    name = '/meta/subscribe'

    def compose(self, channel_name):
        """ Compose a subscribe request message """
        return super().compose(subscription=channel_name)

    def handle(self, message):
        """ Handle subscribe response message """
        if not message['successful']:
            raise BayeuxError(
                'Unsuccessful subscribe response: {}'
                .format(message.get('error')))


class Unsubscribe(Channel):
    """
    Unsubscribe channel

    A connected Bayeux client may send unsubscribe messages to cancel interest
    in a channel and to request that messages published to that channel are
    not delivered to itself. A Bayeux server MUST respond an unsubscribe
    response message. A Bayeux server MAY send event messages for the client
    in the same HTTP response as the unsubscribe response, including events
    for the channels just unsubscribed to as long as the event was processed
    before the unsubscribe request.

    """

    name = '/meta/unsubscribe'

    def compose(self, channel_name):
        """ Compose an unsubscribe request message """
        return super().compose(subscription=channel_name)

    def handle(self, message):
        """ Handle unsubscribe response message """
        if not message['successful']:
            raise BayeuxError(
                'Unsuccessful unsubscribe response: {}'
                .format(message.get('error')))


class Event(Channel):
    """
    Event channel

    Application events are published in event messages sent from a Bayeux
    client to a Bayeux server and are delivered in event messages sent from
    a Bayeux server to a Bayeux client.

    """

    def __init__(self, client, channel_name):
        self.client = client
        self.name = channel_name
        self.callbacks = set()

    def register_callback(self, callback):
        """
        Register a callback to be called when handling the event

        An event can have multiple callbacks. Each callback is then handled
        by a separate Nameko worker if multiple entrypoints are subscribed
        to the same channel.

        """
        self.callbacks.add(callback)

    def compose(self, data):
        """ Compose an event message to be published """
        return super().compose(data=data)

    def handle(self, message):
        """ Handle delivered event message """
        for callback in self.callbacks:
            callback(message['data'])
