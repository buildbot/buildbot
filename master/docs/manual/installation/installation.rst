.. _Installing-the-code:

Installing the code
-------------------

The Buildbot Packages
~~~~~~~~~~~~~~~~~~~~~

Buildbot comes in several parts: ``buildbot`` (the buildmaster), ``buildbot-worker`` (the worker), ``buildbot-www``, and several web plugins such as ``buildbot-waterfall-view``.

The worker and buildmaster can be installed individually or together.
The base web (``buildbot.www``) and web plugins are required to run a master with a web interface (the common configuration).

Installation From PyPI
~~~~~~~~~~~~~~~~~~~~~~

The preferred way to install Buildbot is using ``pip``.
For the master:

.. code-block:: bash

    pip install buildbot

and for the worker:

.. code-block:: bash

    pip install buildbot-worker

When using ``pip`` to install instead of distribution specific package managers, e.g. via `apt-get` or `ports`, it is simpler to choose exactly which version one wants to use.
It may however be easier to install via distribution specific package mangers but note that they may provide an earlier version than what is available via ``pip``.

If you plan to use TLS or SSL in master configuration (e.g. to fetch resources over HTTPS using ``twisted.web.client``), you need to install Buildbot with ``tls`` extras:

.. code-block:: bash

    pip install buildbot[tls]

Installation From Tarballs
~~~~~~~~~~~~~~~~~~~~~~~~~~

Buildbot master and ``buildbot-worker`` are installed using the standard Python `distutils <http://docs.python.org/library/distutils.html>`_ process.
For either component, after unpacking the tarball, the process is:

.. code-block:: bash

    python setup.py build
    python setup.py install

where the install step may need to be done as root.
This will put the bulk of the code in somewhere like :file:`/usr/lib/pythonx.y/site-packages/buildbot`.
It will also install the :command:`buildbot` command-line tool in :file:`/usr/bin/buildbot`.

If the environment variable ``$NO_INSTALL_REQS`` is set to ``1``, then :file:`setup.py` will not try to install Buildbot's requirements.
This is usually only useful when building a Buildbot package.

To test this, shift to a different directory (like :file:`/tmp`), and run:

.. code-block:: bash

    buildbot --version
    # or
    buildbot-worker --version

If it shows you the versions of Buildbot and Twisted, the install went ok.
If it says "no such command" or it gets an ``ImportError`` when it tries to load the libraries, then something went wrong.
``pydoc buildbot`` is another useful diagnostic tool.

Windows users will find these files in other places.
You will need to make sure that Python can find the libraries, and will probably find it convenient to have :command:`buildbot` on your :envvar:`PATH`.

.. _Installation-in-a-Virtualenv:

Installation in a Virtualenv
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you cannot or do not wish to install the buildbot into a site-wide location like :file:`/usr` or :file:`/usr/local`, you can also install it into the account's home directory or any other location using a tool like `virtualenv <http://pypi.python.org/pypi/virtualenv>`_.

.. _Running-Buildbots-Tests-optional:

Running Buildbot's Tests (optional)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you wish, you can run the buildbot unit test suite.
First, ensure you have the `mock <http://pypi.python.org/pypi/mock>`_ Python module installed from PyPI.
You must not be using a Python wheels packaged version of Buildbot or have specified the bdist_wheel command when building.
The test suite is not included with the PyPi packaged version.
This module is not required for ordinary Buildbot operation - only to run the tests.
Note that this is not the same as the Fedora ``mock`` package!

You can check with

.. code-block:: bash

    python -mmock

Then, run the tests:

.. code-block:: bash

    PYTHONPATH=. trial buildbot.test
    # or
    PYTHONPATH=. trial buildbot_worker.test

Nothing should fail, although a few might be skipped.

If any of the tests fail for reasons other than a missing ``mock``, you should stop and investigate the cause before continuing the installation process, as it will probably be easier to track down the bug early.
In most cases, the problem is incorrectly installed Python modules or a badly configured :envvar:`PYTHONPATH`.
This may be a good time to contact the Buildbot developers for help.


