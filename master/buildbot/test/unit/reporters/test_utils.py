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

import datetime
import textwrap

from dateutil.tz import tzutc

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SUCCESS
from buildbot.reporters import utils
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import logging


class TestDataUtils(TestReactorMixin, unittest.TestCase, logging.LoggingMixin):
    LOGCONTENT = textwrap.dedent("""\
        line zero
        line 1
        """)

    def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True,
                                             wantMq=True)

    def setupDb(self):
        self.db = self.master.db
        self.db.insertTestData([
            fakedb.Master(id=92),
            fakedb.Worker(id=13, name='wrk'),
            fakedb.Buildset(id=98, results=SUCCESS, reason="testReason1"),
            fakedb.Buildset(id=99, results=SUCCESS, reason="testReason2", parent_buildid=21),
            fakedb.Builder(id=80, name='Builder1'),
            fakedb.Builder(id=81, name='Builder2'),
            fakedb.BuildRequest(id=9, buildsetid=97, builderid=80),
            fakedb.BuildRequest(id=10, buildsetid=97, builderid=80),
            fakedb.BuildRequest(id=11, buildsetid=98, builderid=80),
            fakedb.BuildRequest(id=12, buildsetid=98, builderid=80),
            fakedb.BuildRequest(id=13, buildsetid=99, builderid=81),
            fakedb.Build(id=18, number=0, builderid=80, buildrequestid=9, workerid=13,
                         masterid=92, results=FAILURE),
            fakedb.Build(id=19, number=1, builderid=80, buildrequestid=10, workerid=13,
                         masterid=92, results=RETRY),
            fakedb.Build(id=20, number=2, builderid=80, buildrequestid=11, workerid=13,
                         masterid=92, results=SUCCESS),
            fakedb.Build(id=21, number=3, builderid=80, buildrequestid=12, workerid=13,
                         masterid=92, results=SUCCESS),
            fakedb.Build(id=22, number=1, builderid=81, buildrequestid=13, workerid=13,
                         masterid=92, results=SUCCESS),
            fakedb.BuildsetSourceStamp(buildsetid=98, sourcestampid=234),
            fakedb.SourceStamp(id=234),
            fakedb.Change(changeid=13, branch='trunk', revision='9283', author='me@foo',
                          repository='svn://...', codebase='cbsvn',
                          project='world-domination', sourcestampid=234),
            fakedb.Patch(id=99, patch_base64='aGVsbG8sIHdvcmxk',
                         patch_author='him@foo', patch_comment='foo', subdir='/foo',
                         patchlevel=3),
            fakedb.SourceStamp(id=235, patchid=99),
        ])
        for _id in (20, 21):
            self.db.insertTestData([
                fakedb.BuildProperty(
                    buildid=_id, name="workername", value="wrk"),
                fakedb.BuildProperty(
                    buildid=_id, name="reason", value="because"),
                fakedb.BuildProperty(
                    buildid=_id, name="owner", value="him"),
                fakedb.Step(id=100 + _id, buildid=_id, name="step1"),
                fakedb.Step(id=200 + _id, buildid=_id, name="step2"),
                fakedb.Log(id=60 + _id, stepid=100 + _id, name='stdio', slug='stdio', type='s',
                           num_lines=2),
                fakedb.LogChunk(logid=60 + _id, first_line=0, last_line=1, compressed=0,
                                content=self.LOGCONTENT),
            ])

        @defer.inlineCallbacks
        def getChangesForBuild(buildid):
            assert buildid == 20
            ch = yield self.master.db.changes.getChange(13)
            return [ch]

        self.master.db.changes.getChangesForBuild = getChangesForBuild

    @defer.inlineCallbacks
    def test_getDetailsForBuildset(self):
        self.setupDb()
        res = yield utils.getDetailsForBuildset(self.master, 98, want_properties=True,
                                                want_steps=True, want_previous_build=True)
        self.assertEqual(len(res['builds']), 2)
        build1 = res['builds'][0]
        build2 = res['builds'][1]
        buildset = res['buildset']
        self.assertEqual(build1['properties'], {'reason': ('because', 'fakedb'),
                                                'owner': ('him', 'fakedb'),
                                                'workername': ('wrk', 'fakedb')})
        self.assertEqual(len(build1['steps']), 2)
        self.assertEqual(build1['buildid'], 20)
        self.assertEqual(build2['buildid'], 21)
        self.assertEqual(buildset['bsid'], 98)

        # make sure prev_build was computed
        self.assertEqual(build1['prev_build']['buildid'], 18)
        self.assertEqual(build2['prev_build']['buildid'], 20)

    @defer.inlineCallbacks
    def test_getDetailsForBuild(self):
        self.setupDb()
        build = yield self.master.data.get(("builds", 21))
        yield utils.getDetailsForBuild(self.master, build, want_properties=False,
                                       want_steps=False, want_previous_build=False,
                                       want_logs=False)

        self.assertEqual(build['parentbuild'], None)
        self.assertEqual(build['parentbuilder'], None)

    @defer.inlineCallbacks
    def test_getDetailsForBuildWithParent(self):
        self.setupDb()
        build = yield self.master.data.get(("builds", 22))
        yield utils.getDetailsForBuild(self.master, build, want_properties=False,
                                       want_steps=False, want_previous_build=False,
                                       want_logs=False)

        self.assertEqual(build['parentbuild']['buildid'], 21)
        self.assertEqual(build['parentbuilder']['name'], "Builder1")

    @defer.inlineCallbacks
    def test_getDetailsForBuildsetWithLogs(self):
        self.setupDb()
        res = yield utils.getDetailsForBuildset(self.master, 98, want_properties=True,
                                                want_steps=True, want_previous_build=True,
                                                want_logs=True, want_logs_content=True)

        build1 = res['builds'][0]
        self.assertEqual(build1['steps'][0]['logs'][0]['content']['content'], self.LOGCONTENT)
        self.assertEqual(build1['steps'][0]['logs'][0]['url'],
                         'http://localhost:8080/#/builders/80/builds/2/steps/29/logs/stdio')

    @defer.inlineCallbacks
    def test_get_details_for_buildset_all(self):
        self.setupDb()
        res = yield utils.getDetailsForBuildset(self.master, 98, want_properties=True,
                                                want_steps=True, want_previous_build=True,
                                                want_logs=True, want_logs_content=True)

        self.assertEqual(res, {
            'builds': [{
                'builder': {
                    'builderid': 80,
                    'description': None,
                    'masterids': [],
                    'name': 'Builder1',
                    'tags': []
                },
                'builderid': 80,
                'buildid': 20,
                'buildrequestid': 11,
                'buildset': {
                    'bsid': 98,
                    'complete': False,
                    'complete_at': None,
                    'external_idstring': 'extid',
                    'parent_buildid': None,
                    'parent_relationship': None,
                    'reason': 'testReason1',
                    'results': 0,
                    'sourcestamps': [{
                        'branch': 'master',
                        'codebase': '',
                        'created_at': datetime.datetime(1972, 11, 5, 18, 7, 14, tzinfo=tzutc()),
                        'patch': None,
                        'project': 'proj',
                        'repository': 'repo',
                        'revision': 'abcd',
                        'ssid': 234
                    }],
                    'submitted_at': 12345678
                },
                'complete': False,
                'complete_at': None,
                'masterid': 92,
                'number': 2,
                'prev_build': {
                    'builderid': 80,
                    'buildid': 18,
                    'buildrequestid': 9,
                    'complete': False,
                    'complete_at': None,
                    'masterid': 92,
                    'number': 0,
                    'properties': {},
                    'results': 2,
                    'started_at': datetime.datetime(2011, 5, 1, 15, 3, 42, tzinfo=tzutc()),
                    'state_string': 'test',
                    'workerid': 13
                },
                'properties': {
                    'owner': ('him', 'fakedb'),
                    'reason': ('because', 'fakedb'),
                    'workername': ('wrk', 'fakedb')
                },
                'results': 0,
                'started_at': datetime.datetime(2011, 5, 1, 15, 3, 42, tzinfo=tzutc()),
                'state_string': 'test',
                'steps': [{
                    'buildid': 20,
                    'complete': False,
                    'complete_at': None,
                    'hidden': False,
                    'logs': [{
                        'complete': False,
                        'content': {
                            'content': 'line zero\nline 1\n',
                            'firstline': 0,
                            'logid': 80
                        },
                        'logid': 80,
                        'name': 'stdio',
                        'num_lines': 2,
                        'slug': 'stdio',
                        'stepid': 120,
                        'type': 's',
                        'url': 'http://localhost:8080/#/builders/80/builds/2/steps/29/logs/stdio'
                    }],
                    'name': 'step1',
                    'number': 29,
                    'results': None,
                    'started_at': datetime.datetime(2011, 5, 1, 15, 3, 42, tzinfo=tzutc()),
                    'state_string': '',
                    'stepid': 120,
                    'urls': []
                }, {
                    'buildid': 20,
                    'complete': False,
                    'complete_at': None,
                    'hidden': False,
                    'logs': [],
                    'name': 'step2',
                    'number': 29,
                    'results': None,
                    'started_at': datetime.datetime(2011, 5, 1, 15, 3, 42, tzinfo=tzutc()),
                    'state_string': '',
                    'stepid': 220,
                    'urls': []
                }],
                'url': 'http://localhost:8080/#/builders/80/builds/2',
                'workerid': 13
            }, {
                'builder': {
                    'builderid': 80,
                    'description': None,
                    'masterids': [],
                    'name': 'Builder1',
                    'tags': []
                },
                'builderid': 80,
                'buildid': 21,
                'buildrequestid': 12,
                'buildset': {
                    'bsid': 98,
                    'complete': False,
                    'complete_at': None,
                    'external_idstring': 'extid',
                    'parent_buildid': None,
                    'parent_relationship': None,
                    'reason': 'testReason1',
                    'results': 0,
                    'sourcestamps': [{
                        'branch': 'master',
                        'codebase': '',
                        'created_at': datetime.datetime(1972, 11, 5, 18, 7, 14, tzinfo=tzutc()),
                        'patch': None,
                        'project': 'proj',
                        'repository': 'repo',
                        'revision': 'abcd',
                        'ssid': 234
                    }],
                    'submitted_at': 12345678
                },
                'complete': False,
                'complete_at': None,
                'masterid': 92,
                'number': 3,
                'prev_build': {
                    'builderid': 80,
                'buildid': 20,
                    'buildrequestid': 11,
                    'complete': False,
                    'complete_at': None,
                    'masterid': 92,
                    'number': 2,
                    'properties': {},
                    'results': 0,
                    'started_at': datetime.datetime(2011, 5, 1, 15, 3, 42, tzinfo=tzutc()),
                    'state_string': 'test',
                    'workerid': 13
                },
                'properties': {
                    'owner': ('him', 'fakedb'),
                    'reason': ('because', 'fakedb'),
                    'workername': ('wrk', 'fakedb')
                },
                'results': 0,
                'started_at': datetime.datetime(2011, 5, 1, 15, 3, 42, tzinfo=tzutc()),
                'state_string': 'test',
                'steps': [{
                    'buildid': 21,
                    'complete': False,
                    'complete_at': None,
                    'hidden': False,
                    'logs': [{
                        'complete': False,
                        'content': {'content': 'line zero\nline 1\n',
                        'firstline': 0,
                        'logid': 81},
                        'logid': 81,
                        'name': 'stdio',
                        'num_lines': 2,
                        'slug': 'stdio',
                        'stepid': 121,
                        'type': 's',
                        'url': 'http://localhost:8080/#/builders/80/builds/3/steps/29/logs/stdio'
                    }],
                    'name': 'step1',
                    'number': 29,
                    'results': None,
                    'started_at': datetime.datetime(2011, 5, 1, 15, 3, 42, tzinfo=tzutc()),
                    'state_string': '',
                    'stepid': 121,
                    'urls': []
                }, {
                    'buildid': 21,
                    'complete': False,
                    'complete_at': None,
                    'hidden': False,
                    'logs': [],
                    'name': 'step2',
                    'number': 29,
                    'results': None,
                    'started_at': datetime.datetime(2011, 5, 1, 15, 3, 42, tzinfo=tzutc()),
                    'state_string': '',
                    'stepid': 221,
                    'urls': []
                }],
                'url': 'http://localhost:8080/#/builders/80/builds/3',
                'workerid': 13
            }],
            'buildset': {
                'bsid': 98,
                'complete': False,
                'complete_at': None,
                'external_idstring': 'extid',
                'parent_buildid': None,
                'parent_relationship': None,
                'reason': 'testReason1',
                'results': 0,
                'sourcestamps': [{
                    'branch': 'master',
                    'codebase': '',
                    'created_at': datetime.datetime(1972, 11, 5, 18, 7, 14, tzinfo=tzutc()),
                    'patch': None,
                    'project': 'proj',
                    'repository': 'repo',
                    'revision': 'abcd',
                    'ssid': 234
                }],
                'submitted_at': 12345678
            }
        })

    @defer.inlineCallbacks
    def test_getResponsibleUsers(self):
        self.setupDb()
        res = yield utils.getResponsibleUsersForSourceStamp(self.master, 234)
        self.assertEqual(res, ["me@foo"])

    @defer.inlineCallbacks
    def test_getResponsibleUsersFromPatch(self):
        self.setupDb()
        res = yield utils.getResponsibleUsersForSourceStamp(self.master, 235)
        self.assertEqual(res, ["him@foo"])

    @defer.inlineCallbacks
    def test_getResponsibleUsersForBuild(self):
        self.setupDb()
        res = yield utils.getResponsibleUsersForBuild(self.master, 20)
        self.assertEqual(sorted(res), sorted(["me@foo", "him"]))

    @defer.inlineCallbacks
    def test_getResponsibleUsersForBuildWithBadOwner(self):
        self.setUpLogging()
        self.setupDb()
        self.db.insertTestData([
            fakedb.BuildProperty(
                buildid=20, name="owner", value=["him"]),
        ])
        res = yield utils.getResponsibleUsersForBuild(self.master, 20)
        self.assertLogged("Please report a bug")
        self.assertEqual(sorted(res), sorted(["me@foo", "him"]))

    @defer.inlineCallbacks
    def test_getResponsibleUsersForBuildWithOwners(self):
        self.setupDb()
        self.db.insertTestData([
            fakedb.BuildProperty(
                buildid=20, name="owners", value=["him", "her"]),
        ])
        res = yield utils.getResponsibleUsersForBuild(self.master, 20)
        self.assertEqual(sorted(res), sorted(["me@foo", "him", "her"]))

    @defer.inlineCallbacks
    def test_getPreviousBuild(self):
        self.setupDb()
        build = yield self.master.data.get(("builds", 21))
        res = yield utils.getPreviousBuild(self.master, build)
        self.assertEqual(res['buildid'], 20)

    @defer.inlineCallbacks
    def test_getPreviousBuildWithRetry(self):
        self.setupDb()
        build = yield self.master.data.get(("builds", 20))
        res = yield utils.getPreviousBuild(self.master, build)
        self.assertEqual(res['buildid'], 18)


class TestURLUtils(TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self)

    def test_UrlForBuild(self):
        self.assertEqual(utils.getURLForBuild(self.master, 1, 3),
                         'http://localhost:8080/#/builders/1/builds/3')
