import collections
import json

from eventlet import sleep
from eventlet.event import Event
from mock import call, Mock, patch
from nameko.testing.utils import find_free_port
from nameko.web.handlers import http
import pytest
import requests
import requests_mock


from nameko_bayeux_client.client import BayeuxClient, Reconnection, subscribe


class TestBayeuxClient:

    @pytest.fixture
    def config(self, config):
        config['BAYEUX'] = {
            'VERSION': '1.0',
            'MINIMUM_VERSION': '1.0',
            'SERVER_URI': 'http://localhost/bayeux/'
        }
        return config

    @pytest.fixture
    def client(self, config):

        client = BayeuxClient()

        client.container = collections.namedtuple('container', ('config',))
        client.container.config = config

        client.session = Mock()

        client.setup()

        return client

    def test_setup(self, client, config):
        assert config['BAYEUX']['VERSION'] == client.version
        assert config['BAYEUX']['MINIMUM_VERSION'] == client.minimum_version
        assert config['BAYEUX']['SERVER_URI'] == client.server_uri

    def test_get_authorisation(self, client):
        assert (None, None) == client.get_authorisation()

    def test_send_and_receive(self, client):

        messages_in = {'spam': 'egg in one'}
        messages_out = [{'spam': 'egg out one'}, {'spam': 'egg out two'}]

        response = Mock(
            status_code=200, json=Mock(return_value=messages_out))
        client.session.post.return_value = response

        received = client.send_and_receive(messages_in)

        assert messages_out == received

        assert (
            call(
                client.server_uri,
                timeout=client.timeout,
                headers={'Content-Type': 'application/json'},
                data='[{"spam": "egg in one"}]'
            ) ==
            client.session.post.call_args
        )
        assert 1 == response.raise_for_status.call_count

    def test_send_and_receive_multiple_messages(self, client):

        messages_in = [{'spam': 'egg in one'}, {'spam': 'egg in two'}]
        messages_out = [{'spam': 'egg out one'}, {'spam': 'egg out two'}]

        response = Mock(
            status_code=200, json=Mock(return_value=messages_out))
        client.session.post.return_value = response

        received = client.send_and_receive(messages_in)

        assert messages_out == received

        assert (
            call(
                client.server_uri,
                timeout=client.timeout,
                headers={'Content-Type': 'application/json'},
                data='[{"spam": "egg in one"}, {"spam": "egg in two"}]'
            ) ==
            client.session.post.call_args
        )
        assert 1 == response.raise_for_status.call_count

    @patch.object(BayeuxClient, 'get_authorisation')
    def test_send_and_receive_with_authorisation(
        self, get_authorisation, client
    ):

        messages_in = [{'spam': 'egg in one'}, {'spam': 'egg in two'}]
        messages_out = [{'spam': 'egg out one'}, {'spam': 'egg out two'}]

        response = Mock(
            status_code=200, json=Mock(return_value=messages_out))
        client.session.post.return_value = response

        get_authorisation.return_value = ('Bearer', '*********')

        received = client.send_and_receive(messages_in)

        assert messages_out == received

        assert (
            call(
                client.server_uri,
                timeout=client.timeout,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer *********',
                },
                data='[{"spam": "egg in one"}, {"spam": "egg in two"}]'
            ) ==
            client.session.post.call_args
        )
        assert 1 == response.raise_for_status.call_count

    @patch.object(BayeuxClient, 'send_and_handle')
    @patch.object(BayeuxClient, 'login')
    def test_handshake_logs_in(self, login, send_and_handle, client):
        client.reconnection = Reconnection.retry
        client.handshake()
        assert Reconnection.handshake == client.reconnection
        assert call() == login.call_args


@pytest.fixture
def client_id():
    return '5b1jdngw1jz9g9w176s5z4jha0h8'


