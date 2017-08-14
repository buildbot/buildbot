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

from io import StringIO

from twisted.internet import defer

from buildbot.test.util.integration import RunMasterBase

# This integration test creates a master and worker environment,
# with two builders and a trigger step linking them

expectedOutputRegex = \
    r"""\*\*\* BUILD 1 \*\*\* ==> build successful \(success\)
    \*\*\* STEP shell \*\*\* ==> 'echo hello' \(success\)
        log:stdio \({loglines}\)
    \*\*\* STEP trigger \*\*\* ==> triggered trigsched \(success\)
       url:trigsched #2 \(http://localhost:8080/#buildrequests/2\)
       url:success: build #1 \(http://localhost:8080/#builders/(1|2)/builds/1\)
    \*\*\* STEP shell_1 \*\*\* ==> 'echo world' \(success\)
        log:stdio \({loglines}\)
\*\*\* BUILD 2 \*\*\* ==> build successful \(success\)
    \*\*\* STEP shell \*\*\* ==> 'echo ola' \(success\)
        log:stdio \({loglines}\)
"""


class TriggeringMaster(RunMasterBase):

    @defer.inlineCallbacks
    def test_trigger(self):
        yield self.setupConfig(masterConfig())

        change = dict(branch="master",
                      files=["foo.c"],
                      author="me@foo.com",
                      comments="good stuff",
                      revision="HEAD",
                      project="none"
                      )
        build = yield self.doForceBuild(wantSteps=True, useChange=change, wantLogs=True)

        self.assertEqual(
            build['steps'][1]['state_string'], 'triggered trigsched')
        builds = yield self.master.data.get(("builds",))
        self.assertEqual(len(builds), 2)
        dump = StringIO()
        for b in builds:
            yield self.printBuild(b, dump)
        # depending on the environment the number of lines is different between
        # test hosts
        loglines = builds[1]['steps'][0]['logs'][0]['num_lines']
        self.assertRegex(dump.getvalue(),
                         expectedOutputRegex.format(loglines=loglines))


# master configuration
def masterConfig():
    c = {}
    from buildbot.config import BuilderConfig
    from buildbot.process.factory import BuildFactory
    from buildbot.plugins import steps, schedulers

    c['schedulers'] = [
        schedulers.Triggerable(
            name="trigsched",
            builderNames=["build"]),
        schedulers.AnyBranchScheduler(
            name="sched",
            builderNames=["testy"])]

    f = BuildFactory()
    f.addStep(steps.ShellCommand(command='echo hello'))
    f.addStep(steps.Trigger(schedulerNames=['trigsched'],
                            waitForFinish=True,
                            updateSourceStamp=True))
    f.addStep(steps.ShellCommand(command='echo world'))
    f2 = BuildFactory()
    f2.addStep(steps.ShellCommand(command='echo ola'))
    c['builders'] = [
        BuilderConfig(name="testy",
                      workernames=["local1"],
                      factory=f),
        BuilderConfig(name="build",
                      workernames=["local1"],
                      factory=f2)]
    return c
