from mock import call, Mock
import pytest

from nameko_bayeux_client import channels, constants, exceptions


class TestChannel:

    @pytest.fixture
    def client(self):
        return Mock()


class TestHandshake(TestChannel):

    @pytest.fixture
    def channel(self, client):
        return channels.Handshake(client)

    def test_compose(self, channel, client):
        assert (
            {
                'channel': '/meta/handshake',
                'id': client.get_next_message_id.return_value,
                'version': client.version,
                'minimumVersion': client.minimum_version,
                'supportedConnectionTypes': ['long-polling'],
            } ==
            channel.compose()
        )

    def test_handle_success(self, channel, client):
        response_message = {
            'successful': True,
            'id': '1',
            'channel': '/meta/handshake',
            'version': '1.0',
            'minimumVersion': '1.0',
            'clientId': '5b1jdngw1jz9g9w176s5z4jha0h8',
            'supportedConnectionTypes': ['long-polling'],
            'ext': {'replay': True},
        }
        channel.handle(response_message)
        assert '5b1jdngw1jz9g9w176s5z4jha0h8' == client.client_id

    @pytest.mark.parametrize('response_message', [
        {'successful': False},
        {'successful': False, 'error': 'Boom!'},
    ])
    def test_handle_failure(self, channel, client, response_message):
        with pytest.raises(exceptions.BayeuxError):
            channel.handle(response_message)


class TestSubscribe(TestChannel):

    @pytest.fixture
    def channel(self, client):
        return channels.Subscribe(client)

    def test_compose(self, channel, client):
        assert (
            {
                'channel': '/meta/subscribe',
                'id': client.get_next_message_id.return_value,
                'clientId': client.client_id,
                'subscription': '/spam/ham',
            } ==
            channel.compose('/spam/ham')
        )

    def test_handle_success(self, channel, client):
        response_message = {
            'successful': True,
            'id': '1',
            'channel': '/meta/subscribe',
            'clientId': '5b1jdngw1jz9g9w176s5z4jha0h8',
            'subscription': '/spam/ham',
        }
        channel.handle(response_message)

    @pytest.mark.parametrize('response_message', [
        {'successful': False},
        {'successful': False, 'error': 'Boom!'},
    ])
    def test_handle_failure(self, channel, client, response_message):
        with pytest.raises(exceptions.BayeuxError):
            channel.handle(response_message)


class TestUnsubscribe(TestChannel):

    @pytest.fixture
    def channel(self, client):
        return channels.Unsubscribe(client)

    def test_compose(self, channel, client):
        assert (
            {
                'channel': '/meta/unsubscribe',
                'id': client.get_next_message_id.return_value,
                'clientId': client.client_id,
                'subscription': '/spam/ham',
            } ==
            channel.compose('/spam/ham')
        )

    def test_handle_success(self, channel, client):
        response_message = {
            'successful': True,
            'id': '1',
            'channel': '/meta/unsubscribe',
            'clientId': '5b1jdngw1jz9g9w176s5z4jha0h8',
            'subscription': '/spam/ham',
        }
        channel.handle(response_message)

    @pytest.mark.parametrize('response_message', [
        {'successful': False},
        {'successful': False, 'error': 'Boom!'},
    ])
    def test_handle_failure(self, channel, client, response_message):
        with pytest.raises(exceptions.BayeuxError):
            channel.handle(response_message)


class TestConnect(TestChannel):

    @pytest.fixture
    def channel(self, client):
        return channels.Connect(client)

    def test_compose(self, channel, client):
        assert (
            {
                'channel': '/meta/connect',
                'id': client.get_next_message_id.return_value,
                'clientId': client.client_id,
                'connectionType': 'long-polling',
            } ==
            channel.compose()
        )

    def test_handle_success(self, channel, client):
        response_message = {
            'successful': True,
            'id': '1',
            'channel': '/meta/connect',
            'clientId': '5b1jdngw1jz9g9w176s5z4jha0h8',
        }
        channel.handle(response_message)

    def test_handle_success_with_advice(self, channel, client):
        response_message = {
            'successful': True,
            'id': '1',
            'channel': '/meta/connect',
            'clientId': '5b1jdngw1jz9g9w176s5z4jha0h8',
            'advice': {
                'reconnect': 'retry',
                'timeout': 111111,
                'interval': 11
            },
        }
        channel.handle(response_message)
        assert constants.Reconnection.retry == client.reconnection
        assert 111111 == client.timeout
        assert 11 == client.interval

    @pytest.mark.parametrize('response_message', [
        {'successful': False},
        {'successful': False, 'error': 'Boom!'},
    ])
    def test_handle_failure(self, channel, client, response_message):
        with pytest.raises(exceptions.BayeuxError):
            channel.handle(response_message)


class TestDisconnect(TestChannel):

    @pytest.fixture
    def channel(self, client):
        return channels.Disconnect(client)

    def test_compose(self, channel, client):
        assert (
            {
                'channel': '/meta/disconnect',
                'id': client.get_next_message_id.return_value,
                'clientId': client.client_id,
            } ==
            channel.compose()
        )

    def test_handle_success(self, channel, client):
        response_message = {
            'successful': True,
            'id': '1',
            'channel': '/meta/disconnect',
            'clientId': '5b1jdngw1jz9g9w176s5z4jha0h8',
        }
        channel.handle(response_message)

    @pytest.mark.parametrize('response_message', [
        {'successful': False},
        {'successful': False, 'error': 'Boom!'},
    ])
    def test_handle_failure(self, channel, client, response_message):
        with pytest.raises(exceptions.BayeuxError):
            channel.handle(response_message)


class TestEvent(TestChannel):

    @pytest.fixture
    def channel_name(self):
        return '/spam/ham'

    @pytest.fixture
    def channel(self, client, channel_name):
        return channels.Event(client, channel_name)

    def test_register_callback(self, client, channel):
        callback_one, callback_two = Mock(), Mock()
        channel.register_callback(callback_one)
        assert {callback_one} == channel.callbacks
        channel.register_callback(callback_two)
        assert {callback_one, callback_two} == channel.callbacks

    def test_compose(self, client, channel, channel_name):
        assert (
            {
                'channel': channel_name,
                'id': client.get_next_message_id.return_value,
                'clientId': client.client_id,
                'data': {'foo': 'bar'},
            } ==
            channel.compose({'foo': 'bar'})
        )

    def test_handle_event_delivery(self, client, channel, channel_name):
        callback_one, callback_two = Mock(), Mock()
        channel.register_callback(callback_one)
        channel.register_callback(callback_two)
        response_message = {
            'id': '1',
            'channel': channel_name,
            'clientId': '5b1jdngw1jz9g9w176s5z4jha0h8',
            'data': {'foo': 'bar'}
        }
        channel.handle(response_message)
        assert (
            [call({'foo': 'bar'})] ==
            callback_one.call_args_list)
        assert (
            [call({'foo': 'bar'})] ==
            callback_two.call_args_list)
