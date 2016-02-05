.. _WWW:
.. _WWW-server:

WWW Server
==========

History and Motivation
----------------------

One of the goals of the 'nine' project is to rework Buildbot's web services to use a more modern, consistent design and implement UI features in client-side JavaScript instead of server-side Python.

The rationale behind this is that a client side UI relieves pressure on the server while being more responsive for the user.
The web server only concentrates on serving data via a REST interface wrapping the :ref:`Data_API`.
This removes a lot of sources of latency where, in previous versions, long synchronous calculations were made on the server to generate complex pages.

Another big advantage is live updates of status pages, without having to poll or reload.
The new system uses Comet techniques in order to relay Data API events to connected clients.

Finally, making web services an integral part of Buildbot, rather than a status plugin, allows tighter integration with the rest of the application.

Design Overview
---------------

The ``www`` service exposes three pieces via HTTP:

* A REST interface wrapping :ref:`Data_API`;
* HTTP-based messaging protocols wrapping the :ref:`Messaging_and_Queues` interface; and
* Static resources implementing the client-side UI.

The REST interface is a very thin wrapper: URLs are translated directly into Data API paths, and results are returned directly, in JSON format.
It is based on `JSON API <http://jsonapi.org/>`_.
Control calls are handled with a simplified form of `JSONRPC 2.0 <http://www.jsonrpc.org/specification>`_.

The message interface is also a thin wrapper around Buildbot's MQ mechanism.
Clients can subscribe to messages, and receive copies of the messages, in JSON, as they are received by the buildmaster.

The client-side UI is an AngularJS application.
Buildbot uses the Python setuptools entry-point mechanism to allow multiple packages to be combined into a single client-side experience.
This allows frontend developers and users to build custom components for the web UI without hacking Buildbot itself.

Python development and AngularJS development are very different processes, requiring different environment requirements and skillsets.
To maximize hackability, Buildbot separates the two cleanly.
An experienced AngularJS hacker should be quite comfortable in the :src:`www/` directory, with a few exceptions described below.
Similarly, an experienced Python hacker can simply download the pre-built web UI (from pypi!) and never venture near the :src:`www/` directory.

URLs
~~~~

The Buildbot web interface is rooted at its base URL, as configured by the user.
It is entirely possible for this base URL to contain path components, e.g., ``http://build.example.org/buildbot/``, if hosted behind an HTTP proxy.
To accomplish this, all URLs are generated relative to the base URL.

Overall, the space under the base URL looks like this:

* ``/`` -- The HTML document that loads the UI
* ``/api/v{version}`` -- The root of the REST APIs, each versioned numerically.
  Users should, in general, use the latest version.
* ``/ws`` -- The WebSocket endpoint to subscribe to messages from the mq system.
* ``/sse`` -- The `server sent event <http://en.wikipedia.org/wiki/Server-sent_events>`_ endpoint where clients can subscribe to messages from the mq system.

REST API
--------

The REST API is a thin wrapper around the data API's "Getter" and "Control" sections.
It is also designed, in keeping with REST principles, to be discoverable.
As such, the details of the paths and resources are not documented here.
Begin at the root URL, and see the :ref:`Data_API` documentation for more information.

Versions
~~~~~~~~

The API described here is version 2.
The ad-hoc API from Buildbot-0.8.x, version 1, is no longer supported.

Getting
~~~~~~~

To get data, issue a GET request to the appropriate path.
For example, with a base URL of ``http://build.example.org/buildbot``, the list of masters for builder 9 is available at ``http://build.example.org/buildbot/api/v2/builder/9/master``.

Results are formatted in keeping with the `JSON API <http://jsonapi.org/>`_ specification.
The top level of every response is an object.
Its keys are the plural names of the resource types, and the values are lists of objects, even for a single-resource request.
For example:

.. code-block:: json

    {
      "meta": {
        "links": [
          {
            "href": "http://build.example.org/api/v2/scheduler",
            "rel": "self"
          }
        ],
        "total": 2
      },
      "schedulers": [
        {
          "link": "http://build.example.org/api/v2/scheduler/1",
          "master": null,
          "name": "smoketest",
          "schedulerid": 1
        },
        {
          "link": "http://build.example.org/api/v2/scheduler/4",
          "master": {
            "active": true,
            "last_active": 1369604067,
            "link": "http://build.example.org/api/v2/master/1",
            "masterid": 1,
            "name": "master3:/BB/master"
          },
          "name": "goaheadtryme",
          "schedulerid": 2
        }
      ]
    }

A response may optionally contain extra, related resources beyond those requested.
The ``meta`` key contains metadata about the response, including navigation links and the total count of resources in a collection.

