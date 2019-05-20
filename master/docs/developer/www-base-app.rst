.. _WWW-base-app:

Base web application
====================

JavaScript Application
----------------------

The client side of the web UI is written in JavaScript and based on the AngularJS framework and concepts.

This is a `Single Page Application <http://en.wikipedia.org/wiki/Single-page_application>`_.
All Buildbot pages are loaded from the same path, at the master's base URL.
The actual content of the page is dictated by the fragment in the URL (the portion following the ``#`` character).
Using the fragment is a common JS technique to avoid reloading the whole page over HTTP when the user changes the URI or clicks a link.

AngularJS
~~~~~~~~~

The best place to learn about AngularJS is `its own documentation <http://docs.angularjs.org/guide/>`_.

AngularJS strong points are:

* A very powerful `MVC system <https://docs.angularjs.org/guide/concepts>`_ allowing automatic update of the UI, when data changes
* A `Testing Framework and philosophy <https://docs.angularjs.org/guide/dev_guide.e2e-testing>`_
* A `deferred system <https://docs.angularjs.org/api/ng.$q>`_ similar to the one from Twisted
* A `fast growing community and ecosystem <https://www.madewithangular.com/>`_

On top of Angular we use nodeJS tools to ease development

* webpack build system, seamlessly build the app, can watch files for modification, rebuild and reload browser in dev mode.
  In production mode, the build system minifies html, css and js, so that the final app is only 3 files to download (+img)
* `pug template language  (aka jade) <https://pugjs.org/>`_, adds syntax sugar and readability to angular html templates
* `Bootstrap <https://getbootstrap.com/>`_ is a CSS library providing know good basis for our styles
* `Font Awesome <http://fortawesome.github.com/Font-Awesome/>`_ is a coherent and large icon library

Additionally the following npm modules are loaded by webpack and available to plugins:

* `@uirouter/angularjs <https://www.npmjs.com/package/@uirouter/angularjs>`
* `angular-animate <https://www.npmjs.com/package/angular-animate>`
* `angular-ui-boostrap <https://www.npmjs.com/package/angular-ui-bootstrap>`
* `d3 <https://www.npmjs.com/package/d3>`
* `jQuery <https://www.npmjs.com/package/jquery>`

For exact versions of these dependencies available, check ``www/base/package.json``.

Extensibility
~~~~~~~~~~~~~

Buildbot UI is designed for extensibility.
The base application should be pretty minimal, and only include very basic status pages.
Base application cannot be disabled so any page not absolutely necessary should be put in plugins.
You can also completely replace the default application by another application more suitable to your needs.

Some Web plugins are maintained inside buildbot's git repository, but this is not required in order for a plugin to work.
Unofficial plugins are possible and encouraged.

Please look at official plugins for working samples.

Typical plugin source code layout is:

.. code-block:: bash

    setup.py                     # standard setup script. Most plugins should use the same boilerplate, which helps building guanlecoja app as part of the setup. Minimal adaptation is needed
    <pluginname>/__init__.py     # python entrypoint. Must contain an "ep" variable of type buildbot.www.plugin.Application. Minimal adaptation is needed
    webpack.config.js            # Configuration for webpack. Few changes are usually needed here. Please see webpack docs for details.
    src/..                       # source code for the angularjs application.
    package.json                 # declares npm dependencies.
    MANIFEST.in                  # needed by setup.py for sdist generation. You need to adapt this file to match the name of your plugin

Plugins are packaged as python entry-points for the ``buildbot.www`` namespace.
The python part is defined in the ``buildbot.www.plugin`` module.
The entrypoint must contain a ``twisted.web`` Resource, that is populated in the web server in ``/<pluginname>/``.

The front-end part of the plugin system automatically loads ``/<pluginname>/scripts.js`` and ``/<pluginname>/styles.css`` into the angular.js application.
The scripts.js files can register itself as a dependency to the main "app" module, register some new states to ``$stateProvider``, or new menu items via glMenuProvider.

The entrypoint containing a Resource, nothing forbids plugin writers to add more REST apis in ``/<pluginname>/api``.
For that, a reference to the master singleton is provided in ``master`` attribute of the Application entrypoint.
You are even not restricted to twisted, and could even `load a wsgi application using flask, django, etc <https://twistedmatrix.com/documents/current/web/howto/web-in-60/wsgi.html>`_.

It is also possible to make a web plugin which only adds http endpoint, and has no javascript UI.
For that the ``Application`` endpoint object should have ``ui=False`` argument.
You can look at the :src:`www/badges` plugin for an example of a ui-less plugin.

.. _Routing:

Routing
~~~~~~~

AngularJS uses router to match URL and choose which page to display.
The router we use is ``ui.router``.
Menu is managed by guanlecoja-ui's glMenuProvider.
Please look at ``ui.router``, and guanlecoja-ui documentation for details.

Typically, a route registration will look like following example.

.. code-block:: javascript

    class MyState {

         // Dependency injection: we inject $stateProvider and glMenuServiceProvider
         constructor($stateProvider, glMenuServiceProvider) {
             // Name of the state
             const name = 'myname';
             const caption = 'My Name Plugin';

             // Configuration
             glMenuServiceProvider.addGroup({
                 name: name,
                 caption: caption,           // text of the menu
                 icon: 'exclamation-circle', // icon, from Font-Awesome
                 // Order in the menu, as menu are declared in several places,
                 // we need this to control menu order
                 order: 5
             });
             const cfg = {
                 group: name,
                 caption: caption
             };

             // Register new state
             const state = {
                 controller: "myStateController",
                 template: require('./myname.tpl.jade'),
                 name: name,
                 url: `/${name}`,
                 data: cfg
             };
             $stateProvider.state(state);
         }
     }

 angular.module('mymodule')
 .config(['$stateProvider', 'glMenuServiceProvider', MyState]);

Directives
~~~~~~~~~~

We use angular directives as much as possible to implement reusable UI components.


Linking with Buildbot
~~~~~~~~~~~~~~~~~~~~~

A running buildmaster needs to be able to find the JavaScript source code it needs to serve the UI.
This needs to work in a variety of contexts - Python development, JavaScript development, and end-user installations.
To accomplish this, the www build process finishes by bundling all of the static data into a Python distribution tarball, along with a little bit of Python glue.
The Python glue implements the interface described below, with some care taken to handle multiple contexts.

See :ref:`JSDevQuickStart` for a more extensive explanation and tutorial.


Testing Setup
-------------

buildbot_www uses `Karma <http://karma-runner.github.io>`_ to run the JavaScript test suite.
This is the official test framework made for angular.js.
We don't run the front-end testsuite inside the python 'trial' test suite, because testing python and JS is technically very different.

Karma needs a browser to run the unit test in.
It supports all the major browsers.
Given our current experience, we did not see any bugs yet that would only happen on a particular browser this is the reason that at the moment, only the "Chrome" is used for testing.

Debug with karma
~~~~~~~~~~~~~~~~

``console.log`` is available via karma.
In order to debug the unit tests, you can also use the global variable ``dump``, which dumps any object for inspection in the console.
This can be handy to be sure that you don't let debug logs in your code to always use ``dump``