@pytest.fixture
def message_maker(config, client_id):

    class MessageMaker:

        def make_handshake_request(self, **fields):
            message = {
                'channel': '/meta/handshake',
                'id': 1,
                'version': config['BAYEUX']['VERSION'],
                'minimumVersion': config['BAYEUX']['MINIMUM_VERSION'],
                'supportedConnectionTypes': ['long-polling'],
            }
            message.update(**fields)
            return message

        def make_subscribe_request(self, **fields):
            message = {
                'clientId': client_id,
                'channel': '/meta/subscribe',
                'id': 2,
                'subscription': '/topic/example',
            }
            message.update(**fields)
            return message

        def make_connect_request(self, **fields):
            message = {
                'clientId': client_id,
                'id': 4,
                'channel': '/meta/connect',
                'connectionType': 'long-polling',
            }
            message.update(**fields)
            return message

        def make_disconnect_request(self, **fields):
            message = {
                'clientId': client_id,
                'id': 5,
                'channel': '/meta/disconnect',
            }
            message.update(**fields)
            return message

        def make_event_delivery_message(self, **fields):
            message = {
                'data': [],
                'channel': '/topic/example-a',
                'clientId': client_id,
            }
            message.update(**fields)
            return message

        def make_handshake_response(self, **fields):
            message = {
                'successful': True,
                'id': '1',
                'channel': '/meta/handshake',
                'version': '1.0',
                'minimumVersion': '1.0',
                'clientId': client_id,
                'supportedConnectionTypes': ['long-polling'],
                'ext': {'replay': True},
            }
            message.update(**fields)
            return message

        def make_subscribe_response(self, **fields):
            message = {
                    'successful': True,
                    'id': '1',
                    'channel': '/meta/subscribe',
                    'clientId': client_id,
                    'subscription': '/spam/ham',
            }
            message.update(**fields)
            return message

        def make_connect_response(self, **fields):
            message = {
                'successful': True,
                'id': '1',
                'channel': '/meta/connect',
                'clientId': client_id,
            }
            message.update(**fields)
            return message

        def make_disconnect_response(self, **fields):
            message = {
                'successful': True,
                'id': '1',
                'channel': '/meta/disconnect',
                'clientId': client_id,
            }
            message.update(**fields)
            return message

    return MessageMaker()


@pytest.fixture
def cometd_server_port():
    return find_free_port()


@pytest.fixture
def config(cometd_server_port):
    config = {
        'BAYEUX': {
            'VERSION': '1.0',
            'MINIMUM_VERSION': '1.0',
            'SERVER_URI': (
                'http://localhost:{}/cometd'.format(cometd_server_port))
        },
    }
    return config


@pytest.fixture
def tracker():
    return Mock()


@pytest.fixture
def waiter():
    return Event()


@pytest.fixture
def make_cometd_server(
    container_factory, cometd_server_port, message_maker,
    tracker, waiter
):
    """ Return a container to imitating a cometd server
    """

    def _make(responses):

        class CometdServer(object):

            name = "cometd"

            @http('POST', "/cometd")
            def handle(self, request):
                tracker.request(
                    json.loads(request.get_data().decode(encoding='UTF-8')))
                try:
                    return 200, json.dumps(responses.pop(0))
                except IndexError:
                    waiter.send()
                    sleep(0.1)
                    no_events_to_deliver = [
                        message_maker.make_connect_response()]
                    return (200, json.dumps(no_events_to_deliver))

        config = {
            'WEB_SERVER_ADDRESS': 'localhost:{}'.format(cometd_server_port)
        }
        container = container_factory(CometdServer, config)

        return container

    return _make


@pytest.fixture
def run_services(container_factory, config, make_cometd_server, waiter):
    """ Returns services runner
    """

    def _run(service_class, responses):
        """
        Run testing cometd server and example service with tested entrypoints

        Before run, the testing cometd server is preloaded with passed
        responses.

        """

        cometd_server = make_cometd_server(responses)
        container = container_factory(service_class, config)

        cometd_server.start()
        container.start()

        waiter.wait()

        container.kill()
        cometd_server.stop()

    return _run


