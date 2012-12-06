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

The client-side UI is also a thin wrapper around a typical Dojo application.
Buildbot uses the Python setuptools entry-point mechanism to allow multiple packages to be combined into a single client-side experience.
This allows developers and users to build custom components for the web UI without hacking Buildbot itself.

Python development and Dojo development are very different processes, requiring different environment requirements and skillsets.
To maimize hackability, Buildbot separates the two cleanly.
An experienced Dojo hacker should be quite comfortable in the :bb:src:`www/` directory, with a few exceptions described below.
Similarly, an experienced Python hacker can simply download the pre-built web UI (from pypi!) and never venture near the :bb:src:`www/` directory.

URLs
~~~~

The Buildbot web interface is rooted at its base URL, as configured by the user.
It is entirely possible for this base URL to contain path components, e.g., ``http://build.myorg.net/buildbot``, if hosted behind an HTTP proxy.
To accomplish this, all URLs are generated relative to the base URL.

Overall, the space under the base URL looks like this:

* ``/`` -- the HTML document that loads the UI
* ``/app/$app`` -- root of the ``static_dir`` for the ``buildbot.www`` application ``$app``.
  The main Buildbot application is named ``base`` and located at ``/app/base``.
* ``/api/v$V`` -- the root of the REST APIs, each versioned numerically.
  Users should, in general, use the latest version.
* ``/ws`` -- the websocket endpoint to subscribe to messages from the mq system.

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

The client side of the web UI is written in JavaScript and based on the Dojo and Dijit framework and concepts.

