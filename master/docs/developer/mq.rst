.. _Messaging_and_Queues:

Messaging and Queues
====================

As of version 0.9.0, Buildbot uses a message-queueing structure to handle asynchronous notifications in a distributed fashion.
This avoids, for the most part, the need for each master to poll the database, allowing masters to react to events as they happen.

Overview
--------

Buildbot is structured as a hybrid state- and event-based application, which will probably offend adherents of either pattern.
In particular, the most current state is stored in the :doc:`Database <database>`, while any changes to the state are announced in the form of a message.
The content of the messages is sufficient to reconstruct the updated state, allowing external processes to represent "live" state without polling the database.

This split nature immediately brings to light the problem of synchronizing the two interfaces.
Queueing systems can introduce queueing delays as messages propagate.
Likewise, database systems may introduce a delay between committed modifications and the modified data appearing in queries; for example, with MySQL master/slave replication, there can be several seconds' delay before a slave is updated.

Buildbot's MQ connector simply relays messages, and makes no attempt to coordinate the timing of those messages with the corresponding database updates.
It is up to higher layers to apply such coordination.

Connector API
-------------

All access to the queueing infrastructure is mediated by an MQ connector.
The connector's API is defined below.
The connector itself is always available as ``master.mq``, where ``master`` is the current :py:class:`~buildbot.master.BuildMaster` instance.

.. py:module:: buildbot.mq.base

The connector API is quite simple.
It is loosely based on AMQP, although simplified because there is only one exchange (see :ref:`queue-schema`).

All messages include a "routing key", which is a tuple of *7-bit ascii* strings describing the content of the message.
By convention, the first element of the tuple gives the type of the data in the message.
The last element of the tuple describes the event represented by the message.
The remaining elements of the tuple describe attributes of the data in the message that may be useful for filtering; for example, buildsets may usefully be filtered on buildsetids.
The topics and associated message types are described below in :ref:`message-schema`.

Filters are also specified with tuples.
For a filter to match a routing key, it must have the same length, and each element of the filter that is not None must match the corresponding routing key element exactly.

.. py:class:: MQConnector

    This is an abstract parent class for MQ connectors, and defines the interface.
    It should not be instantiated directly.
    It is a subclass of :py:class:`buildbot.util.service.AsyncService`, and subclasses can override service methods to start and stop the connector.

    .. py:method:: produce(routing_key, data)

        :param tuple routing_key: the routing key for this message
        :param data: JSON-serializable body of the message

        This method produces a new message and queues it for delivery to any associated consumers.

        The routing key and data should match one of the formats given in :ref:`message-schema`.

        The method returns immediately; the caller will not receive any indication of a failure to transmit the message, although errors will be displayed in ``twistd.log``.

    .. py:method:: startConsuming(callback, filter[, persistent_name=name])

        :param callback: callable to invoke for matching messages
        :param tuple filter: filter for routing keys of interest
        :param persistent_name: persistent name for this consumer
        :returns: a :py:class:`QueueRef` instance via Deferred

        This method will begin consuming messages matching the filter, invoking ``callback`` for each message.
        See above for the format of the filter.

        The callback will be invoked with two arguments: the message's routing key and the message body, as a Python data structure.
        It may return a Deferred, but no special processing other than error handling will be applied to that Deferred.
        In particular, note that the callback may be invoked a second time before the Deferred from the first invocation fires.

        A message is considered delivered as soon as the callback is invoked - there is no support for acknowledgements or re-queueing unhandled messages.

        Note that the timing of messages is implementation-dependent.
        It is not guaranteed that messages sent before the :py:meth:`startConsuming` method completes will be received.
        In fact, because the registration process may not be immediate, even messages sent after the method completes may not be received.

        If ``persistent_name`` is given, then the consumer is assumed to be persistent, and consumption can be resumed with the given name.
        Messages that arrive when no consumer is active are queued and will be delivered when a consumer becomes active.

