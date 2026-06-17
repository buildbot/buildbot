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

import fnmatch
import json
import re
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable
from urllib.parse import urlparse

from twisted.internet import defer
from twisted.python import log

from buildbot.util import bytes2unicode
from buildbot.util import toJson
from buildbot.util import unicode2bytes
from buildbot.www import resource
from buildbot.www.mcp.tools import McpTools
from buildbot.www.mcp.tools import ToolError

if TYPE_CHECKING:
    from twisted.web import server

    from buildbot.master import BuildMaster

# The MCP protocol revision this server implements.
PROTOCOL_VERSION = "2025-11-25"
SUPPORTED_PROTOCOL_VERSIONS = (PROTOCOL_VERSION,)

JSONRPC_VERSION = "2.0"

# JSON-RPC 2.0 error codes (https://www.jsonrpc.org/specification#error_object)
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class JsonRpcError(Exception):
    # Raised by a method handler to produce a JSON-RPC error response.
    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


class McpResource(resource.Resource):
    # Model Context Protocol (MCP) server endpoint, mounted at ``/mcp``.
    #
    # Implements the Streamable HTTP transport for MCP revision 2025-11-25: a
    # single endpoint serving POST (client -> server JSON-RPC messages) and GET
    # (an optional server -> client SSE stream). This layer provides the
    # protocol mechanics -- JSON-RPC 2.0 framing, the initialize/initialized
    # lifecycle, ping, method dispatch and Origin validation. Tools and live
    # log streaming register handlers on top of it in later commits.
    isLeaf = True
    needsReconfig = True

    def __init__(self, master: BuildMaster) -> None:
        super().__init__(master)
        self.origins: list[re.Pattern[str]] = []
        self.tools = McpTools(master)
        # method name -> handler(params) -> result (may return a Deferred)
        self._methods: dict[str, Callable[[dict[str, Any]], Any]] = {
            'initialize': self._handle_initialize,
            'ping': self._handle_ping,
            'tools/list': self._handle_tools_list,
            'tools/call': self._handle_tools_call,
        }
        # notification name -> handler(params) -> None (may return a Deferred)
        self._notifications: dict[str, Callable[[dict[str, Any]], Any]] = {
            'notifications/initialized': self._handle_initialized,
        }

    def reconfigResource(self, new_config: Any) -> None:
        # Mirror RestRootResource: the default allowed origin is the buildbot
        # URL's scheme://host[:port]; additional origins come from config.
        buildbotURL = urlparse(unicode2bytes(new_config.buildbotURL))
        origin_self = buildbotURL.scheme + b"://" + buildbotURL.netloc
        self.origins = []
        for o in new_config.www.get('allowed_origins', [origin_self]):
            origin = bytes2unicode(o).lower()
            self.origins.append(re.compile(fnmatch.translate(origin)))
        self.tools.reset_caches()

    # -- transport --------------------------------------------------------

    def _is_origin_allowed(self, request: server.Request) -> bool:
        # The MCP spec requires servers to validate the Origin header to guard
        # against DNS-rebinding attacks. Non-browser MCP clients usually send
        # no Origin (allowed); browsers send one, which must match the config.
        req_origin = request.getHeader(b'origin')
        if not req_origin:
            return True
        req_origin_str = bytes2unicode(req_origin).lower()
        return any(o.match(req_origin_str) for o in self.origins)

    def _json_response(self, request: server.Request, code: int, payload: dict[str, Any]) -> bytes:
        request.setResponseCode(code)
        request.setHeader(b'content-type', b'application/json; charset=utf-8')
        return unicode2bytes(json.dumps(payload))

    @staticmethod
    def _error_obj(msg_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
        error: dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return {"jsonrpc": JSONRPC_VERSION, "id": msg_id, "error": error}

    def render_GET(self, request: server.Request) -> bytes:
        # No unsolicited server -> client SSE stream is offered yet; the spec
        # allows responding with 405 in that case.
        if not self._is_origin_allowed(request):
            return self._json_response(
                request, 403, self._error_obj(None, INVALID_REQUEST, "invalid origin")
            )
        request.setResponseCode(405)
        request.setHeader(b'content-type', b'text/plain; charset=utf-8')
        return b'GET (server-initiated SSE stream) not supported\n'

    def render_POST(self, request: server.Request) -> int:
        return self.asyncRenderHelper(request, self.renderMcp)

    @defer.inlineCallbacks
    def renderMcp(self, request: server.Request) -> Any:
        if not self._is_origin_allowed(request):
            return self._json_response(
                request, 403, self._error_obj(None, INVALID_REQUEST, "invalid origin")
            )

        raw = request.content.read() if request.content is not None else b''
        try:
            message = json.loads(bytes2unicode(raw))
        except (ValueError, TypeError):
            return self._json_response(
                request, 400, self._error_obj(None, PARSE_ERROR, "parse error")
            )

        # MCP sends one JSON-RPC message per request; batches are not used.
        if not isinstance(message, dict):
            return self._json_response(
                request, 400, self._error_obj(None, INVALID_REQUEST, "invalid request")
            )

        method = message.get('method')

        # Notifications (method, no id) and client responses (no method) are
        # acknowledged with a bare 202 Accepted per the Streamable HTTP spec.
        if not isinstance(method, str) or 'id' not in message:
            if isinstance(method, str) and method in self._notifications:
                try:
                    yield defer.maybeDeferred(
                        self._notifications[method], message.get('params') or {}
                    )
                except Exception as e:
                    log.err(e, 'while handling MCP notification')
            request.setResponseCode(202)
            return b''

        msg_id = message.get('id')
        if message.get('jsonrpc') != JSONRPC_VERSION:
            return self._json_response(
                request, 200, self._error_obj(msg_id, INVALID_REQUEST, "invalid request")
            )

        handler = self._methods.get(method)
        if handler is None:
            return self._json_response(
                request,
                200,
                self._error_obj(msg_id, METHOD_NOT_FOUND, f"method not found: {method}"),
            )

        params = message.get('params') or {}
        try:
            result = yield defer.maybeDeferred(handler, params)
        except JsonRpcError as e:
            return self._json_response(
                request, 200, self._error_obj(msg_id, e.code, e.message, e.data)
            )
        except Exception as e:
            log.err(e, 'while handling MCP request')
            return self._json_response(
                request, 200, self._error_obj(msg_id, INTERNAL_ERROR, "internal error")
            )

        return self._json_response(
            request, 200, {"jsonrpc": JSONRPC_VERSION, "id": msg_id, "result": result}
        )

    # -- method handlers --------------------------------------------------

    def _handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        from buildbot import version as bbversion  # noqa: PLC0415

        # Version negotiation: echo the client's version if we support it,
        # otherwise respond with our latest supported version.
        requested = params.get('protocolVersion')
        version = requested if requested in SUPPORTED_PROTOCOL_VERSIONS else PROTOCOL_VERSION
        return {
            "protocolVersion": version,
            # Resource capabilities (live log streaming) are added in a later
            # commit; tools are available now.
            "capabilities": {"tools": {}},
            "serverInfo": {
                "name": "buildbot",
                "version": bbversion,
            },
        }

    def _handle_ping(self, params: dict[str, Any]) -> dict[str, Any]:
        return {}

    def _handle_initialized(self, params: dict[str, Any]) -> None:
        # The client signals it is ready for normal operation; nothing to do.
        return None

    def _handle_tools_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"tools": self.tools.list_tools()}

    @defer.inlineCallbacks
    def _handle_tools_call(self, params: dict[str, Any]) -> Any:
        name = params.get('name')
        if not isinstance(name, str) or not self.tools.has_tool(name):
            raise JsonRpcError(INVALID_PARAMS, f"unknown tool: {name}")
        arguments = params.get('arguments') or {}
        try:
            data = yield self.tools.call_tool(name, arguments)
        except ToolError as e:
            # Tool-level errors are reported inside the result, not as a
            # protocol error, per the MCP tools specification.
            return {"content": [{"type": "text", "text": str(e)}], "isError": True}
        return {
            "content": [{"type": "text", "text": json.dumps(data, default=toJson)}],
            "isError": False,
        }
