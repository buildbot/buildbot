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

from contextlib import contextmanager

import sqlalchemy as sa
from sqlalchemy.ext import compiler
from sqlalchemy.sql.expression import ClauseElement
from sqlalchemy.sql.expression import Executable

# from http://www.sqlalchemy.org/docs/core/compiler.html#compiling-sub-elements-of-a-custom-expression-construct
# _execution_options per http://docs.sqlalchemy.org/en/rel_0_7/core/compiler.html#enabling-compiled-autocommit
#   (UpdateBase requires sqlalchemy 0.7.0)


class InsertFromSelect(Executable, ClauseElement):
    _execution_options = \
        Executable._execution_options.union({'autocommit': True})

    def __init__(self, table, select):
        self.table = table
        self.select = select


@compiler.compiles(InsertFromSelect)
def _visit_insert_from_select(element, compiler, **kw):
    return "INSERT INTO %s %s" % (
        compiler.process(element.table, asfrom=True),
        compiler.process(element.select)
    )


def sa_version():
    if hasattr(sa, '__version__'):
        def tryint(s):
            try:
                return int(s)
            except (ValueError, TypeError):
                return -1
        return tuple(map(tryint, sa.__version__.split('.')))
    return (0, 0, 0)  # "it's old"


def Table(*args, **kwargs):
    """Wrap table creation to add any necessary dialect-specific options"""
    # work around the case where a database was created for us with
    # a non-utf8 character set (mysql's default)
    kwargs['mysql_character_set'] = 'utf8'
    return sa.Table(*args, **kwargs)


@contextmanager
def withoutSqliteForeignKeys(engine, connection=None):
    conn = connection
    if engine.dialect.name == 'sqlite':
        if conn is None:
            conn = engine.connect()
        # This context is not re-entrant. Ensure it.
        assert not getattr(engine, 'fk_disabled', False)
        engine.fk_disabled = True
        conn.execute('pragma foreign_keys=OFF')
    try:
        yield
    finally:
        if engine.dialect.name == 'sqlite':
            engine.fk_disabled = False
            conn.execute('pragma foreign_keys=ON')
            if connection is None:
                conn.close()
