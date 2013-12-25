.. _WWW:

WWW
===

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
To maimize hackability, Buildbot separates the two cleanly.
An experienced AngularJS hacker should be quite comfortable in the :bb:src:`www/` directory, with a few exceptions described below.
Similarly, an experienced Python hacker can simply download the pre-built web UI (from pypi!) and never venture near the :bb:src:`www/` directory.

URLs
~~~~

The Buildbot web interface is rooted at its base URL, as configured by the user.
It is entirely possible for this base URL to contain path components, e.g., ``http://build.myorg.net/buildbot/``, if hosted behind an HTTP proxy.
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
For example, with a base URL of ``http://build.myorg.net/buildbot``, the list of masters for builder 9 is available at ``http://build.myorg.net/buildbot/api/v2/builder/9/master``.

Results are formatted in keeping with the `JSON API <http://jsonapi.org/>`_ specification.
The top level of every response is an object.
Its keys are the plural names of the resource types, and the values are lists of objects, even for a single-resource request.
For example::

    {
      "meta": {
        "links": [
          {
            "href": "http://build.my.org/api/v2/scheduler",
            "rel": "self"
          }
        ],
        "total": 2
      },
      "schedulers": [
        {
          "link": "http://build.my.org/api/v2/scheduler/1",
          "master": null,
          "name": "smoketest",
          "schedulerid": 1
        },
        {
          "link": "http://build.my.org/api/v2/scheduler/4",
          "master": {
            "active": true,
            "last_active": 1369604067,
            "link": "http://build.my.org/api/v2/master/1",
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

 * ``http://build.my.org/api/v2/scheduler?field=name&field=schedulerid``

Field selection can be used for either detail (single-entity) or collection (multi-entity) requests.
The remaining options only apply to collection requests.

Filtering
.........

Collection responses may be filtered on any simple top-level field.

To select records with a specific value use the query parameter ``{field}={value}``.
For example, ``http://build.my.org/api/v2/scheduler?name=smoketest`` selects the scheduler named "smoketest".

Filters can use any of the operators listed below, with query parameters of the form ``{field}__{operator}={value}``.

 * ``eq`` - equality, or with the same parameter appearing multiple times, set membership
 * ``ne`` - inequality, or set exclusion
 * ``lt`` - select resources where the field's value is less than ``{value}``
 * ``le`` - select resources where the field's value is less than or equal to ``{value}``
 * ``gt`` - select resources where the field's value is greater than ``{value}``
 * ``ge`` - select resources where the field's value is greater than or equal to ``{value}``

For example:

 * ``http://build.my.org/api/v2/builder?name__lt=cccc``
 * ``http://build.my.org/api/v2/buildsets?complete__eq=false``

Boolean values can be given as ``on``/``off``, ``true``/``false``, ``yes``/``no``, or ``1``/``0``.

Sorting
.......

Collection responses may be ordered with the ``order`` query parameter.
This parameter takes a field name to sort on, optionally prefixed with ``-`` to reverse the sort.
The parameter can appear multiple times, and will be sorted lexically with the fields arranged in the given order.
For example:

 * ``http://build.my.org/api/v2/buildrequest?order=builderid&order=buildrequestid``

Pagination
..........

Collection responses may be paginated with the ``offset`` and ``limit`` query parameters.
The offset is the 0-based index of the first result to included, after filtering and sorting.
The limit is the maximum number of results to return.
Some resource types may impose a maximum on the limit parameter; be sure to check the resulting links to determine whether further data is available.
For example:

 * ``http://build.my.org/api/v2/buildrequest?order=builderid&limit=10``
 * ``http://build.my.org/api/v2/buildrequest?order=builderid&offset=20&limit=10``

Controlling
~~~~~~~~~~~

Data API control operations are handled by POST requests using a simplified form of `JSONRPC 2.0 <http://www.jsonrpc.org/specification>`_.
The JSONRPC "method" is mapped to the data API "action", and the parameters are passed to that application.

The following parts of the protocol are not supported:

 * positional parameters
 * batch requests

Requests are sent as an HTTP POST, containing the request JSON in the body.
The content-type header is ignored; for compatibility with simple CORS requests (avoiding preflight checks), use ``text/plain``.

A simple example:

.. code-block:: none

    POST http://build.my.org/api/v2/scheduler/4
    --> {"jsonrpc": "2.0", "method": "force", "params": {"revision": "abcd", "branch": "dev"}, "id": 843}
    <-- {"jsonrpc": "2.0", "result": {"buildsetid": 44}, "id": 843}

.. _API-Discovery:

Discovery
~~~~~~~~~

The Data API provides a discovery endpoint which exposes all endpoints of the API in a JSON format so that one can write middleware to automatically create higher level API, or generate fake data for development.
The endpoint is available at:

.. code-block:: none

    GET http://build.my.org/api/v2/application.spec

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

Message API
-----------

Currently messages are implemented with two protocols: WebSockets and `server sent event <http://en.wikipedia.org/wiki/Server-sent_events>`_.
This may be supplemented with other mechanisms before release.

WebSocket
~~~~~~~~~

WebSocket is a protocol for arbitrary messaging to and from browser.
As an HTTP extension, the protocol is not yet well supported by all HTTP proxy technologies. Although, it has been reported to work well used behind the https protocol. Only one WebSocket connection is needed per browser.

Client can connect using url ``ws[s]://<BB_BASE_URL>/ws``

The client can control which kind of messages he will receive using following message, encoded in json:

 * startConsuming: {'req': 'startConsuming', 'options': {}, 'path': ['change']}
   startConsuming events that match ``path``.

 * stopConsuming: {'req': 'stopConsuming', 'path': ['change']}
   stopConsuming events that match ``path``

Client will receive events as websocket frames encoded in json with following format:

   {'key':key, 'message':message}

Server Sent Events
~~~~~~~~~~~~~~~~~~

SSE is a simpler protocol than WebSockets and is more REST compliant. It uses the chunk-encoding HTTP feature to stream the events. SSE also does not works well behind enterprise proxy, unless you use the https protocol

Client can connect using following endpoints

 * ``http[s]://<BB_BASE_URL>/sse/listen/<path>``: Start listening to events on the http connection. Optionally setup a first event filter on ``<path>``. The first message send is a handshake, giving a uuid that can be used to add or remove event filters.
 * ``http[s]://<BB_BASE_URL>/sse/add/<uuid>/<path>``: Configure a sse session to add an event filter
 * ``http[s]://<BB_BASE_URL>/sse/remote/<uuid>/<path>``: Configure a sse session to remove an event filter

Note that if a load balancer is setup as a front end to buildbot web masters, the load balancer must be configured to always use the same master given a client ip address for /sse endpoint.

Client will receive events as sse events, encoded with following format:

.. code-block:: none

  event: event
  data: {'key': <key>, 'message': <message>}

The first event received is a handshake, and is used to inform the client about uuid to use for configuring additional event filters

.. code-block:: none

  event: handshake
  data: <uuid>


JavaScript Application
----------------------

The client side of the web UI is written in JavaScript and based on the AngularJS framework and concepts.

This is a `Single Page Application" <http://en.wikipedia.org/wiki/Single-page_application>`_
All Buildbot pages are loaded from the same path, at the master's base URL.
The actual content of the page is dictated by the fragment in the URL (the portion following the ``#`` character).
Using the fragment is a common JS techique to avoid reloading the whole page over HTTP when the user changes the URI or clicks a link.

AngularJS
~~~~~~~~~

The best place to learn about AngularJS is `its own documentation <http://docs.angularjs.org/guide/>`_,

AngularJS strong points are:

 * A very powerful `MVC system <http://docs.angularjs.org/guide/concepts>`_ allowing automatic update of the UI, when
   data changes
 * A `Testing Framework and philosophy <http://docs.angularjs.org/guide/dev_guide.e2e-testing>`_
 * A `deferred system <http://docs.angularjs.org/api/ng.$q>`_ similar to the one from Twisted.
 * A `fast growing community and ecosystem <http://builtwith.angularjs.org/>`_

On top of Angular we use nodeJS tools to ease development
 * grunt buildsystem, seemlessly build the app, can watch files for modification, rebuild and reload browser in dev mode.
   In production mode, the buildsystem minifies html, css and js, so that the final app is only 3 files to download (+img).
 * `coffeescript <http://coffeescript.org/>`_, a very expressive langage, preventing some of the major traps of JS.
 * `jade template langage <http://jade-lang.com/>`_, adds syntax sugar and readbility to angular html templates.
 * `bootstrap <http://twitter.github.com/bootstrap/>`_ is a css library providing know good basis for our styles.
 * `Font Awesome <http://fortawesome.github.com/Font-Awesome/>`_ is a coherent and large icon library

modules we may or may not want to include:
 * `momentjs <http://momentjs.com/>`_ is a library implementing human readable relative timings (e.g. "one hour ago")
 * `ngGrid <http://angular-ui.github.com/ng-grid/>`_ is a grid system for full featured searcheable/sortable/csv exportable grids
 * `angular-UI <http://angular-ui.github.com/>`_ is a collection of jquery based directives and filters. Probably not very useful for us
 * `JQuery <http://jquery.com/>`_ the well known JS framework, allows all sort of dom manipulation. Having it inside
   allows for all kind of hacks we may want to avoid.

Extensibility
~~~~~~~~~~~~~

TODO: document writing plugins

.. _Routing:

Routing
~~~~~~~

The router, we used is provided by angular, and the config is in src/scripts/routes.coffee


Directives
~~~~~~~~~~

We use angular directives as much as possible to implement reusable UI components.

Services
~~~~~~~~

BuildbotService
...............

BuildbotService is the base service for accessing to the buildbot data api.
It uses and is derivated from `restangular <https://github.com/mgonto/restangular/blob/master/README.md>`_.
Restangular offers nice semantics around nested REST endpoints. Please see restangular documentation for overview on how it works.

BuildbotService adds serveral methods to restangular objects in order to integrate it with EventSource.
The idea is to simplifify automatic update of the $scope based on events happening on a given data endpoint

.. code-block:: coffeescript

    # Following code will get initial data from 'api/v2/build/1/step/2'
    # and register to events from 'sse/build/1/step/2'
    # Up to the template to specify what to display

    buildbotService.one("build", 1).one("step", 2).bind($scope)

Difference with restangular is all restangular objects are reused, i.e. if you are calling bind() twice on the same
object, no additionnal ressource is gathered via http.

Several methods are added to each "restangularized" objects, aside from get(), put(), delete(), etc.:

    * ``.bind($scope, opts)``

        bind the api results to the $scope, automatically listening to events on this endpoint, and modifying the $scope object accordingly.
        This method automatically references the scopes where the data is used, and will remove the reference when the $scope is destoyed.
        When no scope is referencing the data anymore, the service will wait a configurable amount of time, and stop listening to associated events.
        As a result, the service will loose real-time track of the underlying data, so any subsequent call to bind() will trigger another http requests to get updated data.
        This delayed event unregister mechanism enables better user experience. When user is going back and forth between several pages, chances are that the data is still on-track, so the page will be displayed instantly.

        ``bind()`` takes several optional parameters in ``opts``:

        * ``dest`` (defaults to $scope): object where to store the results

        * ``ismutable``(defaults to always false): ``(elem) ->`` function used to know if the object will not evolve anymore (so no need to register to events)

        * ``onchild``: ``(child) ->`` function called for each child, at init time, and when new child is detected through events.
            This can be used to get more data derived from a list. The child received are restangular elements

    * ``.on(eventtype, callback, $scope)``

        Listen to events for this endpoint. When bind() semantic is not useful enough, you can use this lower level api.
        You need to pass $scope, so that event is unregistered on scope destroy.

    * ``.some(route, queryParams)``

        like .all(), but allows to specify query parameters

        * ``queryParams`` : query parameters used to filter the results of a list api


    * ``.control(method, params)``

        Call the control data api. This builds up a POST with jsonapi encoded parameters

Mocks and testing utils
~~~~~~~~~~~~~~~~~~~~~~~

httpMock.coffee
...............

This modules adds ``decorateHttpBackend($httpBackend)`` to the global namespace. This function decorate the $httpBackend with additional functionality:

    * ``.expectDataGET(ep, {nItems:<int or undefined>, override: <fn or undefined>})``

       automatically create a GET expectation to the data api, given the data spec
       Options available are:

       * ``nItems``: if defined, this will generate a collection of nItems instead of single value

       * ``override``: a custom function to override the resulting generated data

       Example: ``$httpBackend.expectDataGET("change", {nItems:2, override: (val) -> val[1].id=4 })``
       will create 2 changes, but the id of the second change will be overridden to 4

Linking with Buildbot
~~~~~~~~~~~~~~~~~~~~~

A running buildmaster needs to be able to find the JavaScript source code it needs to serve the UI.
This needs to work in a variety of contexts - Python development, JavaScript development, and end-user installations.
To accomplish this, the grunt build process finishes by bundling all of the static data into a Python distribution tarball, along with a little bit of Python glue.
The Python glue implements the interface described below, with some care taken to handle multiple contexts.
The :bb:src:`www/grunt.js`, :bb:src:`www/setup.py`, and :bb:src:`www/buildbot_www.py` scripts are carefully coordinated.


Hacking Quick-Start
-------------------

This section describes how to get set up quickly to hack on the JavaScript UI.
It does not assume familiarity with Python, although a Python installation is required, as well as ``virtualenv``.
You will also need ``NodeJS``, and ``npm`` installed.

Hacking the Buildbot JavaScript
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To effectively hack on the Buildbot JavaScript, you'll need a running Buildmaster, configured to operate out of the source directory (unless you like editing minified JS).
Start by cloning the project and its git submodules:

.. code-block:: none

    git clone git://github.com/buildbot/buildbot.git

In the root of the source tree, create and activate a virtualenv to install everything in:

.. code-block:: none

    virtualenv sandbox
    source sandbox/bin/activate

This creates an isolated Python environment in which you can install packages without affecting other parts of the system.
You should see ``(sandbox)`` in your shell prompt, indicating the sandbox is activated.

Next, install the Buildbot-WWW and Buildbot packages using ``--editable``, which means that they should execute from the source directory.

.. code-block:: none

    pip install --editable www/
    pip install --editable master/

This will fetch a number of dependencies from pypi, the Python package repository.
This will also fetch a bunch a bunch of node.js dependencies used for building the web application,
and a bunch of client side js dependencies, with bower

Now you'll need to create a master instance.
For a bit more detail, see the Buildbot tutorial (:ref:`first-run-label`).

.. code-block:: none

    buildbot create-master sandbox/testmaster
    mv sandbox/testmaster/master.cfg.sample sandbox/testmaster/master.cfg
    buildbot start sandbox/testmaster

If all goes well, the master will start up and begin running in the background.
As you just installed www in editable mode (aka 'develop' mode), setup.py did build
the web site in prod mode, so the everything is minified, making it hard to debug.

When doing web development, you usually run:

.. code-block:: none

    cd www
    . tosource
    grunt dev

This will compile the webapp in development mode, and automatically rebuild when files change.

If your browser and dev environment are on the same machine, you can use the livereload feature of the build script.
For this to work, you need to run those command from another terminal, at the same time as "grunt dev"

.. code-block:: none

    cd www
    . tosource
    grunt reloadserver


Testing Setup
-------------

buildbot_www uses `Karma <http://karma-runner.github.io>`_ to run the coffeescript test suite. This is the official test framework made for angular.js
We dont run the front-end testsuite inside the python 'trial' test suite, because testing python and JS is technically very different.

Karma needs a browser to run the unit test in. It supports all the major browsers. buildbot www's build script supports two popular browsers,
and PhantomJS which is headless web browser made for unit testing.
Like for the livereload feature, the test-runner works with autowatch mode. You need to use "grunt dev" in parallel from the following commands:


Run the tests in Firefox:

.. code-block:: none

    cd www
    . tosource
    grunt fftest

Run the tests in Chrome:

.. code-block:: none

    cd www
    . tosource
    grunt chrometest

Run the tests in PhantomJS (which you can download at http://phantomjs.org/):

.. code-block:: none

    cd www
    . tosource
    grunt pjstest

For the purpose of the metabuildbot, a special grunt target is made for running the test suite inside PhantomJS.
This special target only runs once, so is not connected to the watch mechanics:

.. code-block:: none

    cd www
    . tosource
    grunt ci


