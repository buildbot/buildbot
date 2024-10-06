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

from twisted.trial import unittest

from buildbot.process.properties import Interpolate
from buildbot.process.properties import Properties
from buildbot.process.properties import renderer
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.reporters.generators.build import BuildStartEndStatusGenerator
from buildbot.reporters.gerrit_verify_status import GerritVerifyStatusPush
from buildbot.reporters.message import MessageFormatterRenderable
from buildbot.test.fake import fakemaster
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import logging
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.test.util.reporter import ReporterTestMixin


class TestGerritVerifyStatusPush(
    TestReactorMixin, ReporterTestMixin, ConfigErrorsMixin, logging.LoggingMixin, unittest.TestCase
):
    async def setUp(self):
        self.setup_test_reactor()
        self.setup_reporter_test()
        self.reporter_test_props = {'gerrit_changes': [{'change_id': 12, 'revision_id': 2}]}

        self.master = fakemaster.make_master(self, wantData=True, wantDb=True, wantMq=True)

        await self.master.startService()

    async def createGerritStatus(self, **kwargs):
        auth = kwargs.pop('auth', ('log', Interpolate('pass')))

        self._http = await fakehttpclientservice.HTTPClientService.getService(
            self.master, self, "gerrit", auth=('log', 'pass'), debug=None, verify=None
        )
        self.sp = GerritVerifyStatusPush("gerrit", auth=auth, **kwargs)
        await self.sp.setServiceParent(self.master)

    def tearDown(self):
        return self.master.stopService()

    async def test_basic(self):
        await self.createGerritStatus()
        build = await self.insert_build_new()
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'Build started.',
                'abstain': False,
                'name': 'Builder0',
                'reporter': 'buildbot',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'value': 0,
                'duration': 'pending',
            },
        )
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'Build done.',
                'abstain': False,
                'name': 'Builder0',
                'reporter': 'buildbot',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'value': 1,
                'duration': '2h 1m 4s',
            },
        )
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'Build done.',
                'abstain': False,
                'name': 'Builder0',
                'reporter': 'buildbot',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'value': -1,
                'duration': '2h 1m 4s',
            },
        )
        await self.sp._got_event(('builds', 20, 'new'), build)
        build['complete'] = True
        build['complete_at'] = build['started_at'] + datetime.timedelta(
            hours=2, minutes=1, seconds=4
        )
        build['results'] = SUCCESS
        await self.sp._got_event(('builds', 20, 'finished'), build)
        build['results'] = FAILURE
        await self.sp._got_event(('builds', 20, 'finished'), build)

    async def test_custom_description(self):
        start_formatter = MessageFormatterRenderable(Interpolate("started %(prop:buildername)s"))
        end_formatter = MessageFormatterRenderable(Interpolate("finished %(prop:buildername)s"))

        generator = BuildStartEndStatusGenerator(
            start_formatter=start_formatter, end_formatter=end_formatter
        )

        await self.createGerritStatus(generators=[generator])
        build = await self.insert_build_new()
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'started Builder0',
                'abstain': False,
                'name': 'Builder0',
                'reporter': 'buildbot',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'value': 0,
                'duration': 'pending',
            },
        )
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'finished Builder0',
                'abstain': False,
                'name': 'Builder0',
                'reporter': 'buildbot',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'value': 1,
                'duration': '2h 1m 4s',
            },
        )
        await self.sp._got_event(('builds', 20, 'new'), build)
        build['complete'] = True
        build['complete_at'] = build['started_at'] + datetime.timedelta(
            hours=2, minutes=1, seconds=4
        )
        build['results'] = SUCCESS
        await self.sp._got_event(('builds', 20, 'finished'), build)

    async def test_custom_name(self):
        await self.createGerritStatus(verification_name=Interpolate("builder %(prop:buildername)s"))
        build = await self.insert_build_new()
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'Build started.',
                'abstain': False,
                'name': 'builder Builder0',
                'reporter': 'buildbot',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'value': 0,
                'duration': 'pending',
            },
        )
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'Build done.',
                'abstain': False,
                'name': 'builder Builder0',
                'reporter': 'buildbot',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'value': 1,
                'duration': '2h 1m 4s',
            },
        )
        await self.sp._got_event(('builds', 20, 'new'), build)
        build['complete'] = True
        build['complete_at'] = build['started_at'] + datetime.timedelta(
            hours=2, minutes=1, seconds=4
        )
        build['results'] = SUCCESS
        await self.sp._got_event(('builds', 20, 'finished'), build)

    async def test_custom_abstain(self):
        await self.createGerritStatus(
            abstain=renderer(lambda p: p.getProperty("buildername") == 'Builder0')
        )
        build = await self.insert_build_new()
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'Build started.',
                'abstain': True,
                'name': 'Builder0',
                'reporter': 'buildbot',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'value': 0,
                'duration': 'pending',
            },
        )
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'Build done.',
                'abstain': True,
                'name': 'Builder0',
                'reporter': 'buildbot',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'value': 1,
                'duration': '2h 1m 4s',
            },
        )
        await self.sp._got_event(('builds', 20, 'new'), build)
        build['complete'] = True
        build['complete_at'] = build['started_at'] + datetime.timedelta(
            hours=2, minutes=1, seconds=4
        )
        build['results'] = SUCCESS
        await self.sp._got_event(('builds', 20, 'finished'), build)

    async def test_custom_category(self):
        await self.createGerritStatus(category=renderer(lambda p: p.getProperty("buildername")))
        build = await self.insert_build_new()
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'Build started.',
                'abstain': False,
                'category': 'Builder0',
                'name': 'Builder0',
                'reporter': 'buildbot',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'value': 0,
                'duration': 'pending',
            },
        )
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'Build done.',
                'abstain': False,
                'category': 'Builder0',
                'name': 'Builder0',
                'reporter': 'buildbot',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'value': 1,
                'duration': '2h 1m 4s',
            },
        )
        await self.sp._got_event(('builds', 20, 'new'), build)
        build['complete'] = True
        build['complete_at'] = build['started_at'] + datetime.timedelta(
            hours=2, minutes=1, seconds=4
        )
        build['results'] = SUCCESS
        await self.sp._got_event(('builds', 20, 'finished'), build)

    async def test_custom_reporter(self):
        await self.createGerritStatus(reporter=renderer(lambda p: p.getProperty("buildername")))
        build = await self.insert_build_new()
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'Build started.',
                'abstain': False,
                'name': 'Builder0',
                'reporter': 'Builder0',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'value': 0,
                'duration': 'pending',
            },
        )
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'Build done.',
                'abstain': False,
                'name': 'Builder0',
                'reporter': 'Builder0',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'value': 1,
                'duration': '2h 1m 4s',
            },
        )
        await self.sp._got_event(('builds', 20, 'new'), build)
        build['complete'] = True
        build['complete_at'] = build['started_at'] + datetime.timedelta(
            hours=2, minutes=1, seconds=4
        )
        build['results'] = SUCCESS
        await self.sp._got_event(('builds', 20, 'finished'), build)

    async def test_verbose(self):
        await self.createGerritStatus(verbose=True)
        build = await self.insert_build_new()
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'Build started.',
                'abstain': False,
                'name': 'Builder0',
                'reporter': 'buildbot',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'value': 0,
                'duration': 'pending',
            },
        )
        self.setUpLogging()
        await self.sp._got_event(('builds', 20, 'new'), build)
        self.assertLogged("Sending Gerrit status for")

    async def test_not_verbose(self):
        await self.createGerritStatus(verbose=False)
        build = await self.insert_build_new()
        self._http.expect(
            method='post',
            ep='/a/changes/12/revisions/2/verify-status~verifications',
            json={
                'comment': 'Build started.',
                'abstain': False,
                'name': 'Builder0',
                'reporter': 'buildbot',
                'url': 'http://localhost:8080/#/builders/79/builds/0',
                'value': 0,
                'duration': 'pending',
            },
        )
        self.setUpLogging()
        self._http.quiet = True
        await self.sp._got_event(('builds', 20, 'new'), build)
        self.assertWasQuiet()

    async def test_format_duration(self):
        await self.createGerritStatus(verbose=False)
        self.assertEqual(self.sp.formatDuration(datetime.timedelta(seconds=1)), "0m 1s")
        self.assertEqual(self.sp.formatDuration(datetime.timedelta(hours=1, seconds=1)), "1h 0m 1s")
        self.assertEqual(
            self.sp.formatDuration(datetime.timedelta(days=1, seconds=1)), "1 day 0h 0m 1s"
        )
        self.assertEqual(
            self.sp.formatDuration(datetime.timedelta(days=2, seconds=1)), "2 days 0h 0m 1s"
        )

    async def test_gerrit_changes(self):
        await self.createGerritStatus()

        # from chdict:
        change_props = {
            'event.change.owner.email': 'dustin@mozilla.com',
            'event.change.subject': 'fix 1234',
            'event.change.project': 'pr',
            'event.change.owner.name': 'Dustin',
            'event.change.number': '4321',
            'event.change.url': 'http://buildbot.net',
            'event.change.branch': 'br',
            'event.type': 'patchset-created',
            'event.patchSet.revision': 'abcdef',
            'event.patchSet.number': '12',
            'event.source': 'GerritChangeSource',
        }

        props = Properties.fromDict({k: (v, 'change') for k, v in change_props.items()})
        changes = self.sp.getGerritChanges(props)
        self.assertEqual(changes, [{'change_id': '4321', 'revision_id': '12'}])
