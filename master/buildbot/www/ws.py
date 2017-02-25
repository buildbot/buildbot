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

from __future__ import absolute_import
from __future__ import print_function
from future.utils import itervalues
from future.utils import string_types

import json

from autobahn.twisted.resource import WebSocketResource
from autobahn.twisted.websocket import WebSocketServerFactory
from autobahn.twisted.websocket import WebSocketServerProtocol
from twisted.internet import defer
from twisted.python import log

from buildbot.util import bytes2NativeString
from buildbot.util import toJson


class WsProtocol(WebSocketServerProtocol):

    def __init__(self, master):
        WebSocketServerProtocol.__init__(self)
        self.master = master
        self.qrefs = {}
        self.debug = self.master.config.www.get('debug', False)

    def sendJsonMessage(self, **msg):
        return self.sendMessage(json.dumps(msg, default=toJson, separators=(',', ':')).encode('utf8'))

    def onMessage(self, frame, isBinary):
        if self.debug:
            log.msg("FRAME %s" % frame)
        # parse the incoming request

        frame = json.loads(bytes2NativeString(frame))
        _id = frame.get("_id")
        if _id is None:
            return self.sendJsonMessage(error="no '_id' in websocket frame", code=400, _id=None)
        cmd = frame.pop("cmd", None)
        if cmd is None:
            return self.sendJsonMessage(error="no 'cmd' in websocket frame", code=400, _id=None)
        cmdmeth = "cmd_" + cmd
        meth = getattr(self, cmdmeth, None)
        if meth is None:
            return self.sendJsonMessage(error="no such command '%s'" % (cmd, ), code=404, _id=_id)
        try:
            return meth(**frame)
        except TypeError as e:
            return self.sendJsonMessage(error="Invalid method argument '%s'" % (str(e), ), code=400, _id=_id)
        except Exception as e:
            log.err("while calling command %s" % (cmd, ))
            return self.sendJsonMessage(error="Internal Error '%s'" % (str(e), ), code=500, _id=_id)

    def ack(self, _id):
        return self.sendJsonMessage(msg="OK", code=200, _id=_id)

    def parsePath(self, path):
        path = path.split("/")
        return tuple([str(p) if p != "*" else None for p in path])

    def isPath(self, path):
        if not isinstance(path, string_types):
            return False
        return True

    @defer.inlineCallbacks
    def cmd_startConsuming(self, path, _id):
        if not self.isPath(path):
            yield self.sendJsonMessage(error="invalid path format '%s'" % (str(path), ), code=400, _id=_id)
            return

        # if it's already subscribed, don't leak a subscription
        if self.qrefs is not None and path in self.qrefs:
            yield self.ack(_id=_id)
            return

        def callback(key, message):
            # protocol is deliberately concise in size
            return self.sendJsonMessage(k="/".join(key), m=message)

        qref = yield self.master.mq.startConsuming(callback, self.parsePath(path))

        # race conditions handling
        if self.qrefs is None or path in self.qrefs:
            qref.stopConsuming()

        # only store and ack if we were not disconnected in between
        if self.qrefs is not None:
            self.qrefs[path] = qref
            self.ack(_id=_id)

    @defer.inlineCallbacks
    def cmd_stopConsuming(self, path, _id):
        if not self.isPath(path):
            yield self.sendJsonMessage(error="invalid path format '%s'" % (str(path), ), code=400, _id=_id)
            return

        # only succeed if path has been started
        if path in self.qrefs:
            qref = self.qrefs.pop(path)
            yield qref.stopConsuming()
            yield self.ack(_id=_id)
            return
        yield self.sendJsonMessage(error="path was not consumed '%s'" % (str(path), ), code=400, _id=_id)

    def cmd_ping(self, _id):
        self.sendJsonMessage(msg="pong", code=200, _id=_id)

    def connectionLost(self, reason):
        if self.debug:
            log.msg("connection lost", system=self)
        for qref in itervalues(self.qrefs):
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
