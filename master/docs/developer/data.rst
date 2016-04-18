.. _Data_API:

Data API
========

The data layer combines access to stored state and messages, ensuring consistency between them, and exposing a well-defined API that can be used both internally and externally.
Using caching and the clock information provided by the db and mq layers, this layer ensures that its callers can easily receive a dump of current state plus changes to that state, without missing or duplicating messages.

Sections
--------

The data api is divided into four sections:

* getters - fetching data from the db API, and
* subscriptions - subscribing to messages from the mq layer;
* control - allows state to be changed in specific ways by sending appropriate messages (e.g., stopping a build); and
* updates - direct updates to state appropriate messages.

The getters and subscriptions are exposed everywhere.
Access to the control section should be authenticated at higher levels, as the data layer does no authentication.
The updates section is for use only by the process layer.

The interfaces for all sections but the updates sections are intended to be language-agnostic.
That is, they should be callable from JavaScript via HTTP, or via some other interface added to Buildbot after the fact.

Getter
++++++

The getter section can get either a single resource, or a list of resources.
Getting a single resource requires a resource identifier (a tuple of strings) and a set of options to support automatic expansion of links to other resources (thus saving round-trips).
Lists are requested with a partial resource identifier (a tuple of strings) and an optional set of filter options.
In some cases, certain filters are implicit in the path, e.g., the list of buildsteps for a particular build.

Subscriptions
+++++++++++++

Message subscriptions can be made to anything that can be listed or gotten from the getter sections, using the same resource identifiers.
Options and explicit filters are not supported - a message contains only the most basic information about a resource, and a list subscription results in a message for every new resource of the desired type.
Implicit filters are supported.

Control
+++++++

The control sections defines a set of actions that cause Buildbot to behave in a certain way, e.g., rebuilding a build or shutting down a worker.
Actions correspond to a particular resource, although sometimes that resource is the root resource (an empty tuple).

Updates
-------

The updates section defines a free-form set of methods that Buildbot's process implementation calls to update data.
Most update methods both modify state via the db API and send a message via the mq API.
Some are simple wrappers for these APIs, while others contain more complex logic, e.g., building a source stamp set for a collection of changes.
This section is the proper place to put common functionality, e.g., rebuilding builds or assembling buildsets.

Concrete Interfaces
-------------------

Python Interface
++++++++++++++++

.. py:module:: buildbot.data.connector

Within the buildmaster process, the root of the data API is available at `self.master.data`, which is a :py:class:`DataConnector` instance.

.. py:class:: DataConnector

    This class implements the root of the data API.
    Within the buildmaster process, the data connector is available at `self.master.data`.
    The first three sections are implemented with the :py:meth:`get` and :py:meth:`control` methods, respectively, while the updates section is implemented using the :py:attr:`updates` attribute.
    The ``path`` arguments to these methods should always be tuples.
    Integer arguments can be presented as either integers or strings that can be parsed by ``int``; all other arguments must be strings.

    .. py:method:: get(path, filters=None, fields=None, order=None, limit=None, offset=None):

        :param tuple path: A tuple of path elements representing the API path to fetch.
            Numbers can be passed as strings or integers.
        :param filters: result spec filters
        :param fields: result spec fields
        :param order: result spec order
        :param limit: result spec limit
        :param offset: result spec offset
        :raises: :py:exc:`~buildbot.data.exceptions.InvalidPathError`
        :returns: a resource or list via Deferred, or None

        This method implements the getter section.
        Depending on the path, it will return a single resource or a list of resources.
        If a single resource is not specified, it returns ``None``.

        The ``filters``, ``fields``, ``order``, ``limit``, and ``offset`` are passed to the :py:class:`~buildbot.data.resultspec.ResultSpec` constructor.

        The return value is composed of simple Python objects - lists, dicts, strings, numbers, and None.

    .. py:method:: getEndpoint(path)

        :param tuple path: A tuple of path elements representing the API path.
            Numbers can be passed as strings or integers.
        :raises: :py:exc:`~buildbot.data.exceptions.InvalidPathError`
        :returns: tuple of endpoint and a dictionary of keyword arguments from the path

        Get the endpoint responsible for the given path, along with any arguments extracted from the path.
        This can be used by callers that need access to information from the endpoint beyond that returned from ``get``.

    .. py:method:: produceEvent(rtype, msg, event)

        :param rtype: the name identifying a resource type
        :param msg: a dictionary describing the msg to send
        :param event: the event to produce

        This method implements the production of an event, for the rtype identified by its name string.
        Usually, this is the role of the data layer to produce the events inside the update methods.
        For the potential use cases where it would make sense to solely produce an event, and not update data, please use this API, rather than directly call mq.
        It ensures the event is sent to all the routingkeys specified by eventPathPatterns.

    .. py:method:: control(action, args, path)

        :param action: a short string naming the action to perform
        :param args: dictionary containing arguments for the action
        :param tuple path: A tuple of path elements representing the API path.
            Numbers can be passed as strings or integers.
        :raises: :py:exc:`~buildbot.data.exceptions.InvalidPathError`
        :returns: a resource or list via Deferred, or None

        This method implements the control section.
        Depending on the path, it may return a new created resource.

    .. py:method:: allEndpoints()

        :returns: list of endpoint specifications

        This method returns the deprecated API spec.
        Please use :ref:`Raml-Spec` instead.

    .. py:attribute:: rtypes

        This object has an attribute named for each resource type, named after the singular form (e.g., `self.master.data.builder`).
        These attributes allow resource types to access one another for purposes of coordination.
        They are *not* intended for external access -- all external access to the data API should be via the methods above or update methods.

