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

from buildbot.process.buildstep import BuildStep
from buildbot.process.results import SUCCESS
from buildbot.test.util.integration import RunMasterBase


class DisconnectingStep(BuildStep):
    disconnection_list = []

    def run(self):
        self.disconnection_list.append(self)
        if len(self.disconnection_list) < 2:
            self.worker.disconnect()
        return SUCCESS


class WorkerReconnect(RunMasterBase):
    """integration test for testing worker disconnection and reconnection"""
    proto = "pb"

    @defer.inlineCallbacks
    def test_eventually_reconnect(self):
        DisconnectingStep.disconnection_list = []
        yield self.setupConfig(masterConfig())
        build = yield self.doForceBuild()
        self.assertEqual(build['buildid'], 2)
        self.assertEqual(len(DisconnectingStep.disconnection_list), 2)


# master configuration
def masterConfig():
    c = {}
    from buildbot.config import BuilderConfig
    from buildbot.process.factory import BuildFactory
    from buildbot.plugins import schedulers

    c['schedulers'] = [
        schedulers.AnyBranchScheduler(
            name="sched",
            builderNames=["testy"]),
        schedulers.ForceScheduler(
            name="force",
            builderNames=["testy"])]

    f = BuildFactory()
    f.addStep(DisconnectingStep())
    c['builders'] = [
        BuilderConfig(name="testy",
                      workernames=["local1"],
                      factory=f)]
    return c
