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
from unittest.case import SkipTest

from mock import Mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import www
from buildbot.util import bytes2unicode
from buildbot.www import ws


class WsResource(TestReactorMixin, www.WwwTestMixin, unittest.TestCase):
    def setUp(self):
        self.setup_test_reactor(use_asyncio=True)
        self.master = master = self.make_master(
            url="h:/a/b/", wantMq=True, wantGraphql=True
        )
        self.skip_graphql = False
        if not self.master.graphql.enabled:
            self.skip_graphql = True
        self.ws = ws.WsResource(master)
        self.proto = self.ws._factory.buildProtocol("me")
        self.proto.sendMessage = Mock(spec=self.proto.sendMessage)

    def assert_called_with_json(self, obj, expected_json):
        jsonArg = obj.call_args[0][0]
        jsonArg = bytes2unicode(jsonArg)
        actual_json = json.loads(jsonArg)
        self.assertEqual(actual_json, expected_json)

    def do_onConnect(self, protocols):
        self.proto.is_graphql = None

        class FakeRequest:
            pass

        r = FakeRequest()
        r.protocols = protocols
        return self.proto.onConnect(r)

    def test_onConnect(self):
        self.assertEqual(self.do_onConnect([]), None)
        self.assertEqual(self.do_onConnect(["foo", "graphql-websocket"]), None)
        self.assertEqual(self.proto.is_graphql, None)  # undecided yet
        self.assertEqual(self.do_onConnect(["graphql-ws"]), "graphql-ws")
        self.assertEqual(self.proto.is_graphql, True)
        self.assertEqual(self.do_onConnect(["foo", "graphql-ws"]), "graphql-ws")
        self.assertEqual(self.proto.is_graphql, True)

    def test_ping(self):
        self.proto.onMessage(json.dumps(dict(cmd="ping", _id=1)), False)
        self.assert_called_with_json(
            self.proto.sendMessage, {"msg": "pong", "code": 200, "_id": 1}
        )

    def test_bad_cmd(self):
        self.proto.onMessage(json.dumps(dict(cmd="poing", _id=1)), False)
        self.assert_called_with_json(
            self.proto.sendMessage,
            {"_id": 1, "code": 404, "error": "no such command type 'poing'"},
        )

    def test_no_cmd(self):
        self.proto.onMessage(json.dumps(dict(_id=1)), False)
        self.assert_called_with_json(
            self.proto.sendMessage,
            {"_id": None, "code": 400, "error": "no 'cmd' in websocket frame"},
        )

    def test_too_many_arguments(self):
        self.proto.onMessage(json.dumps(dict(_id=1, cmd="ping", foo="bar")), False)
        self.assert_called_with_json(
            self.proto.sendMessage,
            {
                "_id": 1,
                "code": 400,
                "error": "Invalid method argument 'cmd_ping() got an unexpected keyword "
                "argument 'foo''",
            },
        )

    def test_too_many_arguments_graphql(self):
        self.proto.is_graphql = True
        self.proto.onMessage(
            json.dumps(dict(id=1, type="connection_init", foo="bar")), False
        )
        self.assert_called_with_json(
            self.proto.sendMessage,
            {
                "id": None,
                "message": "Invalid method argument 'graphql_cmd_connection_init() got an "
                "unexpected keyword argument 'foo''",
                "type": "error",
            },
        )

    def test_no_type_while_graphql(self):
        self.proto.is_graphql = True
        self.proto.onMessage(json.dumps(dict(_id=1, cmd="ping")), False)
        self.assert_called_with_json(
            self.proto.sendMessage,
            {
                "id": None,
                "message": "missing 'type' in websocket frame when already started using "
                "graphql",
                "type": "error",
            },
        )

    def test_type_while_not_graphql(self):
        self.proto.is_graphql = False
        self.proto.onMessage(json.dumps(dict(_id=1, type="ping")), False)
        self.assert_called_with_json(
            self.proto.sendMessage,
            {
                "_id": None,
                "error": "using 'type' in websocket frame when "
                "already started using buildbot protocol",
                "code": 400,
            },
        )

    def test_no_id(self):
        self.proto.onMessage(json.dumps(dict(cmd="ping")), False)
        self.assert_called_with_json(
            self.proto.sendMessage,
            {
                "_id": None,
                "code": 400,
                "error": "no '_id' or 'type' in websocket frame",
            },
        )

    def test_startConsuming(self):
        self.proto.onMessage(
            json.dumps(dict(cmd="startConsuming", path="builds/*/*", _id=1)), False
        )
        self.assert_called_with_json(
            self.proto.sendMessage, {"msg": "OK", "code": 200, "_id": 1}
        )
        self.master.mq.verifyMessages = False
        self.master.mq.callConsumer(("builds", "1", "new"), {"buildid": 1})
        self.assert_called_with_json(
            self.proto.sendMessage, {"k": "builds/1/new", "m": {"buildid": 1}}
        )

    def test_startConsumingBadPath(self):
        self.proto.onMessage(
            json.dumps(dict(cmd="startConsuming", path={}, _id=1)), False
        )
        self.assert_called_with_json(
            self.proto.sendMessage,
            {"_id": 1, "code": 400, "error": "invalid path format '{}'"},
        )

    def test_stopConsumingNotRegistered(self):
        self.proto.onMessage(
            json.dumps(dict(cmd="stopConsuming", path="builds/*/*", _id=1)), False
        )
        self.assert_called_with_json(
            self.proto.sendMessage,
            {"_id": 1, "code": 400, "error": "path was not consumed 'builds/*/*'"},
        )

    def test_stopConsuming(self):
        self.proto.onMessage(
            json.dumps(dict(cmd="startConsuming", path="builds/*/*", _id=1)), False
        )
        self.assert_called_with_json(
            self.proto.sendMessage, {"msg": "OK", "code": 200, "_id": 1}
        )
        self.proto.onMessage(
            json.dumps(dict(cmd="stopConsuming", path="builds/*/*", _id=2)), False
        )
        self.assert_called_with_json(
            self.proto.sendMessage, {"msg": "OK", "code": 200, "_id": 2}
        )

    # graphql
    def test_connection_init(self):
        self.proto.onMessage(json.dumps(dict(type="connection_init")), False)
        self.assert_called_with_json(self.proto.sendMessage, {"type": "connection_ack"})

    @defer.inlineCallbacks
    def test_start_stop_graphql(self):
        if self.skip_graphql:
            raise SkipTest("graphql-core not installed")
        yield self.proto.onMessage(
            json.dumps(
                dict(type="start", payload=dict(query="{builders{name}}"), id=1)
            ),
            False,
        )
        self.assertEqual(len(self.proto.graphql_subs), 1)
        self.assert_called_with_json(
            self.proto.sendMessage,
            {
                "payload": {
                    "data": {"builders": []},
                    "errors": None,
                },
                "type": "data",
                "id": 1,
            },
        )
        self.proto.sendMessage.reset_mock()
        yield self.proto.graphql_dispatch_events.function()
        self.proto.sendMessage.assert_not_called()

        # auto create a builder in the db
        yield self.master.db.builders.findBuilderId("builder1")
        self.master.mq.callConsumer(
            ("builders", "1", "started"),
            {"name": "builder1", "masterid": 1, "builderid": 1},
        )
        self.assertNotEqual(self.proto.graphql_dispatch_events.phase, 0)
        # then force the call anyway to speed up the test
        yield self.proto.graphql_dispatch_events.function()
        self.assert_called_with_json(
            self.proto.sendMessage,
            {
                "payload": {
                    "data": {"builders": [{"name": "builder1"}]},
                    "errors": None,
                },
                "type": "data",
                "id": 1,
            },
        )

        yield self.proto.onMessage(json.dumps(dict(type="stop", id=1)), False)

        self.assertEqual(len(self.proto.graphql_subs), 0)

    @defer.inlineCallbacks
    def test_start_graphql_bad_query(self):
        if self.skip_graphql:
            raise SkipTest("graphql-core not installed")
        yield self.proto.onMessage(
            json.dumps(
                dict(type="start", payload=dict(query="{builders{not_existing}}"), id=1)
            ),
            False,
        )
        self.assert_called_with_json(
            self.proto.sendMessage,
            {
                "payload": {
                    "data": None,
                    "errors": [
                        {
                            "locations": [{"column": 11, "line": 1}],
                            "message": "Cannot query field 'not_existing' on type 'Builder'.",
                        }
                    ],
                },
                "id": 1,
                "type": "data",
            },
        )
        self.assertEqual(len(self.proto.graphql_subs), 0)