Updates
.......

The updates section is available at `self.master.data.updates`, and contains a number of ad-hoc methods needed by the process modules.

.. note::
    The update methods are implemented in resource type classes, but through some initialization-time magic, all appear as attributes of ``self.master.data.updates``.

The update methods are found in the resource type pages.

Exceptions
..........

.. py:module:: buildbot.data.exceptions

.. py:exception:: DataException

    This is a base class for all other Data API exceptions.

.. py:exception:: InvalidPathError

    The path argument was invalid or unknown.

.. py:exception:: InvalidOptionError

    A value in the ``options`` argument was invalid or ill-formed.

.. py:exception:: SchedulerAlreadyClaimedError

    Identical to :py:exc:`~buildbot.db.schedulers.SchedulerAlreadyClaimedError`.

Web Interface
+++++++++++++

The HTTP interface is implemented by the :py:mod:`buildbot.www` package, as configured by the user.
Part of that configuration is a base URL, which is considered a prefix for all paths mentioned here.

See :ref:`WWW-base-app` for more information.

.. _Data Model:

Extending the Data API
----------------------

.. py:currentmodule:: buildbot.data.base

The data API may be extended in various ways: adding new endpoints, new fields to resource types, new update methods, or entirely new resource types.
In any case, you should only extend the API if you plan to submit the extensions to be merged into Buildbot itself.
Private API extensions are strongly discouraged.

Adding Resource Types
+++++++++++++++++++++

You'll need to use both plural and singular forms of the resource type; in this example, we'll use 'pub' and 'pubs'.
You can also follow an existing file, like :src:`master/buildbot/data/changes.py`, to see when to use which form.

In :src:`master/buildbot/data/pubs.py`, create a subclass of :py:class:`ResourceType`::

    from buildbot.data import base

    class Pub(base.ResourceType):
        name = "pub"
        endpoints = []
        keyFields = ['pubid']

        class EntityType(types.Entity):
            pubid = types.Integer()
            name = types.String()
            num_taps = types.Integer()
            closes_at = types.Integer()

        entityType = EntityType(name)

.. py:class:: ResourceType

    .. py:attribute:: name

        :type: string

        The singular, lower-cased name of the resource type.
        This becomes the first component in message routing keys.

    .. py:attribute:: plural

        :type: string

        The plural, lower-cased name of the resource type.
        This becomes the key containing the data in REST responses.

    .. py:attribute:: endpoints

        :type: list

        Subclasses should set this to a list of endpoint classes for this resource type.

    .. py:attribute:: eventPathPatterns

        :type: str

        This attribute should list the message routes where events should be sent, encoded as a REST like endpoint:

        ``pub/:pubid``

        In the example above, a call to ``produceEvent({'pubid': 10, 'name': 'Winchester'}, 'opened')`` would result in a message with routing key ``('pub', '10', 'opened')``.

        Several paths can be specified in order to be consistent with rest endpoints.

    .. py:attribute:: entityType

        :type: :py:class:`buildbot.data.types.Entity`

        The entity type describes the types of all of the fields in this particular resource type.
        See :py:class:`buildbot.data.types.Entity` and :ref:`Adding-Fields-To-Resource-Types`.

    The parent class provides the following methods

    .. py:method:: getEndpoints()

        :returns: a list of :py:class:`~Endpoint` instances

        This method returns a list of the endpoint instances associated with the resource type.

        The base method instantiates each class in the :py:attr:`~ResourceType.endpoints` attribute.
        Most subclasses can simply list :py:class:`~Endpoint` subclasses in ``endpoints``.

    .. py:method:: produceEvent(msg, event)

        :param dict msg: the message body
        :param string event: the name of the event that has occurred

        This is a convenience method to produce an event message for this resource type.
        It formats the routing key correctly and sends the message, thereby ensuring consistent routing-key structure.

