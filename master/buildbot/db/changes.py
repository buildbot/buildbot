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

"""
Support for changes in the database
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING

import sqlalchemy as sa
from twisted.internet import defer
from twisted.python import deprecate
from twisted.python import log
from twisted.python import versions

from buildbot.db import base
from buildbot.util import datetime2epoch
from buildbot.util import epoch2datetime
from buildbot.warnings import warn_deprecated

if TYPE_CHECKING:
    import datetime
    from typing import Any
    from typing import Iterable
    from typing import Literal


@dataclass
class ChangeModel:
    changeid: int
    author: str
    committer: str | None
    comments: str
    branch: str | None
    revision: str | None
    revlink: str | None
    when_timestamp: datetime.datetime
    category: str | None
    sourcestampid: int
    parent_changeids: list[int] = field(default_factory=list)
    repository: str = ''
    codebase: str = ''
    project: str = ''

    files: list[str] = field(default_factory=list)
    properties: dict[str, tuple[Any, Literal["Change"]]] = field(default_factory=dict)

    # For backward compatibility
    def __getitem__(self, key: str):
        warn_deprecated(
            '4.1.0',
            (
                'ChangesConnectorComponent '
                'getChange, getChangesForBuild, getChangeFromSSid, and getChanges '
                'no longer return Change as dictionnaries. '
                'Usage of [] accessor is deprecated: please access the member directly'
            ),
        )

        if hasattr(self, key):
            return getattr(self, key)

        raise KeyError(key)


@deprecate.deprecated(versions.Version("buildbot", 4, 1, 0), ChangeModel)
class ChDict(ChangeModel):
    pass


class ChangesConnectorComponent(base.DBConnectorComponent):
    def getParentChangeIds(
        self, branch: str | None, repository: str, project: str, codebase: str
    ) -> defer.Deferred[list[int]]:
        def thd(conn) -> list[int]:
            changes_tbl = self.db.model.changes
            q = (
                sa.select(
                    changes_tbl.c.changeid,
                )
                .where(
                    changes_tbl.c.branch == branch,
                    changes_tbl.c.repository == repository,
                    changes_tbl.c.project == project,
                    changes_tbl.c.codebase == codebase,
                )
                .order_by(
                    sa.desc(changes_tbl.c.changeid),
                )
                .limit(1)
            )
            parent_id = conn.scalar(q)
            return [parent_id] if parent_id else []

        return self.db.pool.do(thd)

    @defer.inlineCallbacks
    def addChange(
        self,
        author: str | None = None,
        committer: str | None = None,
        files: list[str] | None = None,
        comments: str | None = None,
        is_dir: None = None,
        revision: str | None = None,
        when_timestamp: datetime.datetime | None = None,
        branch: str | None = None,
        category: str | None = None,
        revlink: str | None = '',
        properties: dict[str, tuple[Any, Literal['Change']]] | None = None,
        repository: str = '',
        codebase: str = '',
        project: str = '',
        uid: int | None = None,
        _test_changeid: int | None = None,
    ):
        assert project is not None, "project must be a string, not None"
        assert repository is not None, "repository must be a string, not None"

        if is_dir is not None:
            log.msg("WARNING: change source is providing deprecated value is_dir (ignored)")
        if when_timestamp is None:
            when_timestamp = epoch2datetime(self.master.reactor.seconds())

        if author is None:
            author = ''
        if comments is None:
            comments = ''
        if properties is None:
            properties = {}

        # verify that source is 'Change' for each property
        for pv in properties.values():
            assert pv[1] == 'Change', "properties must be qualified with source 'Change'"

        ch_tbl = self.db.model.changes

        self.checkLength(ch_tbl.c.author, author)
        self.checkLength(ch_tbl.c.committer, committer)
        self.checkLength(ch_tbl.c.branch, branch)
        self.checkLength(ch_tbl.c.revision, revision)
        self.checkLength(ch_tbl.c.revlink, revlink)
        self.checkLength(ch_tbl.c.category, category)
        self.checkLength(ch_tbl.c.repository, repository)
        self.checkLength(ch_tbl.c.project, project)

        # calculate the sourcestamp first, before adding it
        ssid = yield self.db.sourcestamps.findSourceStampId(
            revision=revision,
            branch=branch,
            repository=repository,
            codebase=codebase,
            project=project,
        )

        parent_changeids = yield self.getParentChangeIds(branch, repository, project, codebase)
        # Someday, changes will have multiple parents.
        # But for the moment, a Change can only have 1 parent
        parent_changeid = parent_changeids[0] if parent_changeids else None

        def thd(conn) -> int:
            # note that in a read-uncommitted database like SQLite this
            # transaction does not buy atomicity - other database users may
            # still come across a change without its files, properties,
            # etc.  That's OK, since we don't announce the change until it's
            # all in the database, but beware.

            transaction = conn.begin()

            insert_value = {
                "author": author,
                "committer": committer,
                "comments": comments,
                "branch": branch,
                "revision": revision,
                "revlink": revlink,
                "when_timestamp": datetime2epoch(when_timestamp),
                "category": category,
                "repository": repository,
                "codebase": codebase,
                "project": project,
                "sourcestampid": ssid,
                "parent_changeids": parent_changeid,
            }

            if _test_changeid is not None:
                insert_value['changeid'] = _test_changeid

            r = conn.execute(ch_tbl.insert(), [insert_value])
            changeid = r.inserted_primary_key[0]
            if files:
                tbl = self.db.model.change_files
                for f in files:
                    self.checkLength(tbl.c.filename, f)
                conn.execute(tbl.insert(), [{"changeid": changeid, "filename": f} for f in files])
            if properties:
                tbl = self.db.model.change_properties
                inserts = [
                    {"changeid": changeid, "property_name": k, "property_value": json.dumps(v)}
                    for k, v in properties.items()
                ]
                for i in inserts:
                    self.checkLength(tbl.c.property_name, i['property_name'])

                conn.execute(tbl.insert(), inserts)
            if uid:
                ins = self.db.model.change_users.insert()
                conn.execute(ins, {"changeid": changeid, "uid": uid})

            transaction.commit()

            return changeid

        return (yield self.db.pool.do(thd))

    @base.cached("chdicts")
    def getChange(self, changeid: int) -> defer.Deferred[ChangeModel | None]:
        assert changeid >= 0

        def thd(conn) -> ChangeModel | None:
            # get the row from the 'changes' table
            changes_tbl = self.db.model.changes
            q = changes_tbl.select().where(changes_tbl.c.changeid == changeid)
            rp = conn.execute(q)
            row = rp.fetchone()
            if not row:
                return None
            # and fetch the ancillary data (files, properties)
            return self._thd_model_from_row(conn, row)

        return self.db.pool.do(thd)

    @defer.inlineCallbacks
    def getChangesForBuild(self, buildid: int):
        assert buildid > 0

        gssfb = self.master.db.sourcestamps.getSourceStampsForBuild
        changes: list[ChangeModel] = []
        currentBuild = yield self.master.db.builds.getBuild(buildid)
        fromChanges: dict[str, ChangeModel | None] = {}
        toChanges: dict[str, ChangeModel] = {}
        ssBuild = yield gssfb(buildid)
        for ss in ssBuild:
            fromChanges[ss.codebase] = yield self.getChangeFromSSid(ss.ssid)

        # Get the last successful build on the same builder
        previousBuild = yield self.master.db.builds.getPrevSuccessfulBuild(
            currentBuild.builderid, currentBuild.number, ssBuild
        )
        if previousBuild:
            for ss in (yield gssfb(previousBuild.id)):
                ss_change = yield self.getChangeFromSSid(ss.ssid)
                if ss_change:
                    toChanges[ss.codebase] = ss_change

        # For each codebase, append changes until we match the parent
        for cb, change in fromChanges.items():
            if not change:
                continue

            to_cb_change = toChanges.get(cb)
            to_cb_changeid = to_cb_change.changeid if to_cb_change is not None else None
            if to_cb_changeid is not None and to_cb_changeid == change.changeid:
                continue

            changes.append(change)
            while change.parent_changeids and to_cb_changeid not in change.parent_changeids:
                # For the moment, a Change only have 1 parent.
                change = yield self.master.db.changes.getChange(change.parent_changeids[0])
                # http://trac.buildbot.net/ticket/3461 sometimes,
                # parent_changeids could be corrupted
                if change is None:
                    break
                changes.append(change)

        return changes

    def getChangeFromSSid(self, sourcestampid: int) -> defer.Deferred[ChangeModel | None]:
        assert sourcestampid >= 0

        def thd(conn) -> ChangeModel | None:
            # get the row from the 'changes' table
            changes_tbl = self.db.model.changes
            q = changes_tbl.select().where(changes_tbl.c.sourcestampid == sourcestampid)
            # if there are multiple changes for this ssid, get the most recent one
            q = q.order_by(changes_tbl.c.changeid.desc())
            q = q.limit(1)
            rp = conn.execute(q)
            row = rp.fetchone()
            if not row:
                return None
            # and fetch the ancillary data (files, properties)
            return self._thd_model_from_row(conn, row)

        return self.db.pool.do(thd)

    def getChangeUids(self, changeid: int) -> defer.Deferred[list[int]]:
        assert changeid >= 0

        def thd(conn) -> list[int]:
            cu_tbl = self.db.model.change_users
            q = cu_tbl.select().where(cu_tbl.c.changeid == changeid)
            res = conn.execute(q)
            rows = res.fetchall()
            row_uids = [row.uid for row in rows]
            return row_uids

        return self.db.pool.do(thd)

    def _getDataFromRow(self, row):
        return row.changeid

    @defer.inlineCallbacks
    def getChanges(self, resultSpec=None):
        def thd(conn) -> Iterable[int]:
            # get the changeids from the 'changes' table
            changes_tbl = self.db.model.changes

            if resultSpec is not None:
                q = changes_tbl.select()
                return reversed(resultSpec.thd_execute(conn, q, self._getDataFromRow))

            q = sa.select(changes_tbl.c.changeid)
            rp = conn.execute(q)
            changeids = [self._getDataFromRow(row) for row in rp]
            rp.close()
            return list(changeids)

        changeids = yield self.db.pool.do(thd)

        changes = yield defer.gatherResults(
            [self.getChange(changeid) for changeid in changeids], consumeErrors=True
        )

        return changes

    def getChangesCount(self) -> defer.Deferred[int]:
        def thd(conn) -> int:
            changes_tbl = self.db.model.changes
            q = sa.select(sa.func.count()).select_from(changes_tbl)
            rp = conn.execute(q)
            r = 0
            for row in rp:
                r = row[0]
            rp.close()
            return int(r)

        return self.db.pool.do(thd)

    def getLatestChangeid(self) -> defer.Deferred[int | None]:
        def thd(conn) -> int:
            changes_tbl = self.db.model.changes
            q = (
                sa.select(
                    changes_tbl.c.changeid,
                )
                .order_by(
                    sa.desc(changes_tbl.c.changeid),
                )
                .limit(1)
            )
            return conn.scalar(q)

        return self.db.pool.do(thd)

    # utility methods

    @defer.inlineCallbacks
    def pruneChanges(self, changeHorizon: int):
        """
        Called periodically by DBConnector, this method deletes changes older
        than C{changeHorizon}.
        """

        if not changeHorizon:
            return

        def thd(conn) -> None:
            changes_tbl = self.db.model.changes

            # First, get the list of changes to delete.  This could be written
            # as a subquery but then that subquery would be run for every
            # table, which is very inefficient; also, MySQL's subquery support
            # leaves much to be desired, and doesn't support this particular
            # form.
            q = (
                sa.select(
                    changes_tbl.c.changeid,
                )
                .order_by(
                    sa.desc(changes_tbl.c.changeid),
                )
                .offset(changeHorizon)
            )
            res = conn.execute(q)
            ids_to_delete = [r.changeid for r in res]

            # and delete from all relevant tables, in dependency order
            for table_name in (
                'scheduler_changes',
                'change_files',
                'change_properties',
                'changes',
                'change_users',
            ):
                remaining = ids_to_delete[:]
                while remaining:
                    batch = remaining[:100]
                    remaining = remaining[100:]
                    table = self.db.model.metadata.tables[table_name]
                    conn.execute(table.delete().where(table.c.changeid.in_(batch)))

        yield self.db.pool.do_with_transaction(thd)

    def _thd_model_from_row(self, conn, ch_row) -> ChangeModel:
        # This method must be run in a db.pool thread
        change_files_tbl = self.db.model.change_files
        change_properties_tbl = self.db.model.change_properties

        if ch_row.parent_changeids:
            parent_changeids = [ch_row.parent_changeids]
        else:
            parent_changeids = []

        chdict = ChangeModel(
            changeid=ch_row.changeid,
            parent_changeids=parent_changeids,
            author=ch_row.author,
            committer=ch_row.committer,
            comments=ch_row.comments,
            revision=ch_row.revision,
            when_timestamp=epoch2datetime(ch_row.when_timestamp),
            branch=ch_row.branch,
            category=ch_row.category,
            revlink=ch_row.revlink,
            repository=ch_row.repository,
            codebase=ch_row.codebase,
            project=ch_row.project,
            sourcestampid=int(ch_row.sourcestampid),
        )

        query = change_files_tbl.select().where(change_files_tbl.c.changeid == ch_row.changeid)
        rows = conn.execute(query)
        chdict.files.extend(r.filename for r in rows)

        # and properties must be given without a source, so strip that, but
        # be flexible in case users have used a development version where the
        # change properties were recorded incorrectly
        def split_vs(vs) -> tuple[Any, Literal["Change"]]:
            try:
                v, s = vs
                if s != "Change":
                    v, s = vs, "Change"
            except (ValueError, TypeError):
                v, s = vs, "Change"
            return v, s

        query = change_properties_tbl.select().where(
            change_properties_tbl.c.changeid == ch_row.changeid
        )
        rows = conn.execute(query)
        for r in rows:
            try:
                v, s = split_vs(json.loads(r.property_value))
                chdict.properties[r.property_name] = (v, s)
            except ValueError:
                pass

        return chdict
