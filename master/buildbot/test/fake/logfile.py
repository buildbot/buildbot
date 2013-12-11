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

import StringIO
import warnings

from buildbot.status.logfile import HEADER
from buildbot.status.logfile import STDERR
from buildbot.status.logfile import STDOUT
from twisted.internet import defer
from twisted.python import log


class FakeLogFile(object):

    def __init__(self, name, step):
        self.name = name
        self.header = ''
        self.stdout = ''
        self.stderr = ''
        self.chunks = []
        self.finished = False
        self.step = step

    def getName(self):
        return self.name

    def subscribe(self, receiver, catchup):
        assert not catchup, "catchup must be False"
        # no actual subscription..

    def unsubscribe(self, receiver):
        pass

    def addHeader(self, text):
        self.header += text
        self.chunks.append((HEADER, text))

    def addStdout(self, text):
        self.stdout += text
        self.chunks.append((STDOUT, text))
        if self.name in self.step.logobservers:
            for obs in self.step.logobservers[self.name]:
                obs.outReceived(text)

    def addStderr(self, text):
        self.stderr += text
        self.chunks.append((STDERR, text))
        if self.name in self.step.logobservers:
            for obs in self.step.logobservers[self.name]:
                obs.errReceived(text)

    def isFinished(self):
        return self.finished

    def waitUntilFinished(self):
        log.msg("NOTE: fake waitUntilFinished doesn't actually wait")
        return defer.Deferred()

    def finish(self):
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

    # removed methods, here temporarily

    def readlines(self):
        warnings.warn("step uses removed LogFile method `readlines`")
        io = StringIO.StringIO(self.stdout)
        return io.readlines()

    def hasContents(self):
        warnings.warn("step uses removed LogFile method `hasContents`")
        return self.chunks

    def getText(self):
        warnings.warn("step uses removed LogFile method `getText`")
        return ''.join([c for str, c in self.chunks
                        if str in (STDOUT, STDERR)])

    def getTextWithHeaders(self):
        warnings.warn("step uses removed LogFile method `getTextWithHeaders`")
        return ''.join([c for str, c in self.chunks])

    def getChunks(self, channels=[], onlyText=False):
        warnings.warn("step uses removed LogFile method `getChunks`")
        if onlyText:
            return [data
                    for (ch, data) in self.chunks
                    if not channels or ch in channels]
        else:
            return [(ch, data)
                    for (ch, data) in self.chunks
                    if not channels or ch in channels]
