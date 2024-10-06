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

from twisted.trial import unittest

from buildbot.process.properties import Interpolate
from buildbot.process.results import SUCCESS
from buildbot.reporters.http import HttpStatusPush
from buildbot.test.fake import fakemaster
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.test.util.misc import BuildDictLookAlike
from buildbot.test.util.reporter import ReporterTestMixin


class TestHttpStatusPush(TestReactorMixin, unittest.TestCase, ReporterTestMixin, ConfigErrorsMixin):
    async def setUp(self):
        self.setup_test_reactor()
        self.setup_reporter_test()
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True, wantMq=True)
        await self.master.startService()

    async def createReporter(self, auth=("username", "passwd"), headers=None, **kwargs):
        self._http = await fakehttpclientservice.HTTPClientService.getService(
            self.master, self, "serv", auth=auth, headers=headers, debug=None, verify=None
        )

        interpolated_auth = None
        if auth is not None:
            username, passwd = auth
            passwd = Interpolate(passwd)
            interpolated_auth = (username, passwd)

        self.sp = HttpStatusPush("serv", auth=interpolated_auth, headers=headers, **kwargs)
        await self.sp.setServiceParent(self.master)

    async def tearDown(self):
        await self.master.stopService()

    async def test_basic(self):
        await self.createReporter()
        self._http.expect("post", "", json=BuildDictLookAlike(complete=False))
        self._http.expect("post", "", json=BuildDictLookAlike(complete=True))
        build = await self.insert_build_new()
        await self.sp._got_event(('builds', 20, 'new'), build)
        build['complete'] = True
        build['results'] = SUCCESS
        await self.sp._got_event(('builds', 20, 'finished'), build)

    async def test_basic_noauth(self):
        await self.createReporter(auth=None)
        self._http.expect("post", "", json=BuildDictLookAlike(complete=False))
        self._http.expect("post", "", json=BuildDictLookAlike(complete=True))
        build = await self.insert_build_new()
        await self.sp._got_event(('builds', 20, 'new'), build)
        build['complete'] = True
        build['results'] = SUCCESS
        await self.sp._got_event(('builds', 20, 'finished'), build)

    async def test_header(self):
        await self.createReporter(headers={'Custom header': 'On'})
        self._http.expect("post", "", json=BuildDictLookAlike())
        build = await self.insert_build_finished(SUCCESS)
        await self.sp._got_event(('builds', 20, 'finished'), build)

    async def http2XX(self, code, content):
        await self.createReporter()
        self._http.expect('post', '', code=code, content=content, json=BuildDictLookAlike())
        build = await self.insert_build_finished(SUCCESS)
        await self.sp._got_event(('builds', 20, 'finished'), build)

    async def test_http200(self):
        await self.http2XX(code=200, content="OK")

    async def test_http201(self):  # e.g. GitHub returns 201
        await self.http2XX(code=201, content="Created")

    async def test_http202(self):
        await self.http2XX(code=202, content="Accepted")
