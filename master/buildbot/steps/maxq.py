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

from buildbot import config
from buildbot.process import buildstep
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.steps.shell import ShellCommand


class MaxQObserver(buildstep.LogLineObserver):

    def __init__(self):
        buildstep.LogLineObserver.__init__(self)
        self.failures = 0

    def outLineReceived(self, line):
        if line.startswith('TEST FAILURE:'):
            self.failures += 1


class MaxQ(ShellCommand):
    flunkOnFailure = True
    name = "maxq"

    def __init__(self, testdir=None, **kwargs):
        if not testdir:
            config.error("please pass testdir")
        kwargs['command'] = 'run_maxq.py %s' % (testdir,)
        ShellCommand.__init__(self, **kwargs)
        self.observer = MaxQObserver()
        self.addLogObserver('stdio', self.observer)

    def commandComplete(self, cmd):
        self.failures = self.observer.failures

    def evaluateCommand(self, cmd):
        # treat a nonzero exit status as a failure, if no other failures are
        # detected
        if not self.failures and cmd.didFail():
            self.failures = 1
        if self.failures:
            return FAILURE
        return SUCCESS

    def getResultSummary(self):
        if self.failures:
            return {u'step': u"%d maxq failures" % self.failures}
        return {u'step': u'success'}
