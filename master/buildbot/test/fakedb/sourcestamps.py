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

import base64

from twisted.internet import defer

from buildbot.test.fakedb.base import FakeDBComponent
from buildbot.test.fakedb.row import Row
from buildbot.util import epoch2datetime


class Patch(Row):
    table = "patches"

    id_column = 'id'

    def __init__(self, id=None, patchlevel=0,
                 patch_base64='aGVsbG8sIHdvcmxk',  # 'hello, world',
                 patch_author=None, patch_comment=None, subdir=None):
        super().__init__(id=id, patchlevel=patchlevel, patch_base64=patch_base64,
                         patch_author=patch_author, patch_comment=patch_comment, subdir=subdir)


class SourceStamp(Row):
    table = "sourcestamps"

    id_column = 'id'
    hashedColumns = [('ss_hash', ('branch', 'revision', 'repository',
                                  'project', 'codebase', 'patchid',))]

    def __init__(self, id=None, branch='master', revision='abcd', patchid=None, repository='repo',
                 codebase='', project='proj', created_at=89834834, ss_hash=None):
        super().__init__(id=id, branch=branch, revision=revision, patchid=patchid,
                         repository=repository, codebase=codebase, project=project,
                         created_at=created_at, ss_hash=ss_hash)


class FakeSourceStampsComponent(FakeDBComponent):

    def setUp(self):
        self.sourcestamps = {}
        self.patches = {}

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, Patch):
                self.patches[row.id] = dict(
                    patch_level=row.patchlevel,
                    patch_body=base64.b64decode(row.patch_base64),
                    patch_author=row.patch_author,
                    patch_comment=row.patch_comment,
                    patch_subdir=row.subdir)

        for row in rows:
            if isinstance(row, SourceStamp):
                ss = self.sourcestamps[row.id] = row.values.copy()
                ss['created_at'] = epoch2datetime(ss['created_at'])
                del ss['ss_hash']
                del ss['id']

    # component methods

    def findSourceStampId(self, branch=None, revision=None, repository=None,
                          project=None, codebase=None,
                          patch_body=None, patch_level=None,
                          patch_author=None, patch_comment=None,
                          patch_subdir=None):
        d = self.findOrCreateId(
            branch, revision, repository, project, codebase, patch_body,
            patch_level, patch_author, patch_comment, patch_subdir)
        d.addCallback(lambda pair: pair[0])
        return d

    def findOrCreateId(self, branch=None, revision=None, repository=None,
                       project=None, codebase=None,
                       patch_body=None, patch_level=None,
                       patch_author=None, patch_comment=None,
                       patch_subdir=None):

        assert codebase is not None, "codebase cannot be None"
        assert project is not None, "project cannot be None"
        assert repository is not None, "repository cannot be None"

        if patch_body:
            patchid = len(self.patches) + 1
            while patchid in self.patches:
                patchid += 1
            self.patches[patchid] = dict(
                patch_level=patch_level,
                patch_body=patch_body,
                patch_subdir=patch_subdir,
                patch_author=patch_author,
                patch_comment=patch_comment
            )
        else:
            patchid = None

        new_ssdict = dict(branch=branch, revision=revision, codebase=codebase,
                          patchid=patchid, repository=repository, project=project,
                          created_at=epoch2datetime(self.reactor.seconds()))
        for id, ssdict in self.sourcestamps.items():
            keys = ['branch', 'revision', 'repository',
                    'codebase', 'project', 'patchid']
            if [ssdict[k] for k in keys] == [new_ssdict[k] for k in keys]:
                return defer.succeed((id, True))

        id = len(self.sourcestamps) + 100
        while id in self.sourcestamps:
            id += 1
        self.sourcestamps[id] = new_ssdict
        return defer.succeed((id, False))

    def getSourceStamp(self, key, no_cache=False):
        return defer.succeed(self._getSourceStamp_sync(key))

    def getSourceStamps(self):
        return defer.succeed([
            self._getSourceStamp_sync(ssid)
            for ssid in self.sourcestamps
        ])

    def _getSourceStamp_sync(self, ssid):
        if ssid in self.sourcestamps:
            ssdict = self.sourcestamps[ssid].copy()
            ssdict['ssid'] = ssid
            patchid = ssdict['patchid']
            if patchid:
                ssdict.update(self.patches[patchid])
                ssdict['patchid'] = patchid
            else:
                ssdict['patch_body'] = None
                ssdict['patch_level'] = None
                ssdict['patch_subdir'] = None
                ssdict['patch_author'] = None
                ssdict['patch_comment'] = None
            return ssdict
        else:
            return None

    @defer.inlineCallbacks
    def getSourceStampsForBuild(self, buildid):
        build = yield self.db.builds.getBuild(buildid)
        breq = yield self.db.buildrequests.getBuildRequest(build['buildrequestid'])
        bset = yield self.db.buildsets.getBuildset(breq['buildsetid'])

        results = []
        for ssid in bset['sourcestamps']:
            results.append((yield self.getSourceStamp(ssid)))
        return results
