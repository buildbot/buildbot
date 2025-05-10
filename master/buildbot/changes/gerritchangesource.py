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

import copy
import datetime
import hashlib
import json
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable
from typing import ClassVar
from typing import Pattern
from typing import Sequence

from twisted.internet import defer
from twisted.python import log

from buildbot import config
from buildbot import util
from buildbot.changes import base
from buildbot.changes.filter import ChangeFilter
from buildbot.config.checks import check_param_int
from buildbot.config.checks import check_param_int_none
from buildbot.util import bytes2unicode
from buildbot.util import deferwaiter
from buildbot.util import httpclientservice
from buildbot.util import runprocess
from buildbot.util import watchdog
from buildbot.util.protocol import LineProcessProtocol
from buildbot.util.pullrequest import PullRequestMixin

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


def _canonicalize_event(event: dict) -> dict:
    """
    Return an event dictionary which is consistent between the gerrit
    event stream and the gerrit event log formats.
    """
    # For "patchset-created" the events-log JSON looks like:
    #   "project": {"name": "buildbot"}
    # while the stream-events JSON looks like:
    #   "project": "buildbot"
    # so we canonicalize them to the latter
    if "change" not in event:
        return event

    change = event["change"]
    if "project" not in change:
        return event

    project = change["project"]
    if not isinstance(project, dict):
        return event

    if "name" not in project:
        return event

    event = copy.deepcopy(event)
    event["change"]["project"] = project["name"]
    return event


class GerritChangeFilter(ChangeFilter):
    """This gerrit specific change filter helps creating pre-commit and post-commit builders"""

    compare_attrs: ClassVar[Sequence[str]] = ('eventtype_fn', 'gerrit_branch_fn')

    def __init__(
        self,
        branch: Any = util.NotABranch,
        branch_re: str | Pattern | None = None,
        branch_fn: Callable[[str], bool] | None = None,
        eventtype: str | None = None,
        eventtype_re: str | Pattern | None = None,
        eventtype_fn: Callable[[str], bool] | None = None,
        **kw: Any,
    ):
        if eventtype is not None:
            kw.setdefault('property_eq', {})['event.type'] = eventtype
        if eventtype_re is not None:
            kw.setdefault('property_re', {})['event.type'] = eventtype_re

        # for branch change filter, we take the real gerrit branch
        # instead of the change's branch, which is also used as a grouping key
        if branch is not util.NotABranch:
            kw.setdefault('property_eq', {})['event.change.branch'] = branch
        if branch_re is not None:
            kw.setdefault('property_re', {})['event.change.branch'] = branch_re

        super().__init__(**kw)
        self.eventtype_fn = eventtype_fn
        self.gerrit_branch_fn = branch_fn

    def filter_change(self, change: Any) -> bool:
        if self.eventtype_fn is not None:
            value = change.properties.getProperty('event.type', '')
            if not self.eventtype_fn(value):
                return False

        if self.gerrit_branch_fn is not None:
            # for branch change filter, we take the real gerrit branch
            # instead of the change's branch, which is also used as a grouping key
            value = change.properties.getProperty('event.change.branch', '')
            if not self.gerrit_branch_fn(value):
                return False

        return super().filter_change(change)

    def _get_repr_filters(self) -> list[str]:
        filters = super()._get_repr_filters()
        if self.eventtype_fn is not None:
            filters.append(f'{self.eventtype_fn.__name__}(eventtype)')
        if self.gerrit_branch_fn is not None:
            filters.append(f'{self.gerrit_branch_fn.__name__}(branch)')
        return filters


def _gerrit_user_to_author(props: dict, username: str = "unknown") -> str:
    """
    Convert Gerrit account properties to Buildbot format

    Take into account missing values
    """
    username = props.get("username", username)
    username = props.get("name", username)
    if "email" in props:
        username += f" <{props['email']}>"
    return username


