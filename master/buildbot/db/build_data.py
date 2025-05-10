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

from dataclasses import dataclass
from typing import TYPE_CHECKING

import sqlalchemy as sa
from twisted.python import deprecate
from twisted.python import versions

from buildbot.db import NULL
from buildbot.db import base
from buildbot.warnings import warn_deprecated

if TYPE_CHECKING:
    from twisted.internet import defer


@dataclass
class BuildDataModel:
    buildid: int
    name: str
    length: int
    source: str
    value: bytes | None

    # For backward compatibility
    def __getitem__(self, key: str):
        warn_deprecated(
            '4.1.0',
            (
                'BuildDataConnectorComponent getBuildData, getBuildDataNoValue, and getAllBuildDataNoValues '
                'no longer return BuildData as dictionnaries. '
                'Usage of [] accessor is deprecated: please access the member directly'
            ),
        )

        if hasattr(self, key):
            return getattr(self, key)

        raise KeyError(key)


@deprecate.deprecated(versions.Version("buildbot", 4, 1, 0), BuildDataModel)
class BuildDataDict(BuildDataModel):
    pass


class BuildDataConnectorComponent(base.DBConnectorComponent):
    def _insert_race_hook(self, conn):
        # called so tests can simulate a race condition during insertion
        pass

    def setBuildData(
        self, buildid: int, name: str, value: bytes, source: str
    ) -> defer.Deferred[None]:
        def thd(conn) -> None:
            build_data_table = self.db.model.build_data

            retry = True
            while retry:
                try:
                    self.db.upsert(
                        conn,
                        build_data_table,
                        where_values=(
                            (build_data_table.c.buildid, buildid),
                            (build_data_table.c.name, name),
                        ),
                        update_values=(
                            (build_data_table.c.value, value),
                            (build_data_table.c.length, len(value)),
                            (build_data_table.c.source, source),
                        ),
                        _race_hook=self._insert_race_hook,
                    )
                    conn.commit()
                except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                    # there's been a competing insert, retry
                    conn.rollback()
                    if not retry:
                        raise
                finally:
                    retry = False

        return self.db.pool.do(thd)

    def getBuildData(self, buildid: int, name: str) -> defer.Deferred[BuildDataModel | None]:
        def thd(conn) -> BuildDataModel | None:
            build_data_table = self.db.model.build_data

            q = build_data_table.select().where(
                (build_data_table.c.buildid == buildid) & (build_data_table.c.name == name)
            )
            res = conn.execute(q)
            row = res.fetchone()
            if not row:
                return None
            return self._model_from_row(row, value=row.value)

        return self.db.pool.do(thd)

    def getBuildDataNoValue(self, buildid: int, name: str) -> defer.Deferred[BuildDataModel | None]:
        def thd(conn) -> BuildDataModel | None:
            build_data_table = self.db.model.build_data

            q = sa.select(
                build_data_table.c.buildid,
                build_data_table.c.name,
                build_data_table.c.length,
                build_data_table.c.source,
            )
            q = q.where((build_data_table.c.buildid == buildid) & (build_data_table.c.name == name))
            res = conn.execute(q)
            row = res.fetchone()
            if not row:
                return None
            return self._model_from_row(row, value=None)

        return self.db.pool.do(thd)

    def getAllBuildDataNoValues(self, buildid: int) -> defer.Deferred[list[BuildDataModel]]:
        def thd(conn) -> list[BuildDataModel]:
            build_data_table = self.db.model.build_data

            q = sa.select(
                build_data_table.c.buildid,
                build_data_table.c.name,
                build_data_table.c.length,
                build_data_table.c.source,
            )
            q = q.where(build_data_table.c.buildid == buildid)

            return [self._model_from_row(row, value=None) for row in conn.execute(q).fetchall()]

        return self.db.pool.do(thd)

    def deleteOldBuildData(self, older_than_timestamp: int) -> defer.Deferred[int]:
        build_data = self.db.model.build_data
        builds = self.db.model.builds

        def count_build_datum(conn) -> int:
            res = conn.execute(sa.select(sa.func.count(build_data.c.id)))
            count = res.fetchone()[0]
            res.close()
            return count

        def thd(conn) -> int:
            count_before = count_build_datum(conn)

            if self.db._engine.dialect.name == 'sqlite':
                # sqlite does not support delete with a join, so for this case we use a subquery,
                # which is much slower

                q = sa.select(builds.c.id)
                q = q.where(
                    (builds.c.complete_at >= older_than_timestamp) | (builds.c.complete_at == NULL)
                )
                # n.b.: in sqlite we need to filter on `>= older_than_timestamp` because of the following `NOT IN` clause...

                q = build_data.delete().where(build_data.c.buildid.notin_(q))
            else:
                q = build_data.delete()
                q = q.where(builds.c.id == build_data.c.buildid)
                q = q.where(builds.c.complete_at < older_than_timestamp)
            res = conn.execute(q)
            conn.commit()
            res.close()

            count_after = count_build_datum(conn)
            return count_before - count_after

        return self.db.pool.do(thd)

    def _model_from_row(self, row, value: bytes | None):
        return BuildDataModel(
            buildid=row.buildid,
            name=row.name,
            length=row.length,
            source=row.source,
            value=value,
        )
