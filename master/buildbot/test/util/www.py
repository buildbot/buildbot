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

from future.moves.urllib.parse import unquote as urlunquote
from future.utils import iteritems

import cgi
import mock
import os
import pkg_resources

from buildbot.test.fake import fakemaster
from buildbot.util import json
from buildbot.www import auth
from buildbot.www import authz
from cStringIO import StringIO
from twisted.internet import defer
from twisted.web import server
from uuid import uuid1


class FakeSession(object):
    pass


class FakeRequest(object):
    written = ''
    finished = False
    redirected_to = None
    rendered_resource = None
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
        self.postpath = list(map(urlunquote, path[1:].split('/')))

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

    def setResponseCode(self, code):
        self.responseCode = code

    def setHeader(self, hdr, value):
        self.headers.setdefault(hdr, []).append(value)

    def getHeader(self, key):
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

    def make_master(self, url=None, **kwargs):
        master = fakemaster.make_master(wantData=True, testcase=self)
        self.master = master
        master.www = mock.Mock()  # to handle the resourceNeedsReconfigs call
        master.www.getUserInfos = lambda _: getattr(self.master.session, "user_info", {"anonymous": True})
        cfg = dict(port=None, auth=auth.NoAuth(), authz=authz.Authz())
        cfg.update(kwargs)
        master.config.www = cfg
        if url is not None:
            master.config.buildbotURL = url
        self.master.session = FakeSession()
        self.master.authz = cfg["authz"]
        self.master.authz.setMaster(self.master)
        return master

    def make_request(self, path=None, method='GET'):
        self.request = FakeRequest(path)
        self.request.session = self.master.session
        self.request.method = method
        return self.request

    def render_resource(self, rsrc, path='/', accept=None, method='GET',
                        origin=None, access_control_request_method=None,
                        extraHeaders=None, request=None):
        if not request:
            request = self.make_request(path, method=method)
            if accept:
                request.input_headers['accept'] = accept
            if origin:
                request.input_headers['origin'] = origin
            if access_control_request_method:
                request.input_headers['access-control-request-method'] = \
                    access_control_request_method
            if extraHeaders is not None:
                request.input_headers.update(extraHeaders)

        rv = rsrc.render(request)
        if rv != server.NOT_DONE_YET:
            if rv is not None:
                request.write(rv)
            request.finish()
        return request.deferred

    def render_control_resource(self, rsrc, path='/', params={},
                                requestJson=None, action="notfound", id=None,
                                content_type='application/json'):
        # pass *either* a request or postpath
        id = id or self.UUID
        request = self.make_request(path)
        request.method = "POST"
        request.content = StringIO(requestJson or json.dumps(
            {"jsonrpc": "2.0", "method": action, "params": params, "id": id}))
        request.input_headers = {'content-type': content_type}
        rv = rsrc.render(request)
        if rv != server.NOT_DONE_YET:
            d = defer.succeed(rv)
        else:
            d = request.deferred

        @d.addCallback
        def check(_json):
            res = json.loads(_json)
            self.assertIn("jsonrpc", res)
            self.assertEqual(res["jsonrpc"], "2.0")
            if not requestJson:
                # requestJson is used for invalid requests, so don't expect ID
                self.assertIn("id", res)
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
            got['contentType'] = self.request.headers['content-type']
            exp['contentType'] = [contentType]
        if responseCode is not None:
            got['responseCode'] = str(self.request.responseCode)
            exp['responseCode'] = str(responseCode)
        for header, value in iteritems(headers):
            got[header] = self.request.headers.get(header)
            exp[header] = value
        self.assertEqual(got, exp)