class GerritChangeSourceBase(base.ChangeSource, PullRequestMixin):
    """This source will maintain a connection to gerrit ssh server
    that will provide us gerrit events in json format."""

    compare_attrs: ClassVar[Sequence[str]] = ("gerritserver", "gerritport")
    name: str | None = None  # type: ignore[assignment]
    # list of properties that are no of no use to be put in the event dict
    external_property_denylist = ["event.eventCreatedOn"]
    external_property_whitelist = ['*']
    property_basename = 'event'

    def checkConfig(
        self,
        gitBaseURL: str | None = None,
        handled_events: tuple[str, ...] = ("patchset-created", "ref-updated"),
        debug: bool = False,
        get_files: bool = False,
    ) -> None:  # type: ignore[override]  # checkConfig doesn't need to match supertype
        if gitBaseURL is None:
            config.error("gitBaseURL must be specified")

    def reconfigService(
        self,
        gitBaseURL: str | None = None,
        handled_events: tuple[str, ...] = ("patchset-created", "ref-updated"),
        debug: bool = False,
        get_files: bool = False,
    ) -> None:  # type: ignore[override]  # reconfigService doesn't need to match supertype
        self.gitBaseURL = gitBaseURL
        self.handled_events = list(handled_events)
        self._get_files = get_files
        self.debug = debug

    def build_properties(self, event: dict) -> dict:
        properties = self.extractProperties(event)
        properties["event.source"] = self.__class__.__name__
        if event['type'] in ('patchset-created', 'comment-added') and 'change' in event:
            properties['target_branch'] = event["change"]["branch"]
        return properties

    def getFiles(self, change: str, patchset: str) -> defer.Deferred:
        raise NotImplementedError

    def eventReceived(self, event: dict) -> defer.Deferred:
        if event['type'] not in self.handled_events:
            if self.debug:
                log.msg(f"the event type '{event['type']}' is not setup to handle")
            return defer.succeed(None)

        properties = self.build_properties(event)
        func_name = f'eventReceived_{event["type"].replace("-", "_")}'
        func = getattr(self, func_name, None)
        if func is None:
            return self.addChangeFromEvent(properties, event)

        return func(properties, event)

    def get_branch_from_event(self, event: dict) -> str:
        if event['type'] in ('patchset-created', 'comment-added'):
            return event["patchSet"]["ref"]
        return event["change"]["branch"]

    def strip_refs_heads_from_branch(self, branch: str) -> str:
        if branch.startswith('refs/heads/'):
            branch = branch[len('refs/heads/') :]
        return branch

    @defer.inlineCallbacks
    def addChangeFromEvent(self, properties: dict, event: dict) -> InlineCallbacksType[None]:
        if "change" not in event:
            if self.debug:
                log.msg(f'unsupported event {event["type"]}')
            return None

        if "patchSet" not in event:
            if self.debug:
                log.msg(f'unsupported event {event["type"]}')
            return None

        event = _canonicalize_event(event)
        event_change = event["change"]

        files = ["unknown"]
        if self._get_files:
            files = yield self.getFiles(
                change=event_change["number"], patchset=event["patchSet"]["number"]
            )

        yield self.master.data.updates.addChange(
            author=_gerrit_user_to_author(event_change["owner"]),
            project=util.bytes2unicode(event_change["project"]),
            repository=f'{self.gitBaseURL}/{event_change["project"]}',
            branch=self.get_branch_from_event(event),
            revision=event["patchSet"]["revision"],
            revlink=event_change["url"],
            comments=event_change["subject"],
            files=files,
            category=event["type"],
            properties=properties,
        )
        return

    def eventReceived_ref_updated(self, properties: dict, event: dict) -> defer.Deferred:
        ref = event["refUpdate"]
        author = "gerrit"

        if "submitter" in event:
            author = _gerrit_user_to_author(event["submitter"], author)

        # Ignore ref-updated events if patchset-created events are expected for this push.
        # ref-updated events may arrive before patchset-created events and cause problems, as
        # builds would be using properties from ref-updated event and not from patchset-created.
        # As a result it may appear that the change was not related to a Gerrit change and cause
        # reporters to not submit reviews for example.
        if 'patchset-created' in self.handled_events and ref['refName'].startswith('refs/changes/'):
            return defer.succeed(None)

        return self.master.data.updates.addChange(
            author=author,
            project=ref["project"],
            repository=f'{self.gitBaseURL}/{ref["project"]}',
            branch=self.strip_refs_heads_from_branch(ref["refName"]),
            revision=ref["newRev"],
            comments="Gerrit: commit(s) pushed.",
            files=["unknown"],
            category=event["type"],
            properties=properties,
        )


