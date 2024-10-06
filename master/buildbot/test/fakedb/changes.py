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

import copy
import json
from typing import TYPE_CHECKING

from twisted.internet import defer

from buildbot.db.changes import ChangeModel
from buildbot.test.fakedb.base import FakeDBComponent
from buildbot.test.fakedb.row import Row
from buildbot.util import datetime2epoch
from buildbot.util import epoch2datetime

if TYPE_CHECKING:
    import datetime
    from typing import Any
    from typing import Iterable
    from typing import Literal


class Change(Row):
    table = "changes"

    lists = ('files', 'uids')
    dicts = ('properties',)
    id_column = 'changeid'

    def __init__(
        self,
        changeid=None,
        author='frank',
        committer='steve',
        comments='test change',
        branch='master',
        revision='abcd',
        revlink='http://vc/abcd',
        when_timestamp=1200000,
        category='cat',
        repository='repo',
        codebase='',
        project='proj',
        sourcestampid=92,
        parent_changeids=None,
    ):
        super().__init__(
            changeid=changeid,
            author=author,
            committer=committer,
            comments=comments,
            branch=branch,
            revision=revision,
            revlink=revlink,
            when_timestamp=when_timestamp,
            category=category,
            repository=repository,
            codebase=codebase,
            project=project,
            sourcestampid=sourcestampid,
            parent_changeids=parent_changeids,
        )


class ChangeFile(Row):
    table = "change_files"

    foreignKeys = ('changeid',)
    required_columns = ('changeid',)

    def __init__(self, changeid=None, filename=None):
        super().__init__(changeid=changeid, filename=filename)


class ChangeProperty(Row):
    table = "change_properties"

    foreignKeys = ('changeid',)
    required_columns = ('changeid',)

    def __init__(self, changeid=None, property_name=None, property_value=None):
        super().__init__(
            changeid=changeid, property_name=property_name, property_value=property_value
        )


class ChangeUser(Row):
    table = "change_users"

    foreignKeys = ('changeid',)
    required_columns = ('changeid',)

    def __init__(self, changeid=None, uid=None):
        super().__init__(changeid=changeid, uid=uid)