Like all Buildbot source files, every resource type module must have corresponding tests.
These should thoroughly exercise all update methods.

All resource types must be documented in the Buildbot documentation and linked from the bottom of this file (:src:`master/docs/developer/data.rst`).

Adding Endpoints
++++++++++++++++

Each resource path is implemented as an :py:class:`~Endpoint` instance.
In most cases, each instance is of a different class, but this is not required.

The data connector's :py:meth:`~buildbot.data.connector.DataConnector.get` and :py:meth:`~buildbot.data.connector.DataConnector.control` methods both take a ``path`` argument that is used to look up the corresponding endpoint.
The path matching is performed by :py:mod:`buildbot.util.pathmatch`, and supports automatically extracting variable fields from the path.
See that module's description for details.

.. py:class:: Endpoint

    .. py:attribute:: pathPatterns

        :type: string

        This attribute defines the path patterns which incoming paths must match to select this endpoint.
        Paths are specified as URIs, and can contain variables as parsed by :py:class:`buildbot.util.pathmatch.Matcher`.
        Multiple paths are separated by whitespace.

        For example, the following specifies two paths with the second having a single variable::

            pathPatterns = """
                /bugs
                /component/i:component_name/bugs
            """

    .. py:attribute:: rootLinkName

        :type: string

        If set, then the first path pattern for this endpoint will be included as a link in the root of the API.
        This should be set for any endpoints that begin an explorable tree.

    .. py:attribute:: isCollection

        :type: boolean

        If true, then this endpoint returns collections of resources.

    .. py:attribute:: isRaw

        :type: boolean

        If true, then this endpoint returns raw resource.

        Raw resources are used to get the data not encoded in JSON via the rest API.
        In the REST principles, this should be done via another endpoint, and not via a query parameter.
        The get() method from endpoint should return following data structure::

            {
                "raw": u"raw data to be sent to the http client",
                "mime-type": u"<mime-type>",
                "filename": u"filename_to_be_used_in_content_disposition_attachement_header"
            }

    .. py:method:: get(options, resultSpec, kwargs)

        :param dict options: model-specific options
        :param resultSpec: a :py:class:`~buildbot.data.resultspec.ResultSpec` instance describing the desired results
        :param dict kwargs: fields extracted from the path
        :returns: data via Deferred

        Get data from the endpoint.
        This should return either a list of dictionaries (for list endpoints), a dictionary, or None (both for details endpoints).
        The endpoint is free to handle any part of the result spec.
        When doing so, it should remove the relevant configuration from the spec.
        See below.

        Any result spec configuration that remains on return will be applied automatically.

    .. py:method:: control(action, args, kwargs)

        :param action: a short string naming the action to perform
        :param args: dictionary containing arguments for the action
        :param kwargs: fields extracted from the path

Continuing the pub example, a simple endpoint would look like this::

    class PubEndpoint(base.Endpoint):
        pathPattern = ('pub', 'i:pubid')

        def get(self, resultSpec, kwargs):
            return self.master.db.pubs.getPub(kwargs['pubid'])

Endpoint implementations must have unit tests.
An endpoint's path should be documented in the ``.rst`` file for its resource type.

The initial pass at implementing any endpoint should just ignore the ``resultSpec`` argument to ``get``.
After that initial pass, the argument can be used to optimize certain types of queries.
For example, if the resource type has many resources, but most real-life queries use the result spec to filter out all but a few resources from that group, then it makes sense for the endpoint to examine the result spec and allow the underlying DB API to do that filtering.

When an endpoint handles parts of the result spec, it must remove those parts from the spec before it returns.
See the documentation for :py:class:`~buildbot.data.resultspec.ResultSpec` for methods to do so.

Note that endpoints must be careful not to alter the order of the filtering applied for a result spec.
For example, if an endpoint implements pagination, then it must also completely implement filtering and ordering, since those operations precede pagination in the result spec application.

Adding Messages
+++++++++++++++

Message types are defined in :src:`master/buildbot/test/util/validation.py`, via the ``message`` module-level value.
This is a dictionary of ``MessageValidator`` objects, one for each message type.
The message type is determined from the first atom of its routing key.
The ``events`` dictionary lists the possible last atoms of the routing key.
It should be identical to the attribute of the ResourceType with the same name.

Adding Update Methods
+++++++++++++++++++++

Update methods are for use by the Buildbot process code, and as such are generally designed to suit the needs of that code.
They generally encapsulate logic common to multiple users (e.g., creating buildsets), and finish by performing modifications in the database and sending a corresponding message.
In general, Buildbot does not depend on timing of either the database or message broker, so the order in which these operations are initiated is not important.