class GerritSshStreamEventsConnector:
    class LocalPP(LineProcessProtocol):
        MAX_STORED_OUTPUT_DEBUG_LINES = 20

        def __init__(self, connector: GerritSshStreamEventsConnector):
            super().__init__()
            self.connector = connector
            self._output_enabled = True
            self._ended_deferred: defer.Deferred[None] = defer.Deferred()

        @defer.inlineCallbacks
        def outLineReceived(self, line: bytes) -> InlineCallbacksType[None]:
            if self.connector.debug:
                log.msg(
                    f"{self.connector.change_source.name} "
                    + f"stdout: {line.decode('utf-8', errors='replace')}"
                )

            self.connector._append_line_for_debug(line)
            if self._output_enabled:
                yield self.connector.on_line_received_cb(line)

        def errLineReceived(self, line: bytes) -> None:
            if self.connector.debug:
                log.msg(
                    f"{self.connector.change_source.name} "
                    + f"stderr: {line.decode('utf-8', errors='replace')}"
                )
            if self._output_enabled:
                self.connector._append_line_for_debug(line)

        def processEnded(self, status: Any) -> None:
            super().processEnded(status)
            self._ended_deferred.callback(None)
            self.connector._stream_process_stopped()

        def disable_output(self) -> None:
            self._output_enabled = False

        def wait(self) -> defer.Deferred:
            return self._ended_deferred

    # (seconds) connections longer than this are considered good, and reset the backoff timer
    STREAM_GOOD_CONNECTION_TIME = 120

    # (seconds) minimum, but nonzero, time to wait before retrying a failed connection
    STREAM_BACKOFF_MIN = 0.5

    # multiplier used to increase the backoff from MIN to MAX on repeated failures
    STREAM_BACKOFF_EXPONENT = 1.5

    # (seconds) maximum time to wait before retrying a failed connection
    STREAM_BACKOFF_MAX = 60

    # The number of gerrit output lines to print in case of a failure
    MAX_STORED_OUTPUT_DEBUG_LINES = 20

    debug = False

    def __init__(
        self,
        reactor: Any,
        change_source: Any,
        gerritserver: str,
        username: str,
        *,
        gerritport: int = 29418,
        identity_file: str | None = None,
        ssh_server_alive_interval_s: int | None = 15,
        ssh_server_alive_count_max: int | None = 3,
        on_process_start_cb: Callable[[], None],
        on_line_received_cb: Callable[[bytes], defer.Deferred],
    ):
        self.reactor = reactor
        self.change_source = change_source
        self.gerritserver = gerritserver
        self.username = username
        self.gerritport = gerritport
        self.identity_file = identity_file
        self.ssh_server_alive_interval_s = ssh_server_alive_interval_s
        self.ssh_server_alive_count_max = ssh_server_alive_count_max
        self.on_process_start_cb = on_process_start_cb
        self.on_line_received_cb = on_line_received_cb
        self._process: tuple[Any, Any] | None = None
        self._stream_process_timeout = self.STREAM_BACKOFF_MIN
        self._last_lines_for_debug: list[bytes] = []

    def start(self) -> None:
        self._want_process = True
        self.start_stream_process()

    @defer.inlineCallbacks
    def stop(self) -> InlineCallbacksType[None]:
        self._want_process = False
        if self._process is not None:
            self._process[0].disable_output()
            self._process[1].signalProcess("KILL")
            yield self._process[0].wait()

    @defer.inlineCallbacks
    def restart(self) -> InlineCallbacksType[None]:
        if self._process is not None:
            self._process[0].disable_output()
            # Process will restart automatically
            self._process[1].signalProcess("KILL")
            yield self._process[0].wait()
        else:
            self.start()

    def _append_line_for_debug(self, line: bytes) -> None:
        self._last_lines_for_debug.append(line)
        while len(self._last_lines_for_debug) > self.MAX_STORED_OUTPUT_DEBUG_LINES:
            self._last_lines_for_debug.pop(0)

    def _build_gerrit_command(self, *gerrit_args: str) -> list[str]:
        """Get an ssh command list which invokes gerrit with the given args on the
        remote host"""

        options = [
            "-o",
            "BatchMode=yes",
        ]
        if self.ssh_server_alive_interval_s is not None:
            options += ["-o", f"ServerAliveInterval={self.ssh_server_alive_interval_s}"]
        if self.ssh_server_alive_count_max is not None:
            options += ["-o", f"ServerAliveCountMax={self.ssh_server_alive_count_max}"]

        cmd = ["ssh", *options, f"{self.username}@{self.gerritserver}", "-p", str(self.gerritport)]

        if self.identity_file is not None:
            cmd.extend(["-i", self.identity_file])

        cmd.append("gerrit")
        cmd.extend(gerrit_args)
        return cmd

    def start_stream_process(self) -> None:
        if self._process is not None:
            return

        if self.debug:
            log.msg(f"{self.change_source.name}: starting 'gerrit stream-events'")

        # Must be called before start of the process to ensure consistent ordering to avoid race
        # conditions.
        self.on_process_start_cb()

        cmd = self._build_gerrit_command("stream-events")
        self._last_stream_process_start = self.reactor.seconds()
        protocol = self.LocalPP(self)
        self._process = (protocol, self.reactor.spawnProcess(protocol, "ssh", cmd, env=None))
        self._last_lines_for_debug = []

    def _stream_process_stopped(self) -> None:
        self._process = None

        # if the service is stopped, don't try to restart the process
        if not self._want_process or not self.change_source.running:
            return

        now = self.reactor.seconds()
        if now - self._last_stream_process_start < self.STREAM_GOOD_CONNECTION_TIME:
            # bad startup; start the stream process again after a timeout,
            # and then increase the timeout
            log_lines = "\n".join([
                l.decode("utf-8", errors="ignore") for l in self._last_lines_for_debug
            ])

            log.msg(
                f"{self.change_source.name}: stream-events failed; restarting after "
                f"{round(self._stream_process_timeout)}s.\n"
                f"{len(self._last_lines_for_debug)} log lines follow:\n{log_lines}"
            )

            self.reactor.callLater(self._stream_process_timeout, self.start_stream_process)
            self._stream_process_timeout *= self.STREAM_BACKOFF_EXPONENT
            self._stream_process_timeout = min(
                self._stream_process_timeout, self.STREAM_BACKOFF_MAX
            )
        else:
            # good startup, but lost connection; restart immediately,
            # and set the timeout to its minimum

            # make sure we log the reconnection, so that it might be detected
            # and network connectivity fixed
            log.msg(f"{self.change_source.name}: stream-events lost connection. Reconnecting...")
            self.start_stream_process()
            self._stream_process_timeout = self.STREAM_BACKOFF_MIN

    @defer.inlineCallbacks
    def get_files(self, change: str, patchset: str) -> InlineCallbacksType[list[str]]:
        cmd = self._build_gerrit_command(
            "query", str(change), "--format", "JSON", "--files", "--patch-sets"
        )

        if self.debug:
            log.msg(
                f"{self.change_source.name}: querying for changed files in change {change}/{patchset}: {cmd}"
            )

        rc, out = yield runprocess.run_process(self.reactor, cmd, env=None, collect_stderr=False)
        if rc != 0:
            return ["unknown"]

        out = out.splitlines()[0]
        res = json.loads(bytes2unicode(out))

        if res.get("rowCount") == 0:
            return ["unknown"]

        patchsets = {i["number"]: i["files"] for i in res["patchSets"]}
        return [i["file"] for i in patchsets[int(patchset)]]


