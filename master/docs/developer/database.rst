.. _developer-database:

Database
========

Buildbot stores most of its state in a database.
This section describes the database connector classes, which allow other parts of Buildbot to access the database.
It also describes how to modify the database schema and the connector classes themselves.


Database Overview
-----------------

All access to the Buildbot database is mediated by database connector classes.
These classes provide a functional, asynchronous interface to other parts of
Buildbot, and encapsulate the database-specific details in a single location in
the codebase.

The connector API, defined below, is a stable API in Buildbot, and can be
called from any other component.  Given a master ``master``, the root of the
database connectors is available at ``master.db``, so, for example, the state
connector's ``getState`` method is ``master.db.state.getState``.

All the connectors use `SQLAlchemy Core
<http://www.sqlalchemy.org/docs/index.html>`_ to achieve (almost)
database-independent operation.  Note that the SQLAlchemy ORM is not used in
Buildbot.  Database queries are carried out in threads, and report their
results back to the main thread via Twisted Deferreds.

Schema
------

Changes to the schema are accomplished through migration scripts, supported by
`Alembic <https://alembic.sqlalchemy.org/en/latest/>`_.

The schema itself is considered an implementation detail, and may change
significantly from version to version.  Users should rely on the API (below),
rather than performing queries against the database itself.

Identifier
----------

.. _type-identifier:

Restrictions on many string fields in the database are referred to as the Identifier concept.
An "identifier" is a nonempty unicode string of limited length, containing only UTF-8 alphanumeric characters along with ``-`` (dash) and ``_`` (underscore), and not beginning with a digit.
Wherever an identifier is used, the documentation will give the maximum length in characters.
The function :py:func:`buildbot.util.identifiers.isIdentifier` is useful to verify a well-formed identifier.

Writing Database Connector Methods
----------------------------------

The information above is intended for developers working on the rest of
Buildbot, and treating the database layer as an abstraction.  The remainder of
this section describes the internals of the database implementation, and is
intended for developers modifying the schema or adding new methods to the
database layer.

.. warning::

    It's difficult to change the database schema, especially after it has been released.
    Changing the database API is disruptive to users.
    Consider very carefully the future-proofing of any changes here!

The DB Connector and Components
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.db.connector

.. py:class:: DBConnector

    The root of the database connectors, ``master.db``, is a
    :class:`~buildbot.db.connector.DBConnector` instance.  Its main purpose is
    to hold a reference to each of the connector components, but it also handles
    timed cleanup tasks.

    If you are adding a new connector component, import its module and create
    an instance of it in this class's constructor.

.. py:module:: buildbot.db.base

.. py:class:: DBConnectorComponent

    This is the base class for connector components.

    There should be no need to override the constructor defined by this base
    class.

    .. py:attribute:: db

        A reference to the :class:`~buildbot.db.connector.DBConnector`, so that
        connector components can use e.g., ``self.db.pool`` or
        ``self.db.model``.  In the unusual case that a connector component
        needs access to the master, the easiest path is ``self.db.master``.

    .. py:method:: checkLength(col, value)

        For use by subclasses to check that 'value' will fit in 'col', where 'col' is a table column from the model.
        Ignore this check for database engines that either provide this error themselves (postgres) or that do not enforce maximum-length restrictions (sqlite).

    .. py:method:: findSomethingId(self, tbl, whereclause, insert_values, _race_hook=None, autoCreate=True)

        Find (using ``whereclause``) or add (using ``insert_values``) a row to
        ``table``, and return the resulting ID. If ``autoCreate`` == False, we will not automatically insert the row.

    .. py:method:: hashColumns(*args)

        Hash the given values in a consistent manner: None is represented as \xf5, an invalid unicode byte; strings are converted to utf8; and integers are represented by their decimal expansion.
        The values are then joined by '\0' and hashed with sha1.

    .. py:method:: doBatch(batch, batch_n=500)

        returns an Iterator that batches stuff in order to not push to many things in a single request.
        Especially sqlite has 999 limit that it can take in a request.

Direct Database Access
~~~~~~~~~~~~~~~~~~~~~~

.. py:module:: buildbot.db.pool

The connectors all use `SQLAlchemy Core
<http://www.sqlalchemy.org/docs/index.html>`_ as a wrapper around database
client drivers.  Unfortunately, SQLAlchemy is a synchronous library, so some
extra work is required to use it in an asynchronous context, like in Buildbot.
This is accomplished by deferring all database operations to threads, and
returning a Deferred.  The :class:`~buildbot.db.pool.Pool` class takes care of
the details.

