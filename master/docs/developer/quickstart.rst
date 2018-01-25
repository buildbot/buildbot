
Development Quick-start
=======================

Buildbot is a python based application.
It tries very hard to follow the python best practices, and to make is easy to dive into the code.

We won't try to create a full step by step how to install python on whatever distribution.
Basically what you need is just a python environment with maybe some native packages required by our dependencies.
Because those dependencies sometimes change, we keep the most up to date list in the docker file we use to manage our CI (MetaBBotDockerFile_).

If you are completely new to python, the best is to first follow the tutorials that would come when you type "python virtualenv for dummies" in your favorite search engine.

.. _MetaBBotDockerFile: https://github.com/buildbot/metabbotcfg/blob/nine/docker/metaworker/Dockerfile

.. _PythonDevQuickStart:

Create a Buildbot Python Environment
------------------------------------

Buildbot uses Twisted `trial <http://twistedmatrix.com/trac/wiki/TwistedTrial>`_ to run its test suite.

Following is a quick shell session to put you on the right track, including running the test suite.

.. code-block:: bash

    # the usual buildbot development bootstrap with git and virtualenv
    git clone https://github.com/buildbot/buildbot
    cd buildbot

    # helper script which creates the virtualenv for development
    make virtualenv
    . .venv/bin/activate

    # now we run the test suite
    trial buildbot

    # find all tests that talk about mail
    trial -n --reporter=bwverbose buildbot | grep mail

    # run only one test module
    trial buildbot.test.unit.test_reporters_mail


Create a JavaScript Frontend Environment
----------------------------------------

This section describes how to get set up quickly to hack on the JavaScript UI.
It does not assume familiarity with Python, although a Python installation is required, as well as ``virtualenv``.
You will also need ``NodeJS``, and ``npm`` installed.

Prerequisites
~~~~~~~~~~~~~

.. note::

  Buildbot UI is only tested to build on node 4.x.x.

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

.. _JSDevQuickStart:

Hacking the Buildbot JavaScript
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To effectively hack on the Buildbot JavaScript, you'll need a running Buildmaster, configured to operate out of the source directory (unless you like editing minified JS).

thus you need to follow the :ref:`PythonDevQuickStart`

This should have created an isolated Python environment in which you can install packages without affecting other parts of the system.
You should see ``(.venv)`` in your shell prompt, indicating the sandbox is activated.

Next, install the Buildbot-WWW and Buildbot packages using ``--editable``, which means that they should execute from the source directory.

.. code-block:: none

    make frontend

This will fetch a number of dependencies from pypi, the Python package repository.
This will also fetch a bunch a bunch of node.js dependencies used for building the web application, and a bunch of client side js dependencies, with bower

Now you'll need to create a master instance.
For a bit more detail, see the Buildbot tutorial (:ref:`first-run-label`).

.. code-block:: none

    buildbot create-master .venv/testmaster
    mv .venv/testmaster/master.cfg.sample .venv/testmaster/master.cfg
    buildbot start .venv/testmaster

If all goes well, the master will start up and begin running in the background.
As you just installed www in editable mode (aka 'develop' mode), setup.py did build the web site in prod mode, so the everything is minified, making it hard to debug.

When doing web development, you usually run:

.. code-block:: none

    cd www/base
    gulp dev

This will compile the base webapp in development mode, and automatically rebuild when files change.