class FakeChangesComponent(FakeDBComponent):
    def setUp(self):
        self.changes = {}

    def insert_test_data(self, rows):
        for row in rows:
            if isinstance(row, Change):
                # copy this since we'll be modifying it (e.g., adding files)
                ch = self.changes[row.changeid] = copy.deepcopy(row.values)
                ch['files'] = []
                ch['properties'] = {}
                ch['uids'] = []

            elif isinstance(row, ChangeFile):
                ch = self.changes[row.changeid]
                ch['files'].append(row.filename)

            elif isinstance(row, ChangeProperty):
                ch = self.changes[row.changeid]
                n = row.property_name
                vs = row.property_value
                v, s = json.loads(vs)
                ch['properties'][n] = (v, s)

            elif isinstance(row, ChangeUser):
                ch = self.changes[row.changeid]
                ch['uids'].append(row.uid)

    # component methods

    async def addChange(
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
    ):
        if properties is None:
            properties = {}

        if self.changes:
            changeid = max(list(self.changes)) + 1
        else:
            changeid = 500

        ssid = await self.db.sourcestamps.findSourceStampId(
            revision=revision,
            branch=branch,
            repository=repository,
            codebase=codebase,
            project=project,
        )

        parent_changeids = await self.getParentChangeIds(branch, repository, project, codebase)

        self.changes[changeid] = ch = {
            "changeid": changeid,
            "parent_changeids": parent_changeids,
            "author": author,
            "committer": committer,
            "comments": comments,
            "revision": revision,
            "when_timestamp": datetime2epoch(when_timestamp),
            "branch": branch,
            "category": category,
            "revlink": revlink,
            "repository": repository,
            "project": project,
            "codebase": codebase,
            "uids": [],
            "files": files,
            "properties": properties,
            "sourcestampid": ssid,
        }

        if uid:
            ch['uids'].append(uid)

        return changeid

    def getLatestChangeid(self) -> defer.Deferred[int | None]:
        if self.changes:
            return defer.succeed(max(list(self.changes)))
        return defer.succeed(None)

    def getParentChangeIds(
        self, branch: str | None, repository: str, project: str, codebase: str
    ) -> defer.Deferred[list[int]]:
        if self.changes:
            for change in self.changes.values():
                if (
                    change['branch'] == branch
                    and change['repository'] == repository
                    and change['project'] == project
                    and change['codebase'] == codebase
                ):
                    return defer.succeed([change['changeid']])
        return defer.succeed([])

    def getChange(self, key: int, no_cache: bool = False) -> defer.Deferred[ChangeModel | None]:
        try:
            row = self.changes[key]
        except KeyError:
            return defer.succeed(None)

        return defer.succeed(self._model_from_row(row))

    def getChangeUids(self, changeid: int) -> defer.Deferred[list[int]]:
        try:
            ch_uids = self.changes[changeid]['uids']
        except KeyError:
            ch_uids = []
        return defer.succeed(ch_uids)

    def getChanges(self, resultSpec=None) -> defer.Deferred[Iterable[int]]:
        if resultSpec is not None and resultSpec.limit is not None:
            ids = sorted(self.changes.keys())
            chdicts = [self._model_from_row(self.changes[id]) for id in ids[-resultSpec.limit :]]
            return defer.succeed(chdicts)
        chdicts = [self._model_from_row(v) for v in self.changes.values()]
        return defer.succeed(chdicts)

    def getChangesCount(self) -> defer.Deferred[int]:
        return defer.succeed(len(self.changes))

    def getChangesForBuild(self, buildid: int):
        # the algorithm is too complicated to be worth faked, better patch it
        # ad-hoc
        raise NotImplementedError("Please patch in tests to return appropriate results")

    def getChangeFromSSid(self, ssid: int) -> defer.Deferred[ChangeModel | None]:
        chdicts = [
            self._model_from_row(v) for v in self.changes.values() if v['sourcestampid'] == ssid
        ]
        if chdicts:
            return defer.succeed(chdicts[0])
        return defer.succeed(None)

    def _model_from_row(self, row):
        model = ChangeModel(
            changeid=row['changeid'],
            author=row['author'],
            committer=row['committer'],
            comments=row['comments'],
            branch=row['branch'],
            revision=row['revision'],
            revlink=row['revlink'],
            when_timestamp=epoch2datetime(row['when_timestamp']),
            category=row['category'],
            sourcestampid=row['sourcestampid'],
            repository=row['repository'],
            codebase=row['codebase'],
            project=row['project'],
            files=row['files'],
            properties=row['properties'],
        )
        if row['parent_changeids'] is not None:
            model.parent_changeids = row['parent_changeids']

        return model

    # assertions

    def assertChange(self, changeid, row):
        row_only = self.changes[changeid].copy()
        del row_only['files']
        del row_only['properties']
        del row_only['uids']
        if not row_only['parent_changeids']:
            # Convert [] to None
            # None is the value stored in the DB.
            # We need this kind of conversion, because for the moment we only support
            # 1 parent for a change.
            # When we will support multiple parent for change, then we will have a
            # table parent_changes with at least 2 col: "changeid", "parent_changeid"
            # And the col 'parent_changeids' of the table changes will be
            # dropped
            row_only['parent_changeids'] = None
        self.t.assertEqual(row_only, row.values)

    def assertChangeUsers(self, changeid, expectedUids):
        self.t.assertEqual(self.changes[changeid]['uids'], expectedUids)

    # fake methods

    def fakeAddChangeInstance(self, change):
        if not hasattr(change, 'number') or not change.number:
            if self.changes:
                changeid = max(list(self.changes)) + 1
            else:
                changeid = 500
        else:
            changeid = change.number

        # make a row from the change
        row = {
            "changeid": changeid,
            "author": change.who,
            "files": change.files,
            "comments": change.comments,
            "revision": change.revision,
            "when_timestamp": change.when,
            "branch": change.branch,
            "category": change.category,
            "revlink": change.revlink,
            "properties": change.properties,
            "repository": change.repository,
            "codebase": change.codebase,
            "project": change.project,
            "uids": [],
        }
        self.changes[changeid] = row
