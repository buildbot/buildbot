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

import copy
import datetime
import json

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log

from buildbot import config
from buildbot import util
from buildbot.changes import base
from buildbot.changes.filter import ChangeFilter
from buildbot.util import bytes2unicode
from buildbot.util import httpclientservice
from buildbot.util import runprocess
from buildbot.util.protocol import LineProcessProtocol
from buildbot.util.pullrequest import PullRequestMixin


def _canonicalize_event(event):
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

    compare_attrs = ('eventtype_fn', 'gerrit_branch_fn')

    def __init__(self,
                 branch=util.NotABranch, branch_re=None, branch_fn=None,
                 eventtype=None, eventtype_re=None, eventtype_fn=None, **kw):
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

    def filter_change(self, change):
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

    def _get_repr_filters(self):
        filters = super()._get_repr_filters()
        if self.eventtype_fn is not None:
            filters.append(f'{self.eventtype_fn.__name__}(eventtype)')
        if self.gerrit_branch_fn is not None:
            filters.append(f'{self.gerrit_branch_fn.__name__}(branch)')
        return filters


def _gerrit_user_to_author(props, username="unknown"):
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

    compare_attrs = ("gerritserver", "gerritport")
    name = None
    # list of properties that are no of no use to be put in the event dict
    external_property_denylist = ["event.eventCreatedOn"]
    external_property_whitelist = ['*']
    property_basename = 'event'

    def checkConfig(self,
                    gitBaseURL=None,
                    handled_events=("patchset-created", "ref-updated"),
                    debug=False,
                    get_files=False):

        if gitBaseURL is None:
            config.error("gitBaseURL must be specified")

    def reconfigService(self,
                        gitBaseURL=None,
                        handled_events=("patchset-created", "ref-updated"),
                        debug=False,
                        get_files=False):
        self.gitBaseURL = gitBaseURL
        self.handled_events = list(handled_events)
        self._get_files = get_files
        self.debug = debug

    def lineReceived(self, line):
        try:
            event = json.loads(bytes2unicode(line))
        except ValueError:
            log.msg(f"bad json line: {line}")
            return defer.succeed(None)

        if not (isinstance(event, dict) and "type" in event):
            if self.debug:
                log.msg(f"no type in event {line}")
            return defer.succeed(None)

        return self.eventReceived(event)

    def build_properties(self, event):
        properties = self.extractProperties(event)
        properties["event.source"] = self.__class__.__name__
        if event['type'] in ('patchset-created', 'comment-added') and 'change' in event:
            properties['target_branch'] = event["change"]["branch"]
        return properties

    def eventReceived(self, event):
        if not event['type'] in self.handled_events:
            if self.debug:
                log.msg(f"the event type '{event['type']}' is not setup to handle")
            return defer.succeed(None)

        properties = self.build_properties(event)
        func_name = f'eventReceived_{event["type"].replace("-", "_")}'
        func = getattr(self, func_name, None)
        if func is None:
            return self.addChangeFromEvent(properties, event)

        return func(properties, event)

    @defer.inlineCallbacks
    def addChange(self, event_type, chdict):
        stampdict = {
            "branch": chdict["branch"],
            "revision": chdict["revision"],
            "patch_author": chdict["author"],
            "patch_comment": chdict["comments"],
            "repository": chdict["repository"],
            "project": chdict["project"],
            "codebase": '',
        }

        _, found_existing = yield self.master.db.sourcestamps.findOrCreateId(**stampdict)

        if found_existing and event_type in ("patchset-created", "ref-updated"):
            if self.debug:
                eventstr = (f'{self.gitBaseURL}/{chdict["project"]} -- '
                            f'{chdict["branch"]}:{chdict["revision"]}')
                message = (
                    f"gerrit: duplicate change event {eventstr} by {self.__class__.__name__}")
                log.msg(message.encode("utf-8"))
            return

        if self.debug:
            eventstr = f'{chdict["repository"]} -- {chdict["branch"]}:{chdict["revision"]}'
            message = f"gerrit: adding change from {eventstr} in {self.__class__.__name__}"
            log.msg(message.encode("utf-8"))

        try:
            yield self.master.data.updates.addChange(**chdict)
        except Exception:
            # eat failures..
            log.err('error adding change from GerritChangeSource')

    def get_branch_from_event(self, event):
        if event['type'] in ('patchset-created', 'comment-added'):
            return event["patchSet"]["ref"]
        return event["change"]["branch"]

    def strip_refs_heads_from_branch(self, branch):
        if branch.startswith('refs/heads/'):
            branch = branch[len('refs/heads/'):]
        return branch

    @defer.inlineCallbacks
    def addChangeFromEvent(self, properties, event):
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
                change=event_change["number"],
                patchset=event["patchSet"]["number"]
            )

        yield self.addChange(event['type'], {
            'author': _gerrit_user_to_author(event_change["owner"]),
            'project': util.bytes2unicode(event_change["project"]),
            'repository': f'{self.gitBaseURL}/{event_change["project"]}',
            'branch': self.get_branch_from_event(event),
            'revision': event["patchSet"]["revision"],
            'revlink': event_change["url"],
            'comments': event_change["subject"],
            'files': files,
            'category': event["type"],
            'properties': properties})
        return None

    def eventReceived_ref_updated(self, properties, event):
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
            return None

        return self.addChange(event['type'], dict(
            author=author,
            project=ref["project"],
            repository=f'{self.gitBaseURL}/{ref["project"]}',
            branch=self.strip_refs_heads_from_branch(ref["refName"]),
            revision=ref["newRev"],
            comments="Gerrit: commit(s) pushed.",
            files=["unknown"],
            category=event["type"],
            properties=properties))


