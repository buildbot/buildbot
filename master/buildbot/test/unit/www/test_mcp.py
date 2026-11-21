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
from buildbot.www.authz import Forbidden

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
        # www is a Mock here; authorization is exercised explicitly per test.
        # (Mock blocks attribute names starting with "assert", so set it.)
        self.master.www.assertUserAllowed = lambda *a, **k: defer.succeed(None)
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
            fakedb.Step(id=50, number=0, name="compile", buildid=15),
            fakedb.Log(id=60, stepid=50, name="text", slug="text", type="t", num_lines=4),
            fakedb.LogChunk(
                logid=60,
                first_line=0,
                last_line=3,
                content="alpha\nbeta\nERROR boom\ngamma",
            ),
            # a stdio (type 's') log: each line carries a leading channel char
            fakedb.Log(id=61, stepid=50, name="stdio", slug="stdio", type="s", num_lines=3),
            fakedb.LogChunk(
                logid=61,
                first_line=0,
                last_line=2,
                content="ohello\neoops ERROR\nodone",
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
            {
                "get_status",
                "get_builders",
                "get_workers",
                "get_recent_builds",
                "get_build",
                "get_build_logs",
                "force_build",
                "cancel_build",
            },
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

    @defer.inlineCallbacks
    def test_get_build_logs_manifest(self) -> InlineCallbacksType[None]:
        res = yield self._call("get_build_logs", {"build_id": 15})
        data = self._tool_data(res)
        self.assertEqual(data["build_id"], 15)
        self.assertEqual({lg["slug"] for lg in data["logs"]}, {"text", "stdio"})
        self.assertTrue(all(lg["step"] == 0 for lg in data["logs"]))

    @defer.inlineCallbacks
    def test_get_build_logs_content_text(self) -> InlineCallbacksType[None]:
        # a text (type 't') log is returned verbatim, with no stripping
        res = yield self._call("get_build_logs", {"build_id": 15, "step": 0, "log": "text"})
        data = self._tool_data(res)
        self.assertEqual(data["lines_returned"], 4)
        self.assertIn("alpha", data["content"])
        self.assertIn("ERROR boom", data["content"])

    @defer.inlineCallbacks
    def test_get_build_logs_search_text(self) -> InlineCallbacksType[None]:
        res = yield self._call(
            "get_build_logs", {"build_id": 15, "step": 0, "log": "text", "query": "ERROR"}
        )
        data = self._tool_data(res)
        self.assertEqual(data["match_count"], 1)
        self.assertIn("ERROR boom", data["matches"][0]["text"])
        self.assertEqual(data["matches"][0]["line"], 2)

    @defer.inlineCallbacks
    def test_get_build_logs_content_stdio_strips_channel(self) -> InlineCallbacksType[None]:
        # stdio (type 's') lines carry a leading channel char (o/e/h) which must
        # be stripped from the returned content.
        res = yield self._call("get_build_logs", {"build_id": 15, "step": 0, "log": "stdio"})
        data = self._tool_data(res)
        self.assertEqual(data["lines_returned"], 3)
        self.assertEqual(data["content"], "hello\noops ERROR\ndone")
        self.assertNotIn("ohello", data["content"])

    @defer.inlineCallbacks
    def test_get_build_logs_search_stdio_strips_channel(self) -> InlineCallbacksType[None]:
        res = yield self._call(
            "get_build_logs", {"build_id": 15, "step": 0, "log": "stdio", "query": "ERROR"}
        )
        data = self._tool_data(res)
        self.assertEqual(data["match_count"], 1)
        # the matched text is the line without its leading channel character
        self.assertEqual(data["matches"][0]["text"], "oops ERROR")
        self.assertEqual(data["matches"][0]["line"], 1)

    @defer.inlineCallbacks
    def test_get_build_logs_unknown_build(self) -> InlineCallbacksType[None]:
        res = yield self._call("get_build_logs", {"build_id": 999})
        self.assertTrue(res["result"]["isError"])

    @defer.inlineCallbacks
    def test_force_build(self) -> InlineCallbacksType[None]:
        calls = []

        def fake_control(action: str, args: dict[str, Any], path: Any) -> defer.Deferred[Any]:
            calls.append((action, args, path))
            return defer.succeed((1, {21: 2}))

        self.master.data.control = fake_control
        res = yield self._call(
            "force_build", {"scheduler": "force", "builder": "builder-a", "reason": "ci"}
        )
        data = self._tool_data(res)
        self.assertTrue(data["forced"])
        self.assertEqual(calls[0][0], "force")
        self.assertEqual(calls[0][2], ("forceschedulers", "force"))
        self.assertEqual(calls[0][1]["builderid"], 21)
        self.assertEqual(calls[0][1]["reason"], "ci")

    @defer.inlineCallbacks
    def test_force_build_requires_scheduler(self) -> InlineCallbacksType[None]:
        res = yield self._call("force_build", {"builder": "builder-a"})
        self.assertTrue(res["result"]["isError"])

    @defer.inlineCallbacks
    def test_cancel_build(self) -> InlineCallbacksType[None]:
        calls = []

        def fake_control(action: str, args: dict[str, Any], path: Any) -> defer.Deferred[Any]:
            calls.append((action, args, path))
            return defer.succeed(None)

        self.master.data.control = fake_control
        res = yield self._call("cancel_build", {"build_id": 18, "reason": "stop it"})
        data = self._tool_data(res)
        self.assertTrue(data["stopped"])
        self.assertEqual(calls[0][0], "stop")
        self.assertEqual(calls[0][2], ("builds", 18))
        self.assertEqual(calls[0][1]["reason"], "stop it")

    @defer.inlineCallbacks
    def test_cancel_build_not_found(self) -> InlineCallbacksType[None]:
        res = yield self._call("cancel_build", {"build_id": 999})
        self.assertTrue(res["result"]["isError"])

    @defer.inlineCallbacks
    def test_write_tool_authz_denied(self) -> InlineCallbacksType[None]:
        control_called = []
        self.master.www.assertUserAllowed = lambda *a: defer.fail(Forbidden(b"need role"))

        def fake_control(*a: Any) -> defer.Deferred[Any]:
            control_called.append(a)
            return defer.succeed(None)

        self.master.data.control = fake_control
        res = yield self._call("cancel_build", {"build_id": 18})
        self.assertTrue(res["result"]["isError"])
        # authorization must be checked before any control action runs
        self.assertEqual(control_called, [])
