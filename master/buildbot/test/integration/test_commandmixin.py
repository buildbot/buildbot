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

from buildbot.process import results
from buildbot.process.buildstep import BuildStep
from buildbot.process.buildstep import CommandMixin
from buildbot.test.util.integration import RunMasterBase


# This integration test creates a master and worker environment,
# and makes sure the command mixin is working.
class CommandMixinMaster(RunMasterBase):

    @defer.inlineCallbacks
    def test_commandmixin(self):
        yield self.setupConfig(masterConfig())

        change = dict(branch="master",
                      files=["foo.c"],
                      author="me@foo.com",
                      comments="good stuff",
                      revision="HEAD",
                      project="none"
                      )
        build = yield self.doForceBuild(wantSteps=True, useChange=change,
                                        wantLogs=True)
        self.assertEqual(build['buildid'], 1)
        self.assertEqual(build['results'], results.SUCCESS)


class TestCommandMixinStep(BuildStep, CommandMixin):

    def __init__(self, *args, **kwargs):
        BuildStep.__init__(self, *args, **kwargs)

    @defer.inlineCallbacks
    def run(self):
        contents = yield self.runGlob('*')
        if contents != []:
            defer.returnValue(results.FAILURE)

        hasPath = yield self.pathExists('composite_mixin_test')
        if hasPath:
            defer.returnValue(results.FAILURE)

        yield self.runMkdir('composite_mixin_test')

        hasPath = yield self.pathExists('composite_mixin_test')
        if not hasPath:
            defer.returnValue(results.FAILURE)

        contents = yield self.runGlob('*')
        if not contents[0].endswith('composite_mixin_test'):
            defer.returnValue(results.FAILURE)

        yield self.runRmdir('composite_mixin_test')

        hasPath = yield self.pathExists('composite_mixin_test')
        if hasPath:
            defer.returnValue(results.FAILURE)

        defer.returnValue(results.SUCCESS)


# master configuration
def masterConfig():
    c = {}
    from buildbot.config import BuilderConfig
    from buildbot.process.factory import BuildFactory
    from buildbot.plugins import schedulers

    c['schedulers'] = [
        schedulers.AnyBranchScheduler(
            name="sched",
            builderNames=["testy"])]

    f = BuildFactory()
    f.addStep(TestCommandMixinStep())
    c['builders'] = [
        BuilderConfig(name="testy",
                      workernames=["local1"],
                      factory=f)]
    return c
