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

from buildbot import util
from buildbot.changes import base
from buildbot.util import json
from buildbot.changes.filter import ChangeFilter
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet.protocol import ProcessProtocol
from twisted.python import log


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


class GerritChangeSource(base.ChangeSource):

    """This source will maintain a connection to gerrit ssh server
    that will provide us gerrit events in json format."""

    compare_attrs = ["gerritserver", "gerritport"]

    STREAM_GOOD_CONNECTION_TIME = 120
    "(seconds) connections longer than this are considered good, and reset the backoff timer"

    STREAM_BACKOFF_MIN = 0.5
    "(seconds) minimum, but nonzero, time to wait before retrying a failed connection"

    STREAM_BACKOFF_EXPONENT = 1.5
    "multiplier used to increase the backoff from MIN to MAX on repeated failures"

    STREAM_BACKOFF_MAX = 60
    "(seconds) maximum time to wait before retrying a failed connection"

    def __init__(self,
                 gerritserver,
                 username,
                 gerritport=29418,
                 identity_file=None,
                 handled_events=("patchset-created", "ref-updated")):
        """
        @type  gerritserver: string
        @param gerritserver: the dns or ip that host the gerrit ssh server,

        @type  gerritport: int
        @param gerritport: the port of the gerrit ssh server,

        @type  username: string
        @param username: the username to use to connect to gerrit,

        @type  identity_file: string
        @param identity_file: identity file to for authentication (optional),

        @type  handled_events: list
        @param handled_events: event to be handled (optional).
        """
        # TODO: delete API comment when documented

        self.gerritserver = gerritserver
        self.gerritport = gerritport
        self.username = username
        self.identity_file = identity_file
        self.handled_events = list(handled_events)
        self.process = None
        self.wantProcess = False
        self.streamProcessTimeout = self.STREAM_BACKOFF_MIN

    class LocalPP(ProcessProtocol):

        def __init__(self, change_source):
            self.change_source = change_source
            self.data = ""

        @defer.inlineCallbacks
        def outReceived(self, data):
            """Do line buffering."""
            self.data += data
            lines = self.data.split("\n")
            # last line is either empty or incomplete
            self.data = lines.pop(-1)
            for line in lines:
                log.msg("gerrit: %s" % line)
                yield self.change_source.lineReceived(line)

        def errReceived(self, data):
            log.msg("gerrit stderr: %s" % data)

        def processEnded(self, status_object):
            self.change_source.streamProcessStopped()

    def lineReceived(self, line):
        try:
            event = json.loads(line.decode('utf-8'))
        except ValueError:
            msg = "bad json line: %s"
            log.msg(msg % line)
            return defer.succeed(None)

        if not(isinstance(event, dict) and "type" in event):
            msg = "no type in event %s"
            log.msg(msg % line)
            return defer.succeed(None)

        if not (event['type'] in self.handled_events):
            msg = "the event type '%s' is not setup to handle"
            log.msg(msg % event['type'])
            return defer.succeed(None)

        # flatten the event dictionary, for easy access with WithProperties
        def flatten(properties, base, event):
            for k, v in event.items():
                name = "%s.%s" % (base, k)
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
            log.msg("unsupported event %s" % (event["type"],))
            return defer.succeed(None)
        else:
            return func(properties, event)

    def addChange(self, chdict):
        d = self.master.addChange(**chdict)
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
        else:
            return event_change["branch"]

    def addChangeFromEvent(self, properties, event):

        if "change" in event and "patchSet" in event:
            event_change = event["change"]
            return self.addChange({
                'author': "%s <%s>" % (
                    event_change["owner"]["name"],
                    event_change["owner"]["email"]),
                'project': event_change["project"],
                'repository': "ssh://%s@%s:%s/%s" % (
                    self.username, self.gerritserver,
                    self.gerritport, event_change["project"]),
                'branch': self.getGroupingPolicyFromEvent(event),
                'revision': event["patchSet"]["revision"],
                'revlink': event_change["url"],
                'comments': event_change["subject"],
                'files': ["unknown"],
                'category': event["type"],
                'properties': properties})

    def eventReceived_ref_updated(self, properties, event):
        ref = event["refUpdate"]
        author = "gerrit"

        if "submitter" in event:
            author = "%s <%s>" % (
                event["submitter"]["name"], event["submitter"]["email"])

        return self.addChange(dict(
            author=author,
            project=ref["project"],
            repository="ssh://%s@%s:%s/%s" % (
                self.username, self.gerritserver,
                self.gerritport, ref["project"]),
            branch=ref["refName"],
            revision=ref["newRev"],
            comments="Gerrit: patchset(s) merged.",
            files=["unknown"],
            category=event["type"],
            properties=properties))

    def streamProcessStopped(self):
        self.process = None

        # if the service is stopped, don't try to restart the process
        if not self.wantProcess:
            log.msg("service is not running; not reconnecting")
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
            self.startStreamProcess()
            self.streamProcessTimeout = self.STREAM_BACKOFF_MIN

    def startStreamProcess(self):
        log.msg("starting 'gerrit stream-events'")
        self.lastStreamProcessStart = util.now()
        uri = "%s@%s" % (self.username, self.gerritserver)
        args = [uri, "-p", str(self.gerritport)]
        if self.identity_file is not None:
            args = args + ['-i', self.identity_file]
        self.process = reactor.spawnProcess(
            self.LocalPP(self), "ssh",
            ["ssh"] + args + ["gerrit", "stream-events"])

    def startService(self):
        self.wantProcess = True
        self.startStreamProcess()

    def stopService(self):
        self.wantProcess = False
        if self.process:
            self.process.signalProcess("KILL")
        # TODO: if this occurs while the process is restarting, some exceptions
        # may be logged, although things will settle down normally
        return base.ChangeSource.stopService(self)

    def describe(self):
        status = ""
        if not self.process:
            status = "[NOT CONNECTED - check log]"
        msg = ("GerritChangeSource watching the remote "
               "Gerrit repository %s@%s %s")
        return msg % (self.username, self.gerritserver, status)
