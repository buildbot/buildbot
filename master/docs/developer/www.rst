JS based web server
===================

One of the goal of buildbot 0.9 is to rework the WebServer to use a more modern design
and have most of its UI features implemented in JS instead of python/twisted

The rational behind this is that a client side UI releases pressure on the server.
The web server only concentrates on serving json API, which translate seemlessly
into data api calls, which are basic db queries. This removes a lot of sources for
latency issue were long synchronous calculations were made in the server to generate complex
pages.

Other big advantage is the possibility for automatic update of status pages, without
having to poll. The new system is using websocket in order to transfer data api events into
connected clients.

.. _How-To-Enable:

How To Enable
~~~~~~~~~~~~~

The new ``www`` ui is disabled by default for now, to enable it, simply add following code in you
``master.cfg``

.. code-block:: python

     c['www'] = dict(port=8010)

.. _Server-Side-Design:

Server Side Design
~~~~~~~~~~~~~~~~~~~

The server resource set is divided into 4 main paths:

 * /ui - The top level ui that serves main generic html for main ui.
   This html page is just the common page, and a placeholder that is then filled out by JS
 * /static - serves all the static files. JS framework is actually capable to get those static
   files from another path, allowing to production configs to serve those files directly
   via nginx or apache. static is itself divided into several paths:

  * /static/css - The source for css files
  * /static/img - The source for image files
  * /static/js/lib - The javascript source code of all buildbot js framework
  * /static/js/lib/ui - The ui javascript files
  * /static/js/lib/ui/templates - The html/haml templates for the ui
  * /static/js/external - path for external js libs that needs to be downloaded separatly from buildbot

 * /api - serves all the json queries. Those can be either for reading status and for
   controlling buildbot (start builds, stop builds, reload config, etc). Provide json equivalent
   to getters and control parts of the data API.
 * /ws - path for websocket queries. Provide json equivalent for subscriptions part of the data
   API

.. _Client-Side-Design:

Client Side Design
~~~~~~~~~~~~~~~~~~

The js client side is based around the dojo and dijit framework and concepts.

Best place to learn dojo concepts is to start by `its own documentation <http://dojotoolkit.org/documentation/>`_,

Among classical feature one would expect from a JS framework, dojo framework introduce:
 * an `elegant object oriented module <http://dojotoolkit.org/documentation/tutorials/1.7/declare>`_
   system
 * a `deferred system <http://dojotoolkit.org/documentation/tutorials/1.7/deferreds>`_ similar to
   the one from twisted.
 * a `common api <http://dojotoolkit.org/documentation/tutorials/1.7/intro_dojo_store/>`_ for
   accessing remote tabular data
 * a `build system <http://dojotoolkit.org/documentation/tutorials/1.7/build>`_ that
   is in charge of compiling all javascript modules into one big minified js file,
   which is critical to achieve correct load time.


dijit is the ui extension of dojo. It has a number of utilities to write responsive a dynamic web apps.

For css, we use `twisted's bootstrap <http://twitter.github.com/bootstrap/>`_ as a base css framework
for the UI. For the sake of consistency, please try to fit in bootstrap css classes, and avoid defining
your own, with your own placement.

lib/router.js
+++++++++++++
The main html page is only a placeholder for JS to fill with dijit widgets.

Router.js is the center component that is responsible for loading the proper widgets according
to the hash part of the URI.

Routing table is an array of dictionaries like:

.. code-block:: js

            routes = [
	    { path:"", name:"Home", widget:"home"},
	    { path:"overview", name:"Overview", widget:"overview"},
	    { path:"builders/([^/]+)", widget:"builder" }]

keys to the dictionaries are:
 * path - regular expression for matching the hash part of the URI (the part after the ``#``
   which is normally used for anchors). Using hash part is a common JS trick to avoid
   reload the whole page over http when the user changes the URI, or click to a link.
 * name - The name of the navbar shortcut for this path
 * widget - The widget to load for this path, that is located in ``/js/lib/ui/``

For example, when a user points its browser on ``http://localhost:8010/ui/#/builders/builder1``, the system
will load the widget ``builder`` with the special argument path_component being the result for the regex match,
i.e: ``[ "builders/builder1", "builder1"]``. The widget can then use those arguments to adapt its template

The route.js also has support for query arguments, e.g: ``http://localhost:8010/ui/#/builds?builder=builder1&builder=builder2``
The arguments are sent to the widget using the ``url_arg`` parameter.

lib/ui/base.js
++++++++++++++

Every buildbot widgets need to inherit from base. base is a templated widget that adds a deferred capability.
This allows a widget to load some json data (inside the ``loadMoreContext`` callback), and fill its context
before the template is actually rendered.

lib/haml.js
+++++++++++

`Haml <http://haml.info/>`_ is a templating engine originally made for ruby on rails, and later ported for use with node.js.
The version that we use is the javascript version, the langage differs in the fact that js syntax is used instead of ruby
for evaluated expressions. Excellent tutorial is provided in the `haml-js website <https://github.com/creationix/haml-js/>`_

The version that buildbot uses is slighlty modified, in order to fit in dojo's AMD module definition, and to add some syntax sugar to import haml files:

.. code-block:: js

        define(["dojo/_base/declare", "lib/ui/base",
	        "lib/haml!./templates/build.haml"
	       ], function(declare, Base, template) {
	    "use strict";
            return declare([Base], {
		templateFunc : template,

haml emacs mode is `available <http://emacswiki.org/emacs/HamlMode>`_
