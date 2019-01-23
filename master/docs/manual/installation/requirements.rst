.. _Requirements:

Requirements
============

.. _Common-Requirements:

Common Requirements
-------------------

At a bare minimum, you'll need the following for both the buildmaster and a worker:

Python: https://www.python.org

  Buildbot master works with Python-3.5+.
  Buildbot worker works with Python 2.7, or Python 3.5+.

  .. note::

    This should be a "normal" build of Python.
    Builds of Python with debugging enabled or other unusual build parameters are likely to cause incorrect behavior.

Twisted: http://twistedmatrix.com

  Buildbot requires Twisted-17.9.0 or later on the master and the worker.
  In upcoming versions of Buildbot, a newer Twisted will also be required on the worker.
  As always, the most recent version is recommended.

Of course, your project's build process will impose additional requirements on the workers.
These hosts must have all the tools necessary to compile and test your project's source code.

Windows Support
~~~~~~~~~~~~~~~

Buildbot - both master and worker - runs well natively on Windows.
The worker runs well on Cygwin, but because of problems with SQLite on Cygwin, the master does not.

Buildbot's windows testing is limited to the most recent Twisted and Python versions.
For best results, use the most recent available versions of these libraries on Windows.

Pywin32: http://sourceforge.net/projects/pywin32/

  Twisted requires PyWin32 in order to spawn processes on Windows.

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

  Buildbot requires SQLAlchemy version 1.1.0 or higher.
  SQLAlchemy allows Buildbot to build database schemas and queries for a wide variety of database systems.

SQLAlchemy-Migrate: https://sqlalchemy-migrate.readthedocs.io/en/latest/

  Buildbot requires SQLAlchemy-Migrate version 0.9.0 or higher.
  Buildbot uses SQLAlchemy-Migrate to manage schema upgrades from version to version.

Python-Dateutil: http://labix.org/python-dateutil

  Buildbot requires Python-Dateutil in version 1.5 or higher (the last version to support Python-2.x).
  This is a small, pure-Python library.

Autobahn:

  The master requires Autobahn version 0.16.0 or higher with Python 2.7.