class GerritHttpEventLogPollerConnector:
    FIRST_FETCH_LOOKBACK_DAYS = 30

    debug = False

    def __init__(
        self,
        reactor: Any,
        change_source: Any,
        base_url: str,
        auth: Any,
        get_last_event_ts: Callable[[], defer.Deferred[int] | int],
        first_fetch_lookback: int,
        on_lines_received_cb: Callable[[list[bytes]], defer.Deferred],
    ) -> None:
        if base_url.endswith('/'):
            base_url = base_url[:-1]
        self._reactor = reactor
        self._change_source = change_source
        self._get_last_event_ts = get_last_event_ts
        self._base_url = base_url
        self._auth = auth
        self._first_fetch_lookback = first_fetch_lookback
        self._on_lines_received_cb = on_lines_received_cb
        self._last_event_time = None

    @defer.inlineCallbacks
    def setup(self) -> InlineCallbacksType[None]:
        self._http = yield httpclientservice.HTTPSession(
            self._change_source.master.httpservice, self._base_url, auth=self._auth
        )

    @defer.inlineCallbacks
    def poll(self) -> InlineCallbacksType[None]:
        last_event_ts = yield self._get_last_event_ts()
        if last_event_ts is None:
            # If there is not last event time stored in the database, then set
            # the last event time to some historical look-back
            last_event = datetime.datetime.fromtimestamp(
                self._reactor.seconds(), datetime.timezone.utc
            ) - datetime.timedelta(days=self._first_fetch_lookback)
        else:
            last_event = datetime.datetime.fromtimestamp(last_event_ts, datetime.timezone.utc)
        last_event_formatted = last_event.strftime("%Y-%m-%d %H:%M:%S")

        if self.debug:
            log.msg(f"{self._change_source.name}: Polling gerrit: {last_event_formatted}")

        res = yield self._http.get(
            "/plugins/events-log/events/", params={"t1": last_event_formatted}
        )
        if res.code != 200:
            log.msg(f'{self._change_source.name}: Polling gerrit: got HTTP error code {res.code}')
            return

        lines = yield res.content()
        yield self._on_lines_received_cb(lines.splitlines())

    @defer.inlineCallbacks
    def get_files(self, change: str, patchset: str) -> InlineCallbacksType[list[str]]:
        res = yield self._http.get(f"/changes/{change}/revisions/{patchset}/files/")
        res = yield res.content()
        try:
            res = res.splitlines()[1].decode('utf8')  # the first line of every response is `)]}'`
            return list(json.loads(res))
        except Exception as e:
            log.err(e, 'while getting files from connector')
            return []

    @defer.inlineCallbacks
    def do_poll(self) -> InlineCallbacksType[None]:
        try:
            yield self.poll()
        except Exception as e:
            log.err(e, 'while polling for changes')


