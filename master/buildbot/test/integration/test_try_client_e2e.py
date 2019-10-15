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


import os

from twisted.internet import defer
from twisted.internet import reactor

from buildbot.test.util.integration import RunMasterBase


# This integration test tests that the try command line works end2end
class TryClientE2E(RunMasterBase):
    timeout = 15

    @defer.inlineCallbacks
    def test_shell(self):
        yield self.setupConfig(masterConfig())

        def trigger_callback():
            def thd():
                os.system("buildbot try --connect=pb --master=127.0.0.1:8031 -b testy "
                          "--property=foo:bar --username=alice --passwd=pw1 --vc=none")
            reactor.callInThread(thd)

        build = yield self.doForceBuild(wantSteps=True, triggerCallback=trigger_callback, wantLogs=True, wantProperties=True)
        self.assertEqual(build['buildid'], 1)


# master configuration
def masterConfig():
    c = {}
    from buildbot.config import BuilderConfig
    from buildbot.process.factory import BuildFactory
    from buildbot.plugins import steps, schedulers

    c['schedulers'] = [
        schedulers.Try_Userpass(name="try",
                                builderNames=["testy"],
                                port=8031,
                                userpass=[("alice", "pw1")])
    ]
    f = BuildFactory()
    f.addStep(steps.ShellCommand(command='echo hello'))
    c['builders'] = [
        BuilderConfig(name="testy",
                      workernames=["local1"],
                      factory=f)]
    return c
