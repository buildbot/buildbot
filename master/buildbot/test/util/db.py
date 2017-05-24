# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

from __future__ import absolute_import
from __future__ import print_function

import os

from sqlalchemy.schema import MetaData

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log
from twisted.trial import unittest

from buildbot.db import enginestrategy
from buildbot.db import model
from buildbot.db import pool
from buildbot.util.sautils import sa_version
from buildbot.util.sautils import withoutSqliteForeignKeys


def skip_for_dialect(dialect):
    """Decorator to skip a test for a particular SQLAlchemy dialect."""
    def dec(fn):
        def wrap(self, *args, **kwargs):
            if self.db_engine.dialect.name == dialect:
                raise unittest.SkipTest(
                    "Not supported on dialect '%s'" % dialect)
            return fn(self, *args, **kwargs)
        return wrap
    return dec


class RealDatabaseMixin(object):

    """
    A class that sets up a real database for testing.  This sets self.db_url to
    the URL for the database.  By default, it specifies an in-memory SQLite
    database, but if the BUILDBOT_TEST_DB_URL environment variable is set, it
    will use the specified database, being careful to clean out *all* tables in
    the database before and after the tests are run - so each test starts with
    a clean database.

    @ivar db_pool: a (real) DBThreadPool instance that can be used as desired

    @ivar db_url: the DB URL used to run these tests

    @ivar db_engine: the engine created for the test database
    """

    # Note that this class uses the production database model.  A
    # re-implementation would be virtually identical and just require extra
    # work to keep synchronized.

    # Similarly, this class uses the production DB thread pool.  This achieves
    # a few things:
    #  - affords more thorough tests for the pool
    #  - avoids repetitive implementation
    #  - cooperates better at runtime with thread-sensitive DBAPI's

    def __thd_clean_database(self, conn):
        # In general it's nearly impossible to do "bullet proof" database
        # cleanup with SQLAlchemy that will work on a range of databases
        # and they configurations.
        #
        # Following approaches were considered.
        #
        # 1. Drop Buildbot Model schema:
        #
        #     model.Model.metadata.drop_all(bind=conn, checkfirst=True)
        #
        # Dropping schema from model is correct and working operation only
        # if database schema is exactly corresponds to the model schema.
        #
        # If it is not (e.g. migration script failed or migration results in
        # old version of model), then some tables outside model schema may be
        # present, which may reference tables in the model schema.
        # In this case either dropping model schema will fail (if database
        # enforces referential integrity, e.g. PostgreSQL), or
        # dropping left tables in the code below will fail (if database allows
        # removing of tables on which other tables have references,
        # e.g. SQLite).
        #
        # 2. Introspect database contents and drop found tables.
        #
        #     meta = MetaData(bind=conn)
        #     meta.reflect()
        #     meta.drop_all()
        #
        # May fail if schema contains reference cycles (and Buildbot schema
        # has them). Reflection looses metadata about how reference cycles
        # can be teared up (e.g. use_alter=True).
        # Introspection may fail if schema has invalid references
        # (e.g. possible in SQLite).
        #
        # 3. What is actually needed here is accurate code for each engine
        # and each engine configuration that will drop all tables,
        # indexes, constraints, etc in proper order or in a proper way
        # (using tables alternation, or DROP TABLE ... CASCADE, etc).
        #
        # Conclusion: use approach 2 with manually teared apart known
        # reference cycles.

        # pylint: disable=too-many-nested-blocks

        try:
            meta = MetaData(bind=conn)

            # Reflect database contents. May fail, e.g. if table references
            # non-existent table in SQLite.
            meta.reflect()

            # Table.foreign_key_constraints introduced in SQLAlchemy 1.0.
            if sa_version()[:2] >= (1, 0):
                # Restore `use_alter` settings to break known reference cycles.
                # Main goal of this part is to remove SQLAlchemy warning
                # about reference cycle.
                # Looks like it's OK to do it only with SQLAlchemy >= 1.0.0,
                # since it's not issued in SQLAlchemy == 0.8.0

                # List of reference links (table_name, ref_table_name) that
                # should be broken by adding use_alter=True.
                table_referenced_table_links = [
                    ('buildsets', 'builds'), ('builds', 'buildrequests')]
                for table_name, ref_table_name in table_referenced_table_links:
                    if table_name in meta.tables:
                        table = meta.tables[table_name]
                        for fkc in table.foreign_key_constraints:
                            if fkc.referred_table.name == ref_table_name:
                                fkc.use_alter = True

            # Drop all reflected tables and indices. May fail, e.g. if
            # SQLAlchemy wouldn't be able to break circular references.
            # Sqlalchemy fk support with sqlite is not yet perfect, so we must deactivate fk during that
            # operation, even though we made our possible to use use_alter
            with withoutSqliteForeignKeys(conn.engine, conn):
                meta.drop_all()

        except Exception:
            # sometimes this goes badly wrong; being able to see the schema
            # can be a big help
            if conn.engine.dialect.name == 'sqlite':
                r = conn.execute("select sql from sqlite_master "
                                 "where type='table'")
                log.msg("Current schema:")
                for row in r.fetchall():
                    log.msg(row.sql)
            raise

    def __thd_create_tables(self, conn, table_names):
        table_names_set = set(table_names)
        tables = [t for t in model.Model.metadata.tables.values()
                  if t.name in table_names_set]
        # Create tables using create_all() method. This way not only tables
        # and direct indices are created, but also deferred references
        # (that use use_alter=True in definition).
        model.Model.metadata.create_all(
            bind=conn, tables=tables, checkfirst=True)

    def setUpRealDatabase(self, table_names=[], basedir='basedir',
                          want_pool=True, sqlite_memory=True):
        """

        Set up a database.  Ordinarily sets up an engine and a pool and takes
        care of cleaning out any existing tables in the database.  If
        C{want_pool} is false, then no pool will be created, and the database
        will not be cleaned.

        @param table_names: list of names of tables to instantiate
        @param basedir: (optional) basedir for the engine
        @param want_pool: (optional) false to not create C{self.db_pool}
        @param sqlite_memory: (optional) False to avoid using an in-memory db
        @returns: Deferred
        """
        self.__want_pool = want_pool

        default_sqlite = 'sqlite://'
        self.db_url = os.environ.get('BUILDBOT_TEST_DB_URL', default_sqlite)
        if not sqlite_memory and self.db_url == default_sqlite:
            self.db_url = "sqlite:///tmp.sqlite"

        if not os.path.exists(basedir):
            os.makedirs(basedir)

        self.basedir = basedir
        self.db_engine = enginestrategy.create_engine(self.db_url,
                                                      basedir=basedir)
        # if the caller does not want a pool, we're done.
        if not want_pool:
            return defer.succeed(None)

        self.db_pool = pool.DBThreadPool(self.db_engine, reactor=reactor)

        log.msg("cleaning database %s" % self.db_url)
        d = self.db_pool.do(self.__thd_clean_database)
        d.addCallback(lambda _:
                      self.db_pool.do(self.__thd_create_tables, table_names))
        return d

    def tearDownRealDatabase(self):
        if self.__want_pool:
            return self.db_pool.do(self.__thd_clean_database)
        return defer.succeed(None)

    def insertTestData(self, rows):
        """Insert test data into the database for use during the test.

        @param rows: be a sequence of L{fakedb.Row} instances.  These will be
        sorted by table dependencies, so order does not matter.

        @returns: Deferred
        """
        # sort the tables by dependency
        all_table_names = set([row.table for row in rows])
        ordered_tables = [t for t in model.Model.metadata.sorted_tables
                          if t.name in all_table_names]

        def thd(conn):
            # insert into tables -- in order
            for tbl in ordered_tables:
                for row in [r for r in rows if r.table == tbl.name]:
                    tbl = model.Model.metadata.tables[row.table]
                    try:
                        tbl.insert(bind=conn).execute(row.values)
                    except Exception:
                        log.msg("while inserting %s - %s" % (row, row.values))
                        raise
        return self.db_pool.do(thd)


class TestCase(unittest.TestCase):

    @defer.inlineCallbacks
    def assertFailure(self, d, excp):
        exception = None
        try:
            yield d
        except Exception as e:
            exception = e
        self.assertIsInstance(exception, excp)
        self.flushLoggedErrors(excp)
