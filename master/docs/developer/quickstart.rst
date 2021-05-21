
Development Quick-start
=======================

Buildbot is a python based application.
It tries very hard to follow the python best practices and make it easy to dive into the code.

In order to develop on Buildbot you need just a python environment and possibly some native packages in stripped-down setups.
The most up to date list is in the docker file we use to manage our CI (MetaBBotDockerFile_).

If you are completely new to python, it's best to first follow the tutorials you get when you type "python virtualenv for dummies" in your favorite search engine.

.. _MetaBBotDockerFile: https://github.com/buildbot/metabbotcfg/blob/nine/docker/metaworker/Dockerfile

.. _PythonDevQuickStart:

Create a Buildbot Python Environment
------------------------------------

Buildbot uses Twisted `trial <http://twistedmatrix.com/trac/wiki/TwistedTrial>`_ to run its test suite.
Windows users also need GNU make on their machines.
The easiest way is to install it via the choco package manager, ``choco install make``.
But WSL or MSYS2 is an even better option because of the integrated bash.

Following is a quick shell session to put you on the right track, including running the test suite.

.. code-block:: bash

    # the usual buildbot development bootstrap with git and virtualenv
    git clone https://github.com/buildbot/buildbot
    cd buildbot

    # run a helper script which creates the virtualenv for development.
    # Virtualenv allows to install python packages without affecting
    # other parts of the system
    make virtualenv

    # activate the virtualenv (you should now see (.venv) in your shell prompt)
    . .venv/bin/activate

    # now run the test suite
    trial buildbot

    # using all CPU cores within the system helps to speed everything up
    trial -j16 buildbot

    # find all tests that talk about mail
    trial -n --reporter=bwverbose buildbot | grep mail

    # run only one test module
    trial buildbot.test.unit.test_reporters_mail

    # you can also skip the virtualenv activation and
    # run the test suite in one step with make
    make trial

    # you can pass options to make using TRIALOPTS
    make trial TRIALOPTS='-j16 buildbot'

    # or test with a specific Python version
    make trial VENV_PY_VERSION=/usr/local/bin/python3


Create a JavaScript Frontend Environment
----------------------------------------

This section describes how to get set up quickly to hack on the JavaScript UI.
It does not assume familiarity with Python, although a Python installation is required, as well as ``virtualenv``.
You will also need ``NodeJS``, and ``yarn`` installed.

Prerequisites
~~~~~~~~~~~~~

.. note::

  Buildbot UI requires at least node 4 or newer and yarn.

* Install LTS release of node.js.

  http://nodejs.org/ is a good start for Windows and OSX.

  For modern Linux distributions, you can often just install the distribution-provided node version if it's recent enough.
  You can use yarn from the same source.
  The below method has been tested on Ubuntu 18.04 and should work on recent enough Debian.

  .. code-block:: none

    sudo apt install nodejs yarn

  In other cases, use https://deb.nodesource.com.

.. _JSDevQuickStart:

Hacking the Buildbot JavaScript
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To effectively develop Buildbot JavaScript, you'll need a running Buildmaster configured to operate out of the source directory.

As a prerequisite, follow :ref:`PythonDevQuickStart`.
With that, you should have created and enabled a virtualenv Python environment.

Next, you need to install the ``buildbot`` and ``buildbot-www`` python packages in ``--editable`` mode, which means their source directories will be directly used.

.. code-block:: none

    make frontend

This will fetch a number of python dependencies from pypi, the Python package repository, and also a number of node.js dependencies that are used for building the web application.
Then the actual frontend code will be built with artifacts stored in the source directory, e.g. ``www/base/buildbot_www/static``.
Finally, the built python packages will be installed to virtualenv environment as ``--editable`` packages.
This means that the webserver will load resources from ``www/base/buildbot_www/static``.

Now you need to create a master instance.
For more details, see the Buildbot :ref:`first-run-label` tutorial.

.. code-block:: none

    mkdir test-master
    buildbot create-master test-master
    mv test-master/master.cfg.sample test-master/master.cfg
    buildbot start test-master

If all goes well, the master will start up and run in the background.
During ``make frontend``, the www frontend was built using production mode, so everything is minified and hard to debug.
However, the frontend was installed as an editable python package, so all changes in the artifacts (e.g. ``www/base/buildbot_www/static``) in the source directories will be observed in the browser.
Thus, we can manually rebuild the JavaScript resources using development settings, so they are not minified and easier to debug.
This can be done by running the following in e.g. ``www/base`` directory:

.. code-block:: none

    yarn run build-dev

The above rebuilds the resources only once. After each change you need to refresh the built resources.
The actual commands that are run are stored in the ``package.json`` file under the ``scripts`` key.

To avoid the need to type the above command after each change, you can use the following:

.. code-block:: none

    yarn run dev

This will watch files for changes and reload automatically.

To run unit tests, do the following:

.. code-block:: none

    yarn run test

To run unit tests within all frontend packages within Buildbot, do the following at the root of the project:

.. code-block:: none

    make frontend_tests

.. note::

   You need to have Chrome-based browser installed in order to run unit tests in the default configuration.
