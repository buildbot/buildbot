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
from buildbot.www import websocket
from twisted.internet import protocol
from twisted.python import log


class WsProtocol(protocol.Protocol):

    def __init__(self, master):
        self.master = master
        self.qrefs = {}

    def dataReceived(self, frame):
        log.msg("FRAME %s" % frame)
        # parse the incoming request
        # TODO: error handling
        frame = json.loads(frame)
        req = frame['req']
        if req == 'startConsuming':
            path = tuple(frame['path'])
            options = frame['options']

            # if it's already subscribed, don't leak a subscription
            if path in self.qrefs:
                return

            def callback(key, message):
                content = json.dumps(dict(path=path, key=key, message=message))
                self.transport.write(content)
            qref = self.master.data.startConsuming(callback, options, path)
            self.qrefs[path] = qref

    def connectionLost(self, reason):
        log.msg("connection lost", system=self)
        for qref in self.qrefs.values():
            qref.stopConsuming()
        self.qrefs = None  # to be sure we don't add any more


class WsProtocolFactory(protocol.Factory):

    def __init__(self, master):
        self.master = master

    def buildProtocol(self, addr):
        p = WsProtocol(self.master)
        p.factory = self
        return p


class WsResource(websocket.WebSocketsResource):

    def __init__(self, master):
        websocket.WebSocketsResource.__init__(self, WsProtocolFactory(master))
