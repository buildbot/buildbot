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

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Any

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import www
from buildbot.util import bytes2unicode
from buildbot.util import unicode2bytes
from buildbot.www import mcp

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class McpProtocol(TestReactorMixin, www.WwwTestMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = yield self.make_master(url=b'http://localhost:8010/')  # type: ignore[arg-type]
        self.mcp = mcp.McpResource(self.master)
        self.mcp.reconfigResource(self.master.config)

    def _post(self, body: dict[str, Any], **kwargs: Any) -> defer.Deferred[Any]:
        return self.render_resource(
            self.mcp,
            b'/',
            method=b'POST',
            content=unicode2bytes(json.dumps(body)),
            content_type=b'application/json',
            **kwargs,
        )

    def _written_json(self) -> dict[str, Any]:
        return json.loads(bytes2unicode(self.request.written))

    @defer.inlineCallbacks
    def test_initialize(self) -> InlineCallbacksType[None]:
        yield self._post({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"},
            },
        })
        res = self._written_json()
        self.assertEqual(res["jsonrpc"], "2.0")
        self.assertEqual(res["id"], 1)
        self.assertEqual(res["result"]["protocolVersion"], "2025-11-25")
        self.assertEqual(res["result"]["serverInfo"]["name"], "buildbot")
        self.assertIn("capabilities", res["result"])

    @defer.inlineCallbacks
    def test_initialize_unknown_version_falls_back(self) -> InlineCallbacksType[None]:
        yield self._post({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "1999-01-01", "capabilities": {}},
        })
        res = self._written_json()
        self.assertEqual(res["result"]["protocolVersion"], "2025-11-25")

    @defer.inlineCallbacks
    def test_ping(self) -> InlineCallbacksType[None]:
        yield self._post({"jsonrpc": "2.0", "id": 2, "method": "ping"})
        res = self._written_json()
        self.assertEqual(res["id"], 2)
        self.assertEqual(res["result"], {})

    @defer.inlineCallbacks
    def test_initialized_notification(self) -> InlineCallbacksType[None]:
        yield self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.assertEqual(self.request.responseCode, 202)
        self.assertEqual(self.request.written, b'')

    @defer.inlineCallbacks
    def test_method_not_found(self) -> InlineCallbacksType[None]:
        yield self._post({"jsonrpc": "2.0", "id": 3, "method": "does/not/exist"})
        res = self._written_json()
        self.assertEqual(res["id"], 3)
        self.assertEqual(res["error"]["code"], -32601)

    @defer.inlineCallbacks
    def test_parse_error(self) -> InlineCallbacksType[None]:
        yield self.render_resource(
            self.mcp,
            b'/',
            method=b'POST',
            content=b'{ this is not json',
            content_type=b'application/json',
        )
        res = self._written_json()
        self.assertEqual(self.request.responseCode, 400)
        self.assertEqual(res["error"]["code"], -32700)

    @defer.inlineCallbacks
    def test_invalid_jsonrpc_version(self) -> InlineCallbacksType[None]:
        yield self._post({"jsonrpc": "1.0", "id": 4, "method": "ping"})
        res = self._written_json()
        self.assertEqual(res["error"]["code"], -32600)

    @defer.inlineCallbacks
    def test_get_not_allowed(self) -> InlineCallbacksType[None]:
        yield self.render_resource(self.mcp, b'/', method=b'GET')
        self.assertEqual(self.request.responseCode, 405)

    @defer.inlineCallbacks
    def test_invalid_origin_rejected(self) -> InlineCallbacksType[None]:
        yield self._post(
            {"jsonrpc": "2.0", "id": 5, "method": "ping"},
            origin=b'http://evil.example.com',
        )
        self.assertEqual(self.request.responseCode, 403)

    @defer.inlineCallbacks
    def test_matching_origin_allowed(self) -> InlineCallbacksType[None]:
        yield self._post(
            {"jsonrpc": "2.0", "id": 6, "method": "ping"},
            origin=b'http://localhost:8010',
        )
        res = self._written_json()
        self.assertEqual(res["id"], 6)
        self.assertEqual(res["result"], {})
