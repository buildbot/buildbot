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

from typing import TYPE_CHECKING
from typing import Generator

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.db import sourcestamps
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.util import epoch2datetime

if TYPE_CHECKING:
    from buildbot.test.fakedb import FakeDBConnector

CREATED_AT = 927845299


def sourceStampKey(sourceStamp: sourcestamps.SourceStampModel):
    return (sourceStamp.repository, sourceStamp.branch, sourceStamp.created_at)


class Tests(TestReactorMixin, unittest.TestCase):
    db: FakeDBConnector

    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantDb=True)
        self.db = self.master.db

    @defer.inlineCallbacks
    def test_findSourceStampId_simple(self):
        self.reactor.advance(CREATED_AT)
        ssid = yield self.db.sourcestamps.findSourceStampId(
            branch='production',
            revision='abdef',
            repository='test://repo',
            codebase='cb',
            project='stamper',
        )
        ssdict = yield self.db.sourcestamps.getSourceStamp(ssid)
        self.assertEqual(
            ssdict,
            sourcestamps.SourceStampModel(
                branch='production',
                codebase='cb',
                patch=None,
                project='stamper',
                repository='test://repo',
                revision='abdef',
                ssid=ssid,
                created_at=epoch2datetime(CREATED_AT),
            ),
        )

    @defer.inlineCallbacks
    def test_findSourceStampId_simple_unique(self):
        ssid1 = yield self.db.sourcestamps.findSourceStampId(
            branch='production',
            revision='abdef',
            repository='test://repo',
            codebase='cb',
            project='stamper',
        )
        ssid2 = yield self.db.sourcestamps.findSourceStampId(
            branch='production',
            revision='xxxxx',  # different revision
            repository='test://repo',
            codebase='cb',
            project='stamper',
        )
        ssid3 = yield self.db.sourcestamps.findSourceStampId(  # same as ssid1
            branch='production',
            revision='abdef',
            repository='test://repo',
            codebase='cb',
            project='stamper',
        )
        self.assertEqual(ssid1, ssid3)
        self.assertNotEqual(ssid1, ssid2)

    @defer.inlineCallbacks
    def test_findSourceStampId_simple_unique_patch(self):
        ssid1 = yield self.db.sourcestamps.findSourceStampId(
            branch='production',
            revision='abdef',
            repository='test://repo',
            codebase='cb',
            project='stamper',
            patch_body=b'++ --',
            patch_level=1,
            patch_author='me',
            patch_comment='hi',
            patch_subdir='.',
        )
        ssid2 = yield self.db.sourcestamps.findSourceStampId(
            branch='production',
            revision='abdef',
            repository='test://repo',
            codebase='cb',
            project='stamper',
            patch_body=b'++ --',
            patch_level=1,
            patch_author='me',
            patch_comment='hi',
            patch_subdir='.',
        )
        # even with the same patch contents, we get different ids
        self.assertNotEqual(ssid1, ssid2)

    @defer.inlineCallbacks
    def test_findSourceStampId_patch(self):
        self.reactor.advance(CREATED_AT)
        ssid = yield self.db.sourcestamps.findSourceStampId(
            branch='production',
            revision='abdef',
            repository='test://repo',
            codebase='cb',
            project='stamper',
            patch_body=b'my patch',
            patch_level=3,
            patch_subdir='master/',
            patch_author='me',
            patch_comment="comment",
        )
        ssdict = yield self.db.sourcestamps.getSourceStamp(ssid)
        self.assertEqual(
            ssdict,
            sourcestamps.SourceStampModel(
                branch='production',
                codebase='cb',
                project='stamper',
                repository='test://repo',
                revision='abdef',
                created_at=epoch2datetime(CREATED_AT),
                ssid=ssid,
                patch=sourcestamps.PatchModel(
                    patchid=1,
                    author='me',
                    body=b'my patch',
                    comment='comment',
                    level=3,
                    subdir='master/',
                ),
            ),
        )

    @defer.inlineCallbacks
    def test_getSourceStamp_simple(self):
        yield self.db.insert_test_data([
            fakedb.SourceStamp(
                id=234,
                branch='br',
                revision='rv',
                repository='rep',
                codebase='cb',
                project='prj',
                created_at=CREATED_AT,
            ),
        ])
        ssdict = yield self.db.sourcestamps.getSourceStamp(234)

        self.assertEqual(
            ssdict,
            sourcestamps.SourceStampModel(
                ssid=234,
                created_at=epoch2datetime(CREATED_AT),
                branch='br',
                revision='rv',
                repository='rep',
                codebase='cb',
                project='prj',
                patch=None,
            ),
        )

    @defer.inlineCallbacks
    def test_getSourceStamp_simple_None(self):
        "check that NULL branch and revision are handled correctly"
        yield self.db.insert_test_data([
            fakedb.SourceStamp(
                id=234, branch=None, revision=None, repository='rep', codebase='cb', project='prj'
            ),
        ])
        ssdict = yield self.db.sourcestamps.getSourceStamp(234)

        self.assertIsInstance(ssdict, sourcestamps.SourceStampModel)
        self.assertEqual((ssdict.branch, ssdict.revision), (None, None))

    @defer.inlineCallbacks
    def test_getSourceStamp_patch(self) -> Generator[defer.Deferred, None, None]:
        yield self.db.insert_test_data([
            fakedb.Patch(
                id=99,
                patch_base64='aGVsbG8sIHdvcmxk',
                patch_author='bar',
                patch_comment='foo',
                subdir='/foo',
                patchlevel=3,
            ),
            fakedb.SourceStamp(id=234, patchid=99),
        ])
        res = yield self.db.sourcestamps.getSourceStamp(234)
        assert res is not None
        ssdict = res

        self.assertIsInstance(ssdict, sourcestamps.SourceStampModel)
        self.assertIsInstance(ssdict.patch, sourcestamps.PatchModel)
        self.assertEqual(ssdict.patch.body, b'hello, world')
        self.assertEqual(ssdict.patch.level, 3)
        self.assertEqual(ssdict.patch.author, 'bar')
        self.assertEqual(ssdict.patch.comment, 'foo')
        self.assertEqual(ssdict.patch.subdir, '/foo')

    @defer.inlineCallbacks
    def test_getSourceStamp_nosuch(self):
        ssdict = yield self.db.sourcestamps.getSourceStamp(234)

        self.assertEqual(ssdict, None)

    @defer.inlineCallbacks
    def test_getSourceStamps(self):
        yield self.db.insert_test_data([
            fakedb.Patch(
                id=99,
                patch_base64='aGVsbG8sIHdvcmxk',
                patch_author='bar',
                patch_comment='foo',
                subdir='/foo',
                patchlevel=3,
            ),
            fakedb.SourceStamp(
                id=234,
                revision='r',
                project='p',
                codebase='c',
                repository='rep',
                branch='b',
                patchid=99,
                created_at=CREATED_AT,
            ),
            fakedb.SourceStamp(
                id=235,
                revision='r2',
                project='p2',
                codebase='c2',
                repository='rep2',
                branch='b2',
                patchid=None,
                created_at=CREATED_AT + 10,
            ),
        ])
        db_sourcestamps = yield self.db.sourcestamps.getSourceStamps()

        self.assertEqual(
            sorted(db_sourcestamps, key=sourceStampKey),
            sorted(
                [
                    sourcestamps.SourceStampModel(
                        branch='b',
                        codebase='c',
                        project='p',
                        repository='rep',
                        revision='r',
                        created_at=epoch2datetime(CREATED_AT),
                        ssid=234,
                        patch=sourcestamps.PatchModel(
                            patchid=99,
                            author='bar',
                            body=b'hello, world',
                            comment='foo',
                            level=3,
                            subdir='/foo',
                        ),
                    ),
                    sourcestamps.SourceStampModel(
                        branch='b2',
                        codebase='c2',
                        project='p2',
                        repository='rep2',
                        revision='r2',
                        created_at=epoch2datetime(CREATED_AT + 10),
                        ssid=235,
                        patch=None,
                    ),
                ],
                key=sourceStampKey,
            ),
        )

    @defer.inlineCallbacks
    def test_getSourceStamps_empty(self):
        sourcestamps = yield self.db.sourcestamps.getSourceStamps()

        self.assertEqual(sourcestamps, [])

    @defer.inlineCallbacks
    def test_get_sourcestamps_for_buildset_one_codebase(self):
        yield self.db.insert_test_data([
            fakedb.Master(id=88, name="bar"),
            fakedb.Worker(id=13, name="one"),
            fakedb.Builder(id=77, name="A"),
            fakedb.SourceStamp(id=234, codebase="A", created_at=CREATED_AT, revision="aaa"),
            fakedb.Buildset(id=30, reason="foo", submitted_at=1300305712, results=-1),
            fakedb.BuildsetSourceStamp(sourcestampid=234, buildsetid=30),
        ])

        db_sourcestamps = yield self.db.sourcestamps.get_sourcestamps_for_buildset(30)

        expected = [
            sourcestamps.SourceStampModel(
                branch="master",
                codebase="A",
                created_at=epoch2datetime(CREATED_AT),
                patch=None,
                project="proj",
                repository="repo",
                revision="aaa",
                ssid=234,
            )
        ]

        self.assertEqual(
            sorted(db_sourcestamps, key=sourceStampKey), sorted(expected, key=sourceStampKey)
        )

    @defer.inlineCallbacks
    def test_get_sourcestamps_for_buildset_three_codebases(self):
        yield self.db.insert_test_data([
            fakedb.Master(id=88, name="bar"),
            fakedb.Worker(id=13, name="one"),
            fakedb.Builder(id=77, name="A"),
            fakedb.SourceStamp(id=234, codebase="A", created_at=CREATED_AT, revision="aaa"),
            fakedb.SourceStamp(id=235, codebase="B", created_at=CREATED_AT + 10, revision="bbb"),
            fakedb.SourceStamp(id=236, codebase="C", created_at=CREATED_AT + 20, revision="ccc"),
            fakedb.Buildset(id=30, reason="foo", submitted_at=1300305712, results=-1),
            fakedb.BuildsetSourceStamp(sourcestampid=234, buildsetid=30),
            fakedb.BuildsetSourceStamp(sourcestampid=235, buildsetid=30),
            fakedb.BuildsetSourceStamp(sourcestampid=236, buildsetid=30),
        ])

        db_sourcestamps = yield self.db.sourcestamps.get_sourcestamps_for_buildset(30)

        expected = [
            sourcestamps.SourceStampModel(
                branch="master",
                codebase="A",
                created_at=epoch2datetime(CREATED_AT),
                patch=None,
                project="proj",
                repository="repo",
                revision="aaa",
                ssid=234,
            ),
            sourcestamps.SourceStampModel(
                branch="master",
                codebase="B",
                created_at=epoch2datetime(CREATED_AT + 10),
                patch=None,
                project="proj",
                repository="repo",
                revision="bbb",
                ssid=235,
            ),
            sourcestamps.SourceStampModel(
                branch="master",
                codebase="C",
                created_at=epoch2datetime(CREATED_AT + 20),
                patch=None,
                project="proj",
                repository="repo",
                revision="ccc",
                ssid=236,
            ),
        ]

        self.assertEqual(
            sorted(db_sourcestamps, key=sourceStampKey), sorted(expected, key=sourceStampKey)
        )

    @defer.inlineCallbacks
    def do_test_getSourceStampsForBuild(self, rows, buildid, expected):
        yield self.db.insert_test_data(rows)

        sourcestamps = yield self.db.sourcestamps.getSourceStampsForBuild(buildid)

        self.assertEqual(
            sorted(sourcestamps, key=sourceStampKey), sorted(expected, key=sourceStampKey)
        )

    def test_getSourceStampsForBuild_OneCodeBase(self):
        rows = [
            fakedb.Master(id=88, name="bar"),
            fakedb.Worker(id=13, name='one'),
            fakedb.Builder(id=77, name='A'),
            fakedb.SourceStamp(id=234, codebase='A', created_at=CREATED_AT, revision="aaa"),
            # fakedb.Change(changeid=14, codebase='A', sourcestampid=234),
            fakedb.Buildset(id=30, reason='foo', submitted_at=1300305712, results=-1),
            fakedb.BuildsetSourceStamp(sourcestampid=234, buildsetid=30),
            fakedb.BuildRequest(
                id=19, buildsetid=30, builderid=77, priority=13, submitted_at=1300305712, results=-1
            ),
            fakedb.Build(
                id=50,
                buildrequestid=19,
                number=5,
                masterid=88,
                builderid=77,
                state_string="test",
                workerid=13,
                started_at=1304262222,
            ),
        ]

        expected = [
            sourcestamps.SourceStampModel(
                branch='master',
                codebase='A',
                created_at=epoch2datetime(CREATED_AT),
                patch=None,
                project='proj',
                repository='repo',
                revision='aaa',
                ssid=234,
            )
        ]

        return self.do_test_getSourceStampsForBuild(rows, 50, expected)

    def test_getSourceStampsForBuild_3CodeBases(self):
        rows = [
            fakedb.Master(id=88, name="bar"),
            fakedb.Worker(id=13, name='one'),
            fakedb.Builder(id=77, name='A'),
            fakedb.SourceStamp(id=234, codebase='A', created_at=CREATED_AT, revision="aaa"),
            fakedb.SourceStamp(id=235, codebase='B', created_at=CREATED_AT + 10, revision="bbb"),
            fakedb.SourceStamp(id=236, codebase='C', created_at=CREATED_AT + 20, revision="ccc"),
            # fakedb.Change(changeid=14, codebase='A', sourcestampid=234),
            fakedb.Buildset(id=30, reason='foo', submitted_at=1300305712, results=-1),
            fakedb.BuildsetSourceStamp(sourcestampid=234, buildsetid=30),
            fakedb.BuildsetSourceStamp(sourcestampid=235, buildsetid=30),
            fakedb.BuildsetSourceStamp(sourcestampid=236, buildsetid=30),
            fakedb.BuildRequest(
                id=19, buildsetid=30, builderid=77, priority=13, submitted_at=1300305712, results=-1
            ),
            fakedb.Build(
                id=50,
                buildrequestid=19,
                number=5,
                masterid=88,
                builderid=77,
                state_string="test",
                workerid=13,
                started_at=1304262222,
            ),
        ]

        expected = [
            sourcestamps.SourceStampModel(
                branch='master',
                codebase='A',
                created_at=epoch2datetime(CREATED_AT),
                patch=None,
                project='proj',
                repository='repo',
                revision='aaa',
                ssid=234,
            ),
            sourcestamps.SourceStampModel(
                branch='master',
                codebase='B',
                created_at=epoch2datetime(CREATED_AT + 10),
                patch=None,
                project='proj',
                repository='repo',
                revision='bbb',
                ssid=235,
            ),
            sourcestamps.SourceStampModel(
                branch='master',
                codebase='C',
                created_at=epoch2datetime(CREATED_AT + 20),
                patch=None,
                project='proj',
                repository='repo',
                revision='ccc',
                ssid=236,
            ),
        ]
        return self.do_test_getSourceStampsForBuild(rows, 50, expected)