A connector method should look like this::

    def myMethod(self, arg1, arg2):
        def thd(conn):
            q = ... # construct a query
            for row in conn.execute(q):
                ... # do something with the results
            return ... # return an interesting value
        return self.db.pool.do(thd)

Picking that apart, the body of the method defines a function named ``thd``
taking one argument, a :class:`Connection
<sqlalchemy:sqlalchemy.engine.base.Connection>` object.  It then calls
``self.db.pool.do``, passing the ``thd`` function.  This function is called in
a thread, and can make blocking calls to SQLAlchemy as desired.  The ``do``
method will return a Deferred that will fire with the return value of ``thd``,
or with a failure representing any exception raised by ``thd``.

The return value of ``thd`` must not be an SQLAlchemy object - in particular,
any :class:`ResultProxy <sqlalchemy:sqlalchemy.engine.base.ResultProxy>`
objects must be parsed into lists or other data structures before they are
returned.

.. warning::

    As the name ``thd`` indicates, the function runs in a thread.  It should
    not interact with any other part of Buildbot, nor with any of the Twisted
    components that expect to be accessed from the main thread -- the reactor,
    Deferreds, etc.

Queries can be constructed using any of the SQLAlchemy core methods, using
tables from :class:`~buildbot.db.model.Model`, and executed with the connection
object, ``conn``.

.. note::

    SQLAlchemy requires the use of a syntax that is forbidden by pep8.
    If in where clauses you need to select rows where a value is NULL,
    you need to write (`tbl.c.value == None`). This form is forbidden by pep8
    which requires the use of `is None` instead of `== None`. As sqlalchemy is using operator
    overloading to implement pythonic SQL statements, and the `is` operator is not overloadable,
    we need to keep the `==` operators. In order to solve this issue, Buildbot
    uses `buildbot.db.NULL` constant, which is `None`.
    So instead of writing `tbl.c.value == None`, please write `tbl.c.value == NULL`).


.. py:class:: DBThreadPool

    .. py:method:: do(callable, ...)

        :returns: Deferred

        Call ``callable`` in a thread, with a :class:`Connection
        <sqlalchemy:sqlalchemy.engine.base.Connection>` object as first
        argument.  Returns a deferred that will fire with the results of the
        callable, or with a failure representing any exception raised during
        its execution.

        Any additional positional or keyword arguments are passed to
        ``callable``.

    .. py:method:: do_with_engine(callable, ...)

        :returns: Deferred

        Similar to :meth:`do`, call ``callable`` in a thread, but with an
        :class:`Engine <sqlalchemy:sqlalchemy.engine.base.Engine>` object as
        first argument.

        This method is only used for schema manipulation, and should not be
        used in a running master.

Database Schema
~~~~~~~~~~~~~~~

.. py:module:: buildbot.db.model

Database connector methods access the database through SQLAlchemy, which
requires access to Python objects representing the database tables.  That is
handled through the model.

.. py:class:: Model

    This class contains the canonical description of the Buildbot schema.
    It is represented in the form of SQLAlchemy :class:`Table <sqlalchemy:sqlalchemy.schema.Table>` instances, as class variables.
    At runtime, the model is available at ``master.db.model``.
    So, for example, the ``buildrequests`` table can be referred to as ``master.db.model.buildrequests``, and columns are available in its ``c`` attribute.

    The source file, :src:`master/buildbot/db/model.py`, contains comments describing each table; that information is not replicated in this documentation.

    Note that the model is not used for new installations or upgrades of the
    Buildbot database.  See :ref:`Modifying-the-Database-Schema` for more
    information.

    .. py:attribute:: metadata

        The model object also has a ``metadata`` attribute containing a
        :class:`MetaData <sqlalchemy:sqlalchemy.schema.MetaData>` instance.
        Connector methods should not need to access this object.  The metadata
        is not bound to an engine.

    The :py:class:`Model` class also defines some migration-related methods:

    .. py:method:: is_current()

        :returns: boolean via Deferred

        Returns true if the current database's version is current.

    .. py:method:: upgrade()

        :returns: Deferred

        Upgrades the database to the most recent schema version.

Caching
~~~~~~~

.. py:currentmodule:: buildbot.db.base

Connector component methods that get an object based on an ID are good
candidates for caching.  The :func:`~buildbot.db.base.cached` decorator
makes this automatic:

