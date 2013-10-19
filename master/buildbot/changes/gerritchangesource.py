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

from twisted.internet import reactor

from buildbot.changes import base
from buildbot.util import json
from buildbot import util
from twisted.python import log
from twisted.internet import defer
from twisted.internet.protocol import ProcessProtocol

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

    def __init__(self, gerritserver, username, gerritport=29418, identity_file=None):
        """
        @type  gerritserver: string
        @param gerritserver: the dns or ip that host the gerrit ssh server,

        @type  gerritport: int
        @param gerritport: the port of the gerrit ssh server,

        @type  username: string
        @param username: the username to use to connect to gerrit,

        @type  identity_file: string
        @param identity_file: identity file to for authentication (optional).

        """
        # TODO: delete API comment when documented

        self.gerritserver = gerritserver
        self.gerritport = gerritport
        self.username = username
        self.identity_file = identity_file
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
            self.data = lines.pop(-1) # last line is either empty or incomplete
            for line in lines:
                log.msg("gerrit: %s" % (line,))
                yield self.change_source.lineReceived(line)

        def errReceived(self, data):
            log.msg("gerrit stderr: %s" % (data,))

        def processEnded(self, status_object):
            self.change_source.streamProcessStopped()

    def lineReceived(self, line):
        try:
            event = json.loads(line.decode('utf-8'))
        except ValueError:
            log.msg("bad json line: %s" % (line,))
            return defer.succeed(None)

        if not(type(event) == type({}) and "type" in event):
            log.msg("no type in event %s" % (line,))
            return defer.succeed(None)
        func = getattr(self, "eventReceived_"+event["type"].replace("-","_"), None)
        if func == None:
            log.msg("unsupported event %s" % (event["type"],))
            return defer.succeed(None)

        # flatten the event dictionary, for easy access with WithProperties
        def flatten(properties, base, event):
            for k, v in event.items():
                if type(v) == dict:
                    flatten(properties, base + "." + k, v)
                else: # already there
                    properties[base + "." + k] = v

        properties = {}
        flatten(properties, "event", event)
        return func(properties,event)
    def addChange(self, chdict):
        d = self.master.addChange(**chdict)
        # eat failures..
        d.addErrback(log.err, 'error adding change from GerritChangeSource')
        return d
    def eventReceived_patchset_created(self, properties, event):
        change = event["change"]
        return self.addChange(dict(
                author="%s <%s>" % (change["owner"]["name"], change["owner"]["email"]),
                project=change["project"],
                repository="ssh://%s@%s:%s/%s" % (
                    self.username, self.gerritserver, self.gerritport, change["project"]),
                branch=change["branch"]+"/"+change["number"],
                revision=event["patchSet"]["revision"],
                revlink=change["url"],
                comments=change["subject"],
                files=["unknown"],
                category=event["type"],
                properties=properties))
    def eventReceived_ref_updated(self, properties, event):
        ref = event["refUpdate"]
        author = "gerrit"

        if "submitter" in event:
            author="%s <%s>" % (event["submitter"]["name"], event["submitter"]["email"])

        return self.addChange(dict(
                author=author,
                project=ref["project"],
                repository="ssh://%s@%s:%s/%s" % (
                    self.username, self.gerritserver, self.gerritport, ref["project"]),
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
        if now - self.lastStreamProcessStart < self.STREAM_GOOD_CONNECTION_TIME:
            # bad startup; start the stream process again after a timeout, and then
            # increase the timeout
            log.msg("'gerrit stream-events' failed; restarting after %ds" % round(self.streamProcessTimeout))
            reactor.callLater(self.streamProcessTimeout, self.startStreamProcess)
            self.streamProcessTimeout *= self.STREAM_BACKOFF_EXPONENT
            if self.streamProcessTimeout > self.STREAM_BACKOFF_MAX:
                self.streamProcessTimeout = self.STREAM_BACKOFF_MAX
        else:
            # good startup, but lost connection; restart immediately, and set the timeout
            # to its minimum
            self.startStreamProcess()
            self.streamProcessTimeout = self.STREAM_BACKOFF_MIN

    def startStreamProcess(self):
        log.msg("starting 'gerrit stream-events'")
        self.lastStreamProcessStart = util.now()
        args = [ self.username+"@"+self.gerritserver,"-p", str(self.gerritport)]
        if self.identity_file is not None:
            args = args + [ '-i', self.identity_file ]
        self.process = reactor.spawnProcess(self.LocalPP(self), "ssh",
          [ "ssh" ] + args + [ "gerrit", "stream-events" ])

    def startService(self):
        self.wantProcess = True
        self.startStreamProcess()

    def stopService(self):
        self.wantProcess = False
        if self.process:
            self.process.signalProcess("KILL")
        # TODO: if this occurs while the process is restarting, some exceptions may
        # be logged, although things will settle down normally
        return base.ChangeSource.stopService(self)

    def describe(self):
        status = ""
        if not self.process:
            status = "[NOT CONNECTED - check log]"
        str = ('GerritChangeSource watching the remote Gerrit repository %s@%s %s' %
                            (self.username, self.gerritserver, status))
        return str

