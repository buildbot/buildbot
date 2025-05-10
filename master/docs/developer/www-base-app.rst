.. _WWW-base-app:

Base web application
====================

JavaScript Application
----------------------

The client side of the web UI is written in JavaScript and based on the React framework.

This is a `Single Page Application <http://en.wikipedia.org/wiki/Single-page_application>`_. All
Buildbot pages are loaded from the same path, at the master's base URL. The actual content of the
page is dictated by the fragment in the URL (the portion following the ``#`` character). Using the
fragment is a common JS technique to avoid reloading the whole page over HTTP when the user changes
the URI or clicks on a link.

React
~~~~~

The best place to learn about React is `its own documentation <https://react.dev/learn>`_.

React's strong points are:

* A component-based architecture that promotes reusability and maintainability
* A virtual DOM for efficient updates and rendering
* A rich ecosystem of tools and libraries
* Strong community support and frequent updates
* Built-in testing utilities and excellent support for unit testing

On top of React, we use nodeJS tools to ease development:

* `Vite <https://vitejs.dev/>`_ build system, which provides fast builds and hot module replacement
  during development. In production mode, the build system minifies html, css and js, so that the
  final app is only 3 files to download (+img)
* `TypeScript <https://www.typescriptlang.org/>`_ for type-safe JavaScript development
* `JSX <https://react.dev/learn/javascript-in-jsx-with-curly-braces>`_ syntax for combining
  JavaScript and HTML
* `Bootstrap <https://getbootstrap.com/>`_ is a CSS library providing known good basis for our styles
* `React Icons <https://react-icons.github.io/react-icons/>`_ is a comprehensive icon library with support for multiple icon sets

Additionally the following npm modules are loaded by Vite and are available to plugins:

* `react-router-dom <https://www.npmjs.com/package/react-router-dom>`_
* `react-bootstrap <https://www.npmjs.com/package/react-bootstrap>`_
* `d3 <https://www.npmjs.com/package/d3>`_
* `axios <https://www.npmjs.com/package/axios>`_

For the exact versions of these dependencies, check :src:`www/base/package.json`.

Extensibility
~~~~~~~~~~~~~

The Buildbot UI is designed for extensibility. The base application should be pretty minimal and
only include very basic status pages. The base application cannot be disabled, so any page that's
not absolutely necessary should be put in plugins. You can also completely replace the default
application by another application more suitable to your needs.

Some Web plugins are maintained inside Buildbot's git repository, but this is not required in order
for a plugin to work. Unofficial plugins are possible and encouraged.

Typical plugin source code layout is:

``setup.py``
    Standard setup script.
    Most plugins should use the same boilerplate, which implements building the BuildBot plugin app
    as part of the package setup.
    Minimal adaptation is needed.

``<pluginname>/__init__.py``
    The python entrypoint.
    Must contain an "ep" variable of type buildbot.www.plugin.Application.
    Minimal adaptation is needed.

``vite.config.ts``
    Configuration for Vite build system.
    Defines:
    - Entry point (typically src/index.ts)
    - Output directory (buildbot_<pluginname>/static)
    - External dependencies (React, MobX, etc.)
    Few changes are usually needed here.
    Please see Vite docs for details.

``src/...``
    Source code for the React application, typically organized as:
    - src/index.ts: Plugin entry point
    - src/views/: React components
    - src/utils/: Utility functions

``package.json``
    Declares npm dependencies and development scripts.
``tsconfig.json``
    TypeScript configuration.
    Defines compiler options and includes/excludes.

``MANIFEST.in``
    Needed by setup.py for sdist generation.
    You need to adapt this file to match the name of your plugin.


Plugins are packaged as python entry-points for the ``buildbot.www`` namespace.
The python part is defined in the ``buildbot.www.plugin`` module.
The entrypoint must contain a ``twisted.web`` Resource, that is populated in the web server in
``/<pluginname>/``.

The plugin may only add an http endpoint, or it could add a full JavaScript UI. This is controlled
by the ``ui`` argument of the ``Application`` endpoint object. If ``ui==True``, then it will
automatically load ``/<pluginname>/scripts.js`` and ``/<pluginname>/styles.css`` into the
React application.

The plugin's JavaScript entry point (typically src/index.ts) should use the ``buildbotSetupPlugin``
function to register:
- Menu items (with icons from react-icons)
- Routes (using react-router-dom)
- Settings (configuration options)
- Any other UI extensions

Example registration:

.. code-block:: typescript

    buildbotSetupPlugin(reg => {
        reg.registerMenuGroup({
            name: 'pluginname',
            caption: 'Plugin Name',
            icon: <FaIcon/>,
            order: 5,
            route: '/pluginroute',
        });

        reg.registerRoute({
            route: "/pluginroute",
            group: "pluginname",
            element: () => <PluginComponent/>,
        });
    });

The plugin writers may add more REST APIs to ``/<pluginname>/api``. For that, a reference to the
master singleton is provided in ``master`` attribute of the Application entrypoint. The plugins are
not restricted to Twisted, and could even `load a wsgi application using flask, django, or some
other framework <https://twistedmatrix.com/documents/current/web/howto/web-in-60/wsgi.html>`_.

Check out the official BuildBot www plugins for examples. The :src:`www/grid_view` and
:src:`www/badges` are good examples of plugins with and without a JavaScript UI respectively.

.. _Routing:

Routing
~~~~~~~

React uses a router to match URLs and choose which page to display.
The router we use is ``react-router-dom``.

Typically, a route registration will look like following example:

.. code-block:: jsx

    import { Route } from 'react-router-dom';
    import { FaExclamationCircle } from 'react-icons/fa';

    function MyComponent() {
        return (
            <Route path="/myname">
                <div>
                    <h1>My Name Plugin</h1>
                    <FaExclamationCircle />
                </div>
            </Route>
        );
    }

Linking with Buildbot
~~~~~~~~~~~~~~~~~~~~~

A running buildmaster needs to be able to find the JavaScript source code it needs to serve the UI.
This needs to work in a variety of contexts - Python development, JavaScript development, and
end-user installations. To accomplish this, the www build process finishes by bundling all of the
static data into a Python distribution tarball, along with a little bit of Python glue. The Python
glue implements the interface described below, with some care taken to handle multiple contexts.

See :ref:`JSDevQuickStart` for a more extensive explanation and tutorial.

Testing Setup
-------------

buildbot_www uses `Jest <https://jestjs.io/>`_ and `React Testing Library <https://testing-library.com/docs/react-testing-library/intro/>`_ to run the JavaScript test suite. These
are the recommended testing tools for React applications. We don't run the front-end testsuite inside the
python 'trial' test suite, because testing python and JS is technically very different.

Jest needs Node.js to run the unit tests.
Given our current experience, we did not see any bugs yet that would only happen on a particular browser.
This is the reason why only Chrome is used for testing at the moment.

Debug with Jest
~~~~~~~~~~~~~~~

``console.log`` is available via Jest. In order to debug the unit tests, you can use the
Chrome DevTools when running tests in watch mode. The React Developer Tools extension can also
be helpful for debugging component state and props.

Testing with real data
~~~~~~~~~~~~~~~~~~~~~~

It is possible to run the frontend development server while proxying API requests to a real Buildbot instance.
This allows front-end development with realistic data without needing a full local setup.

Vite's development server includes built-in proxy support configured in ``www/base/vite.config.ts``.
By default it proxies to ``https://buildbot.buildbot.net`` but you can modify this in the config file.

To start the development server:

.. code-block:: bash

    cd www/base
    yarn run start

