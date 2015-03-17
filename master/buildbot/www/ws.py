# This file is part of .  Buildbot is free software: you can
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
# Copyright  Team Members

from buildbot.util import json
from twisted.internet import defer
from twisted.python import log

from autobahn.twisted.resource import WebSocketResource
from autobahn.twisted.websocket import WebSocketServerFactory
from autobahn.twisted.websocket import WebSocketServerProtocol


class WsProtocol(WebSocketServerProtocol):

    def __init__(self, master):
        self.master = master
        self.qrefs = {}

    def sendJsonMessage(self, **msg):
        self.sendMessage(json.dumps(msg).encode('utf8'))

    def onMessage(self, frame, isBinary):
        log.msg("FRAME %s" % frame)
        # parse the incoming request

        frame = json.loads(frame)
        _id = frame.get("_id")
        if _id is None:
            self.sendJsonMessage(error="no '_id' in websocket frame", code=400, _id=None)
            return
        cmd = frame.pop("cmd", None)
        if cmd is None:
            self.sendJsonMessage(error="no 'cmd' in websocket frame", code=400, _id=None)
            return
        cmdmeth = "cmd_" + cmd
        meth = getattr(self, cmdmeth, None)
        if meth is None:
            self.sendJsonMessage(error="no such command '%s'" % (cmd, ), code=404, _id=_id)
            return
        try:
            meth(**frame)
        except TypeError as e:
            self.sendJsonMessage(error="Invalid method argument '%s'" % (str(e), ), code=400, _id=_id)
            return
        except Exception as e:
            self.sendJsonMessage(error="Internal Error '%s'" % (str(e), ), code=500, _id=_id)
            log.err("while calling command %s" % (cmd, ))
            return

    def ack(self, _id):
        return self.sendJsonMessage(msg="OK", code=200, _id=_id)

    def parsePath(self, path):
        path = path.split("/")
        return tuple([str(p) if p != "*" else None for p in path])

    @defer.inlineCallbacks
    def cmd_startConsuming(self, path, _id):
        # if it's already subscribed, don't leak a subscription
        if path in self.qrefs:
            self.ack(_id=_id)
            return

        def callback(key, message):
            self.sendJsonMessage(key="/".join(key), message=message)

        qref = yield self.master.mq.startConsuming(callback, self.parsePath(path))

        if path in self.qrefs or self.qrefs is None:  # race conditions handling
            qref.stopConsuming()

        self.qrefs[path] = qref
        self.ack(_id=_id)

    def cmd_ping(self, _id):
        self.sendJsonMessage(msg="pong", code=200, _id=_id)

    def connectionLost(self, reason):
        log.msg("connection lost", system=self)
        for qref in self.qrefs.values():
            qref.stopConsuming()
        self.qrefs = None  # to be sure we don't add any more


class WsProtocolFactory(WebSocketServerFactory):

    def __init__(self, master):
        WebSocketServerFactory.__init__(self)
        self.master = master

    def buildProtocol(self, addr):
        p = WsProtocol(self.master)
        p.factory = self
        return p


class WsResource(WebSocketResource):

    def __init__(self, master):
        WebSocketResource.__init__(self, WsProtocolFactory(master))