def test_basic_communication(message_maker, run_services, tracker):
    """
    Test basic communication

    Simulates successful handshake, subscription to two channels and a few
    connection calls with number of events coming from the server for both
    subscribed channels.

    """

    class Service:

        name = 'example-service'

        @subscribe('/topic/example-a')
        def handle_event_a(self, channel, payload):
            tracker.handle_event_a(channel, payload)

        @subscribe('/topic/example-b')
        def handle_event_b(self, channel, payload):
            tracker.handle_event_b(channel, payload)

    responses = [
        # respond to handshake
        [message_maker.make_handshake_response()],
        # respond to subscribe
        [
            message_maker.make_subscribe_response(
                subscription='/topic/example-a'),
            message_maker.make_subscribe_response(
                subscription='/topic/example-b'),
        ],
        # respond to initial connect
        [
            message_maker.make_connect_response(
                advice={'reconnect': Reconnection.retry.value}),
        ],
        # two events to deliver
        [
            message_maker.make_event_delivery_message(
                channel='/topic/example-a', data={'spam': 'one'}),
            message_maker.make_event_delivery_message(
                channel='/topic/example-b', data={'spam': 'two'}),
        ],
        # no event to deliver within server timeout
        [message_maker.make_connect_response()],
        # one event to deliver
        [
            message_maker.make_event_delivery_message(
                channel='/topic/example-a', data={'spam': 'three'})
        ],
    ]

    run_services(Service, responses)

    handshake, subscriptions = tracker.request.call_args_list[:2]
    connect = tracker.request.call_args_list[2:]

    assert handshake == call(
        [message_maker.make_handshake_request(id=1)])

    topics = [
        message.pop('subscription') for message in subscriptions[0][0]
    ]
    assert set(topics) == set(['/topic/example-a', '/topic/example-b'])

    assert connect == [
        call([message_maker.make_connect_request(id=4)]),
        call([message_maker.make_connect_request(id=5)]),
        call([message_maker.make_connect_request(id=6)]),
        call([message_maker.make_connect_request(id=7)]),
        call([message_maker.make_connect_request(id=8)]),
    ]

    assert tracker.handle_event_a.call_args_list == [
        call('/topic/example-a', {'spam': 'one'}),
        call('/topic/example-a', {'spam': 'three'}),
    ]
    assert tracker.handle_event_b.call_args_list == [
        call('/topic/example-b', {'spam': 'two'})
    ]


def test_multiple_subscriptions(message_maker, run_services, tracker):
    """
    Test multiple subscriptions

    The tested service has one channel handled by multiple entrypoints
    and also multiple channels handled by one entrypoint.

    Simulates successful handshake, subscription to three channels
    and a few connection calls with number of events coming from the server
    for subscribed channels.

    """

    class Service:

        name = 'example_service'

        @subscribe('/topic/example-a')
        @subscribe('/topic/example-c')
        def handle_a_and_c(self, channel, payload):
            tracker.handle_a_and_c(channel, payload)

        @subscribe('/topic/example-a')
        @subscribe('/topic/example-b')
        def handle_a_and_b(self, channel, payload):
            tracker.handle_a_and_b(channel, payload)

    responses = [
        # respond to handshake
        [message_maker.make_handshake_response()],
        # respond to subscribe
        [
            message_maker.make_subscribe_response(
                subscription='/topic/example-a'),
            message_maker.make_subscribe_response(
                subscription='/topic/example-b'),
            message_maker.make_subscribe_response(
                subscription='/topic/example-c'),
        ],
        # respond to initial connect
        [
            message_maker.make_connect_response(
                advice={'reconnect': Reconnection.retry.value}),
        ],
        # two events to deliver
        [
            message_maker.make_event_delivery_message(
                channel='/topic/example-a', data={'spam': 'one'}),
            message_maker.make_event_delivery_message(
                channel='/topic/example-b', data={'spam': 'two'}),
        ],
        # no event to deliver within server timeout
        [message_maker.make_connect_response()],
        # another two events to deliver
        [
            message_maker.make_event_delivery_message(
                channel='/topic/example-a', data={'spam': 'three'}),
            message_maker.make_event_delivery_message(
                channel='/topic/example-c', data={'spam': 'four'}),
        ],
    ]

    run_services(Service, responses)

    handshake, subscriptions = tracker.request.call_args_list[:2]
    connect = tracker.request.call_args_list[2:]

    assert handshake == call.request(
        [message_maker.make_handshake_request(id=1)])

    topics = [
        message.pop('subscription') for message in subscriptions[0][0]
    ]
    assert set(topics) == set(
        ['/topic/example-a', '/topic/example-b', '/topic/example-c']
    )

    assert connect == [
        call([message_maker.make_connect_request(id=5)]),
        call([message_maker.make_connect_request(id=6)]),
        call([message_maker.make_connect_request(id=7)]),
        call([message_maker.make_connect_request(id=8)]),
        call([message_maker.make_connect_request(id=9)]),
    ]

    assert tracker.handle_a_and_c.call_args_list == [
        call('/topic/example-a', {'spam': 'one'}),
        call('/topic/example-a', {'spam': 'three'}),
        call('/topic/example-c', {'spam': 'four'}),
    ]
    assert tracker.handle_a_and_b.call_args_list == [
        call('/topic/example-a', {'spam': 'one'}),
        call('/topic/example-b', {'spam': 'two'}),
        call('/topic/example-a', {'spam': 'three'}),
    ]


