import logging

from nameko_bayeux_client.exceptions import BayeuxError, Reconnect
from nameko_bayeux_client.constants import Reconnection


logger = logging.getLogger(__name__)


class Channel:

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

    name = '/meta/handshake'

    def compose(self):
        return dict(
            id=self.client.get_next_message_id(),
            channel=self.name,
            version=self.client.version,
            minimumVersion=self.client.minimum_version,
            supportedConnectionTypes=['long-polling'],
        )

    def handle(self, message):
        if not message['successful']:
            raise BayeuxError(
                'Unsuccessful handshake response: {}'
                .format(message.get('error')))
        else:
            logger.info('Hand shook client ID %s', message['clientId'])
            self.client.client_id = message['clientId']


class Connect(Channel):

    name = '/meta/connect'

    def compose(self):
        return super().compose(connectionType='long-polling')

    def handle(self, message):

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

    name = '/meta/disconnect'

    def handle(self, message):
        if not message['successful']:
            raise BayeuxError(
                'Unsuccessful disconnect response: {}'
                .format(message.get('error')))


class Subscribe(Channel):

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

    name = '/meta/unsubscribe'

    def compose(self, channel_name):
        return super().compose(subscription=channel_name)

    def handle(self, message):
        if not message['successful']:
            raise BayeuxError(
                'Unsuccessful unsubscribe response: {}'
                .format(message.get('error')))


class Event(Channel):

    def __init__(self, client, channel_name):
        self.client = client
        self.name = channel_name
        self.callbacks = set()

    def register_callback(self, callback):
        self.callbacks.add(callback)

    def compose(self, data):
        return super().compose(data=data)

    def handle(self, message):
        for callback in self.callbacks:
            callback(message['data'])
