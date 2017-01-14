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
from twisted.trial import unittest

from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.util import httpclientservice
from buildbot.util import service


class myTestedService(service.BuildbotService):
    name = 'myTestedService'

    @defer.inlineCallbacks
    def reconfigService(self, baseurl):
        self._http = yield httpclientservice.HTTPClientService.getService(self.master, baseurl)

    @defer.inlineCallbacks
    def doGetRoot(self):
        res = yield self._http.get("/")
        # note that at this point, only the http response headers are received
        if res.code != 200:
            raise Exception("%d: server did not succeed" % (res.code))
        res_json = yield res.json()
        # res.json() returns a deferred to represent the time needed to fetch the entire body
        defer.returnValue(res_json)


class Test(unittest.SynchronousTestCase):

    def setUp(self):
        baseurl = 'http://127.0.0.1:8080'
        self.parent = service.MasterService()
        self._http = self.successResultOf(fakehttpclientservice.HTTPClientService.getFakeService(
            self.parent, self, baseurl))
        self.tested = myTestedService(baseurl)

        self.successResultOf(self.tested.setServiceParent(self.parent))
        self.successResultOf(self.parent.startService())

    def test_root(self):
        self._http.expect("get", "/", content_json={'foo': 'bar'})

        response = self.successResultOf(self.tested.doGetRoot())
        self.assertEqual(response, {'foo': 'bar'})

    def test_root_error(self):
        self._http.expect("get", "/", content_json={'foo': 'bar'}, code=404)

        response = self.failureResultOf(self.tested.doGetRoot())
        self.assertEqual(response.getErrorMessage(), '404: server did not succeed')