def test_events_delivered_together_with_subscription_responses(
    message_maker, run_services, tracker
):
    """
    Test events delivered together with subscription responses

    Test the theoretical possibility that events are delivered not only with
    connection responses.

    """

    class Service:

        name = 'example-service'

        @subscribe('/topic/example-a')
        def handle_event_a(self, channel, payload):
            tracker.handle_event_a(channel, payload)

        @subscribe('/topic/example-b')
        def handle_event_b(self, channel, payload):
            tracker.handle_event_b(channel, payload)

    responses = [
        # respond to handshake
        [message_maker.make_handshake_response()],
        # respond to subscribe and at the same time
        # deliver events for subscribed channels
        [
            message_maker.make_subscribe_response(
                subscription='/topic/example-a'),
            message_maker.make_event_delivery_message(
                channel='/topic/example-a', data={'spam': 'one'}),
            message_maker.make_subscribe_response(
                subscription='/topic/example-b'),
            message_maker.make_event_delivery_message(
                channel='/topic/example-b', data={'spam': 'two'}),
        ],
        # respond to initial connect
        [
            message_maker.make_connect_response(
                advice={'reconnect': Reconnection.retry.value}),
        ],
        # two events to deliver
        [
            message_maker.make_event_delivery_message(
                channel='/topic/example-a', data={'spam': 'three'}),
            message_maker.make_event_delivery_message(
                channel='/topic/example-b', data={'spam': 'four'}),
        ],
        # no event to deliver within server timeout
        [message_maker.make_connect_response()],
        # one event to deliver
        [
            message_maker.make_event_delivery_message(
                channel='/topic/example-a', data={'spam': 'five'})
        ],
    ]

    run_services(Service, responses)

    handshake, subscriptions = tracker.request.call_args_list[:2]
    connect = tracker.request.call_args_list[2:]

    assert handshake == call.request(
        [message_maker.make_handshake_request(id=1)])

    topics = [
        message.pop('subscription') for message in subscriptions[0][0]
    ]
    assert set(topics) == set(['/topic/example-a', '/topic/example-b'])

    assert connect == [
        call([message_maker.make_connect_request(id=4)]),
        call([message_maker.make_connect_request(id=5)]),
        call([message_maker.make_connect_request(id=6)]),
        call([message_maker.make_connect_request(id=7)]),
        call([message_maker.make_connect_request(id=8)]),
    ]

    assert tracker.handle_event_a.call_args_list == [
        call('/topic/example-a', {'spam': 'one'}),
        call('/topic/example-a', {'spam': 'three'}),
        call('/topic/example-a', {'spam': 'five'}),
    ]
    assert tracker.handle_event_b.call_args_list == [
        call('/topic/example-b', {'spam': 'two'}),
        call('/topic/example-b', {'spam': 'four'}),
    ]


