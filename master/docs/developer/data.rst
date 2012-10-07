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
 * control -  allows state to be changed in specific ways by sending appropriate messages (e.g., stopping a build); and
 * updates - direct updates to state appropriate messages.

The getters and subscriptions are exposed everywhere.
Access to the control section should be authenticated at higher levels, as the data layer does no authentication.
The updates section is for use only by the process layer.

The interfaces for all sections but the updates sections are intended to be language-agnostic.  That is, they should be callable from JavaScript via HTTP, or via some other interface added to Buildbot after the fact.

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

The control sections defines a set of actions that cause Buildbot to behave in a certain way, e.g., rebuilding a build or shutting down a slave.
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
    The first three sections are implemented with the :py:meth:`get`, :py:meth:`startConsuming`, and :py:meth:`control` methods, respectively, while the updates section is implemented using the :py:attr:`updates` attribute.
    The ``path`` arguments to these methods should always be tuples.  Integer arguments can be presented as either integers or strings that can be parsed by ``int``; all other arguments must be strings.
    Integer arguments can be presented as either integers or strings that can be parsed by ``int``; all other arguments must be strings.

    .. py:method:: get(options, path)

        :param options: dictionary containing model-specific options
        :param path: a tuple describing the resource to get
        :raises: :py:exc:~buildbot.data.exceptions.InvalidPathError
        :returns: a resource or list via Deferred, or None

        This method implements the getter section.
        Depending on the path, it will return a single resource or a list of resources.
        If a single resource is not specified, it returns ``None``.

        The options argument can be used to filter lists of resources, or to affect the amount of associated data returned with a single resource.

        The return value is composed of simple Python objects - lists, dicts, strings, numbers, and None, along with :py:class:`~buildbot.data.base.Link` instances giving paths to other resources.

    .. py:method:: startConsuming(callback, options, path)

        :param callback: a function to call for each message
        :param options: dictionary containing model-specific options
        :param path: a tuple describing the resource to subscribe to
        :raises: :py:exc:~buildbot.data.exceptions.InvalidPathError

        This method implements the subscriptions section.
        The callback interface is the same as that of :py:meth:`~buildbot.mq.connector.MQConnector.startConsuming`.
        The ``path`` argument is automatically translated into an appropriate topic.

    .. py:method:: control(action, args, path)

        :param action: a short string naming the action to perform
        :param args: dictionary containing arguments for the action
        :param path: a tuple describing the resource to act on
        :raises: :py:exc:~buildbot.data.exceptions.InvalidPathError
        :returns: a resource or list via Deferred, or None

        This method implements the getter section.
        Depending on the path, it will return a single resource or a list of resources.
        If a single resource is not specified, it returns ``None``.

Updates
.......

The updates section is available at `self.master.data.updates`, and contains a number of ad-hoc methods needed by the process modules.

.. note:
    The update methods are implemented in resource type classes, but through some initialization-time magic, all appear as attributes of ``self.master.data.updates``.

All update methods return a Deferred.

.. py:class:: buildbot.data.changes.ChangeResourceType

    .. py:method:: addChange(files=None, comments=None, author=None, revision=None, when_timestamp=None, branch=None, category=None, revlink='', properties={}, repository='', codebase=None, project='', src=None)

        :param files: a list of filenames that were changed
        :type files: list of unicode strings
        :param unicode comments: user comments on the change
        :param unicode author: the author of this change
        :param unicode revision: the revision identifier for this change
        :param integer when_timestamp: when this change occurred (seconds since the epoch), or the current time if None
        :param unicode branch: the branch on which this change took place
        :param unicode category: category for this change
        :param string revlink: link to a web view of this revision
        :param properties: properties to set on this change.  Note that the property source is *not* included in this dictionary.
        :type properties: dictionary with unicode keys and simple values (JSON-able).
        :param unicode repository: the repository in which this change took place
        :param unicode project: the project this change is a part of
        :param unicode src: source of the change (vcs or other)
        :returns: the ID of the new change, via Deferred

        Add a new change to Buildbot.
        This method is the interface between change sources and the rest of Buildbot.

        All parameters should be passed as keyword arguments.

        All parameters labeled 'unicode' must be unicode strings and not bytestrings.
        Filenames in ``files``, and property names, must also be unicode strings.
        This is tested by the fake implementation.

