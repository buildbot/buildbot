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
    equality, or with the same parameter appearing multiple times, set membership
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

* A very powerful `MVC system <http://docs.angularjs.org/guide/concepts>`_ allowing automatic update of the UI, when data changes
* A `Testing Framework and philosophy <http://docs.angularjs.org/guide/dev_guide.e2e-testing>`_
* A `deferred system <http://docs.angularjs.org/api/ng.$q>`_ similar to the one from Twisted.
* A `fast growing community and ecosystem <http://builtwith.angularjs.org/>`_

On top of Angular we use nodeJS tools to ease development

* gulp buildsystem, seemlessly build the app, can watch files for modification, rebuild and reload browser in dev mode.
  In production mode, the buildsystem minifies html, css and js, so that the final app is only 3 files to download (+img).
* `coffeescript <http://coffeescript.org/>`_, a very expressive langage, preventing some of the major traps of JS.
* `jade template langage <http://jade-lang.com/>`_, adds syntax sugar and readbility to angular html templates.
* `Bootstrap <http://getbootstrap.com/>`_ is a css library providing know good basis for our styles.
* `Font Awesome <http://fortawesome.github.com/Font-Awesome/>`_ is a coherent and large icon library

modules we may or may not want to include:

* `momentjs <http://momentjs.com/>`_ is a library implementing human readable relative timings (e.g. "one hour ago")
* `ngGrid <http://angular-ui.github.com/ng-grid/>`_ is a grid system for full featured searcheable/sortable/csv exportable grids
* `angular-UI <http://angular-ui.github.com/>`_ is a collection of jquery based directives and filters. Probably not very useful for us
* `JQuery <http://jquery.com/>`_ the well known JS framework, allows all sort of dom manipulation.
  Having it inside allows for all kind of hacks we may want to avoid.

Extensibility
~~~~~~~~~~~~~

Buildbot UI is designed for extensibility.
The base application should be pretty minimal, and only include very basic status pages.
Base application cannot be disabled so any page not absolutely necessary should be put in plugins.

Some Web plugins are maintained inside buildbot's git repository, but this is absolutely not necessary.
Unofficial plugins are encouraged, please be creative!

Please look at official plugins for working samples.

Typical plugin source code layout is:

.. code-block:: bash

    setup.py                     # standard setup script. Most plugins should use the same boilerplate, which helps building guanlecoja app as part of the setup. Minimal adaptation is needed
    <pluginname>/__init__.py     # python entrypoint. Must contain an "ep" variable of type buildbot.www.plugin.Application. Minimal adaptation is needed
    guanlecoja/config.coffee     # Configuration for guanlecoja. Few changes are needed here. Please see guanlecoja docs for details.
    src/..                       # source code for the angularjs application. See guanlecoja doc for more info of how it is working.
    package.json                 # declares npm dependency. normallly, only guanlecoja is needed. Typically, no change needed
    gulpfile.js                  # entrypoint for gulp, should be a one line call to guanlecoja. Typically, no change needed
    MANIFEST.in                  # needed by setup.py for sdist generation. You need to adapt this file to match the name of your plugin

Plugins are packaged as python entry-points for the buildbot.www namespace.
The python part is defined in the `buildbot.www.plugin` module.
The entrypoint must contain a twisted.web Resource, that is populated in the web server in `/<pluginname>/`.

The front-end part of the plugin system automatically loads `/<pluginname>/scripts.js` and `/<pluginname>/styles.css` into the angular.js application.
The scripts.js files can register itself as a dependency to the main "app" module, register some new states to $stateProvider, or new menu items via glMenuProvider.

The entrypoint containing a Resource, nothing forbids plugin writers to add more REST apis in `/<pluginname>/api`.
For that, a reference to the master singleton is provided in ``master`` attribute of the Application entrypoint.
You are even not restricted to twisted, and could even `load a wsgi application using flask, django, etc <http://twistedmatrix.com/documents/13.1.0/web/howto/web-in-60/wsgi.html>`_.

.. _Routing:

Routing
~~~~~~~

AngularJS uses router to match URL and choose which page to display.
The router we use is ui.router.
Menu is managed by guanlecoja-ui's glMenuProvider.
Please look at ui.router, and guanlecoja-ui documentation for details.

Typically, a route regitration will look like following example.

