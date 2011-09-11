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

from buildbot.steps.shell import ShellCommand
from buildbot.status.results import SUCCESS, FAILURE

class MaxQ(ShellCommand):
    flunkOnFailure = True
    name = "maxq"

    def __init__(self, testdir=None, **kwargs):
        if not testdir:
            raise TypeError("please pass testdir")
        kwargs['command'] = 'run_maxq.py %s' % (testdir,)
        ShellCommand.__init__(self, **kwargs)
        self.addFactoryArguments(testdir=testdir)

    def commandComplete(self, cmd):
        output = cmd.logs['stdio'].getText()
        self.failures = output.count('\nTEST FAILURE:')

    def evaluateCommand(self, cmd):
        # treat a nonzero exit status as a failure, if no other failures are
        # detected
        if not self.failures and cmd.rc != 0:
            self.failures = 1
        if self.failures:
            return FAILURE
        return SUCCESS

    def getText(self, cmd, results):
        if self.failures:
            return [ str(self.failures), 'maxq', 'failures' ]
        return ['maxq', 'tests']