.. py:class:: buildbot.data.changes.MasterResourceType

    .. py:method:: masterActive(name, masterid)

        :param unicode name: the name of this master (generally ``hostname:basedir``)
        :param integer masterid: this master's master ID
        :returns: Deferred

        Mark this master as still active.
        This method should be called at startup and at least once per minute.
        The master ID is acquired directly from the database early in the master startup process.

    .. py:method:: expireMasters()

        :returns: Deferred

        Scan the database for masters that have not checked in for ten minutes.
        This method should be called about once per minute.

    .. py:method:: masterStopped(name, masterid)

        :param unicode name: the name of this master
        :param integer masterid: this master's master ID
        :returns: Deferred

        Mark this master as inactive.
        Masters should call this method before completing an expected shutdown.

.. py:class:: buildbot.data.changes.BuildsetResourceType

    .. py:method:: addBuildset(scheduler=None, sourcestampsetid=None, reason='', properties={}, builderNames=[], external_idstring=None)

        :param string scheduler: the name of the scheduler creating this buildset
        :param integer sourcestampsetid: the source stamp set to be built
        :param unicode reason: the reason for this build
        :param unicode reason: the reason for this build
        :param properties: properties to set on this buildset
        :type properties: dictionary with unicode keys and (source, property value) values
        :param list builderNames: names of the builders for which build requests should be created
        :param unicode external_idstring: arbitrary identifier to recognize this buildset later
        :returns: (buildset id, dictionary mapping builder names to build request ids) via Deferred

        .. warning:

            The ``scheduler`` parameter will be replaced with a ``schedulerid`` parameter in future releases.
            The ``builderNames`` parameter will be replaced with a ``builderIds`` parameter in future releases.

        Create a new buildset and corresponding buildrequests based on the given parameters.
        This is the low-level interface for scheduling builds.

    .. py:method:: maybeBuildsetComplete(bsid)

        :param integer bsid: buildset that may be complete
        :returns: Deferred

        This method should be called when a build request is finished.
        It checks the given buildset to see if all of its buildrequests are finished.
        If so, it updates the status of the buildset and send the appropriate messages.

Links
.....

.. py:module:: buildbot.data.base

.. py:class:: Link

    A link giving the path for this or another object.
    Instances of this class should be serialized appropriately for the medium, e.g., URLs in an HTTP API.

    .. py:attribute:: path

        The path, represented as a list of path elements.


Exceptions
..........

.. py:module:: buildbot.data.exceptions

.. py:exception:: DataException

    This is a base class for all other Data API exceptions

.. py:exception:: InvalidPathError

    The path argument was invalid or unknown.

.. py:exception:: InvalidOptionError

    A value in the ``options`` argument was invalid or ill-formed.

Web Interface
+++++++++++++

The HTTP interface is implemented by the :py:mod:`buildbot.www` package, as configured by the user.
Part of that configuration is a base URL, which is considered a prefix for all paths mentioned here.

