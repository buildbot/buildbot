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
from twisted.internet.error import CannotListenError
from twisted.internet.protocol import ServerFactory
from twisted.web import server
from buildbot.www import service
from buildbot.test.fake import fakemaster
from twisted.python import failure

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

    def assertRequest(self, content=None, contentJson=None, contentType=None,
            responseCode=None, contentDisposition=None):
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
        # if $REQUIRE_GHOST is set, then fail if it's not found
        if os.environ.get('REQUIRE_GHOST'):
            raise Exception(no_ghost_message)


class WwwGhostTestMixin(object):
    if not has_ghost:
        skip = no_ghost_message

    @defer.inlineCallbacks
    def setUp(self):
        # hack to prevent twisted.web.http to setup a 1 sec callback at init
        import twisted
	#twisted.internet.base.DelayedCall.debug = True
        twisted.web.http._logDateTimeUsers = 1
        portFound = False
        port = 18010
        while not portFound:
            try:
                tcp = reactor.listenTCP(port, ServerFactory())
                portFound = True
                yield tcp.stopListening()
            except CannotListenError:
                port+=1
        self.url = 'http://localhost:'+str(port)+"/"
        self.master = self.make_master(url=self.url, port=port, public_html= PUBLIC_HTML_PATH)
        self.svc = service.WWWService(self.master)
        yield self.svc.startService()
        yield self.svc.reconfigService(self.master.config)
        self.ghost = Ghost()

    @defer.inlineCallbacks
    def tearDown(self):
        from  twisted.internet.tcp import Server
        del self.ghost
        yield self.svc.stopService()
        # webkit has the bad habbit on not closing the persistent
        # connections, so we need to hack them away to make trial happy
        for reader in reactor.getReaders():
            if isinstance(reader, Server):
                f = failure.Failure(Exception("test end"))
                reader.connectionLost(f)

    @defer.inlineCallbacks
    def doPageLoadTest(self, ui_path, js_assertions, selector_to_wait = "#content div"):
        """ start ghost on the given path, and make a bunch of js assertions"""
        yield self.ghost.open(urljoin(self.url,ui_path))
        yield self.ghost.wait_for_selector(selector_to_wait)
        # import test framework in the global namespace
        # This is a kind of tricky hack in order to load doh without the _browserRunner module
        # at the end of runner.js, there is a legacy hack to load also _browserRunner, which
        # does much more than we need, including hooking console.log
        runner = open(os.path.join(PUBLIC_HTML_PATH, "static","js","util","doh","runner.js")).read()
        runner = "\n".join(runner.splitlines()[:-4])
        runner = runner.replace('define("doh/runner",', "require(")
        runner = runner.replace('return doh;',
                                """var div = document.createElement("div");
                                div.innerHTML = "<div id=doh_loaded></div>";
                                document.body.appendChild(div);
                                return doh;""")
        self.ghost.evaluate(runner)
        yield self.ghost.wait_for_selector("#doh_loaded")
        doh_boilerplate = """
             (function() {
             try {
             %(js)s
             } catch(err) {
                return String(err);
             } return "OK";
             })()
             """
        for js in js_assertions:
            result, _ = self.ghost.evaluate(doh_boilerplate%dict(js=js))
            self.assertEqual(result, "OK")
