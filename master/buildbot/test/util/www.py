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

    def __init__(self, postpath=None, args={}):
        self.headers = {}
        self.input_headers = {}
        self.prepath = []
        self.postpath = postpath or []
        self.deferred = defer.Deferred()
        self.args = args

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
    def getHeader(self, key, default=None):
        return self.input_headers.get(key, default)
    def processingFailed(self, f):
        self.deferred.errback(f)


class WwwTestMixin(object):
    if not list(pkg_resources.iter_entry_points('buildbot.www', 'base')):
        skip = 'builbot-www not installed'

    def make_master(self, **kwargs):
        master = fakemaster.make_master(wantData=True, testcase=self)
        cfg = dict(url='//', port=None)
        cfg.update(kwargs)
        master.config.www = cfg
        return master

    def make_request(self, postpath=None, args={}):
        self.request = FakeRequest(postpath=postpath, args=args)
        return self.request

    def render_resource(self, rsrc, postpath=None, args={}, request=None):
        # pass *either* a request or postpath (and optionally args)
        if not request:
            request = self.make_request(postpath=postpath, args=args)

        rv = rsrc.render(request)
        if rv != server.NOT_DONE_YET:
            return defer.succeed(rv)
        return request.deferred

    def render_control_resource(self, rsrc, postpath=None, args={}, action="notfound",
                                request=None, jsonRpc=True):
        # pass *either* a request or postpath (and optionally args)
        _id = str(uuid1())
        if not request:
            request = self.make_request(postpath=postpath, args=args)
            request.method = "POST"
            if jsonRpc:
                request.content = StringIO(json.dumps(
                    { "jsonrpc": "2.0", "method": action, "params": args, "id": _id}))
                request.input_headers = {'content-type': 'application/json'}
        rv = rsrc.render(request)
        if rv != server.NOT_DONE_YET:
            d = defer.succeed(rv)
        else:
            d = request.deferred
        @d.addCallback
        def check(_json):
            if jsonRpc:
                res = json.loads(_json)
                self.assertIn("jsonrpc",res)
                self.assertIn("id",res)
                self.assertEqual(res["jsonrpc"], "2.0")
                self.assertEqual(res["id"], _id)
            return json
        return d

    def assertRequest(self, content=None, contentJson=None, contentType=None,
            responseCode=None, contentDisposition=None, errorJsonRpcCode=None):
        got, exp = {}, {}
        if content is not None:
            got['content'] = self.request.written
            exp['content'] = content
        if contentJson is not None:
            got['contentJson'] = json.loads(self.request.written)
            exp['contentJson'] = contentJson
        if errorJsonRpcCode is not None:
            jsonrpc = json.loads(self.request.written)
            self.assertIn("error", jsonrpc)
            self.assertIn("code", jsonrpc["error"])
            got['errorJsonRpcCode'] = jsonrpc["error"]["code"]
            exp['errorJsonRpcCode'] = errorJsonRpcCode
        if contentType is not None:
            got['contentType'] =  self.request.headers['content-type']
            exp['contentType'] = [ contentType ]
        if responseCode is not None:
            got['responseCode'] =  self.request.responseCode
            exp['responseCode'] = responseCode
        if contentDisposition is not None:
            got['contentDisposition'] =  self.request.headers.get(
                                    'content-disposition')
            exp['contentDisposition'] = [ contentDisposition ]
        self.assertEqual(got, exp)
