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

from twisted.internet import defer
from twisted.internet import reactor
from twisted.trial import unittest
from twisted.web.resource import Resource
from twisted.web.server import Site
from twisted.web.util import redirectTo

from buildbot.process import properties
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.steps import http
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import TestBuildStepMixin

try:
    import txrequests
    assert txrequests
    import requests
    assert requests
except ImportError:
    txrequests = requests = None


# We use twisted's internal webserver instead of mocking requests
# to be sure we use the correct requests interfaces

class TestPage(Resource):
    isLeaf = True

    def render_GET(self, request):
        if request.uri == b"/404":
            request.setResponseCode(404)
            return b"404"
        elif request.uri == b'/redirect':
            return redirectTo(b'/redirected-path', request)
        elif request.uri == b"/header":
            return b"".join(request.requestHeaders.getRawHeaders(b"X-Test"))
        return b"OK"

    def render_POST(self, request):
        if request.uri == b"/404":
            request.setResponseCode(404)
            return b"404"
        return b"OK:" + request.content.read()


class TestHTTPStep(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):

    timeout = 3  # those tests should not run long

    def setUp(self):
        self.setup_test_reactor()
        if txrequests is None:
            raise unittest.SkipTest(
                "Need to install txrequests to test http steps")

        # ignore 'http_proxy' environment variable when running tests
        session = http.getSession()
        session.trust_env = False

        # port 0 means random unused port
        self.listener = reactor.listenTCP(0, Site(TestPage()))
        self.port = self.listener.getHost().port
        return self.setup_test_build_step()

    @defer.inlineCallbacks
    def tearDown(self):
        http.closeSession()
        try:
            yield self.listener.stopListening()
        finally:
            yield self.tear_down_test_build_step()

    def get_connection_string(self):
        return f"http://127.0.0.1:{self.port}"

    def getURL(self, path=""):
        return f'{self.get_connection_string()}/{path}'

    def test_get(self):
        url = self.getURL()
        self.setup_step(http.GET(url))
        self.expect_log_file('log', f"URL: {url}\nStatus: 200\n ------ Content ------\nOK")
        self.expect_log_file('content', "OK")
        self.expect_outcome(result=SUCCESS, state_string="Status code: 200")
        return self.run_step()

    def test_connection_error(self):
        def throwing_request(*args, **kwargs):
            raise requests.exceptions.ConnectionError("failed to connect")

        with mock.patch.object(http.getSession(), 'request', throwing_request):
            url = self.getURL("path")
            self.setup_step(http.GET(url))
            self.expect_outcome(result=FAILURE, state_string="Requested (failure)")
            return self.run_step()

    def test_redirect(self):
        url = self.getURL("redirect")
        self.setup_step(http.GET(url))

        expected_log = f'''
Redirected 1 times:

URL: {self.get_connection_string()}/redirect
 ------ Content ------

<html>
    <head>
        <meta http-equiv="refresh" content="0;URL=/redirected-path">
    </head>
    <body bgcolor="#FFFFFF" text="#000000">
    <a href="/redirected-path">click here</a>
    </body>
</html>
============================================================
URL: {self.get_connection_string()}/redirected-path
Status: 200
 ------ Content ------
OK'''

        self.expect_log_file('log', expected_log)
        self.expect_log_file('content', "OK")
        self.expect_outcome(result=SUCCESS, state_string="Status code: 200")
        return self.run_step()

    def test_404(self):
        url = self.getURL("404")
        self.setup_step(http.GET(url))
        self.expect_log_file('log', f"URL: {url}\n ------ Content ------\n404")
        self.expect_log_file('content', "404")
        self.expect_outcome(result=FAILURE, state_string="Status code: 404 (failure)")
        return self.run_step()

    def test_method_not_allowed(self):
        url = self.getURL("path")
        self.setup_step(http.PUT(url))
        self.expect_outcome(result=FAILURE, state_string="Status code: 501 (failure)")
        return self.run_step()

    def test_post(self):
        url = self.getURL("path")
        self.setup_step(http.POST(url))
        self.expect_outcome(result=SUCCESS, state_string="Status code: 200")
        self.expect_log_file('log', f"URL: {url}\nStatus: 200\n ------ Content ------\nOK:")
        self.expect_log_file('content', "OK:")
        return self.run_step()

    def test_post_data(self):
        url = self.getURL("path")
        self.setup_step(http.POST(url, data='mydata'))
        self.expect_outcome(result=SUCCESS, state_string="Status code: 200")
        self.expect_log_file('log',
                           f"URL: {url}\nStatus: 200\n ------ Content ------\nOK:mydata")
        self.expect_log_file('content', "OK:mydata")
        return self.run_step()

    def test_post_data_dict(self):
        url = self.getURL("path")

        self.setup_step(http.POST(url, data={'key1': 'value1'}))
        self.expect_outcome(result=SUCCESS, state_string="Status code: 200")
        self.expect_log_file('log', f'''\
URL: {url}
Status: 200
 ------ Content ------
OK:key1=value1''')
        self.expect_log_file('content', "OK:key1=value1")
        return self.run_step()

    def test_header(self):
        url = self.getURL("header")
        self.setup_step(http.GET(url, headers={"X-Test": "True"}))
        self.expect_log_file('log',
                             f"URL: {url}\nStatus: 200\n ------ Content ------\nTrue")
        self.expect_outcome(result=SUCCESS, state_string="Status code: 200")
        return self.run_step()

    @defer.inlineCallbacks
    def test_hidden_header(self):
        url = self.getURL("header")
        self.setup_step(http.GET(url, headers={"X-Test": "True"},
                                hide_request_headers=["X-Test"],
                                hide_response_headers=["Content-Length"]))
        self.expect_log_file('log',
                             f"URL: {url}\nStatus: 200\n ------ Content ------\nTrue")
        self.expect_outcome(result=SUCCESS, state_string="Status code: 200")
        yield self.run_step()
        self.assertIn("X-Test: <HIDDEN>", self.step.logs['log'].header)
        self.assertIn("Content-Length: <HIDDEN>", self.step.logs['log'].header)

    def test_params_renderable(self):
        url = self.getURL()
        self.setup_step(http.GET(url, params=properties.Property("x")))
        self.properties.setProperty(
            'x', {'param_1': 'param_1', 'param_2': 2}, 'here')
        self.expect_log_file('log',
            f"URL: {url}?param_1=param_1&param_2=2\nStatus: 200\n ------ Content ------\nOK")
        self.expect_log_file('content', "OK")
        self.expect_outcome(result=SUCCESS, state_string="Status code: 200")
        return self.run_step()
