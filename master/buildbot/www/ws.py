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

import hashlib
import json

from autobahn.twisted.resource import WebSocketResource
from autobahn.twisted.websocket import WebSocketServerFactory
from autobahn.twisted.websocket import WebSocketServerProtocol
from twisted.internet import defer
from twisted.python import log

from buildbot.util import bytes2unicode
from buildbot.util import debounce
from buildbot.util import toJson


class Subscription:
    def __init__(self, query, id):
        self.query = query
        self.id = id
        self.last_value_chksum = None


class WsProtocol(WebSocketServerProtocol):
    def __init__(self, master):
        super().__init__()
        self.master = master
        self.qrefs = {}
        self.debug = self.master.config.www.get("debug", False)
        self.is_graphql = None
        self.graphql_subs = {}
        self.graphql_consumer = None

    def to_json(self, msg):
        return json.dumps(msg, default=toJson, separators=(",", ":")).encode()

    def send_json_message(self, **msg):
        return self.sendMessage(self.to_json(msg))

    def send_error(self, error, code, _id):
        if self.is_graphql:
            return self.send_json_message(message=error, type="error", id=_id)

        return self.send_json_message(error=error, code=code, _id=_id)

    def onMessage(self, frame, isBinary):
        """
        Parse the incoming request.
        Can be either a graphql ws:
        https://github.com/apollographql/subscriptions-transport-ws/blob/master/PROTOCOL.md
        or legacy "buildbot" protocol (documented in www-server.rst)
        as they are very similar, we use the same routing method, distinguishing by the
        presence of _id or type attributes.
        """
        if self.debug:
            log.msg(f"FRAME {frame}")

        frame = json.loads(bytes2unicode(frame))
        _id = frame.get("_id")
        _type = frame.pop("type", None)
        if _id is None and _type is None:
            return self.send_error(
                error="no '_id' or 'type' in websocket frame", code=400, _id=None
            )

        if _type is not None:
            cmdmeth = "graphql_cmd_" + _type
            if self.is_graphql is None:
                self.is_graphql = True
            elif not self.is_graphql:
                return self.send_error(
                    error="using 'type' in websocket frame when"
                    " already started using buildbot protocol",
                    code=400,
                    _id=None,
                )
        else:
            if self.is_graphql is None:
                self.is_graphql = False
            elif self.is_graphql:
                return self.send_error(
                    error="missing 'type' in websocket frame when"
                    " already started using graphql",
                    code=400,
                    _id=None,
                )
            self.is_graphql = False
            cmd = frame.pop("cmd", None)
            if cmd is None:
                return self.send_error(
                    error="no 'cmd' in websocket frame", code=400, _id=None
                )
            cmdmeth = "cmd_" + cmd

        meth = getattr(self, cmdmeth, None)
        if meth is None:
            return self.send_error(
                error=f"no such command type '{cmd}'", code=404, _id=_id
            )
        try:
            return meth(**frame)
        except TypeError as e:
            return self.send_error(
                error=f"Invalid method argument '{str(e)}'", code=400, _id=_id
            )
        except Exception as e:
            log.err(e, f"while calling command {cmdmeth}")
            return self.send_error(
                error=f"Internal Error '{str(e)}'", code=500, _id=_id
            )

    # legacy protocol methods

    def ack(self, _id):
        return self.send_json_message(msg="OK", code=200, _id=_id)

    def parsePath(self, path):
        path = path.split("/")
        return tuple(str(p) if p != "*" else None for p in path)

    def isPath(self, path):
        if not isinstance(path, str):
            return False
        return True

    @defer.inlineCallbacks
    def cmd_startConsuming(self, path, _id):
        if not self.isPath(path):
            yield self.send_json_message(
                error=f"invalid path format '{str(path)}'", code=400, _id=_id
            )
            return

        # if it's already subscribed, don't leak a subscription
        if self.qrefs is not None and path in self.qrefs:
            yield self.ack(_id=_id)
            return

        def callback(key, message):
            # protocol is deliberately concise in size
            return self.send_json_message(k="/".join(key), m=message)

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
            yield self.send_json_message(
                error=f"invalid path format '{str(path)}'", code=400, _id=_id
            )
            return

        # only succeed if path has been started
        if path in self.qrefs:
            qref = self.qrefs.pop(path)
            yield qref.stopConsuming()
            yield self.ack(_id=_id)
            return
        yield self.send_json_message(
            error=f"path was not consumed '{str(path)}'", code=400, _id=_id
        )

    def cmd_ping(self, _id):
        self.send_json_message(msg="pong", code=200, _id=_id)

    # graphql methods
    def graphql_cmd_connection_init(self, payload=None, id=None):
        return self.send_json_message(type="connection_ack")

    def graphql_got_event(self, key, message):
        # for now, we just ignore the events
        # an optimization would be to only re-run queries that
        # are impacted by the event
        self.graphql_dispatch_events()

    @debounce.method(0.1)
    @defer.inlineCallbacks
    def graphql_dispatch_events(self):
        """We got a bunch of events, dispatch them to the subscriptions
        For now, we just re-run all queries and see if they changed.
        We use a debouncer to ensure we only do that once a second per connection
        """
        for sub in self.graphql_subs.values():
            yield self.graphql_run_query(sub)

    @defer.inlineCallbacks
    def graphql_run_query(self, sub):
        res = yield self.master.graphql.query(sub.query)
        if res.data is None:
            # bad query, better not re-run it!
            self.graphql_cmd_stop(sub.id)
        errors = None
        if res.errors:
            errors = [e.formatted for e in res.errors]
        data = self.to_json(
            {
                "type": "data",
                "payload": {"data": res.data, "errors": errors},
                "id": sub.id,
            }
        )
        cksum = hashlib.blake2b(data).digest()
        if cksum != sub.last_value_chksum:
            sub.last_value_chksum = cksum
            self.sendMessage(data)

    @defer.inlineCallbacks
    def graphql_cmd_start(self, id, payload=None):
        sub = Subscription(payload.get("query"), id)
        if not self.graphql_subs:
            # consume all events!
            self.graphql_consumer = yield self.master.mq.startConsuming(
                self.graphql_got_event, (None, None, None)
            )

        self.graphql_subs[id] = sub
        yield self.graphql_run_query(sub)

    def graphql_cmd_stop(self, id, payload=None):
        if id in self.graphql_subs:
            del self.graphql_subs[id]
        else:
            return self.send_error(
                error="stopping unknown subscription", code=400, _id=id
            )
        if not self.graphql_subs and self.graphql_consumer:
            self.graphql_consumer.stopConsuming()
            self.graphql_consumer = None

        return None

    def connectionLost(self, reason):
        if self.debug:
            log.msg("connection lost", system=self)
        for qref in self.qrefs.values():
            qref.stopConsuming()
        if self.graphql_consumer:
            self.graphql_consumer.stopConsuming()

        self.qrefs = None  # to be sure we don't add any more

    def onConnect(self, request):
        # we don't mandate graphql-ws subprotocol, but if it is presented
        # we must acknowledge it
        if "graphql-ws" in request.protocols:
            self.is_graphql = True
            return "graphql-ws"
        return None


class WsProtocolFactory(WebSocketServerFactory):
    def __init__(self, master):
        super().__init__()
        self.master = master
        pingInterval = self.master.config.www.get("ws_ping_interval", 0)
        self.setProtocolOptions(webStatus=False, autoPingInterval=pingInterval)

    def buildProtocol(self, addr):
        p = WsProtocol(self.master)
        p.factory = self
        return p


class WsResource(WebSocketResource):
    def __init__(self, master):
        super().__init__(WsProtocolFactory(master))
