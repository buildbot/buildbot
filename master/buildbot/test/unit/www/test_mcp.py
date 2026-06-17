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

from buildbot.test import fakedb
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


class McpTools(TestReactorMixin, www.WwwTestMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = yield self.make_master(url=b'http://localhost:8010/')  # type: ignore[arg-type]
        self.mcp = mcp.McpResource(self.master)
        self.mcp.reconfigResource(self.master.config)
        yield self.master.db.insert_test_data([
            fakedb.Builder(id=21, name="builder-a"),
            fakedb.Builder(id=22, name="builder-b"),
            fakedb.Master(id=1),
            fakedb.Worker(id=2, name="worker-1"),
            fakedb.Buildset(id=17),
            fakedb.BuildRequest(id=16, buildsetid=17, builderid=21),
            fakedb.Build(
                id=15,
                number=1,
                buildrequestid=16,
                masterid=1,
                workerid=2,
                builderid=21,
                complete_at=1304262300,
                state_string="finished",
                results=0,
            ),
            fakedb.Build(
                id=18,
                number=2,
                buildrequestid=16,
                masterid=1,
                workerid=2,
                builderid=21,
                state_string="building",
                results=None,
            ),
        ])

    @defer.inlineCallbacks
    def _call(
        self, name: str, arguments: dict[str, Any] | None = None, msg_id: int = 1
    ) -> InlineCallbacksType[dict[str, Any]]:
        yield self.render_resource(
            self.mcp,
            b'/',
            method=b'POST',
            content=unicode2bytes(
                json.dumps({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "method": "tools/call",
                    "params": {"name": name, "arguments": arguments or {}},
                })
            ),
            content_type=b'application/json',
        )
        return json.loads(bytes2unicode(self.request.written))

    def _tool_data(self, res: dict[str, Any]) -> dict[str, Any]:
        result = res["result"]
        self.assertFalse(result.get("isError"), msg=result)
        return json.loads(result["content"][0]["text"])

    @defer.inlineCallbacks
    def test_tools_list(self) -> InlineCallbacksType[None]:
        yield self.render_resource(
            self.mcp,
            b'/',
            method=b'POST',
            content=unicode2bytes(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})),
            content_type=b'application/json',
        )
        res = json.loads(bytes2unicode(self.request.written))
        names = {t["name"] for t in res["result"]["tools"]}
        self.assertEqual(
            names,
            {"get_status", "get_builders", "get_workers", "get_recent_builds", "get_build"},
        )

    @defer.inlineCallbacks
    def test_get_status(self) -> InlineCallbacksType[None]:
        res = yield self._call("get_status")
        data = self._tool_data(res)
        self.assertEqual(data["builders"], 2)
        self.assertEqual(data["workers"]["total"], 1)
        self.assertEqual([b["buildid"] for b in data["running_builds"]], [18])

    @defer.inlineCallbacks
    def test_get_builders(self) -> InlineCallbacksType[None]:
        res = yield self._call("get_builders")
        data = self._tool_data(res)
        self.assertEqual(data["total_count"], 2)
        self.assertFalse(data["has_more"])
        self.assertEqual([b["name"] for b in data["builders"]], ["builder-a", "builder-b"])

    @defer.inlineCallbacks
    def test_get_builders_pagination(self) -> InlineCallbacksType[None]:
        res = yield self._call("get_builders", {"limit": 1})
        data = self._tool_data(res)
        self.assertEqual(data["returned"], 1)
        self.assertEqual(data["total_count"], 2)
        self.assertTrue(data["has_more"])

    @defer.inlineCallbacks
    def test_get_workers(self) -> InlineCallbacksType[None]:
        res = yield self._call("get_workers")
        data = self._tool_data(res)
        self.assertEqual([w["name"] for w in data["workers"]], ["worker-1"])
        self.assertFalse(data["workers"][0]["connected"])

    @defer.inlineCallbacks
    def test_get_recent_builds(self) -> InlineCallbacksType[None]:
        res = yield self._call("get_recent_builds")
        data = self._tool_data(res)
        self.assertEqual([b["buildid"] for b in data["builds"]], [18, 15])

    @defer.inlineCallbacks
    def test_get_recent_builds_only_running(self) -> InlineCallbacksType[None]:
        res = yield self._call("get_recent_builds", {"only_running": True})
        data = self._tool_data(res)
        self.assertEqual([b["buildid"] for b in data["builds"]], [18])

    @defer.inlineCallbacks
    def test_get_recent_builds_by_builder(self) -> InlineCallbacksType[None]:
        res = yield self._call("get_recent_builds", {"builder": "builder-a"})
        data = self._tool_data(res)
        self.assertEqual(sorted(b["buildid"] for b in data["builds"]), [15, 18])

    @defer.inlineCallbacks
    def test_get_recent_builds_unknown_builder(self) -> InlineCallbacksType[None]:
        res = yield self._call("get_recent_builds", {"builder": "nope"})
        self.assertTrue(res["result"]["isError"])

    @defer.inlineCallbacks
    def test_get_build(self) -> InlineCallbacksType[None]:
        res = yield self._call("get_build", {"build_id": 15})
        data = self._tool_data(res)
        self.assertEqual(data["build"]["buildid"], 15)
        self.assertEqual(data["build"]["result"], "success")

    @defer.inlineCallbacks
    def test_get_build_running_label(self) -> InlineCallbacksType[None]:
        res = yield self._call("get_build", {"build_id": 18})
        data = self._tool_data(res)
        self.assertEqual(data["build"]["result"], "running")

    @defer.inlineCallbacks
    def test_get_build_not_found(self) -> InlineCallbacksType[None]:
        res = yield self._call("get_build", {"build_id": 999})
        self.assertTrue(res["result"]["isError"])

    @defer.inlineCallbacks
    def test_unknown_tool(self) -> InlineCallbacksType[None]:
        res = yield self._call("does_not_exist")
        self.assertEqual(res["error"]["code"], -32602)
