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

import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.fake import endpoint
from buildbot.test.util import www
from buildbot.test.util.misc import TestReactorMixin
from buildbot.util import unicode2bytes
from buildbot.www import graphql

try:
    import graphql as graphql_core
except ImportError:
    graphql_core = None


class V3RootResource(TestReactorMixin, www.WwwTestMixin, unittest.TestCase):
    if not graphql_core:
        skip = 'graphql is required for V3RootResource tests'

    def setUp(self):
        self.setUpTestReactor()
        self.master = self.make_master(url="http://server/path/")
        self.master.config.www["graphql"] = {"debug": True}
        self.master.data._scanModule(endpoint)
        self.rsrc = graphql.V3RootResource(self.master)
        self.rsrc.reconfigResource(self.master.config)

    def assertSimpleError(self, message_or_error, responseCode):
        if isinstance(message_or_error, list):
            errors = message_or_error
        else:
            errors = [{"message": message_or_error}]
        content = json.dumps({"data": None, "errors": errors})
        self.assertRequest(content=unicode2bytes(content), responseCode=responseCode)

    @defer.inlineCallbacks
    def test_failure(self):
        self.rsrc.renderQuery = mock.Mock(
            return_value=defer.fail(RuntimeError("oh noes"))
        )
        yield self.render_resource(
            self.rsrc,
            b"/?query={builders{name}}",
        )
        self.assertSimpleError("internal error - see logs", 500)
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)

    @defer.inlineCallbacks
    def test_invalid_http_method(self):
        yield self.render_resource(self.rsrc, b"/", method=b"PATCH")
        self.assertSimpleError("invalid HTTP method", 400)

    # https://graphql.org/learn/serving-over-http/#get-request
    @defer.inlineCallbacks
    def test_get_query(self):
        yield self.render_resource(
            self.rsrc,
            b"/?query={tests{id}}",
        )
        # TODO verify results
        self.assertRequest(responseCode=200)

    @defer.inlineCallbacks
    def test_get_noquery(self):
        yield self.render_resource(
            self.rsrc,
            b"/",
        )
        # TODO verify results
        self.assertSimpleError("GET request must contain a 'query' parameter", 400)

    # https://graphql.org/learn/serving-over-http/#post-request
    @defer.inlineCallbacks
    def test_post_query_graphql_content(self):
        yield self.render_resource(
            self.rsrc,
            method=b"POST",
            content=b"{tests{id}}",
            content_type=b"application/graphql"
        )
        # TODO verify results
        self.assertRequest(responseCode=200)

    @defer.inlineCallbacks
    def test_post_query_json_content(self):
        query = {
            "query": "{tests{id}}"
        }
        yield self.render_resource(
            self.rsrc,
            method=b"POST",
            content=json.dumps(query).encode(),
            content_type=b"application/json"
        )
        # TODO verify results
        self.assertRequest(responseCode=200)

    @defer.inlineCallbacks
    def test_post_query_json_content_operationName(self):
        query = {
            "query": "query foo {tests{id}} query bar {tests{name}}",
            "operationName": "fsoo"
        }
        yield self.render_resource(
            self.rsrc,
            method=b"POST",
            content=json.dumps(query).encode(),
            content_type=b"application/json"
        )
        self.assertSimpleError("json request unsupported fields: operationName", 400)

    @defer.inlineCallbacks
    def test_post_query_json_badcontent_type(self):

        yield self.render_resource(
            self.rsrc,
            method=b"POST",
            content=b"foo",
            content_type=b"application/foo"
        )
        self.assertSimpleError("unsupported content-type: application/foo", 400)

    @defer.inlineCallbacks
    def test_post_query_json_nocontent_type(self):

        yield self.render_resource(
            self.rsrc,
            method=b"POST"
        )
        self.assertSimpleError("no content-type", 400)

    @defer.inlineCallbacks
    def test_get_bad_query(self):
        yield self.render_resource(
            self.rsrc,
            b"/?query={notexistant{id}}",
        )
        self.assertSimpleError(
            [
                {
                    "message": "Cannot query field 'notexistant' on type 'Query'.",
                    "locations": [{"line": 1, "column": 2}],
                    "path": None,
                }
            ],
            400,
        )


class DisabledV3RootResource(TestReactorMixin, www.WwwTestMixin, unittest.TestCase):
    if not graphql_core:
        skip = 'graphql is required for V3RootResource tests'

    def setUp(self):
        self.setUpTestReactor()
        self.master = self.make_master(url="http://server/path/")
        self.master.data._scanModule(endpoint)
        self.rsrc = graphql.V3RootResource(self.master)
        self.rsrc.reconfigResource(self.master.config)

    @defer.inlineCallbacks
    def test_basic_disabled(self):
        yield self.render_resource(self.rsrc, b"/")
        self.assertRequest(
            content=unicode2bytes(
                json.dumps(
                    {"data": None, "errors": [{"message": "graphql not enabled"}]}
                )
            ),
            responseCode=501,
        )
