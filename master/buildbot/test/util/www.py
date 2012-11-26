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

import os
from urlparse import urljoin
from buildbot.util import json
from twisted.internet import defer, reactor
from twisted.web import server
from buildbot.test.fake import fakemaster
from twisted.python import failure, log
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
            responseCode=None, contentDisposition=None, errorJsonRPC=None):
        got, exp = {}, {}
        if content is not None:
            got['content'] = self.request.written
            exp['content'] = content
        if contentJson is not None:
            got['contentJson'] = json.loads(self.request.written)
            exp['contentJson'] = contentJson
        if errorJsonRPC is not None:
            jsonrpc = json.loads(self.request.written)
            self.assertIn("error", jsonrpc)
            got['errorJsonRPC'] = jsonrpc["error"]
            exp['errorJsonRPC'] = errorJsonRPC
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
try:
    from buildbot.test.util.txghost import Ghost
    has_ghost= Ghost != None
except ImportError:
    no_ghost_message = "Need Ghost.py to run most of www_ui tests"
    has_ghost=False
    # if $REQUIRE_GHOST is set, then fail if it's not found
    if os.environ.get('REQUIRE_GHOST'):
        raise

if has_ghost:
    PUBLIC_HTML_PATH = os.environ.get('PUBLIC_HTML_PATH')
    if not PUBLIC_HTML_PATH:
        has_ghost=False
        no_ghost_message = ("Need PUBLIC_HTML_PATH environment variable which points on 'updatejs'"
                            " installed directory")
    PUBLIC_HTML_PATH = os.path.abspath(PUBLIC_HTML_PATH)
    if (not os.path.isdir(PUBLIC_HTML_PATH) or
        not os.path.isfile(os.path.join(PUBLIC_HTML_PATH,"static","js.built","dojo","dojo.js"))):
        has_ghost=False
        no_ghost_message = ("Needs PUBLIC_HTML_PATH environment variable which points on 'updatejs'"
                            " installed directory, but got" + PUBLIC_HTML_PATH)

if not has_ghost and os.environ.get('REQUIRE_GHOST'):
            raise Exception(no_ghost_message)


class WwwGhostTestMixin(object):
    if not has_ghost:
        skip = no_ghost_message

    @defer.inlineCallbacks
    def setUp(self):
        ## workaround twisted bug  http://twistedmatrix.com/trac/ticket/2386
        import twisted
        twisted.web.http._logDateTimeUsers = 1
        twisted.internet.base.DelayedCall.debug = True
        ## we cannot use self.patch, as _logDateTimeUsers is not present in all versions of twisted
        self.master = yield fakemaster.make_master_for_uitest(0, PUBLIC_HTML_PATH)
        self.url = self.master.config.www["url"]
        log.msg("listening on "+self.url)
        self.ghost = Ghost()

    @defer.inlineCallbacks
    def tearDown(self):
        from  twisted.internet.tcp import Server
        del self.ghost
        # webkit has the bad habbit on not closing the persistent
        # connections, so we need to hack them away to make trial happy
        for reader in reactor.getReaders():
            if isinstance(reader, Server):
                f = failure.Failure(Exception("test end"))
                reader.connectionLost(f)
        yield self.master.www.stopService()

    @defer.inlineCallbacks
    def doDohPageLoadRunnerTests(self, doh_tests="../../dojo/tests/colors"):
        self.ghost.wait_timeout = 200
        yield self.ghost.open(urljoin(self.url,"static/js.built/lib/tests/runner.html#"+doh_tests))
        result_selector = "#testListContainer table tfoot tr.inProgress"
        yield self.ghost.wait_for_selector(result_selector)
        result, _ = self.ghost.evaluate("dojo.map(dojo.query('"+result_selector+" .failure'),function(a){return a.textContent;});")
        errors, failures = map(int,result)
        self.assertEqual(errors, 0,"there is at least one testsuite error")
        self.assertEqual(failures, 0,"there is at least one testsuite failure")
        result, _ = self.ghost.evaluate("dojo.map(dojo.query('"+result_selector+" td'),function(a){return a.textContent;});")
        print "\n",str(result[1]).strip(),
