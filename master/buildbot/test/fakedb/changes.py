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

import copy
import json

from twisted.internet import defer

from buildbot.test.fakedb.base import FakeDBComponent
from buildbot.test.fakedb.row import Row
from buildbot.util import datetime2epoch
from buildbot.util import epoch2datetime


class Change(Row):
    table = "changes"

    lists = ('files', 'uids')
    dicts = ('properties',)
    id_column = 'changeid'

    def __init__(self, changeid=None, author='frank', committer='steve',
                 comments='test change', branch='master', revision='abcd',
                 revlink='http://vc/abcd', when_timestamp=1200000, category='cat',
                 repository='repo', codebase='', project='proj', sourcestampid=92,
                 parent_changeids=None):
        super().__init__(changeid=changeid, author=author, committer=committer, comments=comments,
                         branch=branch, revision=revision, revlink=revlink,
                         when_timestamp=when_timestamp, category=category, repository=repository,
                         codebase=codebase, project=project, sourcestampid=sourcestampid,
                         parent_changeids=parent_changeids)


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
        super().__init__(changeid=changeid, property_name=property_name,
                         property_value=property_value)


class ChangeUser(Row):
    table = "change_users"

    foreignKeys = ('changeid',)
    required_columns = ('changeid',)

    def __init__(self, changeid=None, uid=None):
        super().__init__(changeid=changeid, uid=uid)


class FakeChangesComponent(FakeDBComponent):

    def setUp(self):
        self.changes = {}

    def insertTestData(self, rows):
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
                n, vs = row.property_name, row.property_value
                v, s = json.loads(vs)
                ch['properties'][n] = (v, s)

            elif isinstance(row, ChangeUser):
                ch = self.changes[row.changeid]
                ch['uids'].append(row.uid)

    # component methods

    @defer.inlineCallbacks
    def addChange(self, author=None, committer=None, files=None, comments=None, is_dir=None,
                  revision=None, when_timestamp=None, branch=None,
                  category=None, revlink='', properties=None, repository='',
                  codebase='', project='', uid=None):
        if properties is None:
            properties = {}

        if self.changes:
            changeid = max(list(self.changes)) + 1
        else:
            changeid = 500

        ssid = yield self.db.sourcestamps.findSourceStampId(
            revision=revision, branch=branch, repository=repository,
            codebase=codebase, project=project)

        parent_changeids = yield self.getParentChangeIds(branch, repository, project, codebase)

        self.changes[changeid] = ch = dict(
            changeid=changeid,
            parent_changeids=parent_changeids,
            author=author,
            committer=committer,
            comments=comments,
            revision=revision,
            when_timestamp=datetime2epoch(when_timestamp),
            branch=branch,
            category=category,
            revlink=revlink,
            repository=repository,
            project=project,
            codebase=codebase,
            uids=[],
            files=files,
            properties=properties,
            sourcestampid=ssid)

        if uid:
            ch['uids'].append(uid)

        return changeid

    def getLatestChangeid(self):
        if self.changes:
            return defer.succeed(max(list(self.changes)))
        return defer.succeed(None)

    def getParentChangeIds(self, branch, repository, project, codebase):
        if self.changes:
            for change in self.changes.values():
                if (change['branch'] == branch and
                        change['repository'] == repository and
                        change['project'] == project and
                        change['codebase'] == codebase):
                    return defer.succeed([change['changeid']])
        return defer.succeed([])

    def getChange(self, key, no_cache=False):
        try:
            row = self.changes[key]
        except KeyError:
            return defer.succeed(None)

        return defer.succeed(self._chdict(row))

    def getChangeUids(self, changeid):
        try:
            ch_uids = self.changes[changeid]['uids']
        except KeyError:
            ch_uids = []
        return defer.succeed(ch_uids)

    def getChanges(self, resultSpec=None):
        if resultSpec is not None and resultSpec.limit is not None:
            ids = sorted(self.changes.keys())
            chdicts = [self._chdict(self.changes[id]) for id in ids[-resultSpec.limit:]]
            return defer.succeed(chdicts)
        chdicts = [self._chdict(v) for v in self.changes.values()]
        return defer.succeed(chdicts)

    def getChangesCount(self):
        return defer.succeed(len(self.changes))

    def getChangesForBuild(self, buildid):
        # the algorithm is too complicated to be worth faked, better patch it
        # ad-hoc
        raise NotImplementedError(
            "Please patch in tests to return appropriate results")

    def getChangeFromSSid(self, ssid):
        chdicts = [self._chdict(v) for v in self.changes.values()
                   if v['sourcestampid'] == ssid]
        if chdicts:
            return defer.succeed(chdicts[0])
        return defer.succeed(None)

    def _chdict(self, row):
        chdict = row.copy()
        del chdict['uids']
        if chdict['parent_changeids'] is None:
            chdict['parent_changeids'] = []

        chdict['when_timestamp'] = epoch2datetime(chdict['when_timestamp'])
        return chdict

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
        row = dict(
            changeid=changeid,
            author=change.who,
            files=change.files,
            comments=change.comments,
            revision=change.revision,
            when_timestamp=change.when,
            branch=change.branch,
            category=change.category,
            revlink=change.revlink,
            properties=change.properties,
            repository=change.repository,
            codebase=change.codebase,
            project=change.project,
            uids=[])
        self.changes[changeid] = row