def test_handlers_do_not_block(
    config, container_factory, make_cometd_server, message_maker,
    run_services, tracker, waiter
):
    """ Test that entrypoints do not block each other
    """

    work_a = Event()
    work_b = Event()

    class Service:

        name = 'example-service'

        @subscribe('/topic/example-a')
        def handle_event_a(self, channel, payload):
            work_a.wait()
            tracker.handle_event_a(channel, payload)

        @subscribe('/topic/example-b')
        def handle_event_b(self, channel, payload):
            work_b.wait()
            tracker.handle_event_b(channel, payload)

    responses = [
        # respond to handshake
        [message_maker.make_handshake_response()],
        # respond to subscribe
        [
            message_maker.make_subscribe_response(
                subscription='/topic/example-a'),
            message_maker.make_subscribe_response(
                subscription='/topic/example-b'),
        ],
        # respond to initial connect
        [
            message_maker.make_connect_response(
                advice={'reconnect': Reconnection.retry.value}),
        ],
        # two events to deliver
        [
            message_maker.make_event_delivery_message(
                channel='/topic/example-a', data={'spam': 'one'}),
            message_maker.make_event_delivery_message(
                channel='/topic/example-b', data={'spam': 'two'}),
        ],
    ]

    cometd_server = make_cometd_server(responses)
    container = container_factory(Service, config)

    cometd_server.start()
    container.start()

    try:

        # both handlers are still working
        assert (
            tracker.handle_event_a.call_args_list ==
            [])
        assert (
            tracker.handle_event_b.call_args_list ==
            [])

        # finish work of the second handler
        work_b.send()
        sleep(0.1)

        # second handler is done
        assert (
            tracker.handle_event_a.call_args_list ==
            [])
        assert (
            tracker.handle_event_b.call_args_list ==
            [call('/topic/example-b', {'spam': 'two'})])

        # finish work of the first handler
        work_a.send()
        sleep(0.1)

        # first handler is done
        assert (
            tracker.handle_event_a.call_args_list ==
            [call('/topic/example-a', {'spam': 'one'})])
        assert (
            tracker.handle_event_b.call_args_list ==
            [call('/topic/example-b', {'spam': 'two'})])

    finally:
        if not work_a.ready():
            work_a.send()
        if not work_b.ready():
            work_b.send()
        waiter.wait()
        container.kill()
        cometd_server.stop()


def fail_with(exception_class):
    def callback(request, context):
        raise exception_class('Yo!')
    return callback


class MockedCometdServerTestCase:

    @pytest.fixture
    def service(self, config, container_factory, tracker):

        class Service:

            name = 'example_service'

            @subscribe('/topic/example')
            def handle_event(self, channel, payload):
                tracker.handle_event(channel, payload)

        container = container_factory(Service, config)

        return container

    @pytest.fixture
    def cometd_server(self, config, message_maker, responses, waiter):

        def terminating_callback(request, context):
            waiter.send()
            return [message_maker.make_connect_response()]

        responses.extend([
            {'json': terminating_callback},
            {'json': [message_maker.make_disconnect_response()]},
        ])

        with requests_mock.Mocker() as mocked_requests:

            mocked_requests.post(config['BAYEUX']['SERVER_URI'], responses)

            yield mocked_requests

    @pytest.fixture
    def stack(self, cometd_server, responses, service, waiter):
        service.start()
        waiter.wait()
        yield
        service.stop()


class TestHandshakeFailing(MockedCometdServerTestCase):
    """
    Test failing handshakes

    If a handshake fails, the whole process should be repeated from scratch.

    """

    @pytest.fixture
    def responses(self, message_maker):
        responses = [
            #
            # Fail three times when trying to handshake
            #
            {
                'status_code': 500,
                'json': [message_maker.make_handshake_response()]},
            {'json': fail_with(requests.ConnectionError)},
            {'json': fail_with(requests.Timeout)},
            #
            # Fourth attempt to handshake successful, carry on with normal
            # subscribe, connect scenario...
            #
            {'json': [message_maker.make_handshake_response()]},
            {
                'json': [
                    message_maker.make_subscribe_response(
                        subscription='/topic/example'),
                ],
            },
            {
                'json': [
                    message_maker.make_connect_response(
                        advice={'reconnect': Reconnection.retry.value}),
                ],
            },
            {'json': [message_maker.make_connect_response()]},
        ]
        return responses

    def test_handshake_failing(self, cometd_server, message_maker, stack):
        assert (
            [request.json() for request in cometd_server.request_history] ==
            [
                [message_maker.make_handshake_request(id=1)],
                [message_maker.make_handshake_request(id=2)],
                [message_maker.make_handshake_request(id=3)],
                [message_maker.make_handshake_request(id=4)],
                [
                    message_maker.make_subscribe_request(
                        id=5, subscription='/topic/example'),
                ],
                [message_maker.make_connect_request(id=6)],
                [message_maker.make_connect_request(id=7)],
                [message_maker.make_connect_request(id=8)],
            ]
        )


