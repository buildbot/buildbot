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
import itertools
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable
from typing import Literal
from typing import overload

import sqlalchemy as sa
from twisted.internet import defer

from buildbot.util import service
from buildbot.util import unicode2bytes
from buildbot.util.sautils import hash_columns

if TYPE_CHECKING:
    from collections.abc import Generator
    from collections.abc import Iterable
    from collections.abc import Iterator

    from buildbot.db.connector import DBConnector
    from buildbot.util.twisted import InlineCallbacksType


class DBConnectorComponent(service.AsyncService):
    # A fixed component of the DBConnector, handling one particular aspect of
    # the database.  Instances of subclasses are assigned to attributes of the
    # DBConnector object, so that they are available at e.g.,
    # C{master.db.model} or C{master.db.changes}.  This parent class takes care
    # of the necessary backlinks and other housekeeping.

    connector: DBConnector | None = None
    data2db: dict[str, str] = {}

    def __init__(self, connector: DBConnector) -> None:
        self.db = connector

        # set up caches
        for method in dir(self.__class__):
            o = getattr(self, method)
            if isinstance(o, CachedMethod):
                setattr(self, method, o.get_cached_method(self))

    _isCheckLengthNecessary: bool | None = None

    def checkLength(self, col: sa.Column[Any], value: str | None) -> None:
        if not self._isCheckLengthNecessary:
            if self.db.pool.engine.dialect.name == 'mysql':
                self._isCheckLengthNecessary = True
            else:
                # not necessary, so just stub out the method
                self.checkLength = lambda col, value: None  # type: ignore[method-assign]
                return

        assert col.type.length, f"column {col} does not have a length"  # type: ignore[attr-defined]
        if value and len(value) > col.type.length:  # type: ignore[attr-defined]
            raise RuntimeError(
                f"value for column {col} is greater than max of {col.type.length} "  # type: ignore[attr-defined]
                f"characters: {value}"
            )

    def ensureLength(self, col: sa.Column[Any], value: str | None) -> str | None:
        assert col.type.length, f"column {col} does not have a length"  # type: ignore[attr-defined]
        if value and len(value) > col.type.length:  # type: ignore[attr-defined]
            value = (
                value[: col.type.length // 2]  # type: ignore[attr-defined]
                + hashlib.sha1(unicode2bytes(value)).hexdigest()[: col.type.length // 2]  # type: ignore[attr-defined]
            )
        return value

    @overload
    def findSomethingId(
        self,
        tbl: sa.Table,
        whereclause: sa.sql.elements.ColumnElement[bool] | None,
        insert_values: dict[str, Any],
        _race_hook: Callable[[sa.engine.Connection], None] | None = ...,
        autoCreate: Literal[True] = ...,
    ) -> defer.Deferred[int]: ...

    @overload
    def findSomethingId(
        self,
        tbl: sa.Table,
        whereclause: sa.sql.elements.ColumnElement[bool] | None,
        insert_values: dict[str, Any],
        _race_hook: Callable[[sa.engine.Connection], None] | None = ...,
        autoCreate: bool = ...,
    ) -> defer.Deferred[int | None]: ...

    # returns a Deferred that returns a value
    @defer.inlineCallbacks  # type: ignore[misc]
    def findSomethingId(
        self,
        tbl: sa.Table,
        whereclause: sa.sql.elements.ColumnElement[bool] | None,
        insert_values: dict[str, Any],
        _race_hook: Callable[[sa.engine.Connection], None] | None = None,
        autoCreate: bool = True,
    ) -> InlineCallbacksType[int | None]:
        pair = yield self.findOrCreateSomethingId(
            tbl, whereclause, insert_values, _race_hook, autoCreate
        )
        return pair[0]

    def findOrCreateSomethingId(
        self,
        tbl: sa.Table,
        whereclause: sa.sql.elements.ColumnElement[bool] | None,
        insert_values: dict[str, Any],
        _race_hook: Callable[[sa.engine.Connection], None] | None = None,
        autoCreate: bool = True,
    ) -> defer.Deferred[tuple[int | None, bool]]:
        """
        Find a matching row and if one cannot be found optionally create it.
        Returns a deferred which resolves to the pair (id, found) where
        id is the primary key of the matching row and `found` is True if
        a match was found. `found` will be false if a new row was created.
        """

        def thd(conn: sa.engine.Connection, no_recurse: bool = False) -> tuple[int | None, bool]:
            # try to find the master
            q = sa.select(tbl.c.id)
            if whereclause is not None:
                q = q.where(whereclause)
            r = conn.execute(q)
            row = r.fetchone()
            r.close()

            # found it!
            if row:
                return row.id, True

            if not autoCreate:
                return None, False

            if _race_hook is not None:
                _race_hook(conn)

            try:
                r = conn.execute(tbl.insert(), [insert_values])
                conn.commit()
                return r.inserted_primary_key[0], False
            except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                conn.rollback()
                # try it all over again, in case there was an overlapping,
                # identical call, but only retry once.
                if no_recurse:
                    raise
                return thd(conn, no_recurse=True)

        return self.db.pool.do(thd)

    def hashColumns(self, *args: Any) -> str:
        return hash_columns(*args)

    def doBatch(self, batch: Iterable[Any], batch_n: int = 500) -> Generator[Any, None, None]:
        iterator: Iterator[Any] = iter(batch)
        while True:
            batch_items = list(itertools.islice(iterator, batch_n))
            if not batch_items:
                break
            yield batch_items


class CachedMethod:
    def __init__(self, cache_name: str, method: Callable[..., Any]) -> None:
        self.cache_name = cache_name
        self.method = method

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("CachedMethod must be accessed through an instance")

    def get_cached_method(self, component: DBConnectorComponent) -> Callable[..., Any]:
        meth = self.method

        meth_name = meth.__name__
        cache = component.db.master.caches.get_cache(  # type: ignore[union-attr]
            self.cache_name, lambda key: meth(component, key)
        )

        def wrap(key: Any, no_cache: int = 0) -> Any:
            if no_cache:
                return meth(component, key)
            return cache.get(key)

        wrap.__name__ = meth_name + " (wrapped)"
        wrap.__module__ = meth.__module__
        wrap.__doc__ = meth.__doc__
        wrap.cache = cache  # type: ignore[attr-defined]
        return wrap


def cached(cache_name: str) -> Callable[[Callable[..., Any]], CachedMethod]:
    return lambda method: CachedMethod(cache_name, method)