def extract_gerrit_event_time(event: dict) -> int:
    return event["eventCreatedOn"]


def build_gerrit_event_hash(event: dict) -> str:
    return hashlib.sha1(json.dumps(event, sort_keys=True).encode("utf-8")).hexdigest()


def is_event_valid(event: Any) -> bool:
    return isinstance(event, dict) and "type" in event and "eventCreatedOn" in event


class GerritChangeSource(GerritChangeSourceBase):
    """This source will maintain a connection to gerrit ssh server that will provide us gerrit
    events in json format. Additionally, connection to gerrit HTTP server may be setup so
    that historical events can be fetched to fill any gaps due to Buildbot or Gerrit restarts
    or internet connectivity problems.

    Important considerations for filling gaps in processed events:
     - Gerrit events do not have unique IDs, only eventCreateOn timestamp which is common between
       events coming from the HTTP and SSH APIs
     - Gerrit HTTP API does not provide any ordering guarantees.
     - Gerrit HTTP and SSH APIs return events encoded identically
    """

    compare_attrs: ClassVar[Sequence[str]] = ("gerritserver", "gerritport")

    name = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._stream_connector: GerritSshStreamEventsConnector | None = None
        self._poll_connector: GerritHttpEventLogPollerConnector | None = None

        self._queued_stream_events: list[tuple[int, dict]] = []

        # Events are received from stream event source continuously. If HTTP API is not available,
        # GerritChangeSource is always in this state.
        #
        # This variable is used to synchronize between concurrent data ingestion from poll or
        # stream event sources. If _is_synchronized == True, then polling data is discarded.
        # Otherwise, data from stream data source goes into _queued_stream_events.
        self._is_synchronized = True

        # True if SSH stream did not get events for a long time. It is unclear whether the
        # connection broke or there were simply no activity, so the SSH connection should not be
        # restarted. Note that _stream_activity_watchdog is disabled when
        # _stream_messages_timeout is True and should be re-enabled when exiting out of this
        # condition.
        self._stream_messages_timeout = False

        # Used for polling if last event timestamp is unknown.
        self._start_ts: int | None = None

        # Stores newest events that have been published for further processing and have identical
        # timestamp. This is used to ensure that events are not duplicated across stream and
        # polled sources.
        self._last_second_events: list[dict] = []
        # Contains hashes of self._last_second_events coming from previous run of this service.
        # self._last_second_events is not stored directly because of size considerations.
        self._last_second_event_hashes: list[str] | None = []

        self._last_event_ts: int | None = None
        # Last event timestamp recorded to database. Equivalent to self._last_event_ts. Separate
        # variable is support single database transaction for message batches.
        self._last_event_ts_saved: int | None = None

        self._deferwaiter = deferwaiter.DeferWaiter()
        self._poll_handler: deferwaiter.NonRepeatedActionHandler | None = None
        self._stream_activity_watchdog: watchdog.Watchdog | None = None

    def checkConfig(  # type: ignore[override]
        self,
        gerritserver: str,
        username: str,
        gerritport: int = 29418,
        identity_file: str | None = None,
        ssh_server_alive_interval_s: int | None = 15,
        ssh_server_alive_count_max: int | None = 3,
        http_url: str | None = None,
        http_auth: Any = None,
        http_poll_interval: int = 30,
        **kwargs: Any,
    ) -> None:
        if self.name is None:
            self.name = f"GerritChangeSource:{username}@{gerritserver}:{gerritport}"
        if 'gitBaseURL' not in kwargs:
            kwargs['gitBaseURL'] = "automatic at reconfigure"
        check_param_int_none(
            ssh_server_alive_interval_s, self.__class__, "ssh_server_alive_interval_s"
        )
        check_param_int_none(
            ssh_server_alive_count_max, self.__class__, "ssh_server_alive_count_max"
        )
        check_param_int(http_poll_interval, self.__class__, "http_poll_interval")
        super().checkConfig(**kwargs)

    @defer.inlineCallbacks
    def reconfigService(  # type: ignore[override]
        self,
        gerritserver: str,
        username: str,
        gerritport: int = 29418,
        identity_file: str | None = None,
        name: str | None = None,
        ssh_server_alive_interval_s: int | None = 15,
        ssh_server_alive_count_max: int | None = 3,
        http_url: str | None = None,
        http_auth: Any = None,
        http_poll_interval: int = 30,
        **kwargs: Any,
    ) -> InlineCallbacksType[None]:
        if 'gitBaseURL' not in kwargs:
            kwargs['gitBaseURL'] = f"ssh://{username}@{gerritserver}:{gerritport}"
        self.gerritserver = gerritserver
        self.gerritport = gerritport
        self.username = username
        self.identity_file = identity_file
        self._http_poll_interval = http_poll_interval

        if self._stream_connector is None:
            # TODO: this does not support reconfiguration at the moment
            self._stream_connector = GerritSshStreamEventsConnector(
                self.master.reactor,
                self,
                gerritserver,
                username,
                gerritport=gerritport,
                identity_file=identity_file,
                ssh_server_alive_interval_s=ssh_server_alive_interval_s,
                ssh_server_alive_count_max=ssh_server_alive_count_max,
                on_process_start_cb=self._stream_process_started,
                on_line_received_cb=self._line_received_stream,
            )
        self._stream_messages_timeout = False

        self._oid = yield self.master.db.state.getObjectId(self.name, self.__class__.__name__)

        if self._start_ts is None:
            self._start_ts = self.master.reactor.seconds()

        if self._last_event_ts is None:
            self._last_event_ts = yield self.master.db.state.getState(
                self._oid, 'last_event_ts', None
            )
            self._last_second_event_hashes = yield self.master.db.state.getState(
                self._oid, "last_event_hashes", None
            )

        if self._poll_handler is not None:
            self._poll_handler.stop()
        self._poll_handler = deferwaiter.NonRepeatedActionHandler(
            self.master.reactor,
            self._deferwaiter,
            lambda: self._poll_connector.do_poll(),  # type: ignore[union-attr]
        )

        if http_url is not None:
            if self._poll_connector is None:
                # TODO: this does not support reconfiguration at the moment
                self._poll_connector = GerritHttpEventLogPollerConnector(
                    self.master.reactor,
                    self,
                    http_url + "/a",
                    http_auth,
                    lambda: self._last_event_ts or self._start_ts or 0,  # 0 can't happen
                    first_fetch_lookback=0,
                    on_lines_received_cb=self._lines_received_poll,
                )
                yield self._poll_connector.setup()  # type: ignore[attr-defined]
            self._is_synchronized = False
        else:
            self._poll_connector = None
            self._is_synchronized = True

        self._stream_activity_watchdog = watchdog.Watchdog(
            self.master.reactor, self._no_stream_activity_timed_out, self._http_poll_interval
        )

        yield super().reconfigService(**kwargs)

    def activate(self) -> defer.Deferred[None]:
        assert self._stream_connector is not None
        assert self._stream_activity_watchdog is not None

        self._is_synchronized = self._poll_connector is None
        self._stream_connector.start()
        self._stream_activity_watchdog.start()
        return defer.succeed(None)

    @defer.inlineCallbacks
    def deactivate(self) -> InlineCallbacksType[None]:
        assert self._stream_connector is not None
        assert self._poll_handler is not None
        assert self._stream_activity_watchdog is not None

        self._stream_activity_watchdog.stop()
        yield self._stream_connector.stop()  # Note that this immediately stops event acceptance
        self._poll_handler.stop()
        yield self._deferwaiter.wait()

        if self._last_second_events:
            yield self.master.db.state.setState(
                self._oid,
                "last_event_hashes",
                [build_gerrit_event_hash(event) for event in self._last_second_events],
            )
        else:
            yield self.master.db.state.setState(self._oid, "last_event_hashes", None)

    def getFiles(self, change: str, patchset: str) -> defer.Deferred:
        assert self._stream_connector is not None
        return self._stream_connector.get_files(change, patchset)

    def _no_stream_activity_timed_out(self) -> None:
        assert self._poll_handler is not None
        if self._poll_connector is None:
            return
        self._stream_messages_timeout = True
        self._poll_handler.force()

    def _stream_process_started(self) -> None:
        assert self._poll_handler is not None
        if self._poll_connector is None:
            return
        self._is_synchronized = False
        self._poll_handler.force()

    def _record_last_second_event(self, event: dict, ts: int) -> None:
        if self._last_event_ts != ts:
            self._last_event_ts = ts
            self._last_second_events.clear()
            self._last_second_event_hashes = None
        self._last_second_events.append(event)

    @defer.inlineCallbacks
    def _update_last_event_ts(self) -> InlineCallbacksType[None]:
        if self._last_event_ts != self._last_event_ts_saved:
            self._last_event_ts_saved = self._last_event_ts
            yield self.master.db.state.setState(self._oid, "last_event_ts", self._last_event_ts)

    @defer.inlineCallbacks
    def _line_received_stream(self, line: bytes) -> InlineCallbacksType[None]:
        assert self._poll_handler is not None
        assert self._stream_activity_watchdog is not None

        self._stream_activity_watchdog.notify()
        try:
            event = json.loads(bytes2unicode(line))
        except ValueError:
            log.msg(f"{self.name}: bad json line: {line!r}")
            return

        if not is_event_valid(event):
            if self.debug:
                log.msg(f"no type in event {line!r}")
            return

        if not self._is_synchronized:
            self._queued_stream_events.append((extract_gerrit_event_time(event), event))
            if self._poll_connector is not None:
                self._poll_handler.force()
            return

        if self._stream_messages_timeout:
            self._stream_activity_watchdog.start()
        self._stream_messages_timeout = False
        self._poll_handler.stop()

        self._record_last_second_event(event, extract_gerrit_event_time(event))
        yield self._update_last_event_ts()
        yield self.eventReceived(event)

    def _filter_out_already_received_events(
        self, events: list[tuple[int, dict]]
    ) -> list[tuple[int, dict]]:
        if self._last_event_ts is None:
            return events

        filtered_events = []
        for ts, event in events:
            if ts < self._last_event_ts:
                continue
            if ts == self._last_event_ts:
                if self._last_second_event_hashes is not None:
                    if build_gerrit_event_hash(event) in self._last_second_event_hashes:
                        continue

                if event in self._last_second_events:
                    continue
            filtered_events.append((ts, event))
        return filtered_events

    def _debug_log_polled_event(self, event: dict) -> None:
        line = json.dumps(event, sort_keys=True)
        log.msg(f"{self.name} accepted polled event: {line}")

    @defer.inlineCallbacks
    def _lines_received_poll(self, lines: list[bytes]) -> InlineCallbacksType[None]:
        assert self._stream_connector is not None
        assert self._poll_handler is not None
        assert self._stream_activity_watchdog is not None

        if self._is_synchronized and not self._stream_messages_timeout:
            return

        # The code below parses all retrieved events, ignores already received ones, submits the
        # rest for processing and if it is detected that events from polling source are synchronized
        # with queued events from streaming source, switches to the streaming source.

        events = []
        for line in lines:
            try:
                event = json.loads(bytes2unicode(line))
            except ValueError:
                log.msg(f"{self.name}: bad json line: {line!r}")
                continue

            if not is_event_valid(event):
                if self.debug:
                    log.msg(f"no type in event {line!r}")
                continue
            events.append((extract_gerrit_event_time(event), event))

        events = sorted(self._filter_out_already_received_events(events), key=lambda e: e[0])

        if not events:
            self._poll_handler.schedule(self._http_poll_interval, invoke_again_if_running=True)
            return

        max_event_ts = events[-1][0]

        got_newer_messages_unhandled_before = True
        if self._last_event_ts is not None:
            got_newer_messages_unhandled_before = max_event_ts > self._last_event_ts

        needs_stream_restart = False
        if self._stream_messages_timeout and got_newer_messages_unhandled_before:
            # Stream connector has broken, because usually messages would come through the stream
            # connector first. Now new messages were received through HTTP API.
            #
            # Note: there must not be any asynchronous code between this check and the start of
            # the function to avoid race conditions.
            self._is_synchronized = False
            self._stream_messages_timeout = False
            needs_stream_restart = True

        if not self._queued_stream_events or max_event_ts <= self._queued_stream_events[0][0]:
            # The events from poll source has not caught up to stream events - process all events
            # and leave _is_synchronized as False.

            for ts, event in events:
                self._record_last_second_event(event, ts)
                if self.debug:
                    self._debug_log_polled_event(event)
                yield self.eventReceived(event)

            yield self._update_last_event_ts()
            self._poll_handler.schedule(self._http_poll_interval, invoke_again_if_running=True)
            if needs_stream_restart:
                self._deferwaiter.add(self._stream_connector.restart())
                self._stream_activity_watchdog.start()
            return

        first_queued_ts = self._queued_stream_events[0][0]

        # max_event_ts > first_queued_ts which means that:
        # - events list is guaranteed to have all events up to first_queued_ts (inclusive)
        # - starting with first_queued_ts (exclusive) the stream source has all events.
        for ts, event in events:
            if ts <= first_queued_ts:
                self._record_last_second_event(event, ts)
                if self.debug:
                    self._debug_log_polled_event(event)
                yield self.eventReceived(event)

        i = 0
        while i < len(self._queued_stream_events):
            ts, event = self._queued_stream_events[i]
            if ts == self._last_event_ts and event in self._last_second_events:
                i += 1
                continue
            self._record_last_second_event(event, ts)
            yield self.eventReceived(event)
            i += 1

        self._queued_stream_events.clear()
        if not needs_stream_restart:
            self._is_synchronized = True
        yield self._update_last_event_ts()
        if needs_stream_restart:
            self._deferwaiter.add(self._stream_connector.restart())
            self._stream_activity_watchdog.start()

    def describe(self) -> str:
        status = ""
        if not self._stream_connector or not self._stream_connector._process:
            status = "[NOT CONNECTED - check log]"
        return (
            "GerritChangeSource watching the remote "
            f"Gerrit repository {self.username}@{self.gerritserver} {status}"
        )


