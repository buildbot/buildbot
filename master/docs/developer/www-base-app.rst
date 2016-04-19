.. _WWW-base-app:

Base web application
====================

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
You can also completly replace the default application by another application more suitable to your needs.
The ``md_base`` application is an example rewrite of the app using material design libraries.

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

Plugins are packaged as python entry-points for the ``buildbot.www`` namespace.
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

.. note::

  Buildbot UI is only tested to build on node 4.x.x.
  There are known issues with node 5.x.x and especially npm 3.x.x. (:bug:`4496`).

* Install LTS release of node.js.

  http://nodejs.org/ is a good start for windows and osx

  For Linux, as node.js is evolving very fast, distros versions are often too old, and sometimes distro maintainers make incompatible changes (i.e naming node binary nodejs instead of node)
  For Ubuntu and other Debian based distros, you want to use following method:

  .. code-block:: none

    curl -sL https://deb.nodesource.com/setup_4.x | sudo bash -

  Please feel free to update this documentation for other distros.
  Know good source for Linux binary distribution is: https://github.com/nodesource/distributions

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
Front-end only hackers might want to just skip the master and worker setup, and just focus on the UI.
It can also be very useful to just try the UI with real data from your production.
For those use-cases, ``gulp dev proxy`` can be used.

This tool is a small nodejs app integrated in the gulp build that can proxy the data and websocket api from a production server to your development environment.
Having a proxy is slightly slower, but this can be very useful for testing with real complex data.

You still need to have python virtualenv configured with master package installed, like we described in previous paragraph.

Provided you run it in a buildbot master virtualenv, the following command will start the UI and redirect the api calls to the nine demo server:

.. code-block:: none

    gulp dev proxy --host nine.buildbot.net

You can then just point your browser to localhost:8010, and you will access `<http://nine.buildbot.net>`__, with your own version of the UI.


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
