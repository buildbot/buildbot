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
from twisted.trial import unittest

from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.util import httpclientservice
from buildbot.util import service


class myTestedService(service.BuildbotService):
    name = 'myTestedService'

    @defer.inlineCallbacks
    def reconfigService(self, baseurl):
        self.http = yield httpclientservice.HTTPClientService.getService(self.master, baseurl)

    @defer.inlineCallbacks
    def doGetRoot(self):
        res = yield self.http.get("/")
        res_json = yield res.json()
        defer.returnValue(res_json)


class Test(unittest.SynchronousTestCase):

    def setUp(self):
        baseurl = 'http://127.0.0.1:8080'
        self.parent = service.MasterService()
        self.http = self.successResultOf(fakehttpclientservice.HTTPClientService.getService(
            self.parent, baseurl))
        self.tested = myTestedService(baseurl)

        self.successResultOf(self.tested.setServiceParent(self.parent))
        self.successResultOf(self.parent.startService())

    def test_root(self):
        self.http.expect("get", "/", content_json={'foo': 'bar'})

        response = self.successResultOf(self.tested.doGetRoot())
        self.assertEqual(response, {'foo': 'bar'})
