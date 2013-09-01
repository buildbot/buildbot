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

import mock
import cgi
import os
import urllib
import pkg_resources
from buildbot.util import json
from twisted.internet import defer
from twisted.web import server
from buildbot.test.fake import fakemaster
from cStringIO import StringIO
from uuid import uuid1

class FakeRequest(object):
    written = ''
    finished = False
    redirected_to = None
    failure = None
    method = 'GET'
    path = '/req.path'
    responseCode = 200

    def __init__(self, path=None):
        self.headers = {}
        self.input_headers = {}
        self.prepath = []

        x = path.split('?', 1)
        if len(x) == 1:
            self.path = path
            self.args = {}
        else:
            path, argstring = x
            self.path = path
            self.args = cgi.parse_qs(argstring, 1)
        self.postpath = list(map(urllib.unquote, path[1:].split('/')))

        self.deferred = defer.Deferred()

    def write(self, data):
        self.written = self.written + data

    def redirect(self, url):
        self.redirected_to = url

    def finish(self):
        self.finished = True
        self.deferred.callback(self.written)

    def setResponseCode(self, code):
        self.responseCode = code

    def setHeader(self, hdr, value):
        self.headers.setdefault(hdr, []).append(value)

    def getHeader(self, key):
        return self.input_headers.get(key)

    def processingFailed(self, f):
        self.deferred.errback(f)


class RequiresWwwMixin(object):
    # mix this into a TestCase to skip if buildbot-www is not installed

    if not list(pkg_resources.iter_entry_points('buildbot.www', 'base')):
        if 'BUILDBOT_TEST_REQUIRE_WWW' in os.environ:
            raise RuntimeError('$BUILDBOT_TEST_REQUIRE_WWW is set but '
                               'buildbot-www is not installed')
        else:
            skip = 'buildbot-www not installed'


class WwwTestMixin(RequiresWwwMixin):
    UUID = str(uuid1())

    def make_master(self, **kwargs):
        master = fakemaster.make_master(wantData=True, testcase=self)
        master.www = mock.Mock() # to handle the resourceNeedsReconfigs call
        cfg = dict(url='//', port=None)
        cfg.update(kwargs)
        master.config.www = cfg
        return master

    def make_request(self, path=None, method='GET'):
        self.request = FakeRequest(path)
        self.request.method = method
        return self.request

    def render_resource(self, rsrc, path='/', accept=None, method='GET',
            origin=None, access_control_request_method=None):
        request = self.make_request(path, method=method)
        if accept:
            request.input_headers['accept'] = accept
        if origin:
            request.input_headers['origin'] = origin
        if access_control_request_method:
            request.input_headers['access-control-request-method'] = \
                    access_control_request_method

        rv = rsrc.render(request)
        if rv != server.NOT_DONE_YET:
            return defer.succeed(rv)
        return request.deferred

    def render_control_resource(self, rsrc, path='/', params={},
            requestJson=None, action="notfound", id=None):
        # pass *either* a request or postpath
        id = id or self.UUID
        request = self.make_request(path)
        request.method = "POST"
        request.content = StringIO(requestJson or json.dumps(
            {"jsonrpc": "2.0", "method": action, "params": params, "id": id}))
        request.input_headers = {'content-type': 'application/json'}
        rv = rsrc.render(request)
        if rv != server.NOT_DONE_YET:
            d = defer.succeed(rv)
        else:
            d = request.deferred
        @d.addCallback
        def check(_json):
            res = json.loads(_json)
            self.assertIn("jsonrpc",res)
            self.assertEqual(res["jsonrpc"], "2.0")
            if not requestJson:
                # requestJson is used for invalid requests, so don't expect ID
                self.assertIn("id",res)
                self.assertEqual(res["id"], id)
        return d

    def assertRequest(self, content=None, contentJson=None, contentType=None,
            responseCode=None, contentDisposition=None, headers={}):
        got, exp = {}, {}
        if content is not None:
            got['content'] = self.request.written
            exp['content'] = content
        if contentJson is not None:
            got['contentJson'] = json.loads(self.request.written)
            exp['contentJson'] = contentJson
        if contentType is not None:
            got['contentType'] =  self.request.headers['content-type']
            exp['contentType'] = [ contentType ]
        if responseCode is not None:
            got['responseCode'] =  self.request.responseCode
            exp['responseCode'] = responseCode
        for header, value in headers.iteritems():
            got[header] = self.request.headers.get(header)
            exp[header] = value
        self.assertEqual(got, exp)
