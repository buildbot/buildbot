.. _Requirements:

Requirements
============

.. _Common-Requirements:

Common Requirements
-------------------

At a bare minimum, you'll need the following for both the buildmaster and a worker:

Python: https://www.python.org

  Buildbot master works with Python-3.6+.
  Buildbot worker works with Python 2.7, or Python 3.5+.

  .. note::

    This should be a "normal" build of Python.
    Builds of Python with debugging enabled or other unusual build parameters are likely to cause incorrect behavior.

Twisted: http://twistedmatrix.com

  Buildbot requires Twisted-17.9.0 or later on the master and the worker.
  In upcoming versions of Buildbot, a newer Twisted will also be required on the worker.
  As always, the most recent version is recommended.

Certifi: https://github.com/certifi/python-certifi

  Certifi provides collection of Root Certificates for validating the trustworthiness of SSL certificates. 
  Unfortunately it does not support any addition of own company certificates.
  At the moment you need to add your own .PEM content to cacert.pem manually.

Of course, your project's build process will impose additional requirements on the workers.
These hosts must have all the tools necessary to compile and test your project's source code.

.. note::

  If your internet connection is secured by a proxy server, please check your ``http_proxy`` and ``https_proxy`` environment variables.
  Otherwise ``pip`` and other tools will fail to work.

Windows Support
~~~~~~~~~~~~~~~

Buildbot - both master and worker - runs well natively on Windows.
The worker runs well on Cygwin, but because of problems with SQLite on Cygwin, the master does not.

Buildbot's windows testing is limited to the most recent Twisted and Python versions.
For best results, use the most recent available versions of these libraries on Windows.

Pywin32: http://sourceforge.net/projects/pywin32/

  Twisted requires PyWin32 in order to spawn processes on Windows.

Build Tools for Visual Studio 2019 - Microsoft Visual C++ compiler

  Twisted requires MSVC to compile some parts like tls during the installation, 
  see https://twistedmatrix.com/trac/wiki/WindowsBuilds and https://wiki.python.org/moin/WindowsCompilers.

.. _Buildmaster-Requirements:

Buildmaster Requirements
------------------------

Note that all of these requirements aside from SQLite can easily be installed from the Python package repository, PyPI.

sqlite3: http://www.sqlite.org

  Buildbot requires a database to store its state, and by default uses SQLite.
  Version 3.7.0 or higher is recommended, although Buildbot will run down to 3.6.16 -- at the risk of "Database is locked" errors.
  The minimum version is 3.4.0, below which parallel database queries and schema introspection fail.

  Please note that Python ships with sqlite3 by default since Python 2.6.

  If you configure a different database engine, then SQLite is not required.
  however note that Buildbot's own unit tests require SQLite.

Jinja2: http://jinja.pocoo.org/

  Buildbot requires Jinja version 2.1 or higher.

  Jinja2 is a general purpose templating language and is used by Buildbot to generate the HTML output.

SQLAlchemy: http://www.sqlalchemy.org/

  Buildbot requires SQLAlchemy version 1.2.0 or higher.
  SQLAlchemy allows Buildbot to build database schemas and queries for a wide variety of database systems.

SQLAlchemy-Migrate: https://sqlalchemy-migrate.readthedocs.io/en/latest/

  Buildbot requires SQLAlchemy-Migrate version 0.9.0 or higher.
  Buildbot uses SQLAlchemy-Migrate to manage schema upgrades from version to version.

Python-Dateutil: http://labix.org/python-dateutil

  Buildbot requires Python-Dateutil in version 1.5 or higher (the last version to support Python-2.x).
  This is a small, pure-Python library.

Autobahn:

  The master requires Autobahn version 0.16.0 or higher with Python 2.7.

txrequests: https://github.com/tardyp/txrequests
or
treq: https://github.com/twisted/treq

  Both libraries are optional, but a lot of Buildbot plugins assume that one of it is installed. 
  Otherwise plugins will complain in the twisted log file if it is not installed. Here is 
  a little comparison table:

  +----------------------------------+------------+----------+
  |                                  | txrequests |   treq   |
  +----------------------------------+------------+----------+
  | International Domains and URLs   | yes        | yes      |
  +----------------------------------+------------+----------+
  | Keep-Alive & Connection Pooling  | yes        | yes      |
  +----------------------------------+------------+----------+
  | Sessions with Cookie Persistence | yes        | yes      |
  +----------------------------------+------------+----------+
  | Browser-style SSL Verification   | yes        | yes      |
  +----------------------------------+------------+----------+
  | Basic Authentication             | yes        | yes      |
  +----------------------------------+------------+----------+
  | Digest Authentication            | yes        | no       |
  +----------------------------------+------------+----------+
  | Elegant Key/Value Cookies        | yes        | yes      |
  +----------------------------------+------------+----------+
  | Automatic Decompression          | yes        | yes      |
  +----------------------------------+------------+----------+
  | Unicode Response Bodies          | yes        | yes      |
  +----------------------------------+------------+----------+
  | Multi-part File Uploads          | yes        | yes      |
  +----------------------------------+------------+----------+
  | Connection Timeouts              | yes        | yes      |
  +----------------------------------+------------+----------+
  | HTTP(S) Proxy Support            | yes        | no       |
  +----------------------------------+------------+----------+
  | .netrc support                   | yes        | no       |
  +----------------------------------+------------+----------+
  | Python 2.7                       | yes        | yes      |
  +----------------------------------+------------+----------+
  | Python 3.x                       | yes        | yes      |
  +----------------------------------+------------+----------+
  | Speed                            | slower     | fast     |
  +----------------------------------+------------+----------+

