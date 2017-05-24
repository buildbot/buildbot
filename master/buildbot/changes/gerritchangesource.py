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

from __future__ import absolute_import
from __future__ import print_function
from future.utils import iteritems

import datetime
import json

from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet.protocol import ProcessProtocol
from twisted.python import log

from buildbot import config
from buildbot import util
from buildbot.changes import base
from buildbot.changes.filter import ChangeFilter
from buildbot.util import bytes2NativeString
from buildbot.util import httpclientservice


class GerritChangeFilter(ChangeFilter):

    """This gerrit specific change filter helps creating pre-commit and post-commit builders"""

    def __init__(self,
                 eventtype=None, eventtype_re=None, eventtype_fn=None, **kw):
        ChangeFilter.__init__(self, **kw)

        self.checks.update(
            self.createChecks(
                (eventtype, eventtype_re, eventtype_fn, "prop:event.type"),
            ))
        # for branch change filter, we take the real gerrit branch
        # instead of the change's branch, which is also used as a grouping key
        if "branch" in self.checks:
            self.checks["prop:event.change.branch"] = self.checks["branch"]
            del self.checks["branch"]


def _gerrit_user_to_author(props, username=u"unknown"):
    """
    Convert Gerrit account properties to Buildbot format

    Take into account missing values
    """
    username = props.get("username", username)
    username = props.get("name", username)
    if "email" in props:
        username += u" <%(email)s>" % props
    return username


