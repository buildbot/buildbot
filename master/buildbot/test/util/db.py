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


import os

import sqlalchemy as sa
from sqlalchemy.schema import MetaData
from twisted.python import log
from twisted.trial import unittest

from buildbot.db import model
from buildbot.util.sautils import withoutSqliteForeignKeys


def skip_for_dialect(dialect):
    """Decorator to skip a test for a particular SQLAlchemy dialect."""

    def dec(fn):
        def wrap(self, *args, **kwargs):
            if self.master.db._engine.dialect.name == dialect:
                raise unittest.SkipTest(f"Not supported on dialect '{dialect}'")
            return fn(self, *args, **kwargs)

        return wrap

    return dec


def get_trial_parallel_from_cwd(cwd):
    cwd = cwd.rstrip("/")
    last = os.path.basename(cwd)
    prev = os.path.basename(os.path.dirname(cwd))
    if last == "_trial_temp":
        return False
    if prev == "_trial_temp":
        try:
            return int(last)
        except ValueError:
            return None
    return None


def resolve_test_index_in_db_url(db_url: str) -> str:
    test_id = get_trial_parallel_from_cwd(os.getcwd())

    if "{TEST_ID}" in db_url:
        if test_id is None:
            raise RuntimeError("Database tests are run in parallel, but test index is unknown")

        return db_url.replace("{TEST_ID}", str(test_id or 0))

    if db_url == 'sqlite://':
        return db_url

    if test_id is not None and test_id is not False:
        if db_url.startswith('sqlite:///'):
            # Relative DB URLs in the test directory are fine.
            path = db_url[len('sqlite:///') :]
            if not os.path.relpath(path).startswith(".."):
                return db_url

        raise RuntimeError("Database tests cannnot run in parallel")

    return db_url


def resolve_test_db_url(db_url: str, sqlite_memory: bool) -> str:
    default_sqlite = 'sqlite://'
    if db_url is None:
        db_url = os.environ.get('BUILDBOT_TEST_DB_URL', default_sqlite)
        if not sqlite_memory and db_url == default_sqlite:
            db_url = "sqlite:///tmp.sqlite"

    return resolve_test_index_in_db_url(db_url)


def thd_clean_database(conn) -> None:
    # In general it's nearly impossible to do "bullet proof" database cleanup with SQLAlchemy
    # that will work on a range of databases and they configurations.
    #
    # Following approaches were considered.
    #
    # 1. Drop Buildbot Model schema:
    #
    #     model.Model.metadata.drop_all(bind=conn, checkfirst=True)
    #
    # Dropping schema from model is correct and working operation only if database schema is
    # exactly corresponds to the model schema.
    #
    # If it is not (e.g. migration script failed or migration results in old version of model),
    # then some tables outside model schema may be present, which may reference tables in the model
    # schema. In this case either dropping model schema will fail (if database enforces referential
    # integrity, e.g. PostgreSQL), or dropping left tables in the code below will fail (if database
    # allows removing of tables on which other tables have references, e.g. SQLite).
    #
    # 2. Introspect database contents and drop found tables.
    #
    #     meta = MetaData(bind=conn)
    #     meta.reflect()
    #     meta.drop_all()
    #
    # May fail if schema contains reference cycles (and Buildbot schema has them). Reflection looses
    # metadata about how reference cycles can be teared up (e.g. use_alter=True).
    # Introspection may fail if schema has invalid references (e.g. possible in SQLite).
    #
    # 3. What is actually needed here is accurate code for each engine and each engine configuration
    # that will drop all tables, indexes, constraints, etc in proper order or in a proper way
    # (using tables alternation, or DROP TABLE ... CASCADE, etc).
    #
    # Conclusion: use approach 2 with manually teared apart known reference cycles.

    try:
        meta = MetaData()

        # Reflect database contents. May fail, e.g. if table references
        # non-existent table in SQLite.
        meta.reflect(bind=conn)

        # Restore `use_alter` settings to break known reference cycles.
        # Main goal of this part is to remove SQLAlchemy warning
        # about reference cycle.

        # List of reference links (table_name, ref_table_name) that
        # should be broken by adding use_alter=True.
        table_referenced_table_links = [('buildsets', 'builds'), ('builds', 'buildrequests')]
        for table_name, ref_table_name in table_referenced_table_links:
            if table_name in meta.tables:
                table = meta.tables[table_name]
                for fkc in table.foreign_key_constraints:
                    if fkc.referred_table.name == ref_table_name:
                        fkc.use_alter = True

        # Drop all reflected tables and indices. May fail, e.g. if
        # SQLAlchemy wouldn't be able to break circular references.
        # Sqlalchemy fk support with sqlite is not yet perfect, so we must deactivate fk during
        # that operation, even though we made our possible to use use_alter
        with withoutSqliteForeignKeys(conn):
            meta.drop_all(bind=conn)
            conn.commit()

    except Exception:
        # sometimes this goes badly wrong; being able to see the schema
        # can be a big help
        if conn.engine.dialect.name == 'sqlite':
            r = conn.execute(sa.text("select sql from sqlite_master where type='table'"))
            log.msg("Current schema:")
            for row in r.fetchall():
                log.msg(row.sql)
        raise


def thd_create_tables(conn, table_names):
    table_names_set = set(table_names)
    tables = [t for t in model.Model.metadata.tables.values() if t.name in table_names_set]
    # Create tables using create_all() method. This way not only tables
    # and direct indices are created, but also deferred references
    # (that use use_alter=True in definition).
    model.Model.metadata.create_all(bind=conn, tables=tables, checkfirst=True)
    conn.commit()
