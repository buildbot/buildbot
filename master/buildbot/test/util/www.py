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

import json
import os
import pkg_resources
from io import BytesIO
from io import StringIO
from urllib.parse import parse_qs
from urllib.parse import unquote as urlunquote
from uuid import uuid1

import mock

from twisted.internet import defer
from twisted.web import server

from buildbot.test.fake import fakemaster
from buildbot.util import bytes2unicode
from buildbot.util import unicode2bytes
from buildbot.www import auth
from buildbot.www import authz


class FakeSession:

    def __init__(self):
        self.user_info = {"anonymous": True}

    def updateSession(self, request):
        pass


class FakeRequest:
    written = b''
    finished = False
    redirected_to = None
    rendered_resource = None
    failure = None
    method = b'GET'
    path = b'/req.path'
    responseCode = 200

    def __init__(self, path=None):
        self.headers = {}
        self.input_headers = {}
        self.prepath = []
        x = path.split(b'?', 1)
        if len(x) == 1:
            self.path = path
            self.args = {}
        else:
            path, argstring = x
            self.path = path
            self.args = parse_qs(argstring, 1)
        self.uri = self.path
        self.postpath = []
        for p in path[1:].split(b'/'):
            path = urlunquote(bytes2unicode(p))
            self.postpath.append(unicode2bytes(path))

        self.deferred = defer.Deferred()

    def write(self, data):
        self.written = self.written + data

    def redirect(self, url):
        self.redirected_to = url

    def render(self, rsrc):
        rendered_resource = rsrc
        self.deferred.callback(rendered_resource)

    def finish(self):
        self.finished = True
        if self.redirected_to is not None:
            self.deferred.callback(dict(redirected=self.redirected_to))
        else:
            self.deferred.callback(self.written)

    def setResponseCode(self, code, text=None):
        # twisted > 16 started to assert this
        assert isinstance(code, int)
        self.responseCode = code
        self.responseText = text

    def setHeader(self, hdr, value):
        assert isinstance(hdr, bytes)
        assert isinstance(value, bytes)
        self.headers.setdefault(hdr, []).append(value)

    def getHeader(self, key):
        assert isinstance(key, bytes)
        return self.input_headers.get(key)

    def processingFailed(self, f):
        self.deferred.errback(f)

    def notifyFinish(self):
        d = defer.Deferred()

        @self.deferred.addBoth
        def finished(res):
            d.callback(res)
            return res
        return d

    def getSession(self):
        return self.session


class RequiresWwwMixin:
    # mix this into a TestCase to skip if buildbot-www is not installed

    if not list(pkg_resources.iter_entry_points('buildbot.www', 'base')):
        if 'BUILDBOT_TEST_REQUIRE_WWW' in os.environ:
            raise RuntimeError('$BUILDBOT_TEST_REQUIRE_WWW is set but '
                               'buildbot-www is not installed')
        skip = 'buildbot-www not installed'


class WwwTestMixin(RequiresWwwMixin):
    UUID = str(uuid1())

    def make_master(self, wantGraphql=False, url=None, **kwargs):
        master = fakemaster.make_master(self, wantData=True, wantGraphql=wantGraphql)
        self.master = master
        master.www = mock.Mock()  # to handle the resourceNeedsReconfigs call
        master.www.getUserInfos = lambda _: getattr(
            self.master.session, "user_info", {"anonymous": True})
        cfg = dict(port=None, auth=auth.NoAuth(), authz=authz.Authz())
        cfg.update(kwargs)
        master.config.www = cfg
        if url is not None:
            master.config.buildbotURL = url
        self.master.session = FakeSession()
        self.master.authz = cfg["authz"]
        self.master.authz.setMaster(self.master)
        return master

    def make_request(self, path=None, method=b'GET'):
        self.request = FakeRequest(path)
        self.request.session = self.master.session
        self.request.method = method
        return self.request

    def render_resource(self, rsrc, path=b'/', accept=None, method=b'GET',
                        origin=None, access_control_request_method=None,
                        extraHeaders=None, request=None,
                        content=None, content_type=None):
        if not request:
            request = self.make_request(path, method=method)
            if accept:
                request.input_headers[b'accept'] = accept
            if origin:
                request.input_headers[b'origin'] = origin
            if access_control_request_method:
                request.input_headers[b'access-control-request-method'] = \
                    access_control_request_method
            if extraHeaders is not None:
                request.input_headers.update(extraHeaders)
            if content_type is not None:
                request.input_headers.update({b'content-type': content_type})
                request.content = BytesIO(content)

        rv = rsrc.render(request)
        if rv != server.NOT_DONE_YET:
            if rv is not None:
                request.write(rv)
            request.finish()
        return request.deferred

    @defer.inlineCallbacks
    def render_control_resource(self, rsrc, path=b'/', params=None,
                                requestJson=None, action="notfound", id=None,
                                content_type=b'application/json'):
        # pass *either* a request or postpath
        if params is None:
            params = {}
        id = id or self.UUID
        request = self.make_request(path)
        request.method = b"POST"
        request.content = StringIO(requestJson or json.dumps(
            {"jsonrpc": "2.0", "method": action, "params": params, "id": id}))
        request.input_headers = {b'content-type': content_type}
        rv = rsrc.render(request)
        if rv == server.NOT_DONE_YET:
            rv = yield request.deferred

        res = json.loads(bytes2unicode(rv))
        self.assertIn("jsonrpc", res)
        self.assertEqual(res["jsonrpc"], "2.0")
        if not requestJson:
            # requestJson is used for invalid requests, so don't expect ID
            self.assertIn("id", res)
            self.assertEqual(res["id"], id)

    def assertRequest(self, content=None, contentJson=None, contentType=None,
                      responseCode=None, contentDisposition=None, headers=None):
        if headers is None:
            headers = {}
        got, exp = {}, {}
        if content is not None:
            got['content'] = self.request.written
            exp['content'] = content
        if contentJson is not None:
            got['contentJson'] = json.loads(
                bytes2unicode(self.request.written))
            exp['contentJson'] = contentJson
        if contentType is not None:
            got['contentType'] = self.request.headers[b'content-type']
            exp['contentType'] = [contentType]
        if responseCode is not None:
            got['responseCode'] = str(self.request.responseCode)
            exp['responseCode'] = str(responseCode)
        for header, value in headers.items():
            got[header] = self.request.headers.get(header)
            exp[header] = value
        self.assertEqual(got, exp)
