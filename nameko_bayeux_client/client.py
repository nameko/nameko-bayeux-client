import collections
import json
import logging

import eventlet
import requests

from nameko.extensions import Entrypoint, ProviderCollector, SharedExtension

from nameko_bayeux_client import channels
from nameko_bayeux_client.exceptions import Reconnect
from nameko_bayeux_client.constants import Reconnection


logger = logging.getLogger(__name__)


class BayeuxClient(SharedExtension, ProviderCollector):
    """
    Bayeux protocol communication client for inbound event delivery

    """

    def __init__(self):

        super().__init__()

        self.version = None
        """ Bayeux protocol version """

        self.minimum_version = None
        """
        Minimum Bayeux protocol version

        Indicates the oldest protocol version that can be handled
        by the client/server

        """

        self.server_uri = None
        """ Bayeux server URI """

        self.client_id = None
        """
        Unique identification of the client to the Bayeux server

        The id is given to the client during the handshake negotiation.

        """

        self.message_id = 0
        """ Unique identification of a message """

        self.session = requests.Session()
        """ Requests session for sending HTTP requests to Bayeux server """

        self.timeout = 110000
        """
        Long polling timeout

        The number of milliseconds the server will hold the long poll request

        """

        self.interval = 1
        """
        Long polling interval

        The number of milliseconds the client SHOULD wait before issuing
        another long poll request.

        """

        self.reconnection = Reconnection.handshake
        """
        Reconnection options

        Indicates how the client should act in the case of a failure
        to connect.

        """

        self._channels = {}
        self._subscriptions = set()

    def setup(self):
        config = self.container.config.get('BAYEUX', {})
        self.version = config.get('VERSION', '1.0')
        self.minimum_version = config.get('MINIMUM_VERSION', '1.0')
        self.server_uri = config.get('SERVER_URI', 'http://localhost/cometd')

    def start(self):
        self._register_channels()
        self.container.spawn_managed_thread(self.run)

    def _register_channels(self):
        self.register_channel(channels.Handshake(self))
        self.register_channel(channels.Connect(self))
        self.register_channel(channels.Disconnect(self))
        self.register_channel(channels.Subscribe(self))
        self.register_channel(channels.Unsubscribe(self))
        for provider in self._providers:
            self.register_event_handler(
                provider.channel_name, provider.handle_message)

    def register_channel(self, channel):
        self._channels[channel.name] = channel

    def register_event_handler(self, channel_name, callback):
        channel = self._channels.get(channel_name)
        if not channel:
            channel = channels.Event(self, channel_name)
            self.register_channel(channel)
        channel.register_callback(callback)
        self._subscriptions.add(channel_name)

    def stop(self):
        self.disconnect()
        super().stop()

    def run(self):
        while True:
            try:
                if self.reconnection != Reconnection.retry:
                    self.handshake()
                    self.subscribe()
                self.connect()
            except Reconnect:
                logger.warning(
                    'Need to reconnect to Bayeux server ...', exc_info=True)
            eventlet.sleep(self.interval * 10 ** -3)  # from milliseconds

    def handshake(self):
        """ Send a handshake request and process the handshake response
        """
        self.reconnection = Reconnection.handshake  # reset reconnection
        self.login()  # authenticate before starting the handshake
        self.send_and_handle(channels.Handshake(self).compose())

    def connect(self):
        """ Send a connect message and precess response messages """
        self.send_and_handle(channels.Connect(self).compose())

    def disconnect(self):
        """ Send a disconnect request and process response messages
        """
        self.send_and_handle(channels.Disconnect(self).compose())

    def subscribe(self):
        """ Send all subscription messages and process response messages
        """
        self.send_and_handle([
            channels.Subscribe(self).compose(channel)
            for channel in self._subscriptions
        ])

    def handle(self, messages):
        """ Handle incoming messages
        """
        for message in messages:
            channel = self._channels[message['channel']]
            channel.handle(message)

    def send_and_handle(self, messages):
        """ Send request messages and handle received response messages
        """
        self.handle(self.send_and_receive(messages))

    def send_and_receive(self, messages):
        """ Send request messages and receive response messages
        """
        try:
            return self._send_and_receive(messages)
        except (
            requests.ConnectionError, requests.HTTPError, requests.Timeout
        ) as exc:
            # TODO 400 HTTPErrors maybe should not be reconnected?
            raise Reconnect(
                'Failed to post request messages to Bayeux server'
            ) from exc

    def _send_and_receive(self, messages_out):

        if not isinstance(messages_out, collections.Sequence):
            messages_out = [messages_out]

        headers = {
            'Content-Type': 'application/json',
        }
        auth_schema, auth_param = self.get_authorisation()
        if auth_schema and auth_param:
            headers['Authorization'] = '{} {}'.format(auth_schema, auth_param)

        logger.debug('Sending Bayeux messages %s', messages_out)

        response = self.session.post(
            self.server_uri,
            timeout=self.timeout,
            headers=headers,
            data=json.dumps(messages_out))
        response.raise_for_status()
        messages_in = response.json()

        logger.debug('Received Bayeux messages %s', messages_in)

        return messages_in

    def login(self):
        """
        Log in and set authentication data

        Override if authentication is required.

        """

    def get_authorisation(self):
        """
        Return schema and param of HTTP Authorization header

        Override if authentication is required.

        """
        return None, None

    def get_next_message_id(self):
        self.message_id += 1
        return self.message_id


class BayeuxMessageHandler(Entrypoint):

    client = BayeuxClient()

    def __init__(self, channel_name):
        self.channel_name = channel_name

    def setup(self):
        self.client.register_provider(self)

    def stop(self):
        self.client.unregister_provider(self)

    def handle_message(self, message):
        args = (self.channel_name, message)
        kwargs = {}
        context_data = {}
        self.container.spawn_worker(
            self, args, kwargs, context_data=context_data,
            handle_result=self.handle_result)

    def handle_result(self, message, worker_ctx, result=None, exc_info=None):
        return result, exc_info


subscribe = BayeuxMessageHandler.decorator