class GerritChangeSourceBase(base.ChangeSource):

    """This source will maintain a connection to gerrit ssh server
    that will provide us gerrit events in json format."""

    compare_attrs = ("gerritserver", "gerritport")
    name = None
    # list of properties that are no of no use to be put in the event dict
    EVENT_PROPERTY_BLACKLIST = ["event.eventCreatedOn"]

    def checkConfig(self,
                    gitBaseURL=None,
                    handled_events=("patchset-created", "ref-updated"),
                    debug=False):

        if gitBaseURL is None:
            config.error("gitBaseURL must be specified")

    def reconfigService(self,
                        gitBaseURL=None,
                        handled_events=("patchset-created", "ref-updated"),
                        debug=False):
        self.gitBaseURL = gitBaseURL
        self.handled_events = list(handled_events)
        self.debug = debug

    def lineReceived(self, line):
        try:
            event = json.loads(bytes2NativeString(line))
        except ValueError:
            msg = "bad json line: %s"
            log.msg(msg % line)
            return defer.succeed(None)

        if not(isinstance(event, dict) and "type" in event):
            if self.debug:
                msg = "no type in event %s"
                log.msg(msg % line)
            return defer.succeed(None)

        return self.eventReceived(event)

    def eventReceived(self, event):
        if not (event['type'] in self.handled_events):
            if self.debug:
                msg = "the event type '%s' is not setup to handle"
                log.msg(msg % event['type'])
            return defer.succeed(None)

        # flatten the event dictionary, for easy access with WithProperties
        def flatten(properties, base, event):
            for k, v in iteritems(event):
                name = "%s.%s" % (base, k)
                if name in self.EVENT_PROPERTY_BLACKLIST:
                    continue
                if isinstance(v, dict):
                    flatten(properties, name, v)
                else:  # already there
                    properties[name] = v

        properties = {}
        flatten(properties, "event", event)
        event_with_change = "change" in event and "patchSet" in event
        func_name = "eventReceived_%s" % event["type"].replace("-", "_")
        func = getattr(self, func_name, None)
        if func is None and event_with_change:
            return self.addChangeFromEvent(properties, event)
        elif func is None:
            if self.debug:
                log.msg("unsupported event %s" % (event["type"],))
            return defer.succeed(None)
        else:
            return func(properties, event)

    def addChange(self, chdict):
        d = self.master.data.updates.addChange(**chdict)
        # eat failures..
        d.addErrback(log.err, 'error adding change from GerritChangeSource')
        return d

    def getGroupingPolicyFromEvent(self, event):
        # At the moment, buildbot's change grouping strategy is hardcoded at various place
        # to be the 'branch' of an event.
        # With gerrit, you usually want to group by branch on post commit, and by changeid
        # on pre-commit.
        # we keep this customization point here, waiting to have a better grouping strategy support
        # in the core
        event_change = event["change"]
        if event['type'] in ('patchset-created',):
            return "%s/%s" % (event_change["branch"],
                              event_change['number'])
        return event_change["branch"]

    def addChangeFromEvent(self, properties, event):

        if "change" in event and "patchSet" in event:
            event_change = event["change"]
            return self.addChange({
                'author': _gerrit_user_to_author(event_change["owner"]),
                'project': util.ascii2unicode(event_change["project"]),
                'repository': u"%s/%s" % (
                    self.gitBaseURL, event_change["project"]),
                'branch': self.getGroupingPolicyFromEvent(event),
                'revision': event["patchSet"]["revision"],
                'revlink': event_change["url"],
                'comments': event_change["subject"],
                'files': [u"unknown"],
                'category': event["type"],
                'properties': properties})

    def eventReceived_ref_updated(self, properties, event):
        ref = event["refUpdate"]
        author = u"gerrit"

        if "submitter" in event:
            author = _gerrit_user_to_author(event["submitter"], author)

        return self.addChange(dict(
            author=author,
            project=ref["project"],
            repository="%s/%s" % (
                self.gitBaseURL, ref["project"]),
            branch=ref["refName"],
            revision=ref["newRev"],
            comments="Gerrit: patchset(s) merged.",
            files=[u"unknown"],
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
            self.name = u"GerritChangeSource:%s@%s:%d" % (
                username, gerritserver, gerritport)
        if 'gitBaseURL' not in kwargs:
            kwargs['gitBaseURL'] = "automatic at reconfigure"
        GerritChangeSourceBase.checkConfig(self, **kwargs)

    def reconfigService(self,
                        gerritserver,
                        username,
                        gerritport=29418,
                        identity_file=None,
                        name=None,
                        **kwargs):
        if 'gitBaseURL' not in kwargs:
            kwargs['gitBaseURL'] = "ssh://%s@%s:%s" % (username, gerritserver, gerritport)
        self.gerritserver = gerritserver
        self.gerritport = gerritport
        self.username = username
        self.identity_file = identity_file
        self.process = None
        self.wantProcess = False
        self.streamProcessTimeout = self.STREAM_BACKOFF_MIN
        return GerritChangeSourceBase.reconfigService(self, **kwargs)

    class LocalPP(ProcessProtocol):

        def __init__(self, change_source):
            self.change_source = change_source
            self.data = b""

        @defer.inlineCallbacks
        def outReceived(self, data):
            """Do line buffering."""
            self.data += data
            lines = self.data.split(b"\n")
            # last line is either empty or incomplete
            self.data = lines.pop(-1)
            for line in lines:
                if self.change_source.debug:
                    log.msg(b"gerrit: %s" % line)
                yield self.change_source.lineReceived(line)

        def errReceived(self, data):
            if self.change_source.debug:
                log.msg(b"gerrit stderr: %s" % data)

        def processEnded(self, status_object):
            self.change_source.streamProcessStopped()

    def streamProcessStopped(self):
        self.process = None

        # if the service is stopped, don't try to restart the process
        if not self.wantProcess or reactor._stopped:
            return

        now = util.now()
        if now - self.lastStreamProcessStart < \
           self.STREAM_GOOD_CONNECTION_TIME:
            # bad startup; start the stream process again after a timeout,
            # and then increase the timeout
            log.msg(
                "'gerrit stream-events' failed; restarting after %ds"
                % round(self.streamProcessTimeout))
            reactor.callLater(
                self.streamProcessTimeout, self.startStreamProcess)
            self.streamProcessTimeout *= self.STREAM_BACKOFF_EXPONENT
            if self.streamProcessTimeout > self.STREAM_BACKOFF_MAX:
                self.streamProcessTimeout = self.STREAM_BACKOFF_MAX
        else:
            # good startup, but lost connection; restart immediately,
            # and set the timeout to its minimum

            # make sure we log the reconnection, so that it might be detected
            # and network connectivity fixed
            log.msg("gerrit stream-events lost connection. Reconnecting...")
            self.startStreamProcess()
            self.streamProcessTimeout = self.STREAM_BACKOFF_MIN

    def startStreamProcess(self):
        if self.debug:
            log.msg("starting 'gerrit stream-events'")
        self.lastStreamProcessStart = util.now()
        uri = "%s@%s" % (self.username, self.gerritserver)
        args = [uri, "-p", str(self.gerritport)]
        if self.identity_file is not None:
            args = args + ['-i', self.identity_file]
        self.process = reactor.spawnProcess(
            self.LocalPP(self), "ssh",
            ["ssh"] + args + ["gerrit", "stream-events"], env=None)

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
        msg = ("GerritChangeSource watching the remote "
               "Gerrit repository %s@%s %s")
        return msg % (self.username, self.gerritserver, status)


class GerritEventLogPoller(GerritChangeSourceBase):

    POLL_INTERVAL_SEC = 30

    def checkConfig(self,
                    baseURL,
                    auth,
                    pollInterval=POLL_INTERVAL_SEC,
                    pollAtLaunch=True,
                    **kwargs):
        if self.name is None:
            self.name = u"GerritEventLogPoller:{}".format(baseURL)
        GerritChangeSourceBase.checkConfig(self, **kwargs)

    @defer.inlineCallbacks
    def reconfigService(self,
                        baseURL,
                        auth,
                        pollInterval=POLL_INTERVAL_SEC,
                        pollAtLaunch=True,
                        **kwargs):

        yield GerritChangeSourceBase.reconfigService(self, **kwargs)
        if baseURL.endswith('/'):
            baseURL = baseURL[:-1]

        self._pollInterval = pollInterval
        self._pollAtLaunch = pollAtLaunch
        self._oid = yield self.master.db.state.getObjectId(self.name, self.__class__.__name__)
        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, baseURL, auth=auth)

    @staticmethod
    def now():
        """patchable now (datetime is not patchable as builtin)"""
        return datetime.datetime.utcnow()

    @defer.inlineCallbacks
    def poll(self):
        last_event_ts = yield self.master.db.state.getState(self._oid, 'last_event_ts', None)
        if last_event_ts is None:
            last_event = self.now()
        else:
            last_event = datetime.datetime.utcfromtimestamp(last_event_ts)
        last_event_formatted = last_event.strftime("%Y-%d-%m %H:%M:%S")
        res = yield self._http.get("/plugins/events-log/events/", params=dict(t1=last_event_formatted))
        lines = yield res.content()
        for line in lines.splitlines():
            yield self.lineReceived(line)

    @defer.inlineCallbacks
    def eventReceived(self, event):
        res = yield GerritChangeSourceBase.eventReceived(self, event)
        if 'eventCreatedOn' in event:
            yield self.master.db.state.setState(self._oid, 'last_event_ts', event['eventCreatedOn'])
        defer.returnValue(res)

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