class GerritChangeSource(GerritChangeSourceBase):

    """This source will maintain a connection to gerrit ssh server
    that will provide us gerrit events in json format."""

    compare_attrs = ("gerritserver", "gerritport")

    STREAM_GOOD_CONNECTION_TIME = 120
    "(seconds) connections longer than this are considered good, and reset the backoff timer"

    STREAM_BACKOFF_MIN = 0.5
    "(seconds) minimum, but nonzero, time to wait before retrying a failed connection"

    STREAM_BACKOFF_EXPONENT = 1.5
    "multiplier used to increase the backoff from MIN to MAX on repeated failures"

    STREAM_BACKOFF_MAX = 60
    "(seconds) maximum time to wait before retrying a failed connection"

    name = None

    def checkConfig(self,
                    gerritserver,
                    username,
                    gerritport=29418,
                    identity_file=None,
                    **kwargs):
        if self.name is None:
            self.name = f"GerritChangeSource:{username}@{gerritserver}:{gerritport}"
        if 'gitBaseURL' not in kwargs:
            kwargs['gitBaseURL'] = "automatic at reconfigure"
        super().checkConfig(**kwargs)

    def reconfigService(self,
                        gerritserver,
                        username,
                        gerritport=29418,
                        identity_file=None,
                        name=None,
                        **kwargs):
        if 'gitBaseURL' not in kwargs:
            kwargs['gitBaseURL'] = f"ssh://{username}@{gerritserver}:{gerritport}"
        self.gerritserver = gerritserver
        self.gerritport = gerritport
        self.username = username
        self.identity_file = identity_file
        self.process = None
        self.wantProcess = False
        self.streamProcessTimeout = self.STREAM_BACKOFF_MIN
        return super().reconfigService(**kwargs)

    class LocalPP(LineProcessProtocol):

        def __init__(self, change_source):
            super().__init__()
            self.change_source = change_source

        @defer.inlineCallbacks
        def outLineReceived(self, line):
            if self.change_source.debug:
                log.msg(f"{self.change_source.name} "
                        f"stdout: {line.decode('utf-8', errors='replace')}")
            yield self.change_source.lineReceived(line)

        def errLineReceived(self, line):
            if self.change_source.debug:
                log.msg(f"{self.change_source.name} "
                        f"stderr: {line.decode('utf-8', errors='replace')}")

        def processEnded(self, status):
            super().processEnded(status)
            self.change_source.streamProcessStopped()

    def streamProcessStopped(self):
        self.process = None

        # if the service is stopped, don't try to restart the process
        if not self.wantProcess or not self.running:
            return

        now = util.now()
        if now - self.lastStreamProcessStart < \
           self.STREAM_GOOD_CONNECTION_TIME:
            # bad startup; start the stream process again after a timeout,
            # and then increase the timeout
            log.msg(f"{self.name}: stream-events failed; restarting after "
                    f"{round(self.streamProcessTimeout)}s")
            self.master.reactor.callLater(
                self.streamProcessTimeout, self.startStreamProcess)
            self.streamProcessTimeout *= self.STREAM_BACKOFF_EXPONENT
            if self.streamProcessTimeout > self.STREAM_BACKOFF_MAX:
                self.streamProcessTimeout = self.STREAM_BACKOFF_MAX
        else:
            # good startup, but lost connection; restart immediately,
            # and set the timeout to its minimum

            # make sure we log the reconnection, so that it might be detected
            # and network connectivity fixed
            log.msg(f"{self.name}: stream-events lost connection. Reconnecting...")
            self.startStreamProcess()
            self.streamProcessTimeout = self.STREAM_BACKOFF_MIN

    def _buildGerritCommand(self, *gerrit_args):
        '''Get an ssh command list which invokes gerrit with the given args on the
        remote host'''

        cmd = [
            "ssh",
            "-o", "BatchMode=yes",
            f"{self.username}@{self.gerritserver}",
            "-p", str(self.gerritport)
        ]

        if self.identity_file is not None:
            cmd.extend(["-i", self.identity_file])

        cmd.append("gerrit")
        cmd.extend(gerrit_args)
        return cmd

    def startStreamProcess(self):
        if self.debug:
            log.msg(f"{self.name}: starting 'gerrit stream-events'")

        cmd = self._buildGerritCommand("stream-events")
        self.lastStreamProcessStart = util.now()
        self.process = reactor.spawnProcess(self.LocalPP(self), "ssh", cmd, env=None)

    @defer.inlineCallbacks
    def getFiles(self, change, patchset):
        cmd = self._buildGerritCommand("query", str(change), "--format", "JSON",
                                       "--files", "--patch-sets")

        if self.debug:
            log.msg(f"{self.name}: querying for changed files in change {change}/{patchset}: {cmd}")

        rc, out = yield runprocess.run_process(self.master.reactor, cmd, env=None,
                                               collect_stderr=False)
        if rc != 0:
            return ["unknown"]

        out = out.splitlines()[0]
        res = json.loads(bytes2unicode(out))

        if res.get("rowCount") == 0:
            return ["unknown"]

        patchsets = {i["number"]: i["files"] for i in res["patchSets"]}
        return [i["file"] for i in patchsets[int(patchset)]]

    def activate(self):
        self.wantProcess = True
        self.startStreamProcess()

    def deactivate(self):
        self.wantProcess = False
        if self.process:
            self.process.signalProcess("KILL")
        # TODO: if this occurs while the process is restarting, some exceptions
        # may be logged, although things will settle down normally

    def describe(self):
        status = ""
        if not self.process:
            status = "[NOT CONNECTED - check log]"
        return ("GerritChangeSource watching the remote "
                f"Gerrit repository {self.username}@{self.gerritserver} {status}")


