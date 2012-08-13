JS based web server
===================

One of the goals of buildbot 0.9.x is to rework the WebServer to use a more modern design and have most of its UI features implemented in JavaScript instead of Python.

The rationale behind this is that a client side UI relieves pressure on the server while being more responsive for the user.
The web server only concentrates on serving data via a REST interface to teh :ref:`Data_API`.
This removes a lot of sources of latency where, in previous versions, long synchronous calculations were made on the server to generate complex pages.

Another big advantage is live updates of status pages, without having to poll or reload.
The new system is using websockets in order to transfer Data API events into connected clients.

How To Enable
~~~~~~~~~~~~~

The new ``www`` implementation is disabled by default for now.
To enable it, simply add following code in your ``master.cfg``:

.. code-block:: python

     c['www'] = dict(port=8010)

Unpack the Dojo SDK from the `download page <http://dojotoolkit.org/download/>`_ into ``master/buildbot/www/static/js/external``:

.. code-block:: shell

    mkdir -p master/buildbot/www/static/js/external
    curl http://download.dojotoolkit.org/release-1.7.3/dojo-release-1.7.3-src.tar.gz | \
        tar --strip-components 1 -C master/buildbot/www/static/js/external -zxf -

You'll also need ``dojo/dijit/dgrid/put-selector``.

Server Side Design
~~~~~~~~~~~~~~~~~~~

The server resource set is divided into 4 main paths:

 * /ui - The top level that serves generic html for the user interface.
   This html page is a simple skeleton, and a placeholder that is then filled out by JS
 * /static - static files.
   The JavaScript framework is actually capable of getting these static files from another path, allowing high-volume installations to serve those files directly via Nginx or Apache.
   This path is itself divided into several paths:

  * /static/css - The source for CSS files
  * /static/img - The source for image files
  * /static/js/lib - The javascript source code of all buildbot js framework
  * /static/js/lib/ui - The ui javascript files
  * /static/js/lib/ui/templates - The html/haml templates for the ui
  * /static/js/external - path for external js libs that needs to be downloaded separatly from buildbot

 * /api - This is the root of the REST interface.
   Paths below here can be used either for reading status or for controlling Buildbot (start builds, stop builds, reload config, etc).
   The next component gives the API version.

 * /ws - path for websocket queries.
   This provides the JSON equivalent for the subscriptions part of the data API

Client Side Design
~~~~~~~~~~~~~~~~~~

The client side of the web UI is written in JavaScript and based on the Dojo and Dijit framework and concepts.

The best place to learn about Dojo is `its own documentation <http://dojotoolkit.org/documentation/>`_,

Among the classical features one would expect from a JS framework, Dojo provides:

 * An elegant `object-oriented module system <http://dojotoolkit.org/documentation/tutorials/1.7/declare>`_
 * A `deferred system <http://dojotoolkit.org/documentation/tutorials/1.7/deferreds>`_ similar to the one from Twisted.
 * A `common api <http://dojotoolkit.org/documentation/tutorials/1.7/intro_dojo_store/>`_ for accessing remote tabular data.
 * A `build system <http://dojotoolkit.org/documentation/tutorials/1.7/build>`_ that is in charge of compiling all javascript modules into one big minified js file, which is critical to achieve correct load time.
   It is not used yet by Buildbot.

Dijit is the UI extension of dojo.
It has a number of utilities to write responsive a dynamic web apps.

For CSS, we use `Twitter's bootstrap <http://twitter.github.com/bootstrap/>`_ as a base CSS framework for the UI.
For the sake of consistency, please try to fit in bootstrap CSS classes, and avoid defining your own, with your own placement.

Routing
+++++++

All Buildbot pages are technically the same path - ``/ui``.
The HTML at this location (:bb:file:`master/buildbot/www/ui.html`) is only a placeholder for JS to fill with Dijit widgets.
The actual content is dictated by the fragment in the URL (the portion following the ``#`` character).
Using the fragment is a common JS trick to avoid reloading the whole page over http when the user changes the URI, or clicks a link.
The router, implemented in :bb:file:`master/buildbot/www/static/lib/router.js`, is the component that is responsible for loading the proper content based on the fragment.

The routing table is an array of objects like this:

.. code-block:: js

            routes = [
                { path:"", name:"Home", widget:"home"},
                { path:"overview", name:"Overview", widget:"overview"},
                { path:"builders/([^/]+)", widget:"builder" }]

The keys are:

 * ``path`` - regular expression for matching the fragment.
 * ``name`` - The name of the navbar shortcut for this path
 * ``widget`` - The widget to load for this path.
   Widgets are located in :bb:file:`master/buildbot/www/static/js/lib/ui`.

For example, given the URL ``http://localhost:8010/ui/#/builders/builder1``, the system will load the widget ``builder`` with the special argument ``path_component`` being the result for the regex match, i.e: ``[ "builders/builder1", "builder1"]``.
The widget can then use those arguments to adapt its template.

The router also has support for query arguments, e.g: ``http://localhost:8010/ui/#/builds?builder=builder1&builder=builder2``
The arguments are sent to the widget using the ``url_arg`` parameter.

Widgets
+++++++

Each buildbot page is implmented by a Dijit widget, implemented in a module under ``lib/ui``.
The base class for the widgets is ``lib/ui/base``, templated widget that adds a deferred capability.
This allows a widget to load some JSON data (inside the ``loadMoreContext`` callback), and fill its context before the template is actually rendered.

Templates
+++++++++

Buildbot's templating is performed on the client side, using `Haml <http://haml.info/>`_
Haml is a templating engine originally made for ruby on rails, and later ported for use with node.js.
The language used for Buildbot, differs in the fact that JavaScript syntax is used instead of Ruby for evaluated expressions.
An excellent tutorial is provided in the `haml-js website <https://github.com/creationix/haml-js/>`_

The version that buildbot uses is slighlty modified, in order to fit Dojo's AMD module definition, and to add some syntactic sugar to import Haml files.
The Haml files can be loaded using a Dojo plugin, similar to ``dojo/text!``:

.. code-block:: js

        define(["dojo/_base/declare", "lib/ui/base",
                "lib/haml!./templates/build.haml"
           ], function(declare, Base, template) {
                "use strict";
                return declare([Base], {
                    templateFunc : template,
                    ...

haml emacs mode is `available <http://emacswiki.org/emacs/HamlMode>`_

Testing Setup
~~~~~~~~~~~~~

New www ui is coded fully in client side javascript. Heavy interaction with browser feature make it
difficult to unit test in a strict way. This is why we use a more complex setup to test this part of
the program.

Ghost.py
++++++++

Ghost.py is a testing library offering fullfeatured browser control.
It actually uses python binding to webkit browser engine.
Buildbot www test framework is instanciating the www server with stubbed data api, and testing how the JS code is behaving inside the headless browser.
More info on ghost is on the `original web server <http://jeanphix.me/Ghost.py/>`_

As buildbot is running inside twisted, and our tests are running with the help of trial, we need to have a special version of ghost, we called txghost, for twisted ghost.

This version has the same API as the original documented ghost, but every call is returning deferred.

Note, that as ghost is using webkit, which is based on qt technology, we must use some tricks in order to run the qt main loop inside trial reactor

Developer setup
+++++++++++++++

Unfortunately, PyQt is difficult to install in a virtualenv.
If you use ``--no-site-packages`` to set up a virtualenv, it will not inherit a globally installed PyQt.
So you need to convert your virtual env to use site packages.

.. code-block:: bash

     virtualenv path/to/your/sandbox

You can then install either PyQt or PySide systemwide, and use it within the virtualenv.
