.. _Requirements:

Requirements
============

.. _Common-Requirements:

Common Requirements
-------------------

At a bare minimum, you'll need the following for both the buildmaster and a buildslave:

Python: http://www.python.org

  Both Buildbot master and Buildbot slave require Python-2.6, although Python-2.7 is recommended.

  .. note::

    This should be a "normal" build of Python.
    Builds of Python with debugging enabled or other unusual build parameters are likely to cause incorrect behavior.

Twisted: http://twistedmatrix.com

  Buildbot requires Twisted-11.0.0 or later on the master, and Twisted-8.1.0 on the slave.
  In upcoming versions of Buildbot, a newer Twisted will also be required on the slave.
  As always, the most recent version is recommended.
  Note that Twisted requires ZopeInterface to be installed as well.

Future:

  As part of ongoing (but as-yet incomplete) work to make Buildbot compatible with Python 3, the master requires the ``future`` module.

Of course, your project's build process will impose additional requirements on the buildslaves.
These hosts must have all the tools necessary to compile and test your project's source code.

Windows Support
~~~~~~~~~~~~~~~

Buildbot - both master and slave - runs well natively on Windows.
The slave runs well on Cygwin, but because of problems with SQLite on Cygwin, the master does not.

Buildbot's windows testing is limited to the most recent Twisted and Python versions.
For best results, use the most recent available versions of these libraries on Windows.

Pywin32: http://sourceforge.net/projects/pywin32/

  Twisted requires PyWin32 in order to spawn processes on Windows.

.. _Buildmaster-Requirements:

Buildmaster Requirements
------------------------

Note that all of these requirements aside from SQLite can easily be installed from the Python package repository, PyPi.

sqlite3: http://www.sqlite.org

  Buildbot requires a database to store its state, and by default uses SQLite.
  Version 3.7.0 or higher is recommended, although Buildbot will run against earlier versions -- at the risk of "Database is locked" errors.
  The minimum version is 3.4.0, below which parallel database queries and schema introspection fail.

  If you configure a different database engine, then SQLite is not required.
  however note that Buildbot's own unit tests require SQLite.

Jinja2: http://jinja.pocoo.org/

  Buildbot requires Jinja version 2.1 or higher.

  Jinja2 is a general purpose templating language and is used by Buildbot to generate the HTML output.

SQLAlchemy: http://www.sqlalchemy.org/

  Buildbot requires SQLAlchemy version 0.7.10, or version 0.8.1 or higher
  SQLAlchemy allows Buildbot to build database schemas and queries for a wide variety of database systems.

SQLAlchemy-Migrate: http://code.google.com/p/sqlalchemy-migrate/

  Buildbot requires one of the following SQLAlchemy-Migrate versions: 0.7.2 or 0.9 or higher.
  SQLAlchemy-Migrate-0.9 is required for compatibility with SQLAlchemy versions 0.8.0 and above.
  Buildbot uses SQLAlchemy-Migrate to manage schema upgrades from version to version.

Python-Dateutil: http://labix.org/python-dateutil

  The :bb:sched:`Nightly` scheduler requires Python-Dateutil version 1.5 (the last version to support Python-2.x).
  This is a small, pure-python library.
  Buildbot will function properly without it if the :bb:sched:`Nightly` scheduler is not used.

Autobahn:

  The master requires Autobahn version 0.10.2 or higher

