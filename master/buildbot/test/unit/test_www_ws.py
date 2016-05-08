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
from mock import Mock
from twisted.trial import unittest

from buildbot.test.util import www
from buildbot.util import json
from buildbot.www import ws


class WsResource(www.WwwTestMixin, unittest.TestCase):

    def setUp(self):
        self.master = master = self.make_master(url='h:/a/b/')
        self.ws = ws.WsResource(master)
        self.proto = self.ws._factory.buildProtocol("me")
        self.gotMsg = []
        self.proto.sendMessage = Mock(spec=self.proto.sendMessage)

    def test_ping(self):
        self.proto.onMessage(json.dumps(dict(cmd="ping", _id=1)), False)
        self.proto.sendMessage.assert_called_with(
            '{"msg":"pong","code":200,"_id":1}')

    def test_bad_cmd(self):
        self.proto.onMessage(json.dumps(dict(cmd="poing", _id=1)), False)
        self.proto.sendMessage.assert_called_with(
            '{"_id":1,"code":404,"error":"no such command \'poing\'"}')

    def test_no_cmd(self):
        self.proto.onMessage(json.dumps(dict(_id=1)), False)
        self.proto.sendMessage.assert_called_with(
            '{"_id":null,"code":400,"error":"no \'cmd\' in websocket frame"}')

    def test_no_id(self):
        self.proto.onMessage(json.dumps(dict(cmd="ping")), False)
        self.proto.sendMessage.assert_called_with(
            '{"_id":null,"code":400,"error":"no \'_id\' in websocket frame"}')

    def test_startConsuming(self):
        self.proto.onMessage(
            json.dumps(dict(cmd="startConsuming", path="builds/*/*", _id=1)), False)
        self.proto.sendMessage.assert_called_with(
            '{"msg":"OK","code":200,"_id":1}')
        self.master.mq.verifyMessages = False
        self.master.mq.callConsumer(("builds", "1", "new"), {"buildid": 1})
        self.proto.sendMessage.assert_called_with(
            '{"k":"builds/1/new","m":{"buildid":1}}')

    def test_startConsumingBadPath(self):
        self.proto.onMessage(
            json.dumps(dict(cmd="startConsuming", path={}, _id=1)), False)
        self.proto.sendMessage.assert_called_with(
            '{"_id":1,"code":400,"error":"invalid path format \'{}\'"}')

    def test_stopConsumingNotRegistered(self):
        self.proto.onMessage(
            json.dumps(dict(cmd="stopConsuming", path="builds/*/*", _id=1)), False)
        self.proto.sendMessage.assert_called_with(
            '{"_id":1,"code":400,"error":"path was not consumed \'builds/*/*\'"}')

    def test_stopConsuming(self):
        self.proto.onMessage(
            json.dumps(dict(cmd="startConsuming", path="builds/*/*", _id=1)), False)
        self.proto.sendMessage.assert_called_with(
            '{"msg":"OK","code":200,"_id":1}')
        self.proto.onMessage(
            json.dumps(dict(cmd="stopConsuming", path="builds/*/*", _id=2)), False)
        self.proto.sendMessage.assert_called_with(
            '{"msg":"OK","code":200,"_id":2}')
