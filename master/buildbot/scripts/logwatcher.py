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


import os
import platform

from twisted.internet import defer
from twisted.internet import error
from twisted.internet import protocol
from twisted.internet import reactor
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
        self.lw.print_output(f"ERR: '{data}'")


class LineOnlyLongLineReceiver(protocol.Protocol):
    """
    This is almost the same as Twisted's LineOnlyReceiver except that long lines are handled
    appropriately.
    """
    _buffer = b''
    delimiter = b'\r\n'
    MAX_LENGTH = 16384

    def dataReceived(self, data):
        lines = (self._buffer + data).split(self.delimiter)
        self._buffer = lines.pop(-1)
        for line in lines:
            if self.transport.disconnecting:
                # this is necessary because the transport may be told to lose
                # the connection by a line within a larger packet, and it is
                # important to disregard all the lines in that packet following
                # the one that told it to close.
                return
            if len(line) > self.MAX_LENGTH:
                self.lineLengthExceeded(line)
            else:
                self.lineReceived(line)

    def lineReceived(self, line):
        raise NotImplementedError

    def lineLengthExceeded(self, line):
        raise NotImplementedError


class LogWatcher(LineOnlyLongLineReceiver):
    POLL_INTERVAL = 0.1
    TIMEOUT_DELAY = 10.0
    delimiter = unicode2bytes(os.linesep)

    def __init__(self, logfile, timeout=None, _reactor=reactor):
        self.logfile = logfile
        self.in_reconfig = False
        self.transport = FakeTransport()
        self.pp = TailProcess()
        self.pp.lw = self
        self.timer = None
        self._reactor = _reactor
        self._timeout_delay = timeout or self.TIMEOUT_DELAY

    def start(self):
        # If the log file doesn't exist, create it now.
        self.create_logfile(self.logfile)

        # return a Deferred that fires when the reconfig process has
        # finished. It errbacks with TimeoutError if the startup has not
        # progressed for 10 seconds, and with ReconfigError if the error
        # line was seen. If the logfile could not be opened, it errbacks with
        # an IOError.
        if platform.system().lower() == 'sunos' and os.path.exists('/usr/xpg4/bin/tail'):
            tailBin = "/usr/xpg4/bin/tail"
        elif platform.system().lower() == 'haiku' and os.path.exists('/bin/tail'):
            tailBin = "/bin/tail"
        else:
            tailBin = "/usr/bin/tail"

        args = ("tail", "-F", "-n", "0", self.logfile)
        self.p = self._reactor.spawnProcess(self.pp, tailBin, args,
                                            env=os.environ)
        self.running = True
        d = defer.maybeDeferred(self._start)
        return d

    def _start(self):
        self.d = defer.Deferred()
        self.startTimer()
        return self.d

    def startTimer(self):
        self.timer = self._reactor.callLater(self._timeout_delay, self.timeout)

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

    def create_logfile(self, path):  # pragma: no cover
        if not os.path.exists(path):
            with open(path, 'a', encoding='utf-8'):
                pass

    def print_output(self, output):  # pragma: no cover
        print(output)

    def lineLengthExceeded(self, line):
        msg = f'Got an a very long line in the log (length {len(line)} bytes), ignoring'
        self.print_output(msg)

    def lineReceived(self, line):
        if not self.running:
            return None
        if b"Log opened." in line:
            self.in_reconfig = True
        if b"beginning configuration update" in line:
            self.in_reconfig = True

        if self.in_reconfig:
            self.print_output(line.decode())

        # certain lines indicate progress, so we "cancel" the timeout
        # and it will get re-added when it fires
        PROGRESS_TEXT = [b'Starting BuildMaster', b'Loading configuration from', b'added builder',
                         b'adding scheduler', b'Loading builder', b'Starting factory']
        for progressText in PROGRESS_TEXT:
            if progressText in line:
                self.timer = None
                break

        if b"message from master: attached" in line:
            return self.finished("worker")
        if b"configuration update aborted" in line or \
                b'configuration update partially applied' in line:
            return self.finished(Failure(ReconfigError()))
        if b"Server Shut Down" in line:
            return self.finished(Failure(ReconfigError()))
        if b"configuration update complete" in line:
            return self.finished("buildmaster")
        if b"BuildMaster is running" in line:
            return self.finished("buildmaster")
        if b"BuildMaster startup failed" in line:
            return self.finished(Failure(BuildmasterStartupError()))
        return None
