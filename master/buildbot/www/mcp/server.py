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

from typing import TYPE_CHECKING

from buildbot.www import resource

if TYPE_CHECKING:
    from twisted.web import server


class McpResource(resource.Resource):
    # Model Context Protocol (MCP) server endpoint, mounted at ``/mcp``.
    #
    # This is the initial scaffold: the endpoint is registered and reachable so
    # that the wiring (the ``c['www']['mcp']`` config key and the www
    # registration) can be reviewed in isolation. The protocol implementation
    # -- JSON-RPC 2.0 framing, the ``initialize`` handshake, tool dispatch and
    # SSE streaming -- lands in subsequent commits. Until then every request
    # gets a clean 501 Not Implemented.
    isLeaf = True

    def render(self, request: server.Request) -> bytes:
        request.setResponseCode(501)
        request.setHeader(b'content-type', b'text/plain; charset=utf-8')
        return b'MCP server not implemented yet\n'
