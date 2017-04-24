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

from buildbot.plugins import reporters
from buildbot.reporters.pushover import PushoverNotifier
from buildbot.test.util.integration import RunMasterBase


# This integration test creates a master and worker environment,
# with one builders and a shellcommand step, and a MailNotifier
class PushoverMaster(RunMasterBase):

    @defer.inlineCallbacks
    def setUp(self):
        self.notification = defer.Deferred()

        def sendNotification(_, params):
            self.notification.callback(params)

        self.patch(PushoverNotifier, "sendNotification", sendNotification)
        yield self.setupConfig(masterConfig())

    @defer.inlineCallbacks
    def doTest(self, what):
        change = dict(branch="master",
                      files=["foo.c"],
                      author="author@foo.com",
                      comments="good stuff",
                      revision="HEAD",
                      project="none"
                      )
        build = yield self.doForceBuild(wantSteps=True, useChange=change, wantLogs=True)
        params = yield self.notification
        self.assertEqual(build['buildid'], 1)
        self.assertEqual(params, {'title': "Buildbot success in Buildbot on {}".format(what),
                                  'message': u"This is a message."})

    @defer.inlineCallbacks
    def test_notifiy_for_build(self):
        self.master.config.services = [
            reporters.PushoverNotifier('1234', 'abcd', mode="all",
                messageFormatter=reporters.MessageFormatter(template='This is a message.'))]
        yield self.master.reconfigServiceWithBuildbotConfig(self.master.config)
        yield self.doTest('testy')

    @defer.inlineCallbacks
    def test_notifiy_for_buildset(self):
        self.master.config.services = [
            reporters.PushoverNotifier('1234', 'abcd', mode="all", buildSetSummary=True,
                messageFormatter=reporters.MessageFormatter(template='This is a message.'))]
        yield self.master.reconfigServiceWithBuildbotConfig(self.master.config)
        yield self.doTest('whole buildset')

# master configuration


def masterConfig():
    c = {}
    from buildbot.config import BuilderConfig
    from buildbot.process.factory import BuildFactory
    from buildbot.plugins import steps, schedulers
    c['schedulers'] = [
        schedulers.AnyBranchScheduler(
            name="sched",
            builderNames=["testy"])]

    f = BuildFactory()
    f.addStep(steps.ShellCommand(command='echo hello'))
    c['builders'] = [
        BuilderConfig(name="testy",
                      workernames=["local1"],
                      factory=f)]
    return c
