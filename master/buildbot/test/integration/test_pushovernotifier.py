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

import sys

from types import ModuleType

from twisted.internet import defer


class Client(object):
    deferred = None
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
    def send_message(self, message, **kwargs):
        result = {'self': self, 'message': message}
        result.update(kwargs)
        # call deferred to know when the notification has been set
        if Client.deferred is not None:
            Client.deferred.callback(result)

        return result

pushover = ModuleType('pushover')
pushover.Client = Client
sys.modules['pushover'] = pushover


from buildbot.reporters.pushover import PushoverNotifier
from buildbot.test.util.integration import RunMasterBase


# This integration test creates a master and worker environment,
# with one builders and a shellcommand step, and a MailNotifier
class PushoverMaster(RunMasterBase):

    def setUp(self):
        self.notificationDeferred = defer.Deferred()
        Client.deferred = self.notificationDeferred

    @defer.inlineCallbacks
    def doTest(self):

        change = dict(branch="master",
                      files=["foo.c"],
                      author="author@foo.com",
                      comments="good stuff",
                      revision="HEAD",
                      project="none"
                      )
        build = yield self.doForceBuild(wantSteps=True, useChange=change, wantLogs=True)
        self.assertEqual(build['buildid'], 1)
        n = yield self.notificationDeferred
        self.assertEqual(n['self'].args[0], "1234")
        self.assertEqual(n['self'].kwargs['api_token'], "abcd")
        self.assertIn('message', n)
        self.assertIn('title', n)

    @defer.inlineCallbacks
    def test_notifiy_for_build(self):
        yield self.setupConfig(masterConfig())
        yield self.doTest()

    @defer.inlineCallbacks
    def test_notifiy_for_buildset(self):
        yield self.setupConfig(masterConfig())
        self.master.config.services = [
            PushoverNotifier('1234', 'abcd', mode="all", buildSetSummary=True)]
        yield self.master.reconfigServiceWithBuildbotConfig(self.master.config)
        yield self.doTest()

# master configuration


def masterConfig():
    c = {}
    from buildbot.config import BuilderConfig
    from buildbot.process.factory import BuildFactory
    from buildbot.plugins import steps, schedulers, reporters
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
    c['services'] = [reporters.PushoverNotifier('1234', 'abcd', mode="all")]
    return c
