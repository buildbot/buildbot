.. _Messaging_and_Queues:

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

All messages include a "routing key", which is a tuple of *7-bit ascii* strings describing the content of the message.
By convention, the first element of the tuple gives the type of the data in the message.
The last element of the tuple describes the event represented by the message.
The remaining elements of the tuple describe attributes of the data in the message that may be useful for filtering; for example, buildsets may usefully be filtered on buildsetids.
The topics and associated message types are described below in :ref:`message-schema`.

Filters are also specified with tuples.
For a filter to match a routing key, it must have the same length, and each element of the filter that is not None must match the corresponding routing key element exactly.

.. py:class:: MQConnector

    This is an abstract parent class for MQ connectors, and defines the
    interface.  It should not be instantiated directly.  It is a subclass of
    :py:class:`buildbot.util.service.AsyncService`, and subclasses can
    override service methods to start and stop the connector.

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
        :returns: a :py:class:`QueueRef` instance

        This method will begin consuming messages matching the filter, invoking ``callback`` for each message.  See above for the format of the filter.

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
are sent to a single topic exchange, and consumers define anonymous queues
bound to that exchange.

In future versions of Buildbot, some components (e.g., schedulers) may use
durable queues to ensure that messages are not lost when one or more masters
are disconnected.

.. _message-schema:

Message Schema
--------------

This section describes the structure of each message.  Routing keys are
represented with variables when one or more of the words in the key are defined
by the content of the message.  For example, ``buildset.$bsid`` describes
routing keys such as ``buildset.1984``, where 1984 is the ID of the buildset
described by the message body.

Cautions
~~~~~~~~

Message ordering is generally maintained by the backend implementations, but
this should not be depended on.  That is, messages originating from the same
master are *usually* delivered to consumers in the order they were produced.
Thus, for example, a consumer can expect to see a build request claimed before
it is completed.  That said, consumers should be resilient to messages
delivered out of order, at the very least by scheduling a "reload" from state
stored in the database when messages arrive in an invalid order.

Unit tests should be used to ensure this resiliency.

Some related messages are sent at approximately the same time.  Due to the
non-blocking nature of message delivery, consumers should *not* assume that
subsequent messages in a sequence remain queued.  For example, upon receipt of
a :bb:msg:`buildset.$bsid.new` message, it is already too late to try to
subscribe to the associated build requests messages, as they may already have
been consumed.

Body Format
~~~~~~~~~~~

Message bodies are encoded in JSON.  Most simple Python types - strings,
numbers, lists, and dictionaries - are mapped directly to the corresponding
JSON types. Timestamps are represented as seconds since the UNIX epoch in
message bodies.

The top level of each message is an object (a dictionary), the keys of which
are given in each section, below.

Schema Changes
~~~~~~~~~~~~~~

Future versions of Buildbot may add keys to messages, or add new messages.
Consumers should expect unknown keys and, if using wildcard topics, unknown
messages.

Master Components
~~~~~~~~~~~~~~~~~

Masters use these messages to announce starts, stops, and reconfigurations of
various components.

.. bb:msg:: scheduler.$schedulerid.started (TODO)

    :var $schedulerid: the ID of the scheduler that is starting up
    :key integer schedulerid: the ID of the scheduler that is starting up
    :key integer masterid: the ID of the master where the scheduler is running
    :key string name: the scheduler name
    :key string class: the scheduler class

    This message indicates that a scheduler has started.

.. bb:msg:: scheduler.$schedulerid.stopped (TODO)

    :var $schedulerid: the ID of the scheduler that is starting up
    :key integer schedulerid: the ID of the scheduler that is starting up
    :key integer masterid: the ID of the master where the scheduler is running
    :key string name: the scheduler name
    :key string class: the scheduler class

    This message indicates that a scheduler has stopped.

.. bb:msg:: builder.$builderid.started (TODO)

    :var $builderid: the ID of the builder that is starting up
    :key integer builderid: the ID of the builder that is starting up
    :key integer masterid: the ID of the master where the builder is running
    :key string buildername: the builder name

    This message indicates that a builder has started.

.. bb:msg:: builder.$builderid.stopped (TODO)

    :var $builderid: the ID of the builder that is starting up
    :key integer builderid: the ID of the builder that is starting up
    :key integer masterid: the ID of the master where the builder is running
    :key string buildername: the builder name

    This message indicates that a builder has stopped.

Changes
~~~~~~~

See :bb:rtype:`change`.

Buildsets
~~~~~~~~~

.. bb:msg:: buildset.$bsid.new

    :var $bsid: the ID of the new buildset
    :key bsid: the ID of the new buildset
    :key string external_idstring: arbitrary string for mapping builds
        externally
    :key string reason: reason these builds were triggered
    :key integer sourcestampsetid: source stamp set for this buildset
    :key timestamp submitted_at: time this buildset was created
    :key brids: buildrequest IDs for this buildset
    :type brids: list of integers
    :key object properties: user-specified properties for this change,
        represented as an object mapping keys to tuple (value, source)
    :key string scheduler: the scheduler that created the buildset

    This message indicates that a new buildset has been added, and indicates
    the associated build requests.   Each such build request will be indicated
    with a :bb:msg:`buildrequest.$bsid.$builderid.$brid.new`, but note,
    as mentioned above, that these messages may arrive in any order.

