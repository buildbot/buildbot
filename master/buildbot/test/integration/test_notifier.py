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

import base64

from twisted.internet import defer

from buildbot.reporters.mail import ESMTPSenderFactory
from buildbot.reporters.mail import MailNotifier
from buildbot.reporters.message import MessageFormatter
from buildbot.reporters.message import MessageFormatterMissingWorker
from buildbot.reporters.pushover import PushoverNotifier
from buildbot.test.util.integration import RunMasterBase
from buildbot.util import bytes2unicode
from buildbot.util import unicode2bytes


# This integration test creates a master and worker environment,
# with one builders and a shellcommand step, and a MailNotifier
class NotifierMaster(RunMasterBase):

    if not ESMTPSenderFactory:
        skip = ("twisted-mail unavailable, "
                "see: https://twistedmatrix.com/trac/ticket/8770")

    @defer.inlineCallbacks
    def setUp(self):
        self.mailDeferred = defer.Deferred()

        # patch MailNotifier.sendmail to know when the mail has been sent
        def sendMail(_, mail, recipients):
            self.mailDeferred.callback((mail.as_string(), recipients))
        self.patch(MailNotifier, "sendMail", sendMail)

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
        self.assertEqual(build['buildid'], 1)
        mail, recipients = yield self.mailDeferred
        self.assertEqual(recipients, ["author@foo.com"])
        self.assertIn("From: bot@foo.com", mail)
        self.assertIn("Subject: Buildbot success in Buildbot", mail)
        self.assertEncodedIn("The Buildbot has detected a passing build", mail)
        params = yield self.notification
        self.assertEqual(build['buildid'], 1)
        self.assertEqual(params, {'title': "Buildbot success in Buildbot on {}".format(what),
                                  'message': "This is a message."})

    def assertEncodedIn(self, text, mail):
        # python 2.6 default transfer in base64 for utf-8
        if "base64" not in mail:
            self.assertIn(text, mail)
        else:  # b64encode and remove '=' padding (hence [:-1])
            encodedBytes = base64.b64encode(unicode2bytes(text)).rstrip(b"=")
            encodedText = bytes2unicode(encodedBytes)
            self.assertIn(encodedText, mail)

    @defer.inlineCallbacks
    def test_notifiy_for_build(self):
        yield self.doTest('testy')

    @defer.inlineCallbacks
    def test_notifiy_for_buildset(self):
        self.master.config.services = [
            MailNotifier("bot@foo.com", mode="all", buildSetSummary=True),
            PushoverNotifier('1234', 'abcd', mode="all", buildSetSummary=True,
                messageFormatter=MessageFormatter(template='This is a message.'))]
        yield self.master.reconfigServiceWithBuildbotConfig(self.master.config)
        yield self.doTest('whole buildset')

    @defer.inlineCallbacks
    def test_missing_worker(self):
        yield self.master.data.updates.workerMissing(
            workerid='local1',
            masterid=self.master.masterid,
            last_connection='long time ago',
            notify=['admin@worker.org'],
        )
        mail, recipients = yield self.mailDeferred
        self.assertIn("From: bot@foo.com", mail)
        self.assertEqual(recipients, ['admin@worker.org'])
        self.assertIn("Subject: Buildbot worker local1 missing", mail)
        self.assertIn("disconnected at long time ago", mail)
        self.assertEncodedIn("worker named local1 went away", mail)
        params = yield self.notification
        self.assertEqual(params, {'title': "Buildbot worker local1 missing",
                                  'message': b"No worker."})


# master configuration
def masterConfig():
    c = {}
    from buildbot.config import BuilderConfig
    from buildbot.process.factory import BuildFactory
    from buildbot.plugins import steps, schedulers, reporters
    c['schedulers'] = [
        schedulers.AnyBranchScheduler(
            name="sched",
            builderNames=["testy"])
    ]
    f = BuildFactory()
    f.addStep(steps.ShellCommand(command='echo hello'))
    c['builders'] = [
        BuilderConfig(name="testy",
                      workernames=["local1"],
                      factory=f)
    ]
    notifier = reporters.PushoverNotifier('1234', 'abcd', mode="all", watchedWorkers=['local1'],
                                          messageFormatter=MessageFormatter(template='This is a message.'),
                                          messageFormatterMissingWorker=MessageFormatterMissingWorker(
                                              template='No worker.'))
    c['services'] = [
        reporters.MailNotifier("bot@foo.com", mode="all"),
        notifier
    ]
    return c
