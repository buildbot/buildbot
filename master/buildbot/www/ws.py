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

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Any

from autobahn.twisted.resource import WebSocketResource
from autobahn.twisted.websocket import WebSocketServerFactory
from autobahn.twisted.websocket import WebSocketServerProtocol
from autobahn.websocket.types import ConnectionDeny
from autobahn.websocket.types import ConnectionRequest
from twisted.internet import defer
from twisted.python import log

try:
    from twisted.internet.interfaces import ISSLTransport

    _HAS_SSL = True
except ImportError:
    _HAS_SSL = False


from buildbot.util import bytes2unicode
from buildbot.util import toJson
from buildbot.www import auth

if TYPE_CHECKING:
    from buildbot.master import BuildMaster
    from buildbot.mq.base import QueueRef
    from buildbot.util.twisted import InlineCallbacksType


class Subscription:
    def __init__(self, query: str, id: str):
        self.query = query
        self.id = id
        self.last_value_chksum = None


def parse_cookies(header_value: str) -> dict[str, str]:
    cookies: dict[str, str] = {}

    # autobahn appends multiple cookies using ','
    for kv1 in header_value.split(","):
        for kv in kv1.split(";"):
            kv = kv.lstrip()
            try:
                k, v = kv.split("=", 1)
                cookies[k] = v
            except ValueError:
                pass
    return cookies


def get_ws_sitepath(path: str) -> list[bytes]:
    parts = path.split('/')
    if len(parts) > 0 and parts[-1] == 'ws':
        parts.pop()
    return [p.encode('utf-8') for p in parts if p]


class WsProtocol(WebSocketServerProtocol):
    def __init__(self, master: BuildMaster):
        super().__init__()
        self.master = master
        self.qrefs: dict[str, QueueRef] | None = {}
        self.debug = self.master.config.www.get("debug", False)

    def to_json(self, msg: dict[str, Any]) -> bytes:
        return json.dumps(msg, default=toJson, separators=(",", ":")).encode()

    def send_json_message(self, **msg: Any) -> defer.Deferred:
        return self.sendMessage(self.to_json(msg))

    def send_error(self, error: str, code: int, _id: str | None) -> defer.Deferred:
        return self.send_json_message(error=error, code=code, _id=_id)

    def onMessage(self, frame: bytes, isBinary: bool) -> defer.Deferred | None:
        """
        Parse the incoming request.
        """
        if self.debug:
            log.msg(f"FRAME {bytes2unicode(frame)}")

        frame_dict = json.loads(bytes2unicode(frame))
        _id = frame_dict.get("_id")
        _type = frame_dict.pop("type", None)
        if _id is None and _type is None:
            return self.send_error(
                error="no '_id' or 'type' in websocket frame", code=400, _id=None
            )

        cmd = frame_dict.pop("cmd", None)
        if cmd is None:
            return self.send_error(error="no 'cmd' in websocket frame", code=400, _id=None)
        cmdmeth = "cmd_" + cmd

        meth = getattr(self, cmdmeth, None)
        if meth is None:
            return self.send_error(error=f"no such command type '{cmd}'", code=404, _id=_id)
        try:
            return meth(**frame_dict)
        except TypeError as e:
            return self.send_error(error=f"Invalid method argument '{e!s}'", code=400, _id=_id)
        except Exception as e:
            log.err(e, f"while calling command {cmdmeth}")
            return self.send_error(error=f"Internal Error '{e!s}'", code=500, _id=_id)

    # legacy protocol methods

    def ack(self, _id: str) -> defer.Deferred:
        return self.send_json_message(msg="OK", code=200, _id=_id)

    def parsePath(self, path: str) -> tuple[str | None, ...]:
        path_parts = path.split("/")
        return tuple(str(p) if p != "*" else None for p in path_parts)

    def isPath(self, path: Any) -> bool:
        if not isinstance(path, str):
            return False
        return True

    @defer.inlineCallbacks
    def cmd_startConsuming(self, path: str, _id: str) -> InlineCallbacksType[None]:
        if not self.isPath(path):
            yield self.send_json_message(error=f"invalid path format '{path!s}'", code=400, _id=_id)
            return

        # if it's already subscribed, don't leak a subscription
        if self.qrefs is not None and path in self.qrefs:
            yield self.ack(_id=_id)
            return

        def callback(key: list[str], message: Any) -> defer.Deferred:
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
    def cmd_stopConsuming(self, path: str, _id: str) -> InlineCallbacksType[None]:
        if not self.isPath(path):
            yield self.send_json_message(error=f"invalid path format '{path!s}'", code=400, _id=_id)
            return

        # only succeed if path has been started
        if self.qrefs is not None and path in self.qrefs:
            qref = self.qrefs.pop(path)
            yield qref.stopConsuming()
            yield self.ack(_id=_id)
            return
        yield self.send_json_message(error=f"path was not consumed '{path!s}'", code=400, _id=_id)

    def cmd_ping(self, _id: str) -> None:
        self.send_json_message(msg="pong", code=200, _id=_id)

    def connectionLost(self, reason: Any) -> None:
        if self.debug:
            log.msg("connection lost", system=self)
        if self.qrefs is not None:
            for qref in self.qrefs.values():
                qref.stopConsuming()

        self.qrefs = None  # to be sure we don't add any more

    def is_secure(self) -> bool:
        return _HAS_SSL and ISSLTransport.providedBy(self.transport)

    @defer.inlineCallbacks
    def onConnect(self, request: ConnectionRequest) -> InlineCallbacksType[None]:
        www = self.master.www
        sitepath = get_ws_sitepath(request.path)

        cookies = parse_cookies(request.headers.get('cookie', ''))
        token = cookies.get(auth.build_cookie_name(self.is_secure(), sitepath).decode('utf-8'))

        try:
            if token is None:
                user_info = auth.build_anonymous_user_info()
            else:
                user_info = auth.parse_user_info_from_token(token, www.site.session_secret)

            # assume that if user cannot access /masters endpoint, then it can't access anything
            yield www.authz.assertUserAllowed('masters', 'get', {}, user_info)
        except Exception as e:
            raise ConnectionDeny(403, "Forbidden") from e


class WsProtocolFactory(WebSocketServerFactory):
    def __init__(self, master: BuildMaster):
        super().__init__()
        self.master = master
        pingInterval = self.master.config.www.get("ws_ping_interval", 0)
        self.setProtocolOptions(webStatus=False, autoPingInterval=pingInterval)

    def buildProtocol(self, addr: Any) -> WsProtocol:
        p = WsProtocol(self.master)
        p.factory = self
        return p


class WsResource(WebSocketResource):
    def __init__(self, master: BuildMaster):
        super().__init__(WsProtocolFactory(master))
