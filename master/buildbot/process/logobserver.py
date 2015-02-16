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

from buildbot import interfaces
from twisted.protocols import basic
from zope.interface import implements


class LogObserver:
    implements(interfaces.ILogObserver)

    def setStep(self, step):
        self.step = step

    def setLog(self, loog):
        assert interfaces.IStatusLog.providedBy(loog)
        loog.subscribe(self, True)

    def logChunk(self, build, step, log, channel, text):
        if channel == interfaces.LOG_CHANNEL_STDOUT:
            self.outReceived(text)
        elif channel == interfaces.LOG_CHANNEL_STDERR:
            self.errReceived(text)

    # TODO: add a logEnded method? er, stepFinished?

    def outReceived(self, data):
        """This will be called with chunks of stdout data. Override this in
        your observer."""
        pass

    def errReceived(self, data):
        """This will be called with chunks of stderr data. Override this in
        your observer."""
        pass


class LogLineObserver(LogObserver):

    def __init__(self):
        self.stdoutParser = basic.LineOnlyReceiver()
        self.stdoutParser.delimiter = "\n"
        self.stdoutParser.lineReceived = self.outLineReceived
        self.stdoutParser.transport = self  # for the .disconnecting attribute
        self.disconnecting = False

        self.stderrParser = basic.LineOnlyReceiver()
        self.stderrParser.delimiter = "\n"
        self.stderrParser.lineReceived = self.errLineReceived
        self.stderrParser.transport = self

    def setMaxLineLength(self, max_length):
        """
        Set the maximum line length: lines longer than max_length are
        dropped.  Default is 16384 bytes.  Use sys.maxint for effective
        infinity.
        """
        self.stdoutParser.MAX_LENGTH = max_length
        self.stderrParser.MAX_LENGTH = max_length

    def outReceived(self, data):
        self.stdoutParser.dataReceived(data)

    def errReceived(self, data):
        self.stderrParser.dataReceived(data)

    def outLineReceived(self, line):
        """This will be called with complete stdout lines (not including the
        delimiter). Override this in your observer."""
        pass

    def errLineReceived(self, line):
        """This will be called with complete lines of stderr (not including
        the delimiter). Override this in your observer."""
        pass


class OutputProgressObserver(LogObserver):
    length = 0

    def __init__(self, name):
        self.name = name

    def logChunk(self, build, step, log, channel, text):
        self.length += len(text)
        self.step.setProgress(self.name, self.length)


class BufferLogObserver(LogObserver):

    def __init__(self, wantStdout=True, wantStderr=False):
        self.stdout = [] if wantStdout else None
        self.stderr = [] if wantStderr else None

    def outReceived(self, data):
        if self.stdout is not None:
            self.stdout.append(data)

    def errReceived(self, data):
        if self.stderr is not None:
            self.stderr.append(data)

    def _get(self, chunks):
        if chunks is None or not chunks:
            return u''
        return u''.join(chunks)

    def getStdout(self):
        return self._get(self.stdout)

    def getStderr(self):
        return self._get(self.stderr)
