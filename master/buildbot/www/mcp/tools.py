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

import re
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

# Log content bounds (in lines).
DEFAULT_LOG_LINES = 200
MAX_LOG_LINES = 1000
# When searching, cap how many lines are scanned and how many matches returned.
MAX_SEARCH_LINES = 5000
MAX_MATCHES = 100


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
            "get_build_logs": {
                "description": (
                    "Inspect the logs of a build. Called with only build_id, it lists the "
                    "available logs (per step). Pass step (number) and log (slug) to fetch "
                    "that log's contents, paginated by line. Add query to return only the "
                    "lines matching a regular expression (or substring)."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "build_id": {
                            "type": "integer",
                            "description": "The numeric build id (buildid).",
                        },
                        "step": {
                            "type": "integer",
                            "description": "Step number within the build (from the log listing).",
                        },
                        "log": {
                            "type": "string",
                            "description": "Log slug within the step (from the log listing).",
                        },
                        "query": {
                            "type": "string",
                            "description": (
                                "Optional regex (or substring) to return only matching lines."
                            ),
                        },
                        "offset": {
                            "type": "integer",
                            "description": "First line to read (default 0).",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max lines to return in content mode (default 200, cap 1000).",
                        },
                    },
                    "required": ["build_id"],
                },
                "handler": self.get_build_logs,
            },
            "force_build": {
                "description": (
                    "Trigger a build by invoking a force scheduler. Provide the force "
                    "scheduler name; optionally a builder name and extra parameters "
                    "(e.g. branch, revision). Requires force permission."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "scheduler": {
                            "type": "string",
                            "description": "Name of the force scheduler to invoke.",
                        },
                        "builder": {
                            "type": "string",
                            "description": "Builder name to build (optional; resolved to builderid).",
                        },
                        "reason": {
                            "type": "string",
                            "description": "Reason recorded for the build (optional).",
                        },
                        "params": {
                            "type": "object",
                            "description": "Extra force-scheduler parameters (e.g. branch, revision).",
                            "additionalProperties": True,
                        },
                    },
                    "required": ["scheduler"],
                },
                "handler": self.force_build,
            },
            "cancel_build": {
                "description": "Stop a running build by its build id. Requires stop permission.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "build_id": {
                            "type": "integer",
                            "description": "The numeric build id (buildid) to stop.",
                        },
                        "reason": {
                            "type": "string",
                            "description": "Reason recorded for stopping (optional).",
                        },
                    },
                    "required": ["build_id"],
                },
                "handler": self.cancel_build,
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

    def call_tool(self, name: str, arguments: dict[str, Any], request: Any) -> defer.Deferred[Any]:
        spec = self._tools.get(name)
        if spec is None:
            raise ToolError(f"unknown tool: {name}")
        return defer.maybeDeferred(spec["handler"], arguments or {}, request)

    def _assert_allowed(
        self, request: Any, ep: tuple[Any, ...], action: str, args: dict[str, Any]
    ) -> defer.Deferred[Any]:
        # Route through Buildbot's authorization exactly as the REST layer does
        # (www/rest.py): never call data.control() without this check first.
        return defer.maybeDeferred(self.master.www.assertUserAllowed, request, ep, action, args)

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
    def get_status(self, args: dict[str, Any], request: Any) -> Any:
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
    def get_builders(self, args: dict[str, Any], request: Any) -> Any:
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
    def get_workers(self, args: dict[str, Any], request: Any) -> Any:
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
    def get_recent_builds(self, args: dict[str, Any], request: Any) -> Any:
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
    def get_build(self, args: dict[str, Any], request: Any) -> Any:
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

    @defer.inlineCallbacks
    def get_build_logs(self, args: dict[str, Any], request: Any) -> Any:
        build_id = args.get('build_id')
        if build_id is None:
            raise ToolError("build_id is required")
        build = yield self.master.data.get(('builds', build_id))
        if build is None:
            raise ToolError(f"no build with id {build_id}")

        step = args.get('step')
        log_slug = args.get('log')

        # Without a specific step+log, list the logs available in the build.
        if step is None or log_slug is None:
            manifest = yield self._build_log_manifest(build_id)
            return {"build_id": build_id, "logs": manifest}

        log_path = ('builds', build_id, 'steps', step, 'logs', log_slug)
        log_dict = yield self.master.data.get(log_path)
        if log_dict is None:
            raise ToolError(f"no log '{log_slug}' in step {step} of build {build_id}")
        # stdio logs (type 's') store a per-line stream channel prefix (o/e/h);
        # strip it so callers get clean text, mirroring Buildbot's raw-log
        # endpoint (buildbot.data.logchunks.LogChunkEndpointBase.get_log_lines).
        is_stdio = log_dict.get('type') == 's'

        contents_path = (*log_path, 'contents')
        query = args.get('query')
        if query:
            result = yield self._search_log(contents_path, query, args, is_stdio)
        else:
            result = yield self._fetch_log(contents_path, args, is_stdio)
        return result

    @staticmethod
    def _split_log_lines(content: str, is_stdio: bool) -> list[str]:
        lines = content.splitlines()
        if is_stdio:
            # drop the leading stream-channel character from each stdio line
            lines = [line[1:] for line in lines]
        return lines

    @defer.inlineCallbacks
    def _build_log_manifest(self, build_id: Any) -> Any:
        steps = yield self.master.data.get(('builds', build_id, 'steps'))
        manifest = []
        for s in steps:
            logs = yield self.master.data.get(('steps', s['stepid'], 'logs'))
            for lg in logs:
                manifest.append({
                    "step": s["number"],
                    "step_name": s["name"],
                    "name": lg["name"],
                    "slug": lg["slug"],
                    "type": lg["type"],
                    "num_lines": lg["num_lines"],
                    "complete": lg["complete"],
                })
        return manifest

    @defer.inlineCallbacks
    def _fetch_log(self, path: tuple[Any, ...], args: dict[str, Any], is_stdio: bool) -> Any:
        try:
            offset = max(0, int(args.get('offset', 0)))
        except (TypeError, ValueError):
            offset = 0
        try:
            limit = int(args.get('limit', DEFAULT_LOG_LINES))
        except (TypeError, ValueError):
            limit = DEFAULT_LOG_LINES
        limit = max(1, min(limit, MAX_LOG_LINES))

        chunk = yield self.master.data.get(path, offset=offset, limit=limit)
        if chunk is None:
            return {"firstline": offset, "lines_returned": 0, "content": ""}
        lines = self._split_log_lines(chunk.get('content', ''), is_stdio)
        return {
            "firstline": chunk.get('firstline', offset),
            "lines_returned": len(lines),
            "content": "\n".join(lines),
        }

    @defer.inlineCallbacks
    def _search_log(
        self, path: tuple[Any, ...], query: str, args: dict[str, Any], is_stdio: bool
    ) -> Any:
        try:
            pattern = re.compile(query)
        except re.error:
            # Fall back to a literal substring search on an invalid regex.
            pattern = re.compile(re.escape(query))
        try:
            offset = max(0, int(args.get('offset', 0)))
        except (TypeError, ValueError):
            offset = 0

        chunk = yield self.master.data.get(path, offset=offset, limit=MAX_SEARCH_LINES)
        if chunk is None:
            return {
                "query": query,
                "scanned_lines": 0,
                "match_count": 0,
                "matches": [],
                "truncated_matches": False,
                "scan_capped": False,
            }
        firstline = chunk.get('firstline', offset)
        lines = self._split_log_lines(chunk.get('content', ''), is_stdio)
        matches = [
            {"line": firstline + i, "text": line}
            for i, line in enumerate(lines)
            if pattern.search(line)
        ]
        return {
            "query": query,
            "scanned_lines": len(lines),
            "match_count": len(matches),
            "matches": matches[:MAX_MATCHES],
            "truncated_matches": len(matches) > MAX_MATCHES,
            "scan_capped": len(lines) >= MAX_SEARCH_LINES,
        }

    # -- write tool handlers ----------------------------------------------

    @defer.inlineCallbacks
    def force_build(self, args: dict[str, Any], request: Any) -> Any:
        scheduler = args.get('scheduler')
        if not scheduler:
            raise ToolError("scheduler is required (the name of a force scheduler)")

        force_args = dict(args.get('params') or {})
        builder = args.get('builder')
        if builder:
            force_args['builderid'] = yield self._resolve_builder_id(builder)
        if args.get('reason') and 'reason' not in force_args:
            force_args['reason'] = args['reason']

        ep = ('forceschedulers', scheduler)
        yield self._assert_allowed(request, ep, 'force', force_args)
        try:
            res = yield self.master.data.control('force', force_args, ep)
        except Exception as e:
            raise ToolError(f"force failed: {e}") from e
        return {"forced": True, "scheduler": scheduler, "result": res}

    @defer.inlineCallbacks
    def cancel_build(self, args: dict[str, Any], request: Any) -> Any:
        build_id = args.get('build_id')
        if build_id is None:
            raise ToolError("build_id is required")
        build = yield self.master.data.get(('builds', build_id))
        if build is None:
            raise ToolError(f"no build with id {build_id}")

        control_args: dict[str, Any] = {}
        if args.get('reason'):
            control_args['reason'] = args['reason']

        ep = ('builds', build_id)
        yield self._assert_allowed(request, ep, 'stop', control_args)
        yield self.master.data.control('stop', control_args, ep)
        return {"stopped": True, "build_id": build_id}