class GerritEventLogPoller(GerritChangeSourceBase):
    POLL_INTERVAL_SEC = 30
    FIRST_FETCH_LOOKBACK_DAYS = 30

    def checkConfig(  # type: ignore[override]
        self,
        baseURL: str,
        auth: Any,
        pollInterval: int = POLL_INTERVAL_SEC,
        pollAtLaunch: bool = True,
        firstFetchLookback: int = FIRST_FETCH_LOOKBACK_DAYS,
        **kwargs: Any,
    ) -> None:
        if self.name is None:
            self.name = f"GerritEventLogPoller:{baseURL}"
        super().checkConfig(**kwargs)

    @defer.inlineCallbacks
    def reconfigService(  # type: ignore[override]
        self,
        baseURL: str,
        auth: Any,
        pollInterval: int = POLL_INTERVAL_SEC,
        pollAtLaunch: bool = True,
        firstFetchLookback: int = FIRST_FETCH_LOOKBACK_DAYS,
        **kwargs: Any,
    ) -> InlineCallbacksType[None]:
        yield super().reconfigService(**kwargs)

        self._poll_interval = pollInterval
        self._poll_at_launch = pollAtLaunch

        self._oid = yield self.master.db.state.getObjectId(self.name, self.__class__.__name__)

        def get_last_event_ts() -> defer.Deferred:
            return self.master.db.state.getState(self._oid, 'last_event_ts', None)

        self._connector = GerritHttpEventLogPollerConnector(
            self.master.reactor,
            self,
            baseURL,
            auth,
            get_last_event_ts,
            first_fetch_lookback=firstFetchLookback,
            on_lines_received_cb=self._lines_received,
        )
        yield self._connector.setup()
        self._poller = util.poll.Poller(self._connector.do_poll, self, self.master.reactor)

    def getFiles(self, change: str, patchset: str) -> defer.Deferred:
        return self._connector.get_files(change, patchset)

    def force(self) -> None:
        self._poller()

    def activate(self) -> defer.Deferred[None]:
        self._poller.start(interval=self._poll_interval, now=self._poll_at_launch)
        return defer.succeed(None)

    def deactivate(self) -> defer.Deferred:
        return self._poller.stop()

    def describe(self) -> str:
        msg = "GerritEventLogPoller watching the remote Gerrit repository {}"
        return msg.format(self.name)

    @defer.inlineCallbacks
    def _lines_received(self, lines: list[bytes]) -> InlineCallbacksType[None]:
        last_event_ts = None
        for line in lines:
            try:
                event = json.loads(bytes2unicode(line))
            except ValueError:
                log.msg(f"{self.name}: bad json line: {line!r}")
                continue

            if not is_event_valid(event):
                if self.debug:
                    log.msg(f"no type in event {line!r}")
                continue

            yield super().eventReceived(event)

            this_last_event_ts = extract_gerrit_event_time(event)
            if last_event_ts is None:
                last_event_ts = this_last_event_ts
            else:
                last_event_ts = max(last_event_ts, this_last_event_ts)

        if last_event_ts is not None:
            yield self.master.db.state.setState(self._oid, "last_event_ts", last_event_ts)
