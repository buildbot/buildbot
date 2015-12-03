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

from buildbot.test.util.decorators import flaky
from buildbot.test.util.integration import RunMasterBase
from twisted.internet import defer

# This integration test creates a master and slave environment,
# with two builders and a trigger step linking them

expectedOutput = """\
*** BUILD 1 *** ==> finished (success)
    *** STEP shell *** ==> 'echo hello' (success)
        log:stdio (%(loglines)s)
    *** STEP trigger *** ==> triggered trigsched (success)
       url:trigsched #2 (http://localhost:8080/#buildrequests/2)
       url:success: build #1 (http://localhost:8080/#builders/2/builds/1)
    *** STEP shell_1 *** ==> 'echo world' (success)
        log:stdio (%(loglines)s)
*** BUILD 2 *** ==> finished (success)
    *** STEP shell *** ==> 'echo ola' (success)
        log:stdio (%(loglines)s)
"""


class TriggeringMaster(RunMasterBase):

    @flaky(bugNumber=3339)
    @defer.inlineCallbacks
    def test_trigger(self):

        change = dict(branch="master",
                      files=["foo.c"],
                      author="me@foo.com",
                      comments="good stuff",
                      revision="HEAD",
                      project="none"
                      )
        build = yield self.doForceBuild(wantSteps=True, useChange=change, wantLogs=True)

        self.assertEqual(build['steps'][1]['state_string'], 'triggered trigsched')
        builds = yield self.master.data.get(("builds",))
        self.assertEqual(len(builds), 2)
        dump = StringIO.StringIO()
        for b in builds:
            yield self.printBuild(b, dump)
        # depending on the environment the number of lines is different between test hosts
        loglines = builds[1]['steps'][0]['logs'][0]['num_lines']
        self.assertEqual(dump.getvalue(), expectedOutput % dict(loglines=loglines))


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
                      slavenames=["local1"],
                      factory=f),
        BuilderConfig(name="build",
                      slavenames=["local1"],
                      factory=f2)]
    return c
