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
from buildbot.status.event import Event
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

    def startStatus(self):
        evt = Event("yellow", ['running', 'maxq', 'tests'],
                    files={'log': self.log})
        self.setCurrentActivity(evt)


    def finished(self, rc):
        self.failures = 0
        if rc:
            self.failures = 1
        output = self.log.getAll()
        self.failures += output.count('\nTEST FAILURE:')

        result = (SUCCESS, ['maxq'])

        if self.failures:
            result = (FAILURE, [str(self.failures), 'maxq', 'failures'])

        return self.stepComplete(result)

    def finishStatus(self, result):
        if self.failures:
            text = ["maxq", "failed"]
        else:
            text = ['maxq', 'tests']
        self.updateCurrentActivity(text=text)
        self.finishStatusSummary()
        self.finishCurrentActivity()


