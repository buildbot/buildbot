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

from twisted.internet import defer

from buildbot.process.results import SUCCESS
from buildbot.test import fakedb


class ReporterTestMixin:

    def setup_reporter_test(self):
        self.reporter_test_project = 'testProject'
        self.reporter_test_repo = 'https://example.org/repo'
        self.reporter_test_revision = 'd34db33fd43db33f'
        self.reporter_test_branch = "master"
        self.reporter_test_codebase = 'cbgerrit'
        self.reporter_test_change_id = 'I5bdc2e500d00607af53f0fa4df661aada17f81fc'
        self.reporter_test_builder_name = 'Builder0'
        self.reporter_test_props = {
            'Stash_branch': 'refs/changes/34/1234/1',
            'project': self.reporter_test_project,
            'got_revision': self.reporter_test_revision,
            'revision': self.reporter_test_revision,
            'event.change.id': self.reporter_test_change_id,
            'event.change.project': self.reporter_test_project,
            'branch': 'refs/pull/34/merge',
        }
        self.reporter_test_thing_url = 'http://thing.example.com'

    @defer.inlineCallbacks
    def insert_build(self, results, insert_ss=True, parent_plan=False, insert_patch=False):
        self.insertTestData([results], results, insertSS=insert_ss,
                            parentPlan=parent_plan, insert_patch=insert_patch)
        build = yield self.master.data.get(("builds", 20))
        return build

    @defer.inlineCallbacks
    def insert_build_finished(self, results=SUCCESS, **kwargs):
        return (yield self.insert_build(results=results, **kwargs))

    @defer.inlineCallbacks
    def insert_build_new(self, **kwargs):
        return (yield self.insert_build(results=None, **kwargs))

    @defer.inlineCallbacks
    def insert_buildrequest_new(self, insert_patch=False, **kwargs):
        self.db = self.master.db
        self.db.insertTestData([
            fakedb.Master(id=92),
            fakedb.Worker(id=13, name='wrk'),
            fakedb.Builder(id=79, name='Builder0'),
            fakedb.Builder(id=80, name='Builder1'),
            fakedb.Buildset(id=98, results=None, reason="testReason1",
                            parent_buildid=None),
            fakedb.BuildRequest(id=11, buildsetid=98, builderid=79)
        ])

        patchid = 99 if insert_patch else None

        self.db.insertTestData([
            fakedb.BuildsetSourceStamp(buildsetid=98, sourcestampid=234),
            fakedb.SourceStamp(
                id=234,
                branch=self.reporter_test_branch,
                project=self.reporter_test_project,
                revision=self.reporter_test_revision,
                repository=self.reporter_test_repo,
                codebase=self.reporter_test_codebase,
                patchid=patchid),
            fakedb.Patch(id=99, patch_base64='aGVsbG8sIHdvcmxk',
                         patch_author='him@foo', patch_comment='foo', subdir='/foo',
                         patchlevel=3)
        ])
        request = yield self.master.data.get(("buildrequests", 11))
        return request

    def insertTestData(self, buildResults, finalResult, insertSS=True,
                       parentPlan=False, insert_patch=False):
        self.db = self.master.db
        self.db.insertTestData([
            fakedb.Master(id=92),
            fakedb.Worker(id=13, name='wrk'),
            fakedb.Builder(id=79, name='Builder0'),
            fakedb.Builder(id=80, name='Builder1'),
            fakedb.Buildset(id=98, results=finalResult, reason="testReason1",
                            parent_buildid=19 if parentPlan else None),
            fakedb.Change(changeid=13, branch=self.reporter_test_branch, revision='9283',
                          author='me@foo', repository=self.reporter_test_repo,
                          codebase=self.reporter_test_codebase, project='world-domination',
                          sourcestampid=234),
        ])

        if parentPlan:
            self.db.insertTestData([
                fakedb.Worker(id=12, name='wrk_parent'),
                fakedb.Builder(id=78, name='Builder_parent'),
                fakedb.Buildset(id=97, results=finalResult, reason="testReason0"),
                fakedb.BuildRequest(id=10, buildsetid=98, builderid=78),
                fakedb.Build(id=19, number=1, builderid=78, buildrequestid=10, workerid=12,
                             masterid=92, results=finalResult, state_string="buildText"),
            ])

        if insertSS:
            patchid = 99 if insert_patch else None

            self.db.insertTestData([
                fakedb.BuildsetSourceStamp(buildsetid=98, sourcestampid=234),
                fakedb.SourceStamp(
                    id=234,
                    branch=self.reporter_test_branch,
                    project=self.reporter_test_project,
                    revision=self.reporter_test_revision,
                    repository=self.reporter_test_repo,
                    codebase=self.reporter_test_codebase,
                    patchid=patchid),
                fakedb.Patch(id=99, patch_base64='aGVsbG8sIHdvcmxk',
                             patch_author='him@foo', patch_comment='foo', subdir='/foo',
                             patchlevel=3),
            ])

        for i, results in enumerate(buildResults):
            started_at = 10000001
            complete_at = None if results is None else 10000005
            self.db.insertTestData([
                fakedb.BuildRequest(
                    id=11 + i, buildsetid=98, builderid=79 + i),
                fakedb.Build(id=20 + i, number=i, builderid=79 + i, buildrequestid=11 + i,
                             workerid=13, masterid=92, results=results, state_string="buildText",
                             started_at=started_at, complete_at=complete_at),
                fakedb.Step(id=50 + i, buildid=20 + i, number=5, name='make'),
                fakedb.Log(id=60 + i, stepid=50 + i, name='stdio', slug='stdio', type='s',
                           num_lines=7),
                fakedb.LogChunk(logid=60 + i, first_line=0, last_line=1, compressed=0,
                                content='Unicode log with non-ascii (\u00E5\u00E4\u00F6).'),
                fakedb.BuildProperty(
                    buildid=20 + i, name="workername", value="wrk"),
                fakedb.BuildProperty(
                    buildid=20 + i, name="reason", value="because"),
                fakedb.BuildProperty(
                    buildid=20 + i, name="buildername", value="Builder0"),
                fakedb.BuildProperty(
                    buildid=20 + i, name="buildnumber", value=f"{i}"),
                fakedb.BuildProperty(buildid=20 + i, name="scheduler", value="checkin"),
            ])
            for k, v in self.reporter_test_props.items():
                self.db.insertTestData([
                    fakedb.BuildProperty(buildid=20 + i, name=k, value=v)
                ])

        self.setup_fake_get_changes_for_build()

    def setup_fake_get_changes_for_build(self, has_change=True):
        @defer.inlineCallbacks
        def getChangesForBuild(buildid):
            if not has_change:
                return []

            assert buildid == 20
            ch = yield self.master.db.changes.getChange(13)
            return [ch]

        self.master.db.changes.getChangesForBuild = getChangesForBuild