This version of the API is rooted at ``api/v2`` [#apiv1]_.
A GET operation on any path under the root gets a request.
The following query arguments are available everywhere (with the boolean arguments accepting ``0``, ``false``, ``1``, and ``true``):

 * ``as_text`` - if true, the result is returned as type text/plain, and thus easily readable in a web browser.
 * ``filter`` - if true, or if omitted and ``as_text`` is set true, empty values (empty lists and objects, false, null, and the empty string) are omitted from the result.
 * ``compact`` - if true, or if omitted and ``as_text`` is false, the returned JSON will have unnecessary whitespace stripped.
 * ``callback`` - if given, a JSONP response will be returned with this callback name.

Other query arguments are passed to the resource identified by the path, and have the meanings described in :ref:`Data Model`.

The interface is easily used with common tools like curl:

.. code-block:: none

    dustin@cerf ~ $ curl http://euclid.r.igoro.us:8010/api/v2/change/1?as_text=1
    {
      "author": "Dustin J. Mitchell <dustin@mozilla.com>",
      "branch": "master",
      "changeid": 1,
      "comments": "changed",
      "files": [
        "README.txt"
      ],
      "project": "foo",
      "repository": "/home/dustin/code/buildbot/t/testrepo/",
      "revision": "5a8a560adade3d3be6c5cb09e6e1581dd307a4bd",
      "when_timestamp": 1335680458
    }

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
You can also follow an existing file, like :bb:src:`master/buildbot/data/changes.py`, to see when to use which form.

In :bb:src:`master/buildbot/data/pubs.py`, create a subclass of :py:class:`ResourceType`::

    from buildbot.data import base
    class PubResourceType(base.ResourceType):
        type = "pub"
        endpoints = []
        keyFields = [ 'pubid' ]

.. py:class:: ResourceType

    .. py:attribute:: type

        :type: string

        The singular, lower-cased name of the resource type.
        This becomes the first component in message routing keys.

    .. py:attribute:: endpoints

        :type: list

        Subclasses should set this to a list of endpoint classes for this resource type.

    .. py:attribute:: keyFields

        :type: list

        This attribute should list the message fields hose values will comprise the fields in the message routing key between the type and the event.

        In the example above, a call to ``produceEvent({ 'pubid' : 10, 'name' : 'Winchester' }, 'opened')`` would result in a message with routing key ``('pub', '10', 'opened')``.

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

All resource types must be documented in the Buildbot documentation, linked from the bottom of this file (:bb:src:`master/docs/developer/data.rst`).

All resource types must have corresponding type verification information.
See :ref:`Adding-Fields-to-Resource-Types` for details.

Adding Endpoints
++++++++++++++++

Each resource path is implemented as an :py:class:`~Endpoint` instance.
In most cases, each instance is of a different class, but this is not required.

The data connector's :py:meth:`~buildbot.data.connector.DataConnector.get`, :py:meth:`~buildbot.data.connector.DataConnector.startConsuming`, and :py:meth:`~buildbot.data.connector.DataConnector.control` methods all take a ``path`` argument that is used to look up the corresponding endpoint.
The path matching is performed by :py:mod:`buildbot.util.pathmatch`, and supports automatically extracting variable fields from the path.
See that module's description for details.

.. py:class:: Endpoint

    .. py:attribute:: pathPattern

        :type: tuple

        The path pattern which incoming paths must match to select this endpoint.

    .. py:attribute:: pathPatterns

        :type: list of tuples

        List of path patterns which incoming paths must match to select this endpoint.
        This is useful where the same endpoint class services multiple paths.
        If specified, ``pathPattern`` is prepended to this list.

    .. py:attribute:: rootLinkName

        :type: string

        If set, then the first path pattern for this endpoint will be included as a link in the root of the API.
        This should be set for any endpoints that begin an explorable tree.

    .. py:method:: get(options, kwargs)

        :param options: dictionary containing model-specific options
        :param kwargs: fields extracted from the path

    .. py:method:: startConsuming(callback, options, kwargs)

        :param callback: a function to call for each message
        :param options: dictionary containing model-specific options
        :param kwargs: fields extracted from the path

    .. py:method:: control(action, args, kwargs)

        :param action: a short string naming the action to perform
        :param args: dictionary containing arguments for the action
        :param kwargs: fields extracted from the path

Continuing the pub example, a simple endpoint would look like this::

    class PubEndpoint(base.Endpoint):
        pathPattern = ( 'pub', 'i:pubid' )
        def get(self, options, kwargs):
            return self.master.db.pubs.getPub(kwargs['pubid'])

In a more complex implementation, the options might be used to indicate whether or not the pub's menu should be included in the result.

Endpoint implementations must have unit tests.
An endpoint's path should be documented in the ``.rst`` file for its resource type.

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

Update methods should be documented in :bb:src:`master/docs/developer/data.rst`.
They should be thoroughly tested with unit tests.
They should have a fake implentation in :bb:src:`master/buildbot/test/fake/fakedata.py`.
That fake implementation should be tested to match the real implementation in :bb:src:`master/buildbot/test/interfaces/test_data_connector.py`.

.. _Adding-Fields-to-Resource-Types:

Adding Fields to Resource Types
+++++++++++++++++++++++++++++++

The details of the fields of a resource type are rigorously enforced at several points in the Buildbot tests.
This enforcement is performed by modules under :bb:src:`master/buildbot/test/util/types`, one per resource type.

There are three types of verification performed: messages, database dictionaries, and getter return values (data).
For each type, a verifier is listed in :bb:src:`master/buildbot/test/util/types/__init__.py`, by object name, with  prefix of ``buildbot.test.util.types`` assumed.

Message verifiers take a routing key and message, and should check both for well-formedness.
Database dictionary verifiers take a type (e.g., ``chdict``) and the value to be verified (a dictionary).
Data verifiers take a type (e.g., ``change``), options, and the value to be verified (a dictionary).
They should consult the options to determine which variant is expected.

The module :py:mod:`buildbot.test.util.verifier` provides useful utility methods for all three types of verification.
Consult this module and the existing verifier modules for more details.

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

.. toctree::
    :maxdepth: 1

    rtype-buildset
    rtype-change
    rtype-master

.. [#apiv1] The JSON API defined by ``status_json.py`` in Buildbot-0.8.x is considered version 1, although its root path was ``json``, not ``api/v1``.