.. bb:msg:: buildset.$bsid.complete

    :var $bsid: the ID of the completed buildset
    :key bsid: the ID of the completed buildset
    :key timestamp complete_at: time this buildset was completed
    :key integer results: aggregate result of this buildset; see
        :ref:`Build-Result-Codes`

    This message indicates that a buildset has been completed: all of its
    constituent build requests are complete, and an aggregate result has been
    calculated for the set.

    Note that, if build requests finish on different masters at approximately
    the same time, it is possible for multiple copies of this message to be
    sent for a single buildset.

Build Requests
~~~~~~~~~~~~~~

Due to the very complex request-claiming semantics Buildbot supportsa (see
:ref:`Claiming-Build-Requests`), build requests are claimed in the database,
and the subsequent messages are considered advisory in nature.  The
:bb:msg:`buildrequest.$bsid.$builderid.$brid.new` and
:bb:msg:`buildrequest.$bsid.$builderid.$brid.unclaimed`, messages indicate that
masters supporting the given builder should, if resources are available,
attempt to claim the requeset in the database.  Only if that attempt succeeds
will the master send a :bb:msg:`buildrequest.$bsid.$builderid.$brid.claimed`
message.

.. bb:msg:: buildrequest.$bsid.$builderid.$brid.new

    :var $bsid: the ID of the buildset containing this build request
    :var $builderid: the ID of the builder this request is for (TODO: just a name for now)
    :var $brid: the ID of the new build request
    :key integer brid: the ID of the new build request
    :key integer bsid: the ID of the buildset containing this build request
    :key string buildername: the name of the builder this request is for
    :key integer builderid: th ID of the builder this request is for (TODO: -1 for now)

    This message indicates that a new build request has been added.

.. bb:msg:: buildrequest.$bsid.$builderid.$brid.claimed

    :var $bsid: the ID of the buildset containing this build request
    :var $builderid: the ID of the builder this request is for (TODO: just a name for now)
    :var $brid: the ID of the new build request
    :key integer bsid: the ID of the buildset containing this build request
    :key integer builderid: th ID of the builder this request is for (TODO: -1 for now)
    :key integer brid: the ID of the new build request
    :key string buildername: the name of the builder this request is for
    :key timestamp claimed_at: time this request was claimed
    :key masterid: objectid of the master claiming this request

    This message indicates that a master has successfully claimed this build
    request and will begin a build.

.. bb:msg:: buildrequest.$bsid.$builderid.$brid.unclaimed

    :var $bsid: the ID of the buildset containing this build request
    :var $builderid: the ID of the builder this request is for (TODO: just a name for now)
    :var $brid: the ID of the new build request
    :key integer brid: the ID of the build request
    :key integer bsid: the ID of the buildset containing this build request
    :key string buildername: the name of the builder this request is for
    :key integer builderid: th ID of the builder this request is for (TODO: -1 for now)

    This message indicates that the build request has been unclaimed, and may
    be available for other masters to claim.  This generally represents
    recovery from an error condition, and may occur several times for the same
    build request, as it is marked as unclaimed by other masters.

.. bb:msg:: buildrequest.$bsid.$builderid.$brid.cancelled (TODO - untested)

    :var $bsid: the ID of the buildset containing this build request
    :var $builderid: the ID of the builder this request is for (TODO: just a name for now)
    :var $brid: the ID of the new build request
    :key integer brid: the ID of the build request
    :key integer bsid: the ID of the buildset containing this build request
    :key string buildername: the name of the builder this request is for
    :key integer builderid: th ID of the builder this request is for (TODO: -1 for now)

    This message indicates that the build request has been cancelled, and
    should not result in a build.  A
    :bb:msg:`buildrequest.$bsid.$builderid.$brid.complete` will be sent as
    well, for consistency.

.. bb:msg:: buildrequest.$bsid.$builderid.$brid.complete

    :var $bsid: the ID of the buildset containing this build request
    :var $builderid: the ID of the builder this request is for (TODO: just a name for now)
    :var $brid: the ID of the new build request
    :key integer brid: the ID of the new build request
    :key integer bsid: the ID of the buildset containing this build request
    :key string buildername: the name of the builder this request is for
    :key integer builderid: th ID of the builder this request is for (TODO: -1 for now)
    :key timestamp complete_at: time this request was completed
    :key integer results: aggregate result of this build request; see
        :ref:`Build-Result-Codes`

    This message indicates that the build request is completed.
    TODO: untested

.. todo::
    user.new
    users in changes?
    slave attach/detach
