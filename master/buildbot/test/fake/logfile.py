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
from buildbot.status.logfile import HEADER
from buildbot.status.logfile import STDERR
from buildbot.status.logfile import STDOUT
from buildbot.util import lineboundaries
from twisted.internet import defer
from twisted.python import log


class FakeLogFile(object):

    def __init__(self, name, step):
        self.name = name
        self.header = ''
        self.stdout = ''
        self.stderr = ''
        self.chunks = []
        self.lbfs = {}
        self.finished = False
        self.step = step
        self.subPoint = util.subscription.SubscriptionPoint("%r log" % (name,))

    def getName(self):
        return self.name

    def subscribe(self, callback):
        log.msg("NOTE: fake logfile subscription never produces anything")
        return self.subPoint.subscribe(callback)

    def _getLbf(self, stream, meth):
        try:
            return self.lbfs[stream]
        except KeyError:
            def wholeLines(lines):
                if not isinstance(lines, unicode):
                    lines = lines.decode('utf-8')
                if self.name in self.step.logobservers:
                    for obs in self.step.logobservers[self.name]:
                        getattr(obs, meth)(lines)
            lbf = self.lbfs[stream] = \
                lineboundaries.LineBoundaryFinder(wholeLines)
            return lbf

    def addHeader(self, text):
        self.header += text
        self.chunks.append((HEADER, text))
        self._getLbf('h', 'headerReceived').append(text)
        return defer.succeed(None)

    def addStdout(self, text):
        self.stdout += text
        self.chunks.append((STDOUT, text))
        self._getLbf('o', 'outReceived').append(text)
        return defer.succeed(None)

    def addStderr(self, text):
        self.stderr += text
        self.chunks.append((STDERR, text))
        self._getLbf('e', 'errReceived').append(text)
        return defer.succeed(None)

    def isFinished(self):
        return self.finished

    def waitUntilFinished(self):
        log.msg("NOTE: fake waitUntilFinished doesn't actually wait")
        return defer.Deferred()

    def flushFakeLogfile(self):
        for lbf in self.lbfs.values():
            lbf.flush()

    def finish(self):
        self.flushFakeLogfile()
        self.finished = True

    def fakeData(self, header='', stdout='', stderr=''):
        if header:
            self.header += header
            self.chunks.append((HEADER, header))
        if stdout:
            self.stdout += stdout
            self.chunks.append((STDOUT, stdout))
        if stderr:
            self.stderr += stderr
            self.chunks.append((STDERR, stderr))
