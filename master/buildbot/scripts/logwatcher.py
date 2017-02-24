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
from __future__ import division
from __future__ import print_function

import os
import platform

from twisted.internet import defer
from twisted.internet import error
from twisted.internet import protocol
from twisted.internet import reactor
from twisted.protocols.basic import LineOnlyReceiver
from twisted.python.failure import Failure

from buildbot.util import unicode2bytes


class FakeTransport:
    disconnecting = False


class BuildmasterTimeoutError(Exception):
    pass


class BuildmasterStartupError(Exception):
    pass


class ReconfigError(Exception):
    pass


class TailProcess(protocol.ProcessProtocol):

    def outReceived(self, data):
        self.lw.dataReceived(data)

    def errReceived(self, data):
        print("ERR: '%s'" % (data,))


class LogWatcher(LineOnlyReceiver):
    POLL_INTERVAL = 0.1
    TIMEOUT_DELAY = 10.0
    delimiter = unicode2bytes(os.linesep)

    def __init__(self, logfile):
        self.logfile = logfile
        self.in_reconfig = False
        self.transport = FakeTransport()
        self.pp = TailProcess()
        self.pp.lw = self
        self.timer = None

    def start(self):
        # If the log file doesn't exist, create it now.
        if not os.path.exists(self.logfile):
            open(self.logfile, 'a').close()

        # return a Deferred that fires when the reconfig process has
        # finished. It errbacks with TimeoutError if the finish line has not
        # been seen within 10 seconds, and with ReconfigError if the error
        # line was seen. If the logfile could not be opened, it errbacks with
        # an IOError.
        if platform.system().lower() == 'sunos' and os.path.exists('/usr/xpg4/bin/tail'):
            tailBin = "/usr/xpg4/bin/tail"
        else:
            tailBin = "/usr/bin/tail"
        self.p = reactor.spawnProcess(self.pp, tailBin,
                                      ("tail", "-f", "-n", "0", self.logfile),
                                      env=os.environ,
                                      )
        self.running = True
        d = defer.maybeDeferred(self._start)
        return d

    def _start(self):
        self.d = defer.Deferred()
        self.startTimer()
        return self.d

    def startTimer(self):
        self.timer = reactor.callLater(self.TIMEOUT_DELAY, self.timeout)

    def timeout(self):
        # was the timeout set to be ignored? if so, restart it
        if not self.timer:
            self.startTimer()
            return

        self.timer = None
        e = BuildmasterTimeoutError()
        self.finished(Failure(e))

    def finished(self, results):
        try:
            self.p.signalProcess("KILL")
        except error.ProcessExitedAlready:
            pass
        if self.timer:
            self.timer.cancel()
            self.timer = None
        self.running = False
        self.in_reconfig = False
        self.d.callback(results)

    def lineReceived(self, line):
        if not self.running:
            return
        if b"Log opened." in line:
            self.in_reconfig = True
        if b"beginning configuration update" in line:
            self.in_reconfig = True

        if self.in_reconfig:
            print(line)

        # certain lines indicate progress, so we "cancel" the timeout
        # and it will get re-added when it fires
        PROGRESS_TEXT = [b'Starting BuildMaster', b'Loading configuration from',
                         b'added builder', b'adding scheduler', b'Loading builder', b'Starting factory']
        for progressText in PROGRESS_TEXT:
            if progressText in line:
                self.timer = None
                break

        if b"message from master: attached" in line:
            return self.finished("worker")
        if b"reconfig aborted" in line or b'reconfig partially applied' in line:
            return self.finished(Failure(ReconfigError()))
        if b"Server Shut Down" in line:
            return self.finished(Failure(ReconfigError()))
        if b"configuration update complete" in line:
            return self.finished("buildmaster")
        if b"BuildMaster is running" in line:
            return self.finished("buildmaster")
        if b"BuildMaster startup failed" in line:
            return self.finished(Failure(BuildmasterStartupError()))
