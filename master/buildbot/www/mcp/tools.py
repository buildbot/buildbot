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
from typing import Any

from twisted.internet import defer

from buildbot.data import resultspec
from buildbot.process.results import Results

if TYPE_CHECKING:
    from buildbot.master import BuildMaster

# Pagination defaults. Every list-returning tool is bounded so that a single
# tool call cannot overrun an LLM's context window.
DEFAULT_LIMIT = 25
MAX_LIMIT = 100


class ToolError(Exception):
    # A user-facing tool error (e.g. unknown builder). Surfaced to the client
    # as an MCP tool result with isError=true rather than a protocol error.
    pass


def result_label(results: int | None) -> str:
    # Translate a numeric build/step result into a human-readable label.
    if results is None:
        return "running"
    if 0 <= results < len(Results):
        return Results[results]
    return "unknown"


class McpTools:
    # The read-only MCP tool set, each backed by the Buildbot data API
    # (``master.data``). Tools accept human-friendly arguments (e.g. a builder
    # name) and return compact, JSON-serializable dicts.

    def __init__(self, master: BuildMaster) -> None:
        self.master = master
        # builder name -> builderid cache (ids are stable within a master run;
        # cleared on reconfig).
        self._builder_id_cache: dict[str, int] = {}
        self._tools = self._make_tools()

    def reset_caches(self) -> None:
        self._builder_id_cache = {}

    # -- registry ---------------------------------------------------------

    def _make_tools(self) -> dict[str, dict[str, Any]]:
        pagination = {
            "limit": {
                "type": "integer",
                "description": "Maximum number of items to return (default 25, capped at 100).",
            },
            "offset": {
                "type": "integer",
                "description": "Number of items to skip, for paging (default 0).",
            },
        }
        return {
            "get_status": {
                "description": (
                    "Overall snapshot of the Buildbot master: number of builders, "
                    "worker connectivity, and the builds currently running."
                ),
                "inputSchema": {"type": "object", "properties": {}},
                "handler": self.get_status,
            },
            "get_builders": {
                "description": "List configured builders with their id, name, description and tags.",
                "inputSchema": {"type": "object", "properties": dict(pagination)},
                "handler": self.get_builders,
            },
            "get_workers": {
                "description": "List workers, showing whether each is connected and/or paused.",
                "inputSchema": {"type": "object", "properties": dict(pagination)},
                "handler": self.get_workers,
            },
            "get_recent_builds": {
                "description": (
                    "List recent builds, most recent first. Optionally restrict to a "
                    "single builder or to only the builds still running."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "builder": {
                            "type": "string",
                            "description": "Restrict results to this builder name.",
                        },
                        "only_running": {
                            "type": "boolean",
                            "description": "If true, return only builds still in progress.",
                        },
                        **pagination,
                    },
                },
                "handler": self.get_recent_builds,
            },
            "get_build": {
                "description": "Get a single build by its build id, including its steps and result.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "build_id": {
                            "type": "integer",
                            "description": "The numeric build id (buildid).",
                        }
                    },
                    "required": ["build_id"],
                },
                "handler": self.get_build,
            },
        }

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "description": spec["description"],
                "inputSchema": spec["inputSchema"],
            }
            for name, spec in self._tools.items()
        ]

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> defer.Deferred[Any]:
        spec = self._tools.get(name)
        if spec is None:
            raise ToolError(f"unknown tool: {name}")
        return defer.maybeDeferred(spec["handler"], arguments or {})

    # -- helpers ----------------------------------------------------------

    def _paginate(self, args: dict[str, Any]) -> tuple[int, int]:
        try:
            limit = int(args.get("limit", DEFAULT_LIMIT))
        except (TypeError, ValueError):
            limit = DEFAULT_LIMIT
        limit = max(1, min(limit, MAX_LIMIT))
        try:
            offset = int(args.get("offset", 0))
        except (TypeError, ValueError):
            offset = 0
        offset = max(0, offset)
        return limit, offset

    @staticmethod
    def _page_meta(items: list[Any], total: int | None, offset: int) -> dict[str, Any]:
        returned = len(items)
        has_more = (offset + returned) < total if total is not None else False
        return {
            "total_count": total,
            "returned": returned,
            "offset": offset,
            "has_more": has_more,
        }

    @defer.inlineCallbacks
    def _resolve_builder_id(self, name: str) -> Any:
        if name in self._builder_id_cache:
            return self._builder_id_cache[name]
        builder = yield self.master.data.get(('builders', name))
        if builder is None:
            raise ToolError(f"unknown builder: {name}")
        self._builder_id_cache[name] = builder['builderid']
        return builder['builderid']

    @staticmethod
    def _build_summary(b: dict[str, Any]) -> dict[str, Any]:
        return {
            "buildid": b["buildid"],
            "number": b["number"],
            "builderid": b["builderid"],
            "workerid": b.get("workerid"),
            "complete": b["complete"],
            "result": result_label(b.get("results")),
            "state": b["state_string"],
        }

    # -- tool handlers ----------------------------------------------------

    @defer.inlineCallbacks
    def get_status(self, args: dict[str, Any]) -> Any:
        builders = yield self.master.data.get(('builders',))
        workers = yield self.master.data.get(('workers',))
        running = yield self.master.data.get(
            ('builds',),
            filters=[resultspec.Filter('complete', 'eq', [False])],
            order=['-buildid'],
            limit=MAX_LIMIT,
        )
        connected = sum(1 for w in workers if w.get('connected_to'))
        return {
            "builders": len(builders),
            "workers": {"total": len(workers), "connected": connected},
            "running_builds": [
                {
                    "buildid": b["buildid"],
                    "builderid": b["builderid"],
                    "number": b["number"],
                    "state": b["state_string"],
                }
                for b in running
            ],
        }

    @defer.inlineCallbacks
    def get_builders(self, args: dict[str, Any]) -> Any:
        limit, offset = self._paginate(args)
        builders = yield self.master.data.get(
            ('builders',), order=['name'], limit=limit, offset=offset
        )
        items = [
            {
                "builderid": b["builderid"],
                "name": b["name"],
                "description": b.get("description"),
                "tags": b.get("tags", []),
            }
            for b in builders
        ]
        return {
            "builders": items,
            **self._page_meta(items, getattr(builders, 'total', None), offset),
        }

    @defer.inlineCallbacks
    def get_workers(self, args: dict[str, Any]) -> Any:
        limit, offset = self._paginate(args)
        workers = yield self.master.data.get(
            ('workers',), order=['name'], limit=limit, offset=offset
        )
        items = [
            {
                "workerid": w["workerid"],
                "name": w["name"],
                "connected": bool(w.get("connected_to")),
                "paused": w.get("paused", False),
            }
            for w in workers
        ]
        return {"workers": items, **self._page_meta(items, getattr(workers, 'total', None), offset)}

    @defer.inlineCallbacks
    def get_recent_builds(self, args: dict[str, Any]) -> Any:
        limit, offset = self._paginate(args)
        filters = []
        if args.get('only_running'):
            filters.append(resultspec.Filter('complete', 'eq', [False]))

        path: tuple[Any, ...] = ('builds',)
        builder = args.get('builder')
        if builder:
            builderid = yield self._resolve_builder_id(builder)
            path = ('builders', builderid, 'builds')

        builds = yield self.master.data.get(
            path, filters=filters, order=['-buildid'], limit=limit, offset=offset
        )
        items = [self._build_summary(b) for b in builds]
        return {"builds": items, **self._page_meta(items, getattr(builds, 'total', None), offset)}

    @defer.inlineCallbacks
    def get_build(self, args: dict[str, Any]) -> Any:
        build_id = args.get('build_id')
        if build_id is None:
            raise ToolError("build_id is required")
        build = yield self.master.data.get(('builds', build_id))
        if build is None:
            raise ToolError(f"no build with id {build_id}")
        steps = yield self.master.data.get(('builds', build_id, 'steps'))
        return {
            "build": self._build_summary(build),
            "steps": [
                {
                    "number": s["number"],
                    "name": s["name"],
                    "state": s["state_string"],
                    "result": result_label(s.get("results")),
                }
                for s in steps
            ],
        }
