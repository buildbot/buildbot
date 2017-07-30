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

from twisted.internet import defer
from twisted.python import runtime

from buildbot.process.results import SUCCESS
from buildbot.test.util.integration import RunMasterBase

# This integration test creates a master and worker environment
# and make sure the UrlForBuild renderable is working


class UrlForBuildMaster(RunMasterBase):

    proto = "null"

    @defer.inlineCallbacks
    def test_url(self):
        yield self.setupConfig(masterConfig())

        build = yield self.doForceBuild(wantSteps=True, wantLogs=True)
        self.assertEqual(build['results'], SUCCESS)
        if runtime.platformType == 'win32':
            command = u"echo http://localhost:8080/#builders/1/builds/1"
        else:
            command = u"echo 'http://localhost:8080/#builders/1/builds/1'"

        self.assertIn(command,
                      build['steps'][0]['logs'][0]['contents']['content'])


# master configuration
def masterConfig():
    c = {}
    from buildbot.config import BuilderConfig
    from buildbot.process.factory import BuildFactory
    from buildbot.plugins import steps, schedulers, util

    c['schedulers'] = [
        schedulers.ForceScheduler(
            name="force",
            builderNames=["testy"])]

    f = BuildFactory()
    # do a bunch of transfer to exercise the protocol
    f.addStep(steps.ShellCommand(command=["echo", util.URLForBuild]))
    c['builders'] = [
        BuilderConfig(name="testy",
                      workernames=["local1"],
                      factory=f)
    ]
    return c
