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

from buildbot.reporters.generators.build import BuildStatusGenerator
from buildbot.reporters.generators.buildset import BuildSetStatusGenerator
from buildbot.reporters.generators.worker import WorkerMissingGenerator
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
    def create_master_config(self, build_set_summary=False):
        self.mailDeferred = defer.Deferred()

        # patch MailNotifier.sendmail to know when the mail has been sent
        def sendMail(_, mail, recipients):
            self.mailDeferred.callback((mail.as_string(), recipients))
        self.patch(MailNotifier, "sendMail", sendMail)

        self.notification = defer.Deferred()

        def sendNotification(_, params):
            self.notification.callback(params)
        self.patch(PushoverNotifier, "sendNotification", sendNotification)

        yield self.setupConfig(masterConfig(build_set_summary=build_set_summary))

    @defer.inlineCallbacks
    def doTest(self, what):
        change = dict(branch="master",
                      files=["foo.c"],
                      author="author@foo.com",
                      committer="me@foo.com",
                      comments="good stuff",
                      revision="HEAD",
                      project="projectname"
                      )
        build = yield self.doForceBuild(wantSteps=True, useChange=change, wantLogs=True)
        self.assertEqual(build['buildid'], 1)
        mail, recipients = yield self.mailDeferred
        self.assertEqual(recipients, ["author@foo.com"])
        self.assertIn("From: bot@foo.com", mail)
        self.assertIn(f"Subject: =?utf-8?q?=E2=98=BA_Buildbot_=28Buildbot=29=3A_{what}_-_build_successful_=28master=29?=\n",  # noqa pylint: disable=line-too-long
                      mail)
        self.assertEncodedIn("A passing build has been detected on builder testy while", mail)
        params = yield self.notification
        self.assertEqual(build['buildid'], 1)
        self.assertEqual(params, {
            'title': f"☺ Buildbot (Buildbot): {what} - build successful (master)",
            'message': "This is a message."
        })

    def assertEncodedIn(self, text, mail):
        # The default transfer encoding is base64 for utf-8 even when it could be represented
        # accurately by quoted 7bit encoding. TODO: it is possible to override it,
        # see https://bugs.python.org/issue12552
        if "base64" not in mail:
            self.assertIn(text, mail)
        else:  # b64encode and remove '=' padding (hence [:-1])
            encodedBytes = base64.b64encode(unicode2bytes(text)).rstrip(b"=")
            encodedText = bytes2unicode(encodedBytes)
            self.assertIn(encodedText, mail)

    @defer.inlineCallbacks
    def test_notifiy_for_build(self):
        yield self.create_master_config(build_set_summary=False)
        yield self.doTest('testy')

    @defer.inlineCallbacks
    def test_notifiy_for_buildset(self):
        yield self.create_master_config(build_set_summary=True)
        yield self.doTest('projectname')

    @defer.inlineCallbacks
    def test_missing_worker(self):
        yield self.create_master_config(build_set_summary=False)
        yield self.master.data.updates.workerMissing(
            workerid='local1',
            masterid=self.master.masterid,
            last_connection='long time ago',
            notify=['admin@worker.org'],
        )
        mail, recipients = yield self.mailDeferred
        self.assertIn("From: bot@foo.com", mail)
        self.assertEqual(recipients, ['admin@worker.org'])
        self.assertIn("Subject: Buildbot Buildbot worker local1 missing", mail)
        self.assertIn("disconnected at long time ago", mail)
        self.assertEncodedIn("worker named local1 went away", mail)
        params = yield self.notification
        self.assertEqual(params, {'title': "Buildbot Buildbot worker local1 missing",
                                  'message': b"No worker."})


# master configuration
def masterConfig(build_set_summary):
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

    formatter = MessageFormatter(template='This is a message.')
    formatter_worker = MessageFormatterMissingWorker(template='No worker.')

    if build_set_summary:
        generators_mail = [
            BuildSetStatusGenerator(mode='all'),
            WorkerMissingGenerator(workers='all'),
        ]
        generators_pushover = [
            BuildSetStatusGenerator(mode='all', message_formatter=formatter),
            WorkerMissingGenerator(workers=['local1'], message_formatter=formatter_worker),
        ]
    else:
        generators_mail = [
            BuildStatusGenerator(mode='all'),
            WorkerMissingGenerator(workers='all'),
        ]
        generators_pushover = [
            BuildStatusGenerator(mode='all', message_formatter=formatter),
            WorkerMissingGenerator(workers=['local1'], message_formatter=formatter_worker),
        ]

    c['services'] = [
        reporters.MailNotifier("bot@foo.com", generators=generators_mail),
        reporters.PushoverNotifier('1234', 'abcd', generators=generators_pushover)
    ]
    return c
