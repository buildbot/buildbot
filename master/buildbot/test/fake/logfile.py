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

from twisted.internet import defer

from buildbot import util
from buildbot.util import lineboundaries


class FakeLogFile:

    def __init__(self, name):
        self.name = name
        self.header = ''
        self.stdout = ''
        self.stderr = ''
        self.lbfs = {}
        self.finished = False
        self._finish_waiters = []
        self._had_errors = False
        self.subPoint = util.subscription.SubscriptionPoint("%r log" % (name,))

    def getName(self):
        return self.name

    def subscribe(self, callback):
        return self.subPoint.subscribe(callback)

    def _getLbf(self, stream, meth):
        try:
            return self.lbfs[stream]
        except KeyError:
            def wholeLines(lines):
                self.subPoint.deliver(stream, lines)
                assert not self.finished
            lbf = self.lbfs[stream] = \
                lineboundaries.LineBoundaryFinder(wholeLines)
            return lbf

    def addHeader(self, text):
        if not isinstance(text, str):
            text = text.decode('utf-8')
        self.header += text
        self._getLbf('h', 'headerReceived').append(text)
        return defer.succeed(None)

    def addStdout(self, text):
        if not isinstance(text, str):
            text = text.decode('utf-8')
        self.stdout += text
        self._getLbf('o', 'outReceived').append(text)
        return defer.succeed(None)

    def addStderr(self, text):
        if not isinstance(text, str):
            text = text.decode('utf-8')
        self.stderr += text
        self._getLbf('e', 'errReceived').append(text)
        return defer.succeed(None)

    def isFinished(self):
        return self.finished

    def waitUntilFinished(self):
        d = defer.Deferred()
        if self.finished:
            d.succeed(None)
        else:
            self._finish_waiters.append(d)
        return d

    def flushFakeLogfile(self):
        for lbf in self.lbfs.values():
            lbf.flush()

    def had_errors(self):
        return self._had_errors

    @defer.inlineCallbacks
    def finish(self):
        assert not self.finished

        self.flushFakeLogfile()
        self.finished = True

        # notify subscribers *after* finishing the log
        self.subPoint.deliver(None, None)

        yield self.subPoint.waitForDeliveriesToFinish()
        self._had_errors = len(self.subPoint.pop_exceptions()) > 0

        # notify those waiting for finish
        for d in self._finish_waiters:
            d.callback(None)

    def fakeData(self, header='', stdout='', stderr=''):
        if header:
            self.header += header
        if stdout:
            self.stdout += stdout
        if stderr:
            self.stderr += stderr
