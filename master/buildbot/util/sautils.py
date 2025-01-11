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

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.ext import compiler
from sqlalchemy.sql.elements import BooleanClauseList
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.expression import ClauseElement
from sqlalchemy.sql.expression import Executable

if TYPE_CHECKING:
    from typing import Any
    from typing import Callable
    from typing import Sequence

    from sqlalchemy.future.engine import Connection
    from sqlalchemy.future.engine import Engine

# from http:
# www.sqlalchemy.org/docs/core/compiler.html#compiling-sub-elements-of-a-custom-expression-construct
# _execution_options per
# http://docs.sqlalchemy.org/en/rel_0_7/core/compiler.html#enabling-compiled-autocommit
# (UpdateBase requires sqlalchemy 0.7.0)


class InsertFromSelect(Executable, ClauseElement):
    _execution_options = Executable._execution_options.union({'autocommit': True})

    def __init__(self, table, select):
        self.table = table
        self.select = select


@compiler.compiles(InsertFromSelect)
def _visit_insert_from_select(element, compiler, **kw):
    return (
        f"INSERT INTO {compiler.process(element.table, asfrom=True)} "
        f"{compiler.process(element.select)}"
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
def withoutSqliteForeignKeys(connection: Connection):
    if connection.engine.dialect.name != 'sqlite':
        yield
        return

    res = connection.exec_driver_sql('pragma foreign_keys')
    r = res.fetchone()
    assert r
    foreign_keys_enabled = r[0]
    res.close()
    if not foreign_keys_enabled:
        yield
        return

    # This context is not re-entrant. Ensure it.
    assert not getattr(connection.engine, 'fk_disabled', False)
    connection.fk_disabled = True  # type: ignore[attr-defined]
    connection.exec_driver_sql('pragma foreign_keys=OFF')
    try:
        yield
    finally:
        connection.fk_disabled = False  # type: ignore[attr-defined]
        connection.exec_driver_sql('pragma foreign_keys=ON')


def get_sqlite_version():
    import sqlite3

    return sqlite3.sqlite_version_info


def get_upsert_method(engine: Engine | None):
    if engine is None:
        return _upsert_default

    # https://sqlite.org/lang_upsert.html
    if engine.dialect.name == 'sqlite' and get_sqlite_version() > (3, 24, 0):
        return _upsert_sqlite
    if engine.dialect.name == 'postgresql':
        return _upsert_postgresql
    if engine.dialect.name == 'mysql':
        return _upsert_mysql

    return _upsert_default


def _upsert_sqlite(
    connection: Connection,
    table: sa.Table,
    *,
    where_values: Sequence[tuple[sa.Column, Any]],
    update_values: Sequence[tuple[sa.Column, Any]],
    _race_hook: Callable[[Connection], None] | None = None,
):
    from sqlalchemy.dialects.sqlite import insert  # pylint: disable=import-outside-toplevel

    _upsert_on_conflict_do_update(
        insert,
        connection,
        table,
        where_values=where_values,
        update_values=update_values,
        _race_hook=_race_hook,
    )


def _upsert_postgresql(
    connection: Connection,
    table: sa.Table,
    *,
    where_values: Sequence[tuple[sa.Column, Any]],
    update_values: Sequence[tuple[sa.Column, Any]],
    _race_hook: Callable[[Connection], None] | None = None,
):
    from sqlalchemy.dialects.postgresql import insert  # pylint: disable=import-outside-toplevel

    _upsert_on_conflict_do_update(
        insert,
        connection,
        table,
        where_values=where_values,
        update_values=update_values,
        _race_hook=_race_hook,
    )


def _upsert_on_conflict_do_update(
    insert: Any,
    connection: Connection,
    table: sa.Table,
    *,
    where_values: Sequence[tuple[sa.Column, Any]],
    update_values: Sequence[tuple[sa.Column, Any]],
    _race_hook: Callable[[Connection], None] | None = None,
):
    if _race_hook is not None:
        _race_hook(connection)

    insert_stmt = insert(table).values(
        **_column_value_kwargs(where_values),
        **_column_value_kwargs(update_values),
    )
    do_update_stmt = insert_stmt.on_conflict_do_update(
        index_elements=[c for (c, _) in where_values],
        index_where=_column_values_where_clause(where_values),
        set_=dict(update_values),
    )
    connection.execute(do_update_stmt)


def _upsert_mysql(
    connection: Connection,
    table: sa.Table,
    *,
    where_values: Sequence[tuple[sa.Column, Any]],
    update_values: Sequence[tuple[sa.Column, Any]],
    _race_hook: Callable[[Connection], None] | None = None,
):
    from sqlalchemy.dialects.mysql import insert  # pylint: disable=import-outside-toplevel

    if _race_hook is not None:
        _race_hook(connection)

    update_kwargs = _column_value_kwargs(update_values)
    insert_stmt = insert(table).values(
        **_column_value_kwargs(where_values),
        **update_kwargs,
    )
    on_duplicate_key_stmt = insert_stmt.on_duplicate_key_update(
        **update_kwargs,
    )
    connection.execute(on_duplicate_key_stmt)


def _upsert_default(
    connection: Connection,
    table: sa.Table,
    *,
    where_values: Sequence[tuple[sa.Column, Any]],
    update_values: Sequence[tuple[sa.Column, Any]],
    _race_hook: Callable[[Connection], None] | None = None,
):
    q = table.update()
    if where_values:
        q = q.where(_column_values_where_clause(where_values))
    res = connection.execute(q.values(*update_values))
    if res.rowcount > 0:
        return
    # the update hit 0 rows, so try inserting a new one

    if _race_hook is not None:
        _race_hook(connection)

    connection.execute(
        table.insert().values(
            **_column_value_kwargs(where_values),
            **_column_value_kwargs(update_values),
        )
    )


def _column_value_kwargs(values: Sequence[tuple[sa.Column, Any]]) -> dict[str, Any]:
    return {c.name: v for (c, v) in values}


def _column_values_where_clause(values: Sequence[tuple[sa.Column, Any]]) -> ColumnElement[bool]:
    return BooleanClauseList.and_(*[c == v for (c, v) in values])


def hash_columns(*args):
    def encode(x):
        if x is None:
            return b'\xf5'
        elif isinstance(x, str):
            return x.encode('utf-8')
        return str(x).encode('utf-8')

    return hashlib.sha1(b'\0'.join(map(encode, args))).hexdigest()