.. code-block:: coffeescript

    # ng-classify declaration. Declares a config class
    class State extends Config
        # Dependancy injection: we inject $stateProvider and glMenuServiceProvider
        constructor: ($stateProvider, glMenuServiceProvider) ->

            # Name of the state
            name = 'console'

            # Menu configuration.
            glMenuServiceProvider.addGroup
                name: name
                caption: 'Console View'     # text of the menu
                icon: 'exclamation-circle'  # icon, from Font-Awesome
                order: 5                    # order in the menu, as menu are declared in several places, we need this to control menu order

            # Configuration for the menu-item, here we only have one menu item per menu, glMenuProvider won't create submenus
            cfg =
                group: name
                caption: 'Console View'

            # Register new state
            state =
                controller: "#{name}Controller"
                controllerAs: "c"
                templateUrl: "console_view/views/#{name}.html"
                name: name
                url: "/#{name}"
                data: cfg

            $stateProvider.state(state)

Directives
~~~~~~~~~~

We use angular directives as much as possible to implement reusable UI components.

Services
~~~~~~~~

BuildbotService
...............

BuildbotService is the base service for accessing to the Buildbot data API.
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

``.bind($scope, opts)``

    Bind the api results to the `$scope`, automatically listening to events on this endpoint, and modifying the `$scope` object accordingly.
    This method automatically references the scopes where the data is used, and will remove the reference when the `$scope` is destoyed.
    When no scope is referencing the data anymore, the service will wait a configurable amount of time, and stop listening to associated events.
    As a result, the service will loose real-time track of the underlying data, so any subsequent call to bind() will trigger another http requests to get updated data.
    This delayed event unregister mechanism enables better user experience.
    When user is going back and forth between several pages, chances are that the data is still on-track, so the page will be displayed instantly.

    ``bind()`` takes several optional parameters in ``opts``:

    ``dest`` (default: `$scope`)
        object where to store the results

    ``ismutable``: ``(elem) -> boolean`` (default: always false)
        function used to know if the object will not evolve anymore (so no need to register to events)

    ``onchild``: ``(child) ->``
        function called for each child, at init time, and when new child is detected through events.
        This can be used to get more data derived from a list. The child received are restangular elements

``.on(eventtype, callback)``

    Listen to events for this endpoint. When bind() semantic is not useful enough, you can use this lower level api.

``.some(route, queryParams)``

    like ``.all()``, but allows to specify query parameters

    ``queryParams``
        query parameters used to filter the results of a list api

``.control(method, params)``

    Call the control data api.
    This builds up a POST with jsonapi encoded parameters

DataService
.............

DataService is the replacement of BuildbotService for accessing the Buildbot data API.
It has a modern interface for accessing data.
It uses IndexedDB for storing cached data as a single data store, and LocalStorage for broadcasting events between browser tabs.
DataService works in a master/slave architecture.
The master browser tab is responsible for keeping the requested data up to date in the IndexedDB and notify slaves when a data is ready to be used or it is updated.
It handles both the Rest API calls and the WebSocket subscriptions globally.

It uses the following libraries:

* Dexie.js (https://github.com/dfahlander/Dexie.js) - Minimalistic IndexedDB API with bulletproof transactions
* Tabex (https://github.com/nodeca/tabex) - Master election and in browser message bus

The DataService is available as a standalone AngularJS module.
Installation via bower:

  .. code-block:: sh

      bower install buildbot-data --save

Inject the ``bbData`` module to your application:

  .. code-block:: javascript

      angular.module('myApp', ['bbData'])

Methods:

``.getXs([id], [query])``: returns a promise<Collection>, when the promise is resolved, the Collection contains all the requested data

  * it's highly advised to use these instead of the lower level ``.get('string')`` function
  * ``Xs`` can be the following: ``Builds``, ``Builders``, ``Buildrequests``, ``Buildsets``, ``Buildslaves``, ``Changes``, ``Changesources``, ``Forceschedulers``, ``Masters``, ``Schedulers``, ``Sourcestamps``
  * call ``.getArray()`` on the returned promise to get the Collection before it's filled with the initial data

  .. code-block:: coffeescript

      # assign builds to $scope.builds once the Collection is filled
      dataService.getBuilds(builderid: 1).then (builds) ->
          $scope.builds = builds
          # load steps for every build
          builds.forEach (b) -> b.loadSteps()

      # assign builds to $scope.builds before the Collection is filled using the .getArray() function
      $scope.builds = dataService.getBuilds(builderid: 1).getArray()

``.get(endpoint, [id], [query])``: returns a promise<Collection>, when the promise is resolved, the Collection contains all the requested data

  * call ``.getArray()`` on the returned promise to get the Collection before it's filled with the initial data

  .. code-block:: coffeescript

      # assign builds to $scope.builds once the Collection is filled
      builderid = 1
      dataService.get("builders/#{builderid}/builds", limit: 1).then (builds) ->
          $scope.builds = builds
          # load steps for every build
          builds.forEach (b) -> b.loadSteps()

      # assign builds to $scope.builds before the Collection is filled using the .getArray() function
      $scope.builds = dataService.get('builds', builderid: 1).getArray()

``.open(scope)``: returns a DataAccessor, handles bindings

  * open a new accessor every time you need updating data in a controller
  * it registers a $destroy event handling function on the scope, it automatically unsubscribes from updates that has been requested by the DataAccessor

  .. code-block:: coffeescript

      # open a new accessor every time you need updating data in a controller
      class DemoController extends Controller
          constructor: ($scope, dataService) ->
              # automatically closes all the bindings when the $scope is destroyed
              opened = dataService.open($scope)
              # alternative syntax:
              #   opened = dataService.open()
              #   opened.closeOnDestroy($scope)
              # closing it manually is also possible:
              #   opened.close()

              # request new data, it updates automatically
              @builders = opened.getBuilders(limit: 10, order: '-started_at').getArray()

``.control(url, method, [params])``: returns a promise, sends a JSON RPC2 POST request to the server

  .. code-block:: coffeescript

      # open a new accessor every time you need updating data in a controller
      dataService.control('forceschedulers/force', 'force').then (response) ->
          $log.debug(response)
      , (reason) ->
          $log.error(reason)

``.clearCache()``: clears the IndexedDB tables and reloads the current page

  .. code-block:: coffeescript

      class DemoController extends Controller
          constructor: (@dataService) ->
          onClick: -> @dataService.clearCache()

Methods on the object returned by the ``.getXs()`` methods:

``.getXs([id], [query])``: returns a promise<Collection>, when the promise is resolved, the Collection contains all the requested data

  * same as ``dataService.getXs``, but with relative endpoint

  .. code-block:: coffeescript

      # assign builds to $scope.builds once the Collection is filled
      dataService.getBuilds(builderid: 1).then (builds) ->
          $scope.builds = builds
          # get steps for every build
          builds.forEach (b) ->
              b.getSteps().then (steps) ->
                  # assign completed test to every build
                  b.complete_steps = steps.map (s) -> s.complete

``.loadXs([id], [query])``: returns a promise<Collection>, the Collection contains all the requested data, which is also assigned to ``o.Xs``

  * ``o.loadXs()`` is equivalent to ``o.getXs().then (xs) -> o.xs = xs``

  .. code-block:: coffeescript

      $q (resolve) ->
          # get builder with id = 1
          dataService.getBuilders(1).then (builders) ->
              builders.forEach (builder) ->
                  # load all builds
                  builder.loadBuilds().then (builds) ->
                      builds.forEach (build) ->
                          # load all buildsteps
                          build.loadSteps().then -> resolve(builders[0])
      .then (builder) ->
          # builder has a builds field, and the builds have a steps field containing the corresponding data
          $log.debug(builder)

``.control(method, params)``: returns a promise, sends a JSON RPC2 POST request to the server

RecentStorage
.............

The service provides methods for adding, retrieving and clearing recently viewed builders and builds.
It uses IndexedDB to store data inside the user’s browser.
You can see the list of supported browsers here: http://caniuse.com/indexeddb.

builder and build object properties:

* ``link`` - string: this specifies the builder’s or build’s link
* ``caption`` - string: this specifies the builder’s or build’s shown caption

Sample:

.. code-block:: coffeescript

    {
        link: '#/builders/1'
        caption: 'Mac'
    }

Methods:

* ``.addBuild(build)``: stores the build passed as argument
* ``.addBuild(builder)``: stores the builder passed as argument
* ``.getBuilds()``: returns a promise, the result will be an array of builds when the promise is resolved example:

    .. code-block:: coffeescript

        recentStorage.getBuilds().then (e) ->
            $scope.builds = e

* ``.getBuilders()``: returns a promise, the result will be an array of builders when the promise is resolved example:

    .. code-block:: coffeescript

        recentStorage.getBuilders().then (e) ->
            $scope.builders = e

* ``.getAll()``: returns a promise, the result will be an object with two fields, recent_builds and recent_builders example:

    .. code-block:: coffeescript

        recentStorage.getAll().then (e) ->
            $scope.builds = e.recent_builds
            $scope.builders = e.recent_builders

* ``.clearAll()``: removes the stored builds and builders example:

    .. code-block:: coffeescript

        recentStorage.clearAll()

Mocks and testing utils
~~~~~~~~~~~~~~~~~~~~~~~

DataService provides an easy way to mock data requests in tests.

* ``.when(url, [query], returnValue)``

    You can to specify on which parameters what value needs to be returned by the dataService's ``.get`` method.
    Available options are:

    * ``url``: the url of the request
    * ``query``: the query of the request (default: {})
    * ``returnValue``: the value that will be returned

    Example: ``dataService.when('buildrequests/1', [{buildrequestid: 1}])``

Linking with Buildbot
~~~~~~~~~~~~~~~~~~~~~

A running buildmaster needs to be able to find the JavaScript source code it needs to serve the UI.
This needs to work in a variety of contexts - Python development, JavaScript development, and end-user installations.
To accomplish this, the gulp build process finishes by bundling all of the static data into a Python distribution tarball, along with a little bit of Python glue.
The Python glue implements the interface described below, with some care taken to handle multiple contexts.

Hacking Quick-Start
-------------------

This section describes how to get set up quickly to hack on the JavaScript UI.
It does not assume familiarity with Python, although a Python installation is required, as well as ``virtualenv``.
You will also need ``NodeJS``, and ``npm`` installed.

Prerequisites
~~~~~~~~~~~~~

* Install latest release of node.js.

  http://nodejs.org/ is a good start for windows and osx.

  For linux, as node.js is evolving very fast, distros versions are often too old. For ubuntu, for example, you want to use following ppa:

  .. code-block:: none

    sudo add-apt-repository -y ppa:chris-lea/node.js

  Please feel free to update this documentation for other distros.

* Install gulp globally. Gulp is the build system used for coffeescript development.

  .. code-block:: none

    sudo npm install -g gulp

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

    pip install --editable pkg
    pip install --editable master/
    make frontend

This will fetch a number of dependencies from pypi, the Python package repository.
This will also fetch a bunch a bunch of node.js dependencies used for building the web application, and a bunch of client side js dependencies, with bower

Now you'll need to create a master instance.
For a bit more detail, see the Buildbot tutorial (:ref:`first-run-label`).

.. code-block:: none

    buildbot create-master sandbox/testmaster
    mv sandbox/testmaster/master.cfg.sample sandbox/testmaster/master.cfg
    buildbot start sandbox/testmaster

If all goes well, the master will start up and begin running in the background.
As you just installed www in editable mode (aka 'develop' mode), setup.py did build the web site in prod mode, so the everything is minified, making it hard to debug.

When doing web development, you usually run:

.. code-block:: none

    cd www/base
    gulp dev

This will compile the base webapp in development mode, and automatically rebuild when files change.


Testing with real data
~~~~~~~~~~~~~~~~~~~~~~
Front-end only hackers might want to just skip the master and slave setup, and just focus on the UI.
It can also be very useful to just try the UI with real data from your production.
For those use-cases, ``gulp dev proxy`` can be used.

This tool is a small nodejs app integrated in the gulp build that can proxy the data and websocket api from a production server to your development environment.
Having a proxy is slightly slower, but this can be very useful for testing with real complex data.

You still need to have python virtualenv configured with master package installed, like we described in previous paragraph.

Provided you run it in a buildbot master virtualenv, the following command will start the UI and redirect the api calls to the nine demo server:

.. code-block:: none

    gulp dev proxy --host nine.buildbot.net

You can then just point your browser to localhost:8010, and you will access nine.buildbot.net, with your own version of the UI.


Guanlecoja
----------

Buildbot's build environment has been factorized for reuse in other projects and plugins, and is callsed Guanlecoja.

The documentation and meaning of this name is maintained in Guanlecoja's own site. https://github.com/buildbot/guanlecoja/

Testing Setup
-------------

buildbot_www uses `Karma <http://karma-runner.github.io>`_ to run the coffeescript test suite.
This is the official test framework made for angular.js.
We don't run the front-end testsuite inside the python 'trial' test suite, because testing python and JS is technically very different.

Karma needs a browser to run the unit test in.
It supports all the major browsers.
Given our current experience, we did not see any bugs yet that would only happen on a particular browser this is the reason that at the moment, only headless browser "PhantomJS" is used for testing.

We enforce that the tests are run all the time after build.
This does not impact the build time by a great factor, and simplify the workflow.

In some case, this might not be desirable, for example if you run the build on headless system, without X.
PhantomJS, even if it is headless needs a X server like xvfb.
In the case where you are having difficulties to run Phantomjs, you can build without the tests using the command:

.. code-block:: none

    gulp prod --notests

Debug with karma
~~~~~~~~~~~~~~~~

``console.log`` is available via karma.
In order to debug the unit tests, you can also use the global variable ``dump``, which dumps any object for inspection in the console.
This can be handy to be sure that you dont let debug logs in your code to always use ``dump``