Update methods are considered part of Buildbot's user-visible interface, and as such incompatible changes should be avoied wherever possible.
Instead, either add a new method (and potentially re-implement existing methods in terms of the new method) or add new, optional parameters to an existing method.
If an incompatible change is unavoidable, it should be described clearly in the release notes.

Update methods are implemented as methods of :py:class:`~buildbot.data.base.ResourceType` subclasses, decorated with ``@base.updateMethod``:

.. py:function:: updateMethod(f)

    A decorator for :py:class:`~buildbot.data.base.ResourceType` subclass methods, indicating that the method should be copied to ``master.data.updates``.

Returning to the pub example::

    class PubResourceType(base.ResourceType):
        # ...
        @base.updateMethod
        @defer.inlineCallbacks
        def setPubTapList(self, pubid, beers):
            pub = yield self.master.db.pubs.getPub(pubid)
            # ...
            self.produceMessage(pub, 'taps-updated')

Update methods should be documented in :src:`master/docs/developer/data.rst`.
They should be thoroughly tested with unit tests.
They should have a fake implentation in :src:`master/buildbot/test/fake/fakedata.py`.
That fake implementation should be tested to match the real implementation in :src:`master/buildbot/test/interfaces/test_data_connector.py`.

.. _Adding-Fields-to-Resource-Types:

Adding Fields to Resource Types
+++++++++++++++++++++++++++++++

.. py:module:: buildbot.data.types

The details of the fields of a resource type are rigorously enforced at several points in the Buildbot tests.
The enforcement is performed by the :py:mod:`buildbot.data.types` module.

The module provides a number of type classes for basic and compound types.
Each resource type class defines its entity type in its :py:attr:`~buildbot.data.base.ResourceType.entityType` class attribute.
Other resource types may refer to this class attribute if they embed an entity of that type.

The types are used both for tests, and by the REST interface to properly decode user-supplied query parameters.

Basic Types
...........

.. py:class:: Integer()

    An integer.

    ::

        myid = types.Integer()

.. py:class:: String()

    A string.
    Strings must always be Unicode.

    ::

        name = types.String()

.. py:class:: Binary()

    A binary bytestring.

    ::

        data = types.Binary()

.. py:class:: Boolean()

    A boolean value.

    ::

        complete = types.Boolean()

.. py:class:: Identifier(length)

    An identifier; see :ref:`Identifier <type-identifier>`.
    The constructor argument specifies the maximum length.

    ::

        ident = types.Identifier(25)

Compound Types
..............

.. py:class:: NoneOk(nestedType)

    Either the nested type, or None.

    ::

        category = types.NoneOk(types.String())

.. py:class:: List(of)

    An list of objects.
    The named constructor argument ``of`` specifies the type of the list elements.

    ::

        tags = types.List(of=types.String())

.. py:class:: SourcedProperties()

    A data structure representing properties with their sources, in the form ``{name: (value, source)}``.
    The property name and source must be Unicode, and the value must be JSON-able.

    ::

        props = types.SourcedProperties()

Entity Type
...........

.. py:class:: Entity(name)

    A data resource is represented by a dictionary with well-known keys.
    To define those keys and their values, subclass the :py:class:`Entity` class within your ResourceType class and include each field as an attribute::

        class MyStuff(base.ResourceType):
            name = "mystuff"
            # ...
            class EntityType(types.Entity):
                myid = types.Integer()
                name = types.String()
                data = types.Binary()
                complete = types.Boolean()
                ident = types.Identifier(25)
                category = types.NoneOk(types.String())
                tags = types.List(of=types.String())
                props = types.SourcedProperties()

    Then instantiate the class with the resource type name::

        entityType = EntityType(name)

    To embed another entity type, reference its entityType class attribute::

        class EntityType(types.Entity):
            # ...
            master = masters.Master.entityType

Data Model
----------

The data api enforces a strong and well-defined model on Buildbot's data.
This model is influenced by REST, in the sense that it defines resources, representations for resources, and identifiers for resources.
For each resource type, the API specifies

* the attributes of the resource and their types (e.g., changes have a string specifying their project);
* the format of links to other resources (e.g., buildsets to sourcestamp sets);
* the paths relating to the resource type;
* the format of routing keys for messages relating to the resource type;
* the events that can occur on that resource (e.g., a buildrequest can be claimed); and
* options and filters for getting resources.

Some resource type attributes only appear in certain formats, as noted in the documentation for the resource types.
In general, messages do not include any optional attributes, nor links.

Paths are given here separated by slashes, with key names prefixed by ``:`` and described below.
Similarly, message routing keys given here are separated by dots, with key names prefixed by ``$``.
The translation to tuples and other formats should be obvious.

All strings in the data model are unicode strings.


.. [#apiv1] The JSON API defined by ``status_json.py`` in Buildbot-0.8.x is considered version 1, although its root path was ``json``, not ``api/v1``.