Several query parameters may be used to affect the results of a request.
These parameters are applied in the order described (so, it is not possible to sort on a field that is not selected, for example).

Field Selection
...............

If only certain fields of each resource are required, the ``field`` query parameter can be used to select them.
For example, the following will select just the names and id's of all schedulers:

* ``http://build.example.org/api/v2/scheduler?field=name&field=schedulerid``

Field selection can be used for either detail (single-entity) or collection (multi-entity) requests.
The remaining options only apply to collection requests.

Filtering
.........

Collection responses may be filtered on any simple top-level field.

To select records with a specific value use the query parameter ``{field}={value}``.
For example, ``http://build.example.org/api/v2/scheduler?name=smoketest`` selects the scheduler named "smoketest".

Filters can use any of the operators listed below, with query parameters of the form ``{field}__{operator}={value}``.

``eq``
    equality, or with the same parameter appearing multiple times, equality with one of the given values (so `foo__eq=x&foo__eq=y` would match resources where foo is `x` or `y`)
``ne``
    inequality, or set exclusion
``lt``
    select resources where the field's value is less than ``{value}``
``le``
    select resources where the field's value is less than or equal to ``{value}``
``gt``
    select resources where the field's value is greater than ``{value}``
``ge``
    select resources where the field's value is greater than or equal to ``{value}``
``contains``
    select resources where the field's value contains ``{value}``

For example:

* ``http://build.example.org/api/v2/builder?name__lt=cccc``
* ``http://build.example.org/api/v2/buildsets?complete__eq=false``

Boolean values can be given as ``on``/``off``, ``true``/``false``, ``yes``/``no``, or ``1``/``0``.

Sorting
.......

Collection responses may be ordered with the ``order`` query parameter.
This parameter takes a field name to sort on, optionally prefixed with ``-`` to reverse the sort.
The parameter can appear multiple times, and will be sorted lexically with the fields arranged in the given order.
For example:

* ``http://build.example.org/api/v2/buildrequest?order=builderid&order=buildrequestid``

Pagination
..........

Collection responses may be paginated with the ``offset`` and ``limit`` query parameters.
The offset is the 0-based index of the first result to included, after filtering and sorting.
The limit is the maximum number of results to return.
Some resource types may impose a maximum on the limit parameter; be sure to check the resulting links to determine whether further data is available.
For example:

* ``http://build.example.org/api/v2/buildrequest?order=builderid&limit=10``
* ``http://build.example.org/api/v2/buildrequest?order=builderid&offset=20&limit=10``

Controlling
~~~~~~~~~~~

Data API control operations are handled by POST requests using a simplified form of `JSONRPC 2.0 <http://www.jsonrpc.org/specification>`_.
The JSONRPC "method" is mapped to the data API "action", and the parameters are passed to that application.

The following parts of the protocol are not supported:

* positional parameters
* batch requests

Requests are sent as an HTTP POST, containing the request JSON in the body.
The content-type header must be ``application/json``.

A simple example:

.. code-block:: none

    POST http://build.example.org/api/v2/scheduler/4
    --> {"jsonrpc": "2.0", "method": "force", "params": {"revision": "abcd", "branch": "dev"}, "id": 843}
    <-- {"jsonrpc": "2.0", "result": {"buildsetid": 44}, "id": 843}

.. _API-Discovery:

Discovery
~~~~~~~~~

The Data API provides a discovery endpoint which exposes all endpoints of the API in a JSON format so that one can write middleware to automatically create higher level API, or generate fake data for development.
The endpoint is available at:

.. code-block:: none

    GET http://build.example.org/api/v2/application.spec

This metadata is guaranteed to be correct, as this is generated from the spec used in data's unit tests.
See :ref:`Adding-Fields-to-Resource-Types` for more details on the type system used.

The data validation type system is serialized into JSON in a very simple way.
The API returns a list of endpoint specs, each of the form:

.. code-block:: javascript

    {
      path: "<endpoint_path>"
      type: "<endpoint_entity_type>"
      type_spec: "<endpoint_entity_type_spec>"
    }

The type spec encoding can have several forms:

* Entity or Dict

  .. code-block:: javascript

        {
            ..
            type_spec: {
                type: "<type name>"
                fields: [
                    {
                    name: "<field name>"
                    type: "<field type name>"
                    type_spec: "<field type spec>"
                    }, // [...]
                ]
            }
        }