class TestSubscriptionFailing(MockedCometdServerTestCase):
    """
    Test failing subscription

    If subscription fails, the whole process should be repeated from scratch
    (starting from the handshake).

    """

    @pytest.fixture
    def responses(self, message_maker):
        responses = [
            #
            # successful handshake
            #
            {'json': [message_maker.make_handshake_response()]},
            #
            # subscription fails
            #
            {'json': fail_with(requests.ConnectionError)},
            #
            # starting with a handshake again - successful
            #
            {'json': [message_maker.make_handshake_response()]},
            #
            # whoops, subscription fails again
            #
            {'json': fail_with(requests.Timeout)},
            #
            # starting with a handshake again - successful
            #
            {'json': [message_maker.make_handshake_response()]},
            #
            # finally, the subscription went well, carry on with normal
            # connection scenario...
            {
                'status_code': 200,
                'json': [
                    message_maker.make_subscribe_response(
                        subscription='/topic/example'),
                ],
            },
            {
                'status_code': 200,
                'json': [
                    message_maker.make_connect_response(
                        advice={'reconnect': Reconnection.retry.value}),
                ],
            },
            {'json': [message_maker.make_connect_response()]},
        ]
        return responses

    def test_subscription_failing(self, cometd_server, message_maker, stack):
        assert (
            [request.json() for request in cometd_server.request_history] ==
            [
                [message_maker.make_handshake_request(id=1)],
                [
                    message_maker.make_subscribe_request(
                        id=2, subscription='/topic/example'),
                ],
                [message_maker.make_handshake_request(id=3)],
                [
                    message_maker.make_subscribe_request(
                        id=4, subscription='/topic/example'),
                ],
                [message_maker.make_handshake_request(id=5)],
                [
                    message_maker.make_subscribe_request(
                        id=6, subscription='/topic/example'),
                ],
                [message_maker.make_connect_request(id=7)],
                [message_maker.make_connect_request(id=8)],
                [message_maker.make_connect_request(id=9)],
            ]
        )


class TestConnectionFailingHandshakeReconnection(MockedCometdServerTestCase):
    """
    Test failing connection when handshake reconnect strategy set

    If connection fails and the reconnect strategy is set to handshake,
    the whole process should be repeated from scratch (starting from
    the handshake).

    """

    @pytest.fixture
    def responses(self, message_maker):
        responses = [
            #
            # successful handshake, subscription
            # by default, reconnect is set handshake
            #
            {'json': [message_maker.make_handshake_response()]},
            {
                'status_code': 200,
                'json': [
                    message_maker.make_subscribe_response(
                        subscription='/topic/example'),
                ],
            },
            #
            # connection fails, twice...
            #
            {'json': fail_with(requests.ConnectionError)},
            {'json': [message_maker.make_handshake_response()]},
            {
                'status_code': 200,
                'json': [
                    message_maker.make_subscribe_response(
                        subscription='/topic/example'),
                ],
            },
            {'json': fail_with(requests.Timeout)},
            {'json': [message_maker.make_handshake_response()]},
            {
                'status_code': 200,
                'json': [
                    message_maker.make_subscribe_response(
                        subscription='/topic/example'),
                ],
            },
            #
            # third connection is successful ...
            #
            {
                'status_code': 200,
                'json': [
                    message_maker.make_connect_response(
                        advice={'reconnect': Reconnection.retry.value}),
                ],
            },
            {'json': [message_maker.make_connect_response()]},
        ]
        return responses

    def test_connection_failing_handshake_reconnection(
        self, cometd_server, message_maker, stack
    ):
        assert (
            [request.json() for request in cometd_server.request_history] ==
            [
                [message_maker.make_handshake_request(id=1)],
                [
                    message_maker.make_subscribe_request(
                        id=2, subscription='/topic/example'),
                ],
                [message_maker.make_connect_request(id=3)],
                [message_maker.make_handshake_request(id=4)],
                [
                    message_maker.make_subscribe_request(
                        id=5, subscription='/topic/example'),
                ],
                [message_maker.make_connect_request(id=6)],
                [message_maker.make_handshake_request(id=7)],
                [
                    message_maker.make_subscribe_request(
                        id=8, subscription='/topic/example'),
                ],
                [message_maker.make_connect_request(id=9)],
                [message_maker.make_connect_request(id=10)],
                [message_maker.make_connect_request(id=11)],
            ]
        )


