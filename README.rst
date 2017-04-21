.. image:: https://travis-ci.org/Overseas-Student-Living/nameko-bayeux-client.svg?branch=master
    :target: https://travis-ci.org/Overseas-Student-Living/nameko-bayeux-client


Nameko Cometd Bayeux Client
===========================

`Nameko`_ extension with a `Cometd`_ client implementing `Bayeux`_ protocol
supporting server to client event delivery via long-polling HTTP transport.

.. _Nameko: http://nameko.readthedocs.org
.. _Cometd: https://docs.cometd.org/current/reference/
.. _Bayeux: https://docs.cometd.org/current/reference/#_bayeux


Usage
-----

Add Bayeux client configuration to your Nameko config file:

.. code-block:: yaml

    # config.yaml

    BAYEUX:
        VERSION: 1.0
        MINIMUM_VERSION: 1.0
        SERVER_URI: http://example.com/cometd


Decorate entrypoint in your service class:

.. code-block:: python
 
    # service.py

    from nameko_bayeux_client import subscribe

    class Service:

        name = 'some-service'

        @subscribe('/some/topic')
        def handle_event(self, data):
            # this entrypoint is fired on incoming events
            # of '/some/topic' channel
            print(data)


Run your service, providing the config file:

.. code-block:: shell

    $ nameko run service --config config.yaml


On start-up, the extension connects to Cometd server, subscribes and starts
listening to channels defined by entrypoints.
