.. _WWW:

WWW
===

History and Motivation
----------------------

One of the goals of the 'nine' project is to rework Buildbot's web services to use a more modern, consistent design and implement UI features in client-side JavaScript instead of server-side Python.

The rationale behind this is that a client side UI relieves pressure on the server while being more responsive for the user.
The web server only concentrates on serving data via a REST interface wrappgin the the :ref:`Data_API`.
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

A simple example::

    POST http://build.my.org/api/v2/scheduler/4
    --> {"jsonrpc": "2.0", "method": "force", "params": {"revision": "abcd", "branch": "dev"}, "id": 843}
    <-- {"jsonrpc": "2.0", "result": {"buildsetid": 44}, "id": 843}

Message API
-----------

Currently messages are implemented with two protocols: WebSockets and `server sent event <http://en.wikipedia.org/wiki/Server-sent_events>`_.
This will likely change or be supplemented with other mechanisms before release.

WebSocket is a protocol for arbitrary messaging to and from browser.
As an HTTP extension, the protocol is not yet well supported by all HTTP proxy technologies, and thus not well suited for enterprise.
Only one WebSocket connection is needed per browser.

SSE is a simpler protocol than WebSockets and is more REST compliant.
It uses the chunk-encoding HTTP feature to stream the events.
It may use one connection to server per event type.

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

The Buildbot UI should be designed to support plug-ins to the web UI, allowing users and developers to create customized views without modifying Buildbot code.

How we can do that with angular is TBD


.. _Routing:

Routing
~~~~~~~

The router, we used is provided by angular, and the config is in src/scripts/routes.coffee


Directives
~~~~~~~~~~

We use angular directives as much as possible to implement reusable UI components.



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
    cd buildbot/www
    npm install

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

Now you'll need to create a master instance.
For a bit more detail, see the Buildbot tutorial (:ref:`first-run-label`).

.. code-block:: none

    buildbot create-master sandbox/testmaster
    mv sandbox/testmaster/master.cfg.sample sandbox/testmaster/master.cfg
    buildbot start sandbox/testmaster

If all goes well, the master will start up and begin running in the background.
Since you haven't yet done a full grunt build, the application will run from ``www/src``.
If, when the master starts, ``www/built`` exists, then it will run from that directory instead.

When doing web development, you can run:

.. code-block:: none

    cd www
    . tosource
    grunt dev

This will compile the webapp in development mode, and automatically rebuild when files change.
If your browser and dev environment are on the same machine, this will even reload the browser!


Testing Setup
-------------

TBD with testacular


Ghost.py
~~~~~~~~

Ghost.py is a testing library offering fullfeatured browser control.
It actually uses python binding to webkit browser engine.
Buildbot www test framework is instanciating the www server with stubbed data api, and testing how the JS code is behaving inside the headless browser.
More info on ghost is on the `original web server <http://jeanphix.me/Ghost.py/>`_

As buildbot is running inside twisted, and our tests are running with the help of trial, we need to have a special version of ghost, we called txghost, for twisted ghost.

This version has the same API as the original documented ghost, but every call is returning deferred.

Note, that as ghost is using webkit, which is based on qt technology, we must use some tricks in order to run the qt main loop inside trial reactor

Also, ghost has no support for websocket, so message passing tests are disabled when websocket is unavailable.

The ghost tests is running the same tests as ``buildbot ui-test-server`` would do on a real browser, but allows them to be run automatically in metabuildbot.
It is not recomended to run the tests via ghost method for development. Running them inside a real browser is much more productive, because you can use
the powerfull debug tools provided by them.

Developer setup
~~~~~~~~~~~~~~~

Unfortunately, PyQt is difficult to install in a virtualenv.
If you use ``--no-site-packages`` to set up a virtualenv, it will not inherit a globally installed PyQt.
So you need to convert your virtual env to use site packages.

.. code-block:: bash

     virtualenv path/to/your/sandbox

You can then install either PyQt or PySide systemwide, and use it within the virtualenv.
