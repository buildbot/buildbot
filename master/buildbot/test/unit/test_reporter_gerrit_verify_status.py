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

import datetime

from mock import Mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot import config
from buildbot.process.properties import Interpolate
from buildbot.process.properties import Properties
from buildbot.process.properties import renderer
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.reporters.gerrit_verify_status import GerritVerifyStatusPush
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.fake import fakemaster
from buildbot.test.util import logging
from buildbot.test.util.reporter import ReporterTestMixin

from .test_changes_gerritchangesource import TestGerritChangeSource


class TestGerritVerifyStatusPush(unittest.TestCase, ReporterTestMixin, logging.LoggingMixin):
    TEST_PROPS = {'gerrit_changes': [{'change_id': 12, 'revision_id': 2}]}

    @defer.inlineCallbacks
    def setUp(self):
        # ignore config error if txrequests is not installed
        self.patch(config, '_errors', Mock())
        self.master = fakemaster.make_master(
            testcase=self, wantData=True, wantDb=True, wantMq=True)

        yield self.master.startService()

    @defer.inlineCallbacks
    def createGerritStatus(self, **kwargs):
        auth = kwargs.pop('auth', ('log', 'pass'))
        self._http = yield fakehttpclientservice.HTTPClientService.getFakeService(
            self.master, self, "gerrit", auth=auth,
            debug=None, verify=None)
        self.sp = sp = GerritVerifyStatusPush("gerrit", auth=auth, **kwargs)
        sp.sessionFactory = Mock(return_value=Mock())
        yield sp.setServiceParent(self.master)

    def tearDown(self):
        return self.master.stopService()

    @defer.inlineCallbacks
    def setupBuildResults(self, buildResults):
        self.insertTestData([buildResults], buildResults)
        build = yield self.master.data.get(("builds", 20))
        defer.returnValue(build)

    @defer.inlineCallbacks
    def test_basic(self):
        yield self.createGerritStatus()
        build = yield self.setupBuildResults(SUCCESS)
        # we make sure proper calls to txrequests have been made
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'Build started.',
                'abstain': False,
                'name': u'Builder0',
                'reporter': 'buildbot',
                'url': 'http://localhost:8080/#builders/79/builds/0',
                'value': 0,
                'duration': 'pending'
            })
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'Build done.',
                'abstain': False,
                'name': u'Builder0',
                'reporter': 'buildbot',
                'url': 'http://localhost:8080/#builders/79/builds/0',
                'value': 1,
                'duration': '2h 1m 4s'
            })
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'Build done.',
                'abstain': False,
                'name': u'Builder0',
                'reporter': 'buildbot',
                'url': 'http://localhost:8080/#builders/79/builds/0',
                'value': -1,
                'duration': '2h 1m 4s'
            })
        build['complete'] = False
        build['complete_at'] = None
        self.sp.buildStarted(("build", 20, "started"), build)
        build['complete'] = True
        build['complete_at'] = build['started_at'] + datetime.timedelta(hours=2, minutes=1, seconds=4)
        self.sp.buildFinished(("build", 20, "finished"), build)
        build['results'] = FAILURE
        self.sp.buildFinished(("build", 20, "finished"), build)

    @defer.inlineCallbacks
    def test_custom_description(self):
        yield self.createGerritStatus(
            startDescription=Interpolate("started %(prop:buildername)s"),
            endDescription=Interpolate("finished %(prop:buildername)s"))
        build = yield self.setupBuildResults(SUCCESS)
        # we make sure proper calls to txrequests have been made
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'started Builder0',
                'abstain': False,
                'name': u'Builder0',
                'reporter': 'buildbot',
                'url': 'http://localhost:8080/#builders/79/builds/0',
                'value': 0,
                'duration': 'pending'
            })
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'finished Builder0',
                'abstain': False,
                'name': u'Builder0',
                'reporter': 'buildbot',
                'url': 'http://localhost:8080/#builders/79/builds/0',
                'value': 1,
                'duration': '2h 1m 4s'
            })
        build['complete'] = False
        build['complete_at'] = None
        self.sp.buildStarted(("build", 20, "started"), build)
        build['complete'] = True
        build['complete_at'] = build['started_at'] + datetime.timedelta(hours=2, minutes=1, seconds=4)
        self.sp.buildFinished(("build", 20, "finished"), build)

    @defer.inlineCallbacks
    def test_custom_name(self):
        yield self.createGerritStatus(
            verification_name=Interpolate("builder %(prop:buildername)s"))
        build = yield self.setupBuildResults(SUCCESS)
        # we make sure proper calls to txrequests have been made
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'Build started.',
                'abstain': False,
                'name': u'builder Builder0',
                'reporter': 'buildbot',
                'url': 'http://localhost:8080/#builders/79/builds/0',
                'value': 0,
                'duration': 'pending'
            })
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'Build done.',
                'abstain': False,
                'name': u'builder Builder0',
                'reporter': 'buildbot',
                'url': 'http://localhost:8080/#builders/79/builds/0',
                'value': 1,
                'duration': '2h 1m 4s'
            })
        build['complete'] = False
        build['complete_at'] = None
        self.sp.buildStarted(("build", 20, "started"), build)
        build['complete'] = True
        build['complete_at'] = build['started_at'] + datetime.timedelta(hours=2, minutes=1, seconds=4)
        self.sp.buildFinished(("build", 20, "finished"), build)

    @defer.inlineCallbacks
    def test_custom_abstain(self):
        yield self.createGerritStatus(
            abstain=renderer(lambda p: p.getProperty("buildername") == 'Builder0'))
        build = yield self.setupBuildResults(SUCCESS)
        # we make sure proper calls to txrequests have been made
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'Build started.',
                'abstain': True,
                'name': u'Builder0',
                'reporter': 'buildbot',
                'url': 'http://localhost:8080/#builders/79/builds/0',
                'value': 0,
                'duration': 'pending'
            })
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'Build done.',
                'abstain': True,
                'name': u'Builder0',
                'reporter': 'buildbot',
                'url': 'http://localhost:8080/#builders/79/builds/0',
                'value': 1,
                'duration': '2h 1m 4s'
            })
        build['complete'] = False
        build['complete_at'] = None
        self.sp.buildStarted(("build", 20, "started"), build)
        build['complete'] = True
        build['complete_at'] = build['started_at'] + datetime.timedelta(hours=2, minutes=1, seconds=4)
        self.sp.buildFinished(("build", 20, "finished"), build)

    @defer.inlineCallbacks
    def test_custom_category(self):
        yield self.createGerritStatus(
            category=renderer(lambda p: p.getProperty("buildername")))
        build = yield self.setupBuildResults(SUCCESS)
        # we make sure proper calls to txrequests have been made
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'Build started.',
                'abstain': False,
                'category': 'Builder0',
                'name': u'Builder0',
                'reporter': 'buildbot',
                'url': 'http://localhost:8080/#builders/79/builds/0',
                'value': 0,
                'duration': 'pending'
            })
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'Build done.',
                'abstain': False,
                'category': 'Builder0',
                'name': u'Builder0',
                'reporter': 'buildbot',
                'url': 'http://localhost:8080/#builders/79/builds/0',
                'value': 1,
                'duration': '2h 1m 4s'
            })
        build['complete'] = False
        build['complete_at'] = None
        self.sp.buildStarted(("build", 20, "started"), build)
        build['complete'] = True
        build['complete_at'] = build['started_at'] + datetime.timedelta(hours=2, minutes=1, seconds=4)
        self.sp.buildFinished(("build", 20, "finished"), build)

    @defer.inlineCallbacks
    def test_custom_reporter(self):
        yield self.createGerritStatus(
            reporter=renderer(lambda p: p.getProperty("buildername")))
        build = yield self.setupBuildResults(SUCCESS)
        # we make sure proper calls to txrequests have been made
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'Build started.',
                'abstain': False,
                'name': u'Builder0',
                'reporter': 'Builder0',
                'url': 'http://localhost:8080/#builders/79/builds/0',
                'value': 0,
                'duration': 'pending'
            })
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'Build done.',
                'abstain': False,
                'name': u'Builder0',
                'reporter': 'Builder0',
                'url': 'http://localhost:8080/#builders/79/builds/0',
                'value': 1,
                'duration': '2h 1m 4s'
            })
        build['complete'] = False
        build['complete_at'] = None
        self.sp.buildStarted(("build", 20, "started"), build)
        build['complete'] = True
        build['complete_at'] = build['started_at'] + datetime.timedelta(hours=2, minutes=1, seconds=4)
        self.sp.buildFinished(("build", 20, "finished"), build)

    @defer.inlineCallbacks
    def test_verbose(self):
        yield self.createGerritStatus(verbose=True)
        build = yield self.setupBuildResults(SUCCESS)
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'Build started.',
                'abstain': False,
                'name': u'Builder0',
                'reporter': 'buildbot',
                'url': 'http://localhost:8080/#builders/79/builds/0',
                'value': 0,
                'duration': 'pending'
            })
        self.setUpLogging()
        self.sp.buildStarted(("build", 20, "started"), build)
        self.assertLogged("Sending Gerrit status for")

    @defer.inlineCallbacks
    def test_not_verbose(self):
        yield self.createGerritStatus(verbose=False)
        build = yield self.setupBuildResults(SUCCESS)
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'Build started.',
                'abstain': False,
                'name': u'Builder0',
                'reporter': 'buildbot',
                'url': 'http://localhost:8080/#builders/79/builds/0',
                'value': 0,
                'duration': 'pending'
            })
        self.setUpLogging()
        self._http.quiet = True
        self.sp.buildStarted(("build", 20, "started"), build)
        self.assertWasQuiet()

    @defer.inlineCallbacks
    def test_format_duration(self):
        yield self.createGerritStatus(verbose=False)
        self.assertEqual(
            self.sp.formatDuration(datetime.timedelta(seconds=1)),
            "0m 1s")
        self.assertEqual(
            self.sp.formatDuration(datetime.timedelta(hours=1, seconds=1)),
            "1h 0m 1s")
        self.assertEqual(
            self.sp.formatDuration(datetime.timedelta(days=1, seconds=1)),
            "1 day 0h 0m 1s")
        self.assertEqual(
            self.sp.formatDuration(datetime.timedelta(days=2, seconds=1)),
            "2 days 0h 0m 1s")

    @defer.inlineCallbacks
    def test_gerrit_changes(self):
        yield self.createGerritStatus()

        # from chdict:
        chdict = TestGerritChangeSource.expected_change
        props = Properties.fromDict(dict([
            (k, (v, 'change')) for k, v in chdict['properties'].items()]))
        changes = self.sp.getGerritChanges(props)
        self.assertEqual(changes, [
            {'change_id': '4321', 'revision_id': '12'}
        ])