* List

  .. code-block:: javascript

        {
            ..
            type_spec: {
            type: "list"
            of: {
                type: "<field type name>"
                type_spec: "<field type spec>"
            }
        }

* Links

  .. code-block:: javascript

        {
            ..
            type_spec: {
            type: "link"
            link_specs: [
                "<ep1 path>",
                "<ep2 path>", // [...]
            ]
        }

* Other base types

  .. code-block:: javascript

        {
            ..
            type_spec: {
            type: "(string|integer|boolean|binary|identifier|jsonobject|sourced-properties)"
        }

Server-Side Session
-------------------

The web server keeps a session state for each user, keyed on a session cookie.
This session is available from ``request.getSession()``, and data is stored as attributes.
The following attributes may be available:

``user_info``
    A dictionary maintained by the :doc:`authentication subsystem <auth>`.
    It may have the following information about the logged-in user:

    * ``username``
    * ``email``
    * ``full_name``
    * ``groups`` (a list of group names)

    As well as additional fields specific to the user info implementation.

    The contents of the ``user_info`` dictionary are made available to the UI as ``config.user``.

Message API

Currently messages are implemented with two protocols: WebSockets and `server sent event <http://en.wikipedia.org/wiki/Server-sent_events>`_.
This may be supplemented with other mechanisms before release.

WebSocket
~~~~~~~~~

WebSocket is a protocol for arbitrary messaging to and from browser.
As an HTTP extension, the protocol is not yet well supported by all HTTP proxy technologies. Although, it has been reported to work well used behind the https protocol. Only one WebSocket connection is needed per browser.

Client can connect using url ``ws[s]://<BB_BASE_URL>/ws``

The protocol used is a simple in-house protocol based on json. Structure of a command from client is as following:

.. code-block:: javascript

    { "cmd": "<command name>", '_id': <id of the command>, "arg1": arg1, "arg2": arg2 }

* ``cmd`` is use to reference a command name
* ``_id`` is used to track the response, can be any unique number or string.
  Generated by the client.
  Needs to be unique per websocket session.

Response is sent asynchronously, reusing ``_id`` to track which command is responded.

Success answer example would be:

.. code-block:: javascript

    { "msg": "OK", '_id': 1, code=200 }

Error answer example would be:

.. code-block:: javascript

    {"_id":1,"code":404,"error":"no such command \'poing\'"}


Client can send several command without waiting response.

Responses are not guaranteed to be sent in order.

Several command are implemented:

``ping``
    .. code-block:: javascript

        {"_id":1,"cmd":"ping"}

    server will respond with a "pong" message:

    .. code-block:: javascript

        {"_id":1,"msg":"pong","code":200}

``startConsuming``
    start consuming events that match ``path``.
    ``path`` are described in the :ref:`Messaging_and_Queues` section.
    For size optimization reasons, path are encoded joined with "/", and with None wildcard replaced by '*'.

    .. code-block:: javascript

        {"_id":1,"cmd":"startConsuming", "path": "change/*/*"}

    Success answer example will be:

    .. code-block:: javascript

        { "msg": "OK", '_id': 1, code=200 }

``stopConsuming``
    stop consuming events that was previously registered with ``path``.

    .. code-block:: javascript

        {"_id":1,"cmd":"stopConsuming", "path": "change/*/*"}

    Success answer example will be:

    .. code-block:: javascript

        { "msg": "OK", '_id': 1, code=200 }

Client will receive events as websocket frames encoded in json with following format:

.. code-block:: javascript

   {"k":key,"m":message}

Server Sent Events
~~~~~~~~~~~~~~~~~~

SSE is a simpler protocol than WebSockets and is more REST compliant. It uses the chunk-encoding HTTP feature to stream the events. SSE also does not works well behind enterprise proxy, unless you use the https protocol

Client can connect using following endpoints

* ``http[s]://<BB_BASE_URL>/sse/listen/<path>``: Start listening to events on the http connection.
  Optionally setup a first event filter on ``<path>``.
  The first message send is a handshake, giving a uuid that can be used to add or remove event filters.
* ``http[s]://<BB_BASE_URL>/sse/add/<uuid>/<path>``: Configure a sse session to add an event filter
* ``http[s]://<BB_BASE_URL>/sse/remove/<uuid>/<path>``: Configure a sse session to remove an event filter

Note that if a load balancer is setup as a front end to buildbot web masters, the load balancer must be configured to always use the same master given a client ip address for /sse endpoint.

Client will receive events as sse events, encoded with following format:

.. code-block:: none

  event: event
  data: {'key': <key>, 'message': <message>}

The first event received is a handshake, and is used to inform the client about uuid to use for configuring additional event filters

.. code-block:: none

  event: handshake
  data: <uuid>