.. py:function:: cached(cachename)

    :param cache_name: name of the cache to use

    A decorator for "getter" functions that fetch an object from the database
    based on a single key.  The wrapped method will only be called if the named
    cache does not contain the key.

    The wrapped function must take one argument (the key); the wrapper will
    take a key plus an optional ``no_cache`` argument which, if true, will
    cause it to invoke the underlying method even if the key is in the cache.

    The resulting method will have a ``cache`` attribute which can be used to
    access the underlying cache.

In most cases, getter methods return a well-defined dictionary.  Unfortunately,
Python does not handle weak references to bare dictionaries, so components must
instantiate a subclass of ``dict``.  The whole assembly looks something like
this::

    class ThDict(dict):
        pass

    class ThingConnectorComponent(base.DBConnectorComponent):

        @base.cached('thdicts')
        def getThing(self, thid):
            def thd(conn):
                ...
                thdict = ThDict(thid=thid, attr=row.attr, ...)
                return thdict
            return self.db.pool.do(thd)

Tests
~~~~~

It goes without saying that any new connector methods must be fully tested!

You will also want to add an in-memory implementation of the methods to the
fake classes in ``master/buildbot/test/fake/fakedb.py``.  Non-DB Buildbot code
is tested using these fake implementations in order to isolate that code from
the database code, and to speed-up tests.

The keys and types used in the return value from a connector's ``get`` methods are described in :src:`master/buildbot/test/util/validation.py`, via the ``dbdict`` module-level value.
This is a dictionary of ``DictValidator`` objects, one for each return value.

These values are used within test methods like this::

    rv = yield self.db.masters.getMaster(7)
    validation.verifyDbDict(self, 'masterdict', rv)

.. _Modifying-the-Database-Schema:

Modifying the Database Schema
-----------------------------

Changes to the schema are accomplished through migration scripts, supported by
`Alembic <https://alembic.sqlalchemy.org/en/latest/>`_.

The schema is tracked by a revision number, stored in the ``alembic_version`` table.
It can be anything, but by convention Buildbot uses revision numbers that are numbers incremented by one for each revision.
The master will refuse to run with an outdated database.

To make a change to the schema, first consider how to handle any existing data.
When adding new columns, this may not be necessary, but table refactorings can
be complex and require caution so as not to lose information.

Refer to the documentation of Alembic for details of how database migration scripts should be written.

The database schema itself is stored in :src:`master/buildbot/db/model.py` which should be updated to represent the new schema.
Buildbot's automated tests perform a rudimentary comparison of an upgraded database with the model, but it is important to check the details - key length, nullability, and so on can sometimes be missed by the checks.
If the schema and the upgrade scripts get out of sync, bizarre behavior can result.

Changes to database schema should be reflected in corresponding fake database table definitions in :src:`master/buildbot/test/fakedb`

The upgrade scripts should have unit tests.
The classes in :src:`master/buildbot/test/util/migration.py` make this straightforward.
Unit test scripts should be named e.g., :file:`test_db_migrate_versions_015_remove_bad_master_objectid.py`.

The :src:`master/buildbot/test/integration/test_upgrade.py <master/buildbot/test/integration/test_upgrade.py>` also tests
upgrades, and will confirm that the resulting database matches the model.  If
you encounter implicit indexes on MySQL, that do not appear on SQLite or
Postgres, add them to ``implied_indexes`` in
:file:`master/buidlbot/db/model.py`.

Foreign key checking
--------------------
PostgreSQL and SQlite db backends check the foreign keys consistency.
:bug:`2248` needs to be fixed so that we can support foreign key checking for MySQL.

To maintain consistency with real db, fakedb can check the foreign key consistency of your test data. For this, just enable it with::

    self.db = fakedb.FakeDBConnector(self.master, self)
    self.db.checkForeignKeys = True

Note that tests that only use fakedb do not really need foreign key consistency, even if this is a good practice to enable it in new code.


.. note:

    Since version `3.6.19 <https://www.sqlite.org/releaselog/3_6_19.html>`_, sqlite can do `foreignkey checks <https://www.sqlite.org/pragma.html#pragma_foreign_key_check>`_, which help a lot for testing foreign keys constraint in a developer friendly environment.
    For compat reason, they decided to disable foreign key checks by default.
    Since 0.9.0b8, buildbot now enforces by default the foreign key checking, and is now dependent on sqlite3 >3.6.19, which was released in 2009.


Database Compatibility Notes
----------------------------

Or: "If you thought any database worked right, think again"

Because Buildbot works over a wide range of databases, it is generally limited
to database features present in all supported backends.  This section
highlights a few things to watch out for.

In general, Buildbot should be functional on all supported database backends.
If use of a backend adds minor usage restrictions, or cannot implement some
kinds of error checking, that is acceptable if the restrictions are
well-documented in the manual.

