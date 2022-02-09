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

from buildbot import config
from buildbot.process import buildstep
from buildbot.process import logobserver
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS


class MaxQObserver(logobserver.LogLineObserver):

    def __init__(self):
        super().__init__()
        self.failures = 0

    def outLineReceived(self, line):
        if line.startswith('TEST FAILURE:'):
            self.failures += 1


class MaxQ(buildstep.ShellMixin, buildstep.BuildStep):
    flunkOnFailure = True
    name = "maxq"
    binary = 'run_maxq.py'

    failures = 0

    def __init__(self, testdir=None, **kwargs):
        if not testdir:
            config.error("please pass testdir")
        self.testdir = testdir

        kwargs = self.setupShellMixin(kwargs)
        super().__init__(**kwargs)
        self.observer = MaxQObserver()
        self.addLogObserver('stdio', self.observer)

    @defer.inlineCallbacks
    def run(self):
        command = [self.binary]
        command.append(self.testdir)

        cmd = yield self.makeRemoteShellCommand(command=command)
        yield self.runCommand(cmd)

        stdio_log = yield self.getLog('stdio')
        yield stdio_log.finish()

        self.failures = self.observer.failures

        # treat a nonzero exit status as a failure, if no other failures are
        # detected
        if not self.failures and cmd.didFail():
            self.failures = 1
        if self.failures:
            return FAILURE
        return SUCCESS

    def getResultSummary(self):
        if self.failures:
            return {'step': f"{self.failures} maxq failures"}
        return {'step': 'success'}
