Messaging and Queues
====================

As of version 0.9.0, Buildbot uses a message-queueing structure to handle
asynchronous notifications in a distributed fashion.  This avoids, for the most
part, the need for each master to poll the database, allowing masters to react
to events as they happen.

Overview
--------

Buildbot is structured as a hybrid state- and event-based application, which
will probably offend adherents of either pattern.  In particular, the most
current state is stored in the :doc:`Database <database>`, while any
changes to the state are announced in the form of a message.  The content of
the messages is sufficient to reconstruct the updated state, allowing external
processes to represent "live" state without polling the database.

This split nature immediately brings to light the problem of synchronizing the
two interfaces.  Queueing systems can introduce queueing delays as messages
propagate.   Likewise, database systems may introduce a delay between committed
modifications and the modified data appearing in queries; for example, with
MySQL master/slave replication, there can be several seconds' delay in a before
a slave is updated.

Buildbot's MQ connector simply relays messages, and makes no attempt to
coordinate the timing of those messages with the corresponding database
updates.  It is up to higher layers to apply such coordination.

Connector API
-------------

All access to the queueing infrastructure is mediated by an MQ connector.  The
connector's API is defined below.  The connector itself is always available as
``master.mq``, where ``master`` is the current
:py:class:`~buildbot.master.BuildMaster` instance.

.. py:module:: buildbot.mq.base

The connector API is quite simple.  It is loosely based on AMQP, although
simplified because there is only one exchange (see :ref:`queue-schema`).

All messages include a "topic", which is a string describing the content of the
message, suitable for filtering.  The topics and associated message types are
described below in :ref:`message-schema`.

.. py:class:: MQConnector

    This is an abstract parent class for MQ connectors, and defines the
    interface.  It should not be instantiated directly.  It is a subclass of
    :py:class:`twisted.application.service.Service`, and subclasses can
    override service methods to start and stop the connector.

    .. py:method:: produce(routing_key, data)

        :param routing_key: the routing key for this message
        :param data: JSON-serializable body of the message

        This method produces a new message and sends it to the exchange for
        dissemination to consumers.

        The routing key and data should match one of the formats given in
        :ref:`message-schema`.

        The method returns immediately; the caller will not receive any
        indication of a failure to transmit the message, although errors will
        be displayed in ``twistd.log``.

    .. py:method:: startConsuming(callback, topic, [topic, ..]
                                [, persistent_name=name])

        :param callback: callable to invoke for matching messages
        :param topic: pattern for routing keys of interest
        :param persistent_name: persistent name for this consumer
        :returns: a :py:class:`QueueRef` instance

        This method will begin consuming messages matching any of the given
        topics, invoking ``callback`` for each message.

        Topics follow the AMQP-defined syntax: routing keys are treated as
        dot-separated sequences of words and matched against topics. A star
        (``*``) in the topic will match any single word, while an octothorpe
        (``#``) will match zero or more words.

        The callback will be invoked with two arguments: the message's routing
        key and the message body, as a Python data structure.  It may return a
        Deferred, but no special processing other than error handling will be
        applied to that Deferred.  In particular, note that the callback may be
        invoked a second time before the Deferred from the first invocation
        fires.

        A message is considered delivered as soon as the callback is invoked -
        there is no support for acknowledgements or re-queueing unhandled
        messages.  This may change in future versions.

        Note that the timing of messages is implementation-dependent.  It is
        not guaranteed that messages sent before the :py:meth:`startConsuming`
        method completes will be received.  In fact, because the registration
        process may not be immediate, even messages sent after the method
        completes may not be received.

        If ``persistent_name`` is given, then the consumer is assumed to be
        persistent, and consumption can be resumed with the given name.
        Messages that arrive when no consumer is active are queued, and will be
        delivered when a consumer becomes active.

.. py:class:: QueueRef

    The :py:class:`QueueRef` returned from
    :py:meth:`~MQConnector.startConsuming` can be used to stop consuming
    messages when they are no longer needed.  Users should be *very* careful to
    ensure that consumption is terminated in all cases.

    .. py:method:: stopConsuming()

        Stop invoking the ``callback`` passed to
        :py:meth:`~MQConnector.startConsuming`.  This method can be called
        multiple times for the same :py:class:`QueueRef` instance without harm.

        After the first call to this method has returned, the callback will not
        be invoked.

Implementations
~~~~~~~~~~~~~~~

Several concrete implementations of the MQ connector exist.  The simplest is
intended for cases where only one master exists, similar to the SQLite database
support.  The remainder use various existing queueing applications to support
distributed communications.

Simple
......

.. py:module:: buildbot.mq.simple

.. py:class:: SimpleConnector

    The :py:class:`SimpleMQ` class implements a local equivalent of a
    message-queueing server.  It is intended for Buildbot installations with
    only one master.

.. index::
    AMQP
    RabbitMQ
    Qpid

AMQP
....

.. py:module:: buildbot.mq.amqp

.. py:class:: AmqpConnector

    The AMQP MQ connector can connect to queuing applications which use AMQP,
    including `RabbitMQ <http://www.rabbitmq.com/>`_ and `Qpid
    <http://qpid.apache.org/>`_.

    The AMQP protocol specifies that most of the server configuration is
    carried out via the protocol itself, so once a server is set up, Buildbot
    can create the necessary queues, exchanges, and so on without additional
    user interaction.

    This connector is based on `txAMQP <https://launchpad.net/txamqp>`_.

ØMQ
...

TBD

.. _queue-schema:

Queue Schema
------------

Buildbot uses a particularly simple architecture: in AMQP terms, all messages
are sent to a single topic exchange, and consumers define queues bound to that
exchange.  The API allows use of persistent queues (the `persistent_name`
argument to :py:meth:`~buildbot.mq.base.MQConnector.consume`).

.. _message-schema:

Message Schema
--------------

TBD
