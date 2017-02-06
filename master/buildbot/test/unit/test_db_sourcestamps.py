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
from future.utils import iteritems

from twisted.internet import defer
from twisted.internet import task
from twisted.trial import unittest

from buildbot.db import sourcestamps
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import connector_component
from buildbot.test.util import interfaces
from buildbot.test.util import validation
from buildbot.util import epoch2datetime

CREATED_AT = 927845299


def sourceStampKey(sourceStamp):
    return (sourceStamp['repository'], sourceStamp['branch'],
            sourceStamp['created_at'])


class Tests(interfaces.InterfaceTests):

    def test_signature_findSourceStampId(self):
        @self.assertArgSpecMatches(self.db.sourcestamps.findSourceStampId)
        def findSourceStampId(self, branch=None, revision=None,
                              repository=None, project=None, codebase=None, patch_body=None,
                              patch_level=None, patch_author=None, patch_comment=None,
                              patch_subdir=None):
            pass

    def test_signature_getSourceStamp(self):
        @self.assertArgSpecMatches(self.db.sourcestamps.getSourceStamp)
        def getSourceStamp(self, key, no_cache=False):
            pass

    def test_signature_getSourceStamps(self):
        @self.assertArgSpecMatches(self.db.sourcestamps.getSourceStamps)
        def getSourceStamps(self):
            pass

    @defer.inlineCallbacks
    def test_findSourceStampId_simple(self):
        clock = task.Clock()
        clock.advance(CREATED_AT)
        ssid = yield self.db.sourcestamps.findSourceStampId(
            branch=u'production', revision=u'abdef',
            repository=u'test://repo', codebase=u'cb', project=u'stamper',
            _reactor=clock)
        ssdict = yield self.db.sourcestamps.getSourceStamp(ssid)
        validation.verifyDbDict(self, 'ssdict', ssdict)
        self.assertEqual(ssdict, {
            'branch': u'production',
            'codebase': u'cb',
            'patchid': None,
            'patch_author': None,
            'patch_body': None,
            'patch_comment': None,
            'patch_level': None,
            'patch_subdir': None,
            'project': u'stamper',
            'repository': u'test://repo',
            'revision': u'abdef',
            'ssid': ssid,
            'created_at': epoch2datetime(CREATED_AT),
        })

    @defer.inlineCallbacks
    def test_findSourceStampId_simple_unique(self):
        ssid1 = yield self.db.sourcestamps.findSourceStampId(
            branch='production', revision='abdef',
            repository='test://repo', codebase='cb', project='stamper')
        ssid2 = yield self.db.sourcestamps.findSourceStampId(
            branch='production', revision='xxxxx',  # different revision
            repository='test://repo', codebase='cb', project='stamper')
        ssid3 = yield self.db.sourcestamps.findSourceStampId(  # same as ssid1
            branch='production', revision='abdef',
            repository='test://repo', codebase='cb', project='stamper')
        self.assertEqual(ssid1, ssid3)
        self.assertNotEqual(ssid1, ssid2)

    @defer.inlineCallbacks
    def test_findSourceStampId_simple_unique_patch(self):
        ssid1 = yield self.db.sourcestamps.findSourceStampId(
            branch='production', revision='abdef',
            repository='test://repo', codebase='cb', project='stamper',
            patch_body=b'++ --', patch_level=1, patch_author='me',
            patch_comment='hi', patch_subdir='.')
        ssid2 = yield self.db.sourcestamps.findSourceStampId(
            branch='production', revision='abdef',
            repository='test://repo', codebase='cb', project='stamper',
            patch_body=b'++ --', patch_level=1, patch_author='me',
            patch_comment='hi', patch_subdir='.')
        # even with the same patch contents, we get different ids
        self.assertNotEqual(ssid1, ssid2)

    @defer.inlineCallbacks
    def test_findSourceStampId_patch(self):
        clock = task.Clock()
        clock.advance(CREATED_AT)
        ssid = yield self.db.sourcestamps.findSourceStampId(
            branch=u'production', revision=u'abdef',
            repository=u'test://repo', codebase=u'cb', project=u'stamper',
            patch_body=b'my patch', patch_level=3, patch_subdir=u'master/',
            patch_author=u'me', patch_comment=u"comment", _reactor=clock)
        ssdict = yield self.db.sourcestamps.getSourceStamp(ssid)
        validation.verifyDbDict(self, 'ssdict', ssdict)
        self.assertEqual(ssdict, {
            'branch': u'production',
            'codebase': u'cb',
            'patchid': 1,
            'patch_author': 'me',
            'patch_body': b'my patch',
            'patch_comment': 'comment',
            'patch_level': 3,
            'patch_subdir': 'master/',
            'project': u'stamper',
            'repository': u'test://repo',
            'revision': u'abdef',
            'created_at': epoch2datetime(CREATED_AT),
            'ssid': ssid,
        })

    def test_getSourceStamp_simple(self):
        d = self.insertTestData([
            fakedb.SourceStamp(id=234, branch='br', revision='rv',
                               repository='rep', codebase='cb', project='prj',
                               created_at=CREATED_AT),
        ])
        d.addCallback(lambda _:
                      self.db.sourcestamps.getSourceStamp(234))

        def check(ssdict):
            validation.verifyDbDict(self, 'ssdict', ssdict)
            self.assertEqual(ssdict, {
                'ssid': 234,
                'created_at': epoch2datetime(CREATED_AT),
                'branch': 'br',
                'revision': 'rv',
                'repository': 'rep',
                'codebase': 'cb',
                'project': 'prj',
                'patchid': None,
                'patch_body': None,
                'patch_level': None,
                'patch_subdir': None,
                'patch_author': None,
                'patch_comment': None,
            })
        d.addCallback(check)
        return d

    def test_getSourceStamp_simple_None(self):
        "check that NULL branch and revision are handled correctly"
        d = self.insertTestData([
            fakedb.SourceStamp(id=234, branch=None, revision=None,
                               repository='rep', codebase='cb', project='prj'),
        ])
        d.addCallback(lambda _:
                      self.db.sourcestamps.getSourceStamp(234))

        def check(ssdict):
            validation.verifyDbDict(self, 'ssdict', ssdict)
            self.assertEqual((ssdict['branch'], ssdict['revision']),
                             (None, None))
        d.addCallback(check)
        return d

    def test_getSourceStamp_patch(self):
        d = self.insertTestData([
            fakedb.Patch(id=99, patch_base64='aGVsbG8sIHdvcmxk',
                         patch_author='bar', patch_comment='foo', subdir='/foo',
                         patchlevel=3),
            fakedb.SourceStamp(id=234, patchid=99),
        ])
        d.addCallback(lambda _:
                      self.db.sourcestamps.getSourceStamp(234))

        def check(ssdict):
            validation.verifyDbDict(self, 'ssdict', ssdict)
            self.assertEqual(dict((k, v) for k, v in iteritems(ssdict)
                                  if k.startswith('patch_')),
                             dict(patch_body=b'hello, world',
                                  patch_level=3,
                                  patch_author='bar',
                                  patch_comment='foo',
                                  patch_subdir='/foo'))
        d.addCallback(check)
        return d

    def test_getSourceStamp_nosuch(self):
        d = self.db.sourcestamps.getSourceStamp(234)

        def check(ssdict):
            self.assertEqual(ssdict, None)
        d.addCallback(check)
        return d

    def test_getSourceStamps(self):
        d = self.insertTestData([
            fakedb.Patch(id=99, patch_base64='aGVsbG8sIHdvcmxk',
                         patch_author='bar', patch_comment='foo', subdir='/foo',
                         patchlevel=3),
            fakedb.SourceStamp(id=234, revision='r', project='p',
                               codebase='c', repository='rep', branch='b', patchid=99,
                               created_at=CREATED_AT),
            fakedb.SourceStamp(id=235, revision='r2', project='p2',
                               codebase='c2', repository='rep2', branch='b2', patchid=None,
                               created_at=CREATED_AT + 10),
        ])
        d.addCallback(lambda _:
                      self.db.sourcestamps.getSourceStamps())

        @d.addCallback
        def check(sourcestamps):
            self.assertEqual(sorted(sourcestamps, key=sourceStampKey),
                             sorted([{
                                 'branch': u'b',
                                 'codebase': u'c',
                                 'patch_author': u'bar',
                                 'patchid': 99,
                                 'patch_body': b'hello, world',
                                 'patch_comment': u'foo',
                                 'patch_level': 3,
                                 'patch_subdir': u'/foo',
                                 'project': u'p',
                                 'repository': u'rep',
                                 'revision': u'r',
                                 'created_at': epoch2datetime(CREATED_AT),
                                 'ssid': 234,
                             }, {
                                 'branch': u'b2',
                                 'codebase': u'c2',
                                 'patchid': None,
                                 'patch_author': None,
                                 'patch_body': None,
                                 'patch_comment': None,
                                 'patch_level': None,
                                 'patch_subdir': None,
                                 'project': u'p2',
                                 'repository': u'rep2',
                                 'revision': u'r2',
                                 'created_at': epoch2datetime(CREATED_AT + 10),
                                 'ssid': 235,
                             }], key=sourceStampKey))
        return d

    def test_getSourceStamps_empty(self):
        d = self.db.sourcestamps.getSourceStamps()

        @d.addCallback
        def check(sourcestamps):
            self.assertEqual(sourcestamps, [])
        return d

    def test_signature_getSourceStampsForBuild(self):
        @self.assertArgSpecMatches(self.db.sourcestamps.getSourceStampsForBuild)
        def getSourceStampsForBuild(self, buildid):
            pass

    def do_test_getSourceStampsForBuild(self, rows, buildid, expected):
        d = self.insertTestData(rows)

        d.addCallback(lambda _:
                      self.db.sourcestamps.getSourceStampsForBuild(buildid))

        @d.addCallback
        def check(sourcestamps):
            self.assertEqual(sorted(sourcestamps, key=sourceStampKey),
                             sorted(expected, key=sourceStampKey))
        return d

    def test_getSourceStampsForBuild_OneCodeBase(self):
        rows = [fakedb.Master(id=88, name="bar"),
                fakedb.Worker(id=13, name='one'),
                fakedb.Builder(id=77, name='A'),
                fakedb.SourceStamp(id=234, codebase='A', created_at=CREATED_AT,
                                   revision="aaa"),
                # fakedb.Change(changeid=14, codebase='A', sourcestampid=234),
                fakedb.Buildset(id=30, reason='foo',
                                submitted_at=1300305712, results=-1),
                fakedb.BuildsetSourceStamp(sourcestampid=234, buildsetid=30),
                fakedb.BuildRequest(id=19, buildsetid=30, builderid=77,
                                    priority=13, submitted_at=1300305712, results=-1),
                fakedb.Build(id=50, buildrequestid=19, number=5, masterid=88,
                             builderid=77, state_string="test", workerid=13,
                             started_at=1304262222), ]

        expected = [{
            'branch': u'master',
            'codebase': u'A',
            'created_at': epoch2datetime(CREATED_AT),
            'patch_author': None,
            'patch_body': None,
            'patch_comment': None,
            'patch_level': None,
            'patch_subdir': None,
            'patchid': None,
            'project': u'proj',
            'repository': u'repo',
            'revision': u'aaa',
            'ssid': 234}]

        return self.do_test_getSourceStampsForBuild(rows, 50, expected)

    def test_getSourceStampsForBuild_3CodeBases(self):
        rows = [fakedb.Master(id=88, name="bar"),
                fakedb.Worker(id=13, name='one'),
                fakedb.Builder(id=77, name='A'),
                fakedb.SourceStamp(id=234, codebase='A', created_at=CREATED_AT,
                                   revision="aaa"),
                fakedb.SourceStamp(id=235, codebase='B', created_at=CREATED_AT + 10,
                                   revision="bbb"),
                fakedb.SourceStamp(id=236, codebase='C', created_at=CREATED_AT + 20,
                                   revision="ccc"),
                # fakedb.Change(changeid=14, codebase='A', sourcestampid=234),
                fakedb.Buildset(id=30, reason='foo',
                                submitted_at=1300305712, results=-1),
                fakedb.BuildsetSourceStamp(sourcestampid=234, buildsetid=30),
                fakedb.BuildsetSourceStamp(sourcestampid=235, buildsetid=30),
                fakedb.BuildsetSourceStamp(sourcestampid=236, buildsetid=30),
                fakedb.BuildRequest(id=19, buildsetid=30, builderid=77,
                                    priority=13, submitted_at=1300305712, results=-1),
                fakedb.Build(id=50, buildrequestid=19, number=5, masterid=88,
                             builderid=77, state_string="test", workerid=13,
                             started_at=1304262222), ]

        expected = [{'branch': u'master',
                     'codebase': u'A',
                     'created_at': epoch2datetime(CREATED_AT),
                     'patch_author': None,
                     'patch_body': None,
                     'patch_comment': None,
                     'patch_level': None,
                     'patch_subdir': None,
                     'patchid': None,
                     'project': u'proj',
                     'repository': u'repo',
                     'revision': u'aaa',
                     'ssid': 234},
                    {'branch': u'master',
                     'codebase': u'B',
                     'created_at': epoch2datetime(CREATED_AT + 10),
                     'patch_author': None,
                     'patch_body': None,
                     'patch_comment': None,
                     'patch_level': None,
                     'patch_subdir': None,
                     'patchid': None,
                     'project': u'proj',
                     'repository': u'repo',
                     'revision': u'bbb',
                     'ssid': 235},
                    {'branch': u'master',
                     'codebase': u'C',
                     'created_at': epoch2datetime(CREATED_AT + 20),
                     'patch_author': None,
                     'patch_body': None,
                     'patch_comment': None,
                     'patch_level': None,
                     'patch_subdir': None,
                     'patchid': None,
                     'project': u'proj',
                     'repository': u'repo',
                     'revision': u'ccc',
                     'ssid': 236}]
        return self.do_test_getSourceStampsForBuild(rows, 50, expected)


class RealTests(Tests):

    pass


class TestFakeDB(unittest.TestCase, Tests):

    def setUp(self):
        self.master = fakemaster.make_master(wantDb=True, testcase=self)
        self.db = self.master.db
        self.db.checkForeignKeys = True
        self.insertTestData = self.db.insertTestData


class TestRealDB(unittest.TestCase,
                 connector_component.ConnectorComponentMixin,
                 RealTests):

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['sourcestamps',
                         'patches',
                         'masters',
                         'workers',
                         'buildsets',
                         'builders',
                         'buildrequests',
                         'buildset_sourcestamps',
                         'builds'])

        def finish_setup(_):
            self.db.sourcestamps = \
                sourcestamps.SourceStampsConnectorComponent(self.db)
        d.addCallback(finish_setup)

        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()
