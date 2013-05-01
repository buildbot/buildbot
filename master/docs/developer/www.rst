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
 * A WebSocket (and other Comet-related protocoles) wrapping the :ref:`Messaging_and_Queues` interface; and
 * Static JavaScript and resources implementing the client-side UI.

The REST interface is a very thin wrapper: URLs are translated directly into Data API paths, and results are returned directly, in JSON format.
Control calls are handled with JSONRPC.

The message interface is also a thin wrapper around Buildbot's MQ mechanism.
Clients can subscribe to messages, and receive copies of the messages, in JSON, as they are received by the buildmaster.

The client-side UI is also a thin wrapper around a typical AngularJS application.
Buildbot uses the Python setuptools entry-point mechanism to allow multiple packages to be combined into a single client-side experience.
This allows developers and users to build custom components for the web UI without hacking Buildbot itself.

Python development and AngularJS development are very different processes, requiring different environment requirements and skillsets.
To maimize hackability, Buildbot separates the two cleanly.
An experienced AngularJS hacker should be quite comfortable in the :bb:src:`www/` directory, with a few exceptions described below.
Similarly, an experienced Python hacker can simply download the pre-built web UI (from pypi!) and never venture near the :bb:src:`www/` directory.

URLs
~~~~

The Buildbot web interface is rooted at its base URL, as configured by the user.
It is entirely possible for this base URL to contain path components, e.g., ``http://build.myorg.net/buildbot``, if hosted behind an HTTP proxy.
To accomplish this, all URLs are generated relative to the base URL.

Overall, the space under the base URL looks like this:

* ``/`` -- the HTML document that loads the UI
* ``/api/v$V`` -- the root of the REST APIs, each versioned numerically.
  Users should, in general, use the latest version.
* ``/ws`` -- the websocket endpoint to subscribe to messages from the mq system.
  websocket is full-fledge protocol for arbitrary messaging to and from browser. Being an http extension, the protocol is not yet well
  supported by all http proxy technologies, and thus not well suited for enterprise.
  Only one connection needed per browser
* ``/sse`` -- the server-sent-event endpoint to subscribe to messages from the mq system.
  sse is a simpler protocol, that is more REST compliant, only using chunk-encoding http feature
  to stream the events. Potencially one connection to server per event type.

REST API
--------

The REST API is a thin wrapper around the data API's "Getter" and "Control" sections.
It is also designed, in keeping with REST principles, to be discoverable.
As such, the details of the paths and resources are not documented here.
See the :ref:`Data_API` documentation instead.

Getting
~~~~~~~

To get data, issue a GET request to the appropriate path.
For example, with a base URL of ``http://build.myorg.net/buildbot``, the list of masters for builder 9 is available at ``http://build.myorg.net/buildbot/api/v2/builder/9/master/``.

The following query arguments can be added to the request to alter the format of the response:

 * ``as_text`` -- (boolean) return content-type ``text/plain``, for ease of use in a browser
 * ``filter`` -- (boolean) filter out empty or false-ish values
 * ``compact`` -- (boolean) return compact JSON, rather than pretty-printed
 * ``callback`` -- if given, return a JSONP-encoded response with this callback

Controlling
~~~~~~~~~~~

Data API control operations are handled by POST requests.
The request body content type can be either ``application/x-www-form-urlencoded`` or, better, ``application/json``.

If encoded in ``application/x-www-form-urlencoded`` options are retrived in the form request args, and transmitted to
the control data api, special ``action`` parameter is removed, and transmitted to control data api, in its ``action``
argument. Response is transmitted json encoded in the same format as GET

If encoded in ``application/json``, JSON-RPC2 encodding is used: ``http://www.jsonrpc.org/specification``, where
jsonrpc's ``method`` is mapped to ``action``, and jsonrpc's ``params`` is mapped to options.
This allows to leverage existing client implementation of jsonrpc: ``http://en.wikipedia.org/wiki/JSON-RPC#Implementations``


Message API
-----------

Currently messages are implemented with an experimental WebSockets implementation at ``ws://$baseurl/ws``.
This will likely change or be supplemented with other mechanisms before release.

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
This will also fetch a bunch a bunch of node.js dependancies used for building the web application.

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

Karma needs a browser to run the unit test in. It supports all the major browsers. buildbot www's build script supports two popular browsers. like for the livereload feature, the test-runner works with autowatch mode. You need to use "grunt dev" in parallel from the following commands:


Run the tests in Firefox:

.. code-block:: none

    cd www
    . tosource
    grunt fftest

Run the tests in Chrome:

.. code-block:: none

    cd www
    . tosource
    grunt fftest

For the purpose of the metabuildbot, a special grunt target is made for running the test suite inside PhantomJS:

.. code-block:: none

    cd www
    . tosource
    grunt ci