All Buildbot pages are loaded from the same path, at the master's base URL.
The actual content of the page is dictated by the fragment in the URL (the portion following the ``#`` character).
Using the fragment is a common JS techique to avoid reloading the whole page over HTTP when the user changes the URI or clicks a link.

Dojo
~~~~

The best place to learn about Dojo is `its own documentation <http://dojotoolkit.org/documentation/>`_,

Among the classical features one would expect from a JS framework, Dojo provides:

 * An elegant `object-oriented module system <http://dojotoolkit.org/documentation/tutorials/1.7/declare>`_
 * A `deferred system <http://dojotoolkit.org/documentation/tutorials/1.7/deferreds>`_ similar to the one from Twisted.
 * A `common api <http://dojotoolkit.org/documentation/tutorials/1.7/intro_dojo_store/>`_ for accessing remote tabular data.
 * A `build system <http://dojotoolkit.org/documentation/tutorials/1.7/build>`_ that is in charge of compiling all javascript modules into one big minified js file, which is critical to achieve correct load time.

Dijit is the UI extension of dojo.
It has a number of utilities to write responsive a dynamic web apps.

Extensibility
~~~~~~~~~~~~~

The Buildbot UI is designed to support plug-ins to the web UI, allowing users and developers to create customized views without modifying Buildbot code.
See :ref:`Building-A-JavaScript-Extension`, below, for more information.

The Dojo Project
~~~~~~~~~~~~~~~~

The :bb:src:`www` directory of the Buildbot source distribution is organized as a typical Dojo project, with a few minor exceptions.
It contains a ``build.sh`` script which, when run, will build the project.
It also contains a ``src/`` directory containing the source materials.
Within this directory are a number of git submodules, used to include the source of libraries (including Dojo itself) that are not part of Buildbot, but are included in the build.

The Buildbot source is in :bb:src:`www/src/bb``.
It contains all of the trappings of a typical Dojo package: ``package.js`` and ``package.json``, along with a collection of JS modules and static resources.
This directory should look familiar to a Dojo developer.

One exception is the use of Haml templates.
These templates must be converted to JavaScript before they will execute, using a node-based Haml compiler included with Buildbot.
The easiest way to do this is to run ``./build.sh --haml-only``.

Another exception is the location of the packages list, routes, and build profile.
These appear in :bb:src:`www/buildbot_www.py` as Python dictionaries.
The format should be obvious enough, and easy to modify if necessary.

A number of other libraries and utilities are also included.
See the git submodules in :bb:src:`www/src` for the full list.
Note that all libraries used must be license-compatible with Buildbot.

.. note:

    Moment.js does not play well with Dojo.
    The version used in Buildbot is forked and has some patches applied to work better, but not perfectly, with the Dojo build system.
    In particular, while moment.js itself works fine, none of its language files are available.

For CSS, Buildbot uses `Twitter's bootstrap <http://twitter.github.com/bootstrap/>`_ as a base CSS framework.
For the sake of consistency, please try to use bootstrap CSS classes, and avoid defining your own, with your own placement.

.. _Routing:

Routing
~~~~~~~

The router, implemented in :bb:src:`www/src/bb/router.js`, is the component that is responsible for loading the proper content based on the URL "hash" fragment.

Its input is a routing table -- an array of objects like this:

.. code-block:: js

            routes = [
                { path:"", name:"Home", widget:"home"},
                { path:"overview", name:"Overview", widget:"overview"},
                { path:"builders/([^/]+)", widget:"builder" },
            ]

The keys are:

 * ``path`` - regular expression for matching the fragment.
 * ``name`` - The name of the navbar shortcut for this path, if any
 * ``widget`` - The widget to load for this path.
   Widgets are located in :bb:src:`master/buildbot/www/static/js/lib/ui`.
 * ``enableif`` - array of conditions that must be satisfied to enable the route.

The conditions that can be specified for ``enableif`` are

 * ``admin`` - the user is an administrator

For example, given the URL ``http://localhost:8010/#/builders/builder1``, the system will load the widget ``builder`` with the special argument ``path_component`` being the result for the regex match, i.e: ``[ "builders/builder1", "builder1"]``.
The widget can then use those arguments to adapt its template.

The router also has support for query arguments, e.g: ``http://localhost:8010/ui/#/builds?builder=builder1&builder=builder2``
The arguments are sent to the widget using the ``url_arg`` parameter.

Routes are specified in Python via the :ref:`Buildbot-JavaScript-Application-Interface`.

Widgets
~~~~~~~

Each buildbot page is implmented by a Dijit widget, implemented in a module under :bb:src:`www/src/bb/ui`.
The base class for the widgets is ``bb/ui/base``, a templated widget that adds a deferred capability.
This allows a widget to load some JSON data (inside the ``loadMoreContext`` callback), and fill its context before the template is actually rendered.

Templates
~~~~~~~~~

Buildbot's templating is performed on the client side, using `Haml <http://haml.info/>`_.
Haml is a templating engine originally made for ruby on rails, and later ported for use with node.js.
The language used for Buildbot differs from the original in that JavaScript syntax is used instead of Ruby for evaluated expressions.
An excellent tutorial is provided in the `haml-js website <https://github.com/creationix/haml-js/>`_

We use `hamlcc <https://github.com/tardyp/hamlcc/>`_ to compile the haml templates into JavaScript.
This tool compiles an haml file into a js function that can be easily embedded into a Dojo build.
Buildbot's ``build.sh`` automatically compiles these templates, and will stop after doing so if given the ``--haml-only`` option.

Note that a haml emacs mode is `available <http://emacswiki.org/emacs/HamlMode>`_

Dojo Config
~~~~~~~~~~~

The buildmaster generates the Dojo configuration dynamically, inserting it into the global variable ``dojoConfig``.
This configuration can be used from any JavaScript module.
Among the standard Dojo keys in this variable, the ``baseUrl`` is is particularly helpful.
It should be used to generate fully-qualified URLs for all links and other references.

The ``dojoConfig.bb`` object contains Buildbot-specific configuration.
It has the following keys:

 * ``wsUrl`` -- the WebSocket URL
 * ``buildbotVersion`` -- the software version of the buildmaster
 * ``appInfo`` -- information (``name``, ``description``, and ``version``) about the installed JS applications
 * ``routes`` -- the combined routes for all JS applications (for use by ``bb/router``)

Building
~~~~~~~~

To build the project, follow the normal Dojo procedure:

.. code-block:: none

    cd www
    ./build.sh

This script will:

 * compile the Haml templates;
 * perform a typical Dojo build; and
 * wrap the result into a Python package which appears in the ``www/dist`` directory.

Linking with Buildbot
~~~~~~~~~~~~~~~~~~~~~

A running buildmaster needs to be able to find the JavaScript source code it needs to serve the UI.
This needs to work in a variety of contexts - Python development, JavaScript development, and end-user installations.
To accomplish this, the Dojo build process finishes by bundling all of the static data into a Python distribution tarball, along with a little bit of Python glue.
The Python glue implements the interface described below, with some care taken to handle multiple contexts.
The :bb:src:`www/build.sh`, :bb:src:`www/setup.py`, and :bb:src:`www/buildbot_www.py` scripts are carefully coordinated.

The buildmaster loads all of the available applications and combines their configuration into a single ``dojoConfig``, as described above.
This configuration is embedded in the generated HTML which is then served as the Buildbot UI.

.. _Buildbot-JavaScript-Application-Interface:

Buildbot JavaScript Application Interface
+++++++++++++++++++++++++++++++++++++++++

Buildbot uses setuptools "entry points" to locate Python packages that provide JavaScript applications.
Each such application is described by an entry point under the ``buildbot.www`` namespace.
When loaded, the entry point should present an object with the following attributes:

 * ``description`` -- a short description of the application (a word or two)
 * ``version`` -- the version of the application
 * ``static_dir`` -- the directory containing the source files
 * ``packages`` -- a list of Dojo packages contained in the application, with locations relative to ``static_dir``
 * ``routes`` -- a list of routes to be added to the router (see :ref:`Routing`)

The application's ``static_dir`` will be served at ``$baseUrl/app/$name``, where ``$name`` is the name of the setuptools entry point.
The location field of the packages will be adjusted to match.

A very simple implementation of this interface might have a ``setup.py`` like this::

    setup(
        # ...
        py_modules=['buildbot_www_milestones'],
        entry_points = """
            milestones = buildbot_www_milestones:ep
        """
    )

With ``buildbot_www_milestones.py`` containing::

    import os
    class Application:
        self.version = "1.0"
        self.description = "Milestones Page"
        self.static_dir = os.path.join(os.path.dirname(__file__), "src")
        self.packages = [ 'milestones' ]
        self.routes = [
            { 'path': 'milestones', 'name': 'Milestones', 'widget': 'milestones/ui/widget' },
        ]
    ep = Application()

.. warning::

    Inter-version compatibility between JavaScript applications and Buildbot is not supported.
    This interface is very likely to change incompatibly in each Buildbot version.

Hacking Quick-Start
-------------------

This section describes how to get set up quickly to hack on the JavaScript UI.
It does not assume familiarity with Python, although a Python installation is required, as well as ``virtualenv``.
You will also need Java and Node, as you would for any Dojo application.

Hacking the Buildbot JavaScript
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To effectively hack on the Buildbot JavaScript, you'll need a running Buildmaster, configured to operate out of the source directory (unless you like editing minified JS).
Start by cloning the project and its git submodules:

.. code-block:: none

    git clone git://github.com/buildbot/buildbot.git
    cd buildbot
    git submodule init
    git submodule update

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
You'll also need to compile the Haml templates:

.. code-block:: none

    www/build.sh --haml-only

Now you'll need to create a master instance.
For a bit more detail, see the Buildbot tutorial (:ref:`first-run-label`).

.. code-block:: none

    buildbot create-master sandbox/testmaster
    mv sandbox/testmaster/master.cfg.sample sandbox/testmaster/master.cfg
    buildbot start sandbox/testmaster

If all goes well, the master will start up and begin running in the background.
Since you haven't yet done a full Dojo build, the application will run from ``www/src``.
If, when the master starts, ``www/built`` exists, then it will run from that directory instead.

.. _Building-A-JavaScript-Extension:

Building A JavaScript Extension
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Buildbot can load several applications meeting the standards described in :ref:`Buildbot-JavaScript-Application-Interface`.
At least one must be the base UI implemented by Buildbot itself, but others can be supplied to add additional routes or other functionality.

The format for such an extension should roughly match that in the :bb:src:`www/` directory, including ``setup.py`` and an appropriately named Python module.
Do not name the module ``buildbot_www``, as that will conflict with the base application.

TODO: This section will need more detail when the interface is firm.

Testing Setup
-------------

New www ui is coded fully in client side javascript. Heavy interaction with browser feature make it
difficult to unit test in a strict way. This is why we use a more complex setup to test this part of
the program.

The JS tests are not using trial as a test suite runner, but rather are using dojo's test runner called
`doh <http://dojotoolkit.org/reference-guide/1.8/util/doh.html>`_.
A simple command is made to ease up the run of the js unit tests. just type the following command ::

    buildbot ui-test-server

This will start buildbot master in a special mode, so that the JS unit tests can run. This mode is mocking
some of the api inside the master, and enabling a new control api ``/api/testshooks``, that can play test scenarios.
Basically, a test scenario is a python method that calls the internal data api to create data events, or database rows.
The JS tests can then make sure the corresponding UI is generated in the web browser.

Test scenarios are located in master's test directory: ``master/buildbot/test/scenarios``.
The js test suite is located in ``www/src/bb/tests``. You can look at existing tests to see example.
The idea of the test suite is to let doh run the test web page iframe into a hashpath provided by the :ref:`Routing` table, and then verify that
the UI is behaving as expected. A ``bb/utils`` class is used in order to factorize common stuff. It contains following methods:

    - ``utils.registerBBTests(doh, <hashpath>, <testpath>)``: this function loads the hashpath into the test iframe, and make the router
      run the test module inside the iframe environment. This function is called in two environment. The "topdog" environment of doh's runner.html test environment,
      and the iframe environment, that runs the full buildbot website. The actual tests are to be run in the iframe environment. That is why this function only return
      true if run in iframe environment, so that you can embed it in a ``if (utils.registerBBTests(..)) { doh.register([...]) }``, and have only one test file for topdog,
      and iframe test declaration.

    - ``utils.assertDomText( expected, cssquery)``: This function run a query, assert that one and only one element is returned, and verify that the innerText attribute
      is equal to expected parameter.

    - ``utils.playTestScenario(scenariopath)``: This function use ``testhooks`` data control api to run a scenario inside the mocked master. It returns a promise that calls when
      when scenario's own deferred as called (in the python side), and then the Rest api has answered.

    - ``utils.playTestScenarioWaitForDomChange(scenariopath, cssquery)``: a variant of playTestScenario, that polls for a cssquery to change. It will return via promise, when
      the dom matched by cssquery has changed its innerHTML. The caller is then supposed to query again and verify that the changes are as expected. There is a 500ms polling timeout
      in which case the promise will call, triggering the test, which is supposed to fail.



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
