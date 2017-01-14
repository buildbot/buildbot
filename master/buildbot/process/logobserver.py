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

from zope.interface import implementer

from buildbot import interfaces


@implementer(interfaces.ILogObserver)
class LogObserver(object):

    def setStep(self, step):
        self.step = step

    def setLog(self, loog):
        loog.subscribe(self.gotData)

    def gotData(self, stream, data):
        if data is None:
            self.finishReceived()
        elif stream is None or stream == 'o':
            self.outReceived(data)
        elif stream == 'e':
            self.errReceived(data)
        elif stream == 'h':
            self.headerReceived(data)

    def finishReceived(self):
        pass

    def outReceived(self, data):
        pass

    def errReceived(self, data):
        pass

    def headerReceived(self, data):
        pass


class LogLineObserver(LogObserver):
    stdoutDelimiter = "\n"
    stderrDelimiter = "\n"
    headerDelimiter = "\n"

    def __init__(self):
        self.max_length = 16384

    def setMaxLineLength(self, max_length):
        """
        Set the maximum line length: lines longer than max_length are
        dropped.  Default is 16384 bytes.  Use sys.maxint for effective
        infinity.
        """
        self.max_length = max_length

    def _lineReceived(self, data, delimiter, funcReceived):
        for line in data.rstrip().split(delimiter):
            if len(line) > self.max_length:
                continue
            funcReceived(line)

    def outReceived(self, data):
        self._lineReceived(data, self.stdoutDelimiter, self.outLineReceived)

    def errReceived(self, data):
        self._lineReceived(data, self.stderrDelimiter, self.errLineReceived)

    def headerReceived(self, data):
        self._lineReceived(data, self.headerDelimiter, self.headerLineReceived)

    def outLineReceived(self, line):
        """This will be called with complete stdout lines (not including the
        delimiter). Override this in your observer."""
        pass

    def errLineReceived(self, line):
        """This will be called with complete lines of stderr (not including
        the delimiter). Override this in your observer."""
        pass

    def headerLineReceived(self, line):
        """This will be called with complete lines of stderr (not including
        the delimiter). Override this in your observer."""
        pass


class LineConsumerLogObserver(LogLineObserver):

    def __init__(self, consumerFunction):
        LogLineObserver.__init__(self)
        self.generator = None
        self.consumerFunction = consumerFunction

    def feed(self, input):
        # note that we defer starting the generator until the first bit of
        # data, since the observer may be instantiated during configuration as
        # well as for each execution of the step.
        self.generator = self.consumerFunction()
        next(self.generator)
        # shortcut all remaining feed operations
        self.feed = self.generator.send
        self.feed(input)

    def outLineReceived(self, line):
        self.feed(('o', line))

    def errLineReceived(self, line):
        self.feed(('e', line))

    def headerLineReceived(self, line):
        self.feed(('h', line))

    def finishReceived(self):
        if self.generator:
            self.generator.close()


class OutputProgressObserver(LogObserver):
    length = 0

    def __init__(self, name):
        self.name = name

    def gotData(self, stream, data):
        if data:
            self.length += len(data)
        self.step.setProgress(self.name, self.length)


class BufferLogObserver(LogObserver):

    def __init__(self, wantStdout=True, wantStderr=False):
        LogObserver.__init__(self)
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
