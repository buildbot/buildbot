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

from twisted.internet import defer

from buildbot.reporters import utils
from buildbot.test.fake import fakedb


class NotifierTestMixin(object):
    @defer.inlineCallbacks
    def setupBuildResults(self, results, wantPreviousBuild=False):
        # this testsuite always goes through setupBuildResults so that
        # the data is sure to be the real data schema known coming from data
        # api

        self.db = self.master.db
        self.db.insertTestData([
            fakedb.Master(id=92),
            fakedb.Worker(id=13, name='wrk'),
            fakedb.Buildset(id=98, results=results, reason="testReason1"),
            fakedb.Builder(id=80, name='Builder1'),
            fakedb.BuildRequest(id=11, buildsetid=98, builderid=80),
            fakedb.Build(id=20, number=0, builderid=80, buildrequestid=11, workerid=13,
                         masterid=92, results=results),
            fakedb.Step(id=50, buildid=20, number=5, name='make'),
            fakedb.BuildsetSourceStamp(buildsetid=98, sourcestampid=234),
            fakedb.SourceStamp(id=234, patchid=99),
            fakedb.Change(changeid=13, branch=u'trunk', revision=u'9283', author='me@foo',
                          repository=u'svn://...', codebase=u'cbsvn',
                          project=u'world-domination', sourcestampid=234),
            fakedb.Log(id=60, stepid=50, name='stdio', slug='stdio', type='s',
                       num_lines=7),
            fakedb.LogChunk(logid=60, first_line=0, last_line=1, compressed=0,
                            content=u'Unicode log with non-ascii (\u00E5\u00E4\u00F6).'),
            fakedb.Patch(id=99, patch_base64='aGVsbG8sIHdvcmxk',
                         patch_author='him@foo', patch_comment='foo', subdir='/foo',
                         patchlevel=3),
        ])
        for _id in (20,):
            self.db.insertTestData([
                fakedb.BuildProperty(
                    buildid=_id, name="workername", value="wrk"),
                fakedb.BuildProperty(
                    buildid=_id, name="reason", value="because"),
                fakedb.BuildProperty(
                    buildid=_id, name="scheduler", value="checkin"),
                fakedb.BuildProperty(
                    buildid=_id, name="branch", value="master"),
            ])
        res = yield utils.getDetailsForBuildset(self.master, 98, wantProperties=True,
                                                wantPreviousBuild=wantPreviousBuild)
        builds = res['builds']
        buildset = res['buildset']

        @defer.inlineCallbacks
        def getChangesForBuild(buildid):
            assert buildid == 20
            ch = yield self.master.db.changes.getChange(13)
            defer.returnValue([ch])

        self.master.db.changes.getChangesForBuild = getChangesForBuild
        defer.returnValue((buildset, builds))