class TestConnectionFailingRetryReconnection(MockedCometdServerTestCase):
    """
    Test failing connection when retry reconnect strategy set

    If connection fails and the reconnect strategy is set to retry, the client
    should reconnect with another connection.

    """

    @pytest.fixture
    def responses(self, message_maker):
        responses = [
            #
            # successful handshake, subscription and initial connection
            # (the initial connection sets the reconnect strategy to retry)
            #
            {'json': [message_maker.make_handshake_response()]},
            {
                'status_code': 200,
                'json': [
                    message_maker.make_subscribe_response(
                        subscription='/topic/example'),
                ],
            },
            {
                'status_code': 200,
                'json': [
                    message_maker.make_connect_response(
                        advice={'reconnect': Reconnection.retry.value}),
                ],
            },
            #
            # connection fails, twice...
            #
            {'json': fail_with(requests.ConnectionError)},
            {'json': fail_with(requests.Timeout)},
            #
            # third connection is successful ...
            #
            {
                'status_code': 200,
                'json': [
                    message_maker.make_connect_response(
                        advice={'reconnect': Reconnection.retry.value}),
                ],
            },
            {'json': [message_maker.make_connect_response()]},
        ]
        return responses

    def test_connection_failing_retry_reconnection(
        self, cometd_server, message_maker, stack
    ):
        assert (
            [request.json() for request in cometd_server.request_history] ==
            [
                [message_maker.make_handshake_request(id=1)],
                [
                    message_maker.make_subscribe_request(
                        id=2, subscription='/topic/example'),
                ],
                [message_maker.make_connect_request(id=3)],
                [message_maker.make_connect_request(id=4)],
                [message_maker.make_connect_request(id=5)],
                [message_maker.make_connect_request(id=6)],
                [message_maker.make_connect_request(id=7)],
                [message_maker.make_connect_request(id=8)],
            ]
        )


class TestConnectionFailingUnsuccessfulResponseMessage(
    MockedCometdServerTestCase
):
    """
    Test failing connection on unsuccessful connection response message

    If a connection response message does not contain `successful` key set
    to `True` the client should reconnect. The test simulates "handshake"
    reconnection.

    """

    @pytest.fixture
    def responses(self, message_maker):
        responses = [
            #
            # successful handshake, subscription and initial connection
            # (the initial connection sets the reconnect strategy to retry)
            #
            {'json': [message_maker.make_handshake_response()]},
            {
                'status_code': 200,
                'json': [
                    message_maker.make_subscribe_response(
                        subscription='/topic/example'),
                ],
            },
            {
                'status_code': 200,
                'json': [
                    message_maker.make_connect_response(
                        advice={'reconnect': Reconnection.retry.value}),
                ],
            },
            #
            # first connect is successful (with no event)
            #
            {'json': [message_maker.make_connect_response()]},
            #
            # second connection gets failing response with and advice setting
            # the reconnect strategy to handshake
            #
            {
                'status_code': 200,
                'json': [
                    message_maker.make_connect_response(
                        successful=False,
                        error='403::Unknown client',
                        advice={'reconnect': Reconnection.handshake.value}),
                ],
            },
            #
            # Reconnected from scratch (starting with handshake)
            #
            {'json': [message_maker.make_handshake_response()]},
            {
                'status_code': 200,
                'json': [
                    message_maker.make_subscribe_response(
                        subscription='/topic/example'),
                ],
            },
            {
                'status_code': 200,
                'json': [
                    message_maker.make_connect_response(
                        advice={'reconnect': Reconnection.retry.value}),
                ],
            },
            {'json': [message_maker.make_connect_response()]},
        ]
        return responses

    def test_connection_failing_on_unsuccessful_connection_response_message(
        self, cometd_server, message_maker, stack
    ):
        assert (
            [request.json() for request in cometd_server.request_history] ==
            [
                [message_maker.make_handshake_request(id=1)],
                [
                    message_maker.make_subscribe_request(
                        id=2, subscription='/topic/example'),
                ],
                [message_maker.make_connect_request(id=3)],
                [message_maker.make_connect_request(id=4)],
                [message_maker.make_connect_request(id=5)],
                [message_maker.make_handshake_request(id=6)],
                [
                    message_maker.make_subscribe_request(
                        id=7, subscription='/topic/example'),
                ],
                [message_maker.make_connect_request(id=8)],
                [message_maker.make_connect_request(id=9)],
                [message_maker.make_connect_request(id=10)],
            ]
        )
