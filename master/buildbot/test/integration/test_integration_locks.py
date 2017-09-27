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
from twisted.internet import reactor

from buildbot.process.buildstep import BuildStep
from buildbot.test.util.integration import RunMasterBase


class LockedStep(BuildStep):
    locks_steps = []  # class variable

    def run(self):
        self.locks_steps.append(self)
        self.d = defer.Deferred()
        return self.d


class ShellMaster(RunMasterBase):

    @defer.inlineCallbacks
    def test_shell(self):
        yield self.setupConfig(masterConfig())

        # there is no event that is sent *after* the lock, so no way to
        # reliably synchronize without polling :-(
        def unlockStep():
            for l in LockedStep.locks_steps:
                if not l.d.called:
                    l.d.callback(0)
            if len(LockedStep.locks_steps) < 3:
                reactor.callLater(.3, unlockStep)
        reactor.callLater(.3, unlockStep)

        change = dict(branch="master",
                      files=["foo.c"],
                      author="me@foo.com",
                      comments="good stuff",
                      revision="HEAD",
                      project="none"
                      )

        yield self.doForceBuild(useChange=change)
        LockedStep.locks_steps = []


# master configuration
def masterConfig():
    c = {}
    from buildbot.config import BuilderConfig
    from buildbot.process.factory import BuildFactory
    from buildbot.plugins import schedulers
    from buildbot.plugins import util
    lock = util.MasterLock("lock")

    c['schedulers'] = [
        schedulers.AnyBranchScheduler(
            name="sched",
            builderNames=["testy", "testy2", "testy3"]),
        ]
    f = BuildFactory()
    lockstep = LockedStep(locks=[lock.access('exclusive')])
    f.addStep(lockstep)
    # assert lockstep._factory.buildStep() == lockstep._factory.buildStep()
    c['builders'] = [
        BuilderConfig(name="testy",
                      workernames=["local1"],
                      factory=f),
        BuilderConfig(name="testy2",
                      workernames=["local1"],
                      factory=f),
        BuilderConfig(name="testy3",
              workernames=["local1"],
              factory=f)]

    return c
