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

import datetime
import json
import re
from typing import Any
from unittest import mock

import jwt
from autobahn.websocket.types import ConnectionDeny
from autobahn.websocket.types import ConnectionRequest
from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import www
from buildbot.util import bytes2unicode
from buildbot.www import auth
from buildbot.www import ws


class WsResource(TestReactorMixin, www.WwwTestMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.master = master = yield self.make_master(url="h:/a/b/", wantMq=True, wantGraphql=True)
        self.ws = ws.WsResource(master)
        self.proto = self.ws._factory.buildProtocol("me")
        self.proto.sendMessage = mock.Mock(spec=self.proto.sendMessage)

    def assert_called_with_json(self, obj, expected_json):
        jsonArg = obj.call_args[0][0]
        jsonArg = bytes2unicode(jsonArg)
        actual_json = json.loads(jsonArg)

        keys_to_pop = []
        for key in expected_json:
            if hasattr(expected_json[key], 'match'):
                keys_to_pop.append(key)
                regex = expected_json[key]
                value = actual_json[key]
                self.assertRegex(value, regex)

        for key in keys_to_pop:
            expected_json.pop(key)
            actual_json.pop(key)

        self.assertEqual(actual_json, expected_json)

    def test_ping(self):
        self.proto.onMessage(json.dumps({"cmd": 'ping', "_id": 1}), False)
        self.assert_called_with_json(self.proto.sendMessage, {"msg": "pong", "code": 200, "_id": 1})

    def test_bad_cmd(self):
        self.proto.onMessage(json.dumps({"cmd": 'poing', "_id": 1}), False)
        self.assert_called_with_json(
            self.proto.sendMessage,
            {"_id": 1, "code": 404, "error": "no such command type 'poing'"},
        )

    def test_no_cmd(self):
        self.proto.onMessage(json.dumps({"_id": 1}), False)
        self.assert_called_with_json(
            self.proto.sendMessage,
            {"_id": None, "code": 400, "error": "no 'cmd' in websocket frame"},
        )

    def test_too_many_arguments(self):
        self.proto.onMessage(json.dumps({"_id": 1, "cmd": 'ping', "foo": 'bar'}), False)
        self.assert_called_with_json(
            self.proto.sendMessage,
            {
                "_id": 1,
                "code": 400,
                "error": re.compile(".*Invalid method argument.*"),
            },
        )

    def test_no_id(self):
        self.proto.onMessage(json.dumps({"cmd": 'ping'}), False)
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
            json.dumps({"cmd": 'startConsuming', "path": 'builds/*/*', "_id": 1}), False
        )
        self.assert_called_with_json(self.proto.sendMessage, {"msg": "OK", "code": 200, "_id": 1})
        self.master.mq.verifyMessages = False
        self.master.mq.callConsumer(("builds", "1", "new"), {"buildid": 1})
        self.assert_called_with_json(
            self.proto.sendMessage, {"k": "builds/1/new", "m": {"buildid": 1}}
        )

    def test_startConsumingBadPath(self):
        self.proto.onMessage(json.dumps({"cmd": 'startConsuming', "path": {}, "_id": 1}), False)
        self.assert_called_with_json(
            self.proto.sendMessage,
            {"_id": 1, "code": 400, "error": "invalid path format '{}'"},
        )

    def test_stopConsumingNotRegistered(self):
        self.proto.onMessage(
            json.dumps({"cmd": 'stopConsuming', "path": 'builds/*/*', "_id": 1}), False
        )
        self.assert_called_with_json(
            self.proto.sendMessage,
            {"_id": 1, "code": 400, "error": "path was not consumed 'builds/*/*'"},
        )

    def test_stopConsuming(self):
        self.proto.onMessage(
            json.dumps({"cmd": 'startConsuming', "path": 'builds/*/*', "_id": 1}), False
        )
        self.assert_called_with_json(self.proto.sendMessage, {"msg": "OK", "code": 200, "_id": 1})
        self.proto.onMessage(
            json.dumps({"cmd": 'stopConsuming', "path": 'builds/*/*', "_id": 2}), False
        )
        self.assert_called_with_json(self.proto.sendMessage, {"msg": "OK", "code": 200, "_id": 2})

    def build_token(self, expired: bool, user_info: dict[str, Any]) -> str:
        delta = datetime.timedelta(weeks=1)
        if expired:
            delta = -delta

        expiration = datetime.datetime.now(datetime.timezone.utc) + delta

        payload = {'user_info': user_info, 'exp': expiration}
        return jwt.encode(
            payload, self.master.www.site.session_secret, algorithm=auth.SESSION_SECRET_ALGORITHM
        )

    @defer.inlineCallbacks
    def test_on_connect_no_ssl(self):
        self.master.www = mock.Mock()
        self.master.www.authz = mock.Mock()
        self.master.www.authz.assertUserAllowed = mock.Mock(return_value=defer.succeed(None))

        request = ConnectionRequest(
            path='/ws',
            headers={'cookie': ''},
            peer='tcp:127.0.0.1:1234',
            host='localhost',
            origin='http://localhost',
            protocols=[],
            version=13,
            params={},
            extensions=[],
        )
        yield self.proto.onConnect(request)
        self.master.www.authz.assertUserAllowed.assert_called_once_with(
            'masters', 'get', {}, {'anonymous': True}
        )

    @defer.inlineCallbacks
    def test_on_connect_with_token(self):
        self.master.www = mock.Mock()
        self.master.www.site = mock.Mock()
        self.master.www.site.session_secret = 'secret'
        self.master.www.authz = mock.Mock()
        self.master.www.authz.assertUserAllowed = mock.Mock(return_value=defer.succeed(None))

        token = self.build_token(expired=False, user_info={'some': 'payload'})

        request = ConnectionRequest(
            path='/ws',
            headers={'cookie': f'TWISTED_SESSION={token}'},
            peer='tcp:127.0.0.1:1234',
            host='localhost',
            origin='http://localhost',
            protocols=[],
            version=13,
            params={},
            extensions=[],
        )

        yield self.proto.onConnect(request)
        self.master.www.authz.assertUserAllowed.assert_called_once_with(
            'masters', 'get', {}, {'some': 'payload'}
        )

    @defer.inlineCallbacks
    def test_on_connect_with_expired_token(self):
        self.master.www = mock.Mock()
        self.master.www.site = mock.Mock()
        self.master.www.site.session_secret = 'secret'
        self.master.www.authz = mock.Mock()
        self.master.www.authz.assertUserAllowed = mock.Mock(return_value=defer.succeed(None))

        token = self.build_token(expired=True, user_info={'some': 'payload'})

        request = ConnectionRequest(
            path='/ws',
            headers={'cookie': f'TWISTED_SESSION={token}'},
            peer='tcp:127.0.0.1:1234',
            host='localhost',
            origin='http://localhost',
            protocols=[],
            version=13,
            params={},
            extensions=[],
        )

        with self.assertRaises(ConnectionDeny) as cm:
            yield self.proto.onConnect(request)
        self.assertEqual(cm.exception.args, (403, 'Forbidden'))

    @defer.inlineCallbacks
    def test_on_connect_invalid_token(self):
        self.master.www = mock.Mock()
        self.master.www.site = mock.Mock()
        self.master.www.site.session_secret = 'secret'
        self.master.www.authz = mock.Mock()

        request = ConnectionRequest(
            path='/ws',
            headers={'cookie': 'TWISTED_SESSION=invalid_token'},
            peer='tcp:127.0.0.1:1234',
            host='localhost',
            origin='http://localhost',
            protocols=[],
            version=13,
            params={},
            extensions=[],
        )

        with self.assertRaises(ConnectionDeny) as cm:
            yield self.proto.onConnect(request)
        self.assertEqual(cm.exception.args, (403, 'Forbidden'))
        self.assertEqual(len(self.flushLoggedErrors(jwt.exceptions.DecodeError)), 1)

    @defer.inlineCallbacks
    def test_on_connect_with_ssl(self):
        self.master.www = mock.Mock()
        self.master.www.site = mock.Mock()
        self.master.www.site.session_secret = 'secret'
        self.master.www.authz = mock.Mock()
        self.master.www.authz.assertUserAllowed = mock.Mock(return_value=defer.succeed(None))

        self.proto.is_secure = mock.Mock(return_value=True)

        token = self.build_token(expired=False, user_info={'some': 'payload'})
        request = ConnectionRequest(
            path='/ws',
            headers={'cookie': f'TWISTED_SECURE_SESSION={token}'},
            peer='tcp:127.0.0.1:1234',
            host='localhost',
            origin='http://localhost',
            protocols=[],
            version=13,
            params={},
            extensions=[],
        )

        yield self.proto.onConnect(request)
        self.master.www.authz.assertUserAllowed.assert_called_once_with(
            'masters', 'get', {}, {'some': 'payload'}
        )

    @defer.inlineCallbacks
    def test_on_connect_different_path(self):
        self.master.www = mock.Mock()
        self.master.www.site = mock.Mock()
        self.master.www.site.session_secret = 'secret'
        self.master.www.authz = mock.Mock()
        self.master.www.authz.assertUserAllowed = mock.Mock(return_value=defer.succeed(None))

        token = self.build_token(expired=False, user_info={'some': 'payload'})

        request = ConnectionRequest(
            path='/custom/ws',
            headers={'cookie': f'TWISTED_SESSION_custom={token}'},
            peer='tcp:127.0.0.1:1234',
            host='localhost',
            origin='http://localhost',
            protocols=[],
            version=13,
            params={},
            extensions=[],
        )

        yield self.proto.onConnect(request)
        self.master.www.authz.assertUserAllowed.assert_called_once_with(
            'masters', 'get', {}, {'some': 'payload'}
        )

    @defer.inlineCallbacks
    def test_on_connect_direct_connection_deny(self):
        self.master.www = mock.Mock()
        self.master.www.site = mock.Mock()
        self.master.www.site.session_secret = 'secret'
        self.master.www.authz = mock.Mock()
        self.master.www.authz.assertUserAllowed = mock.Mock(
            side_effect=ConnectionDeny(403, "Forbidden")
        )

        request = ConnectionRequest(
            path='/ws',
            headers={'cookie': 'auth_token=valid'},
            peer='tcp:127.0.0.1:1234',
            host='localhost',
            origin='http://localhost',
            protocols=[],
            version=13,
            params={},
            extensions=[],
        )

        with self.assertRaises(ConnectionDeny) as cm:
            yield self.proto.onConnect(request)
        self.assertEqual(cm.exception.args, (403, 'Forbidden'))


class TestParseCookies(unittest.TestCase):
    def test_parse_cookies_single(self):
        result = ws.parse_cookies("name=value")
        self.assertEqual(result, {"name": "value"})

    def test_parse_cookies_multiple_comma(self):
        result = ws.parse_cookies("name1=value1,name2=value2")
        self.assertEqual(result, {"name1": "value1", "name2": "value2"})

    def test_parse_cookies_multiple_semicolon(self):
        result = ws.parse_cookies("name1=value1; name2=value2")
        self.assertEqual(result, {"name1": "value1", "name2": "value2"})

    def test_parse_cookies_mixed_separators(self):
        result = ws.parse_cookies("name1=value1,name2=value2; name3=value3")
        self.assertEqual(result, {"name1": "value1", "name2": "value2", "name3": "value3"})

    def test_parse_cookies_malformed(self):
        result = ws.parse_cookies("name1=value1; invalid; name2=value2")
        self.assertEqual(result, {"name1": "value1", "name2": "value2"})

    def test_parse_cookies_empty(self):
        result = ws.parse_cookies("")
        self.assertEqual(result, {})
