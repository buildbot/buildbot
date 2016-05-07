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
import base64

from twisted.internet import defer

from buildbot.reporters.mail import MailNotifier
from buildbot.test.util.integration import RunMasterBase


# This integration test creates a master and worker environment,
# with one builders and a shellcommand step, and a MailNotifier
class MailMaster(RunMasterBase):

    def setUp(self):
        self.mailDeferred = defer.Deferred()

        # patch MailNotifier.sendmail to know when the mail has been sent
        def sendmail(_, mail, recipients):
            self.mailDeferred.callback((mail, recipients))
        self.patch(MailNotifier, "sendmail", sendmail)

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
        mail, recipients = yield self.mailDeferred
        self.assertEqual(recipients, ["author@foo.com"])
        self.assertIn("From: bot@foo.com", mail)
        self.assertIn("Subject: buildbot success in Buildbot", mail)
        self.assertEncodedIn("The Buildbot has detected a passing build", mail)

    def assertEncodedIn(self, text, mail):
        # python 2.6 default transfer in base64 for utf-8
        if "base64" not in mail:
            self.assertIn(text, mail)
        else:  # b64encode and remove '=' padding (hence [:-1])
            self.assertIn(base64.b64encode(text).rstrip("="), mail)

    @defer.inlineCallbacks
    def test_notifiy_for_build(self):
        yield self.setupConfig(masterConfig())
        yield self.doTest()

    @defer.inlineCallbacks
    def test_notifiy_for_buildset(self):
        yield self.setupConfig(masterConfig())
        self.master.config.services = [
            MailNotifier("bot@foo.com", mode="all", buildSetSummary=True)]
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
    c['services'] = [reporters.MailNotifier("bot@foo.com", mode="all")]
    return c