.. py:class:: QueueRef

    The :py:class:`QueueRef` returned (via Deferred) from :py:meth:`~MQConnector.startConsuming` can be used to stop consuming messages when they are no longer needed.
    Users should be *very* careful to ensure that consumption is terminated in all cases.

    .. py:method:: stopConsuming()

        Stop invoking the ``callback`` passed to :py:meth:`~MQConnector.startConsuming`.
        This method can be called multiple times for the same :py:class:`QueueRef` instance without harm.

        After the first call to this method has returned, the callback will not be invoked.

Implementations
~~~~~~~~~~~~~~~

Several concrete implementations of the MQ connector exist.
The simplest is intended for cases where only one master exists, similar to the SQLite database support.
The remainder use various existing queueing applications to support distributed communications.

Simple
......

.. py:module:: buildbot.mq.simple

.. py:class:: SimpleMQ

    The :py:class:`SimpleMQ` class implements a local equivalent of a message-queueing server.
    It is intended for Buildbot installations with only one master.

Wamp
....

.. py:module:: buildbot.mq.wamp

.. py:class:: WampMQ

    The :py:class:`WampMQ` class implements message-queueing using a wamp router.
    This class translates the semantics of the buildbot mq api to the semantics of the wamp messaging system.
    The message route is translated to a wamp topic by joining with dot and prefixing with buildbot namespace.
    Example message that is sent via wamp is:

    .. code-block:: python

        topic = "org.buildbot.mq.builds.1.new"
        data = {
            'builderid': 10,
            'buildid': 1,
            'buildrequestid': 13,
            'workerid': 20,
            'complete': False,
            'complete_at': None,
            'masterid': 824,
            'number': 1,
            'results': None,
            'started_at': 1,
            'state_string': u'created'
        }

.. py:module:: buildbot.wamp.connector

.. py:class:: WampConnector

    The :py:class:`WampConnector` class implements a buildbot service for wamp.
    It is managed outside of the mq module as this protocol can also be reused for worker protocol.
    The connector support queuing of requests until the wamp connection is created, but do not support disconnection and reconnection.
    Reconnection will be supported as part of a next release of AutobahnPython (https://github.com/tavendo/AutobahnPython/issues/295).
    There is a chicken and egg problem at the buildbot initialization phasis, so the produce messages are actually not sent with deferred.

.. _queue-schema:

Queue Schema
------------

Buildbot uses a particularly simple architecture: in AMQP terms, all messages are sent to a single topic exchange, and consumers define anonymous queues bound to that exchange.

In future versions of Buildbot, some components (e.g., schedulers) may use durable queues to ensure that messages are not lost when one or more masters are disconnected.

.. _message-schema:

Message Schema
--------------

This section describes the general structure messages.
The specific routing keys and content of each message are described in the relevant sub-section of :ref:`Data_API`.

Routing Keys
~~~~~~~~~~~~

Routing keys are a sequence of strings, usually written with dot separators.
Routing keys are represented with variables when one or more of the words in the key are defined by the content of the message.
For example, ``buildset.$bsid`` describes routing keys such as ``buildset.1984``, where 1984 is the ID of the buildset described by the message body.
Internally, keys are represented as tuples of strings.

Body Format
~~~~~~~~~~~

Message bodies are encoded in JSON.
The top level of each message is an object (a dictionary).

Most simple Python types - strings, numbers, lists, and dictionaries - are mapped directly to the corresponding JSON types.
Timestamps are represented as seconds since the UNIX epoch in message bodies.

Cautions
~~~~~~~~

Message ordering is generally maintained by the backend implementations, but this should not be depended on.
That is, messages originating from the same master are *usually* delivered to consumers in the order they were produced.
Thus, for example, a consumer can expect to see a build request claimed before it is completed.
That said, consumers should be resilient to messages delivered out of order, at the very least by scheduling a "reload" from state stored in the database when messages arrive in an invalid order.

Unit tests should be used to ensure this resiliency.

Some related messages are sent at approximately the same time.
Due to the non-blocking nature of message delivery, consumers should *not* assume that subsequent messages in a sequence remain queued.
For example, upon receipt of a ``buildset.$bsid.new`` message, it is already too late to try to subscribe to the associated build requests messages, as they may already have been consumed.

Schema Changes
~~~~~~~~~~~~~~

Future versions of Buildbot may add keys to messages, or add new messages.
Consumers should expect unknown keys and, if using wildcard topics, unknown messages.