The metabuildbot tests Buildbot against all supported databases, so most
compatibility errors will be caught before a release.

Index Length in MySQL
~~~~~~~~~~~~~~~~~~~~~

.. index:: single: MySQL; limitations

MySQL only supports about 330-character indexes. The actual index length is
1000 bytes, but MySQL uses 3-byte encoding for UTF8 strings.  This is a
longstanding bug in MySQL - see `"Specified key was too long; max key
length is 1000 bytes" with utf8 <http://bugs.mysql.com/bug.php?id=4541>`_.
While this makes sense for indexes used for record lookup, it limits the
ability to use unique indexes to prevent duplicate rows.

InnoDB only supports indexes up to 255 unicode characters, which is why
all indexed columns are limited to 255 characters in Buildbot.

Transactions in MySQL
~~~~~~~~~~~~~~~~~~~~~

.. index:: single: MySQL; limitations

Unfortunately, use of the MyISAM storage engine precludes real transactions in
MySQL.  ``transaction.commit()`` and ``transaction.rollback()`` are essentially
no-ops: modifications to data in the database are visible to other users
immediately, and are not reverted in a rollback.

Referential Integrity in SQLite and MySQL
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. index:: single: SQLite; limitations
.. index:: single: MySQL; limitations

Neither MySQL nor SQLite enforce referential integrity based on foreign keys.
Postgres does enforce it, however.  If possible, test your changes on Postgres
before committing, to check that tables are added and removed in the proper
order.

Subqueries in MySQL
~~~~~~~~~~~~~~~~~~~

.. index:: single: MySQL; limitations

MySQL's query planner is easily confused by subqueries.  For example, a DELETE
query specifying id's that are IN a subquery will not work.  The workaround is
to run the subquery directly, and then execute a DELETE query for each returned
id.

If this weakness has a significant performance impact, it would be acceptable to
conditionalize use of the subquery on the database dialect.

Too Many Variables in SQLite
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. index:: single: SQLite; limitations

Sqlite has a limitation on the number of variables it can use.
This limitation is usually `SQLITE_LIMIT_VARIABLE_NUMBER=999 <http://www.sqlite.org/c3ref/c_limit_attached.html#sqlitelimitvariablenumber>`_.
There is currently no way with pysqlite to query the value of this limit.
The C-api ``sqlite_limit`` is just not bound to the python.

When you hit this problem, you will get error like the following:

.. code-block:: none

    sqlalchemy.exc.OperationalError: (OperationalError) too many SQL variables
    u'DELETE FROM scheduler_changes WHERE scheduler_changes.changeid IN (?, ?, ?, ..., ?)

You can use the method :py:meth:`doBatch` in order to write batching code in a consistent manner.

Testing migrations with real databases
--------------------------------------

By default Buildbot test suite uses SQLite database for testing database
migrations.
To use other database set ``BUILDBOT_TEST_DB_URL`` environment variable to
value in `SQLAlchemy database URL specification
<http://docs.sqlalchemy.org/en/latest/core/engines.html#database-urls>`_.

For example, to run tests with file-based SQLite database you can start
tests in the following way:

.. code-block:: bash

   BUILDBOT_TEST_DB_URL=sqlite:////tmp/test_db.sqlite trial buildbot.test

Run databases in Docker
~~~~~~~~~~~~~~~~~~~~~~~

`Docker <https://www.docker.com/>`_ allows to easily install and configure
different databases locally in containers.

To run tests with PostgreSQL:

.. code-block:: bash

   # Install psycopg
   pip install psycopg2
   # Start container with PostgreSQL 9.5
   # It will listen on port 15432 on localhost
   sudo docker run --name bb-test-postgres -e POSTGRES_PASSWORD=password \
       -p 127.0.0.1:15432:5432 -d postgres:9.5
   # Start interesting tests
   BUILDBOT_TEST_DB_URL=postgresql://postgres:password@localhost:15432/postgres \
       trial buildbot.test

To run tests with MySQL:

.. code-block:: bash

   # Install mysqlclient
   pip install mysqlclient
   # Start container with MySQL 5.5
   # It will listen on port 13306 on localhost
   sudo docker run --name bb-test-mysql -e MYSQL_ROOT_PASSWORD=password \
       -p 127.0.0.1:13306:3306 -d mysql:5.5
   # Start interesting tests
   BUILDBOT_TEST_DB_URL=mysql+mysqldb://root:password@127.0.0.1:13306/mysql \
       trial buildbot.test
