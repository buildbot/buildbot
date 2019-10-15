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

from buildbot.test.fake import fakedb


class ReporterTestMixin:

    TEST_PROJECT = 'testProject'
    TEST_REPO = 'https://example.org/repo'
    TEST_REVISION = 'd34db33fd43db33f'
    TEST_CODEBASE = 'cbgerrit'
    TEST_CHANGE_ID = 'I5bdc2e500d00607af53f0fa4df661aada17f81fc'
    TEST_BUILDER_NAME = 'Builder0'
    TEST_PROPS = {
        'Stash_branch': 'refs/changes/34/1234/1',
        'project': TEST_PROJECT,
        'got_revision': TEST_REVISION,
        'revision': TEST_REVISION,
        'event.change.id': TEST_CHANGE_ID,
        'event.change.project': TEST_PROJECT,
        'branch': 'refs/pull/34/merge',
    }
    THING_URL = 'http://thing.example.com'

    def insertTestData(self, buildResults, finalResult, insertSS=True):
        self.db = self.master.db
        self.db.insertTestData([
            fakedb.Master(id=92),
            fakedb.Worker(id=13, name='wrk'),
            fakedb.Builder(id=79, name='Builder0'),
            fakedb.Builder(id=80, name='Builder1'),
            fakedb.Buildset(id=98, results=finalResult, reason="testReason1"),
            fakedb.Change(changeid=13, branch='master', revision='9283', author='me@foo',
                          repository=self.TEST_REPO, codebase=self.TEST_CODEBASE,
                          project='world-domination', sourcestampid=234),
        ])

        if insertSS:
            self.db.insertTestData([
                fakedb.BuildsetSourceStamp(buildsetid=98, sourcestampid=234),
                fakedb.SourceStamp(
                    id=234,
                    project=self.TEST_PROJECT,
                    revision=self.TEST_REVISION,
                    repository=self.TEST_REPO,
                    codebase=self.TEST_CODEBASE)
            ])

        for i, results in enumerate(buildResults):
            self.db.insertTestData([
                fakedb.BuildRequest(
                    id=11 + i, buildsetid=98, builderid=79 + i),
                fakedb.Build(id=20 + i, number=i, builderid=79 + i, buildrequestid=11 + i, workerid=13,
                             masterid=92, results=results, state_string="buildText"),
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
            ])
            for k, v in self.TEST_PROPS.items():
                self.db.insertTestData([
                    fakedb.BuildProperty(buildid=20 + i, name=k, value=v)
                ])