class GerritEventLogPoller(GerritChangeSourceBase):

    POLL_INTERVAL_SEC = 30
    FIRST_FETCH_LOOKBACK_DAYS = 30

    def checkConfig(self,
                    baseURL,
                    auth,
                    pollInterval=POLL_INTERVAL_SEC,
                    pollAtLaunch=True,
                    firstFetchLookback=FIRST_FETCH_LOOKBACK_DAYS,
                    **kwargs):
        if self.name is None:
            self.name = f"GerritEventLogPoller:{baseURL}"
        super().checkConfig(**kwargs)

    @defer.inlineCallbacks
    def reconfigService(self,
                        baseURL,
                        auth,
                        pollInterval=POLL_INTERVAL_SEC,
                        pollAtLaunch=True,
                        firstFetchLookback=FIRST_FETCH_LOOKBACK_DAYS,
                        **kwargs):

        yield super().reconfigService(**kwargs)
        if baseURL.endswith('/'):
            baseURL = baseURL[:-1]

        self._pollInterval = pollInterval
        self._pollAtLaunch = pollAtLaunch
        self._oid = yield self.master.db.state.getObjectId(self.name, self.__class__.__name__)
        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, baseURL, auth=auth)

        self._first_fetch_lookback = firstFetchLookback
        self._last_event_time = None

    @staticmethod
    def now():
        """patchable now (datetime is not patchable as builtin)"""
        return datetime.datetime.utcnow()

    @defer.inlineCallbacks
    def poll(self):
        last_event_ts = yield self.master.db.state.getState(self._oid, 'last_event_ts', None)
        if last_event_ts is None:
            # If there is not last event time stored in the database, then set
            # the last event time to some historical look-back
            last_event = self.now() - datetime.timedelta(days=self._first_fetch_lookback)
        else:
            last_event = datetime.datetime.utcfromtimestamp(last_event_ts)
        last_event_formatted = last_event.strftime("%Y-%m-%d %H:%M:%S")

        if self.debug:
            log.msg(f"{self.name}: Polling gerrit: {last_event_formatted}".encode("utf-8"))

        res = yield self._http.get("/plugins/events-log/events/",
                                   params=dict(t1=last_event_formatted))
        lines = yield res.content()
        for line in lines.splitlines():
            yield self.lineReceived(line)

    @defer.inlineCallbacks
    def eventReceived(self, event):
        res = yield super().eventReceived(event)
        if 'eventCreatedOn' in event:
            yield self.master.db.state.setState(self._oid, 'last_event_ts', event['eventCreatedOn'])
        return res

    @defer.inlineCallbacks
    def getFiles(self, change, patchset):
        res = yield self._http.get(f"/changes/{change}/revisions/{patchset}/files/")
        res = yield res.content()

        res = res.splitlines()[1].decode('utf8')  # the first line of every response is `)]}'`
        return list(json.loads(res))

    # FIXME this copy the code from PollingChangeSource
    # but as PollingChangeSource and its subclasses need to be ported to reconfigurability
    # we can't use it right now
    @base.poll_method
    def doPoll(self):
        d = defer.maybeDeferred(self.poll)
        d.addErrback(log.err, 'while polling for changes')
        return d

    def force(self):
        self.doPoll()

    def activate(self):
        self.doPoll.start(interval=self._pollInterval, now=self._pollAtLaunch)

    def deactivate(self):
        return self.doPoll.stop()

    def describe(self):
        msg = ("GerritEventLogPoller watching the remote "
               "Gerrit repository {}")
        return msg.format(self.name)
