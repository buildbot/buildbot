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

import re
import sys

from buildbot import config
from buildbot.config import ConfigErrors
from buildbot.process import properties
from buildbot.status import mail
from buildbot.status.mail import MailNotifier
from buildbot.status.results import EXCEPTION
from buildbot.status.results import FAILURE
from buildbot.status.results import SUCCESS
from buildbot.status.results import WARNINGS
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.fake.fakebuild import FakeBuildStatus
from buildbot.test.util.config import ConfigErrorsMixin
from mock import Mock
from twisted.internet import defer
from twisted.trial import unittest

py_27 = sys.version_info[0] > 2 or (sys.version_info[0] == 2
                                    and sys.version_info[1] >= 7)


class FakeLog(object):

    def __init__(self, text):
        self.text = text

    def getName(self):
        return 'log-name'

    def getStep(self):
        class FakeStep(object):

            def getName(self):
                return 'step-name'
        return FakeStep()

    def getText(self):
        return self.text


class FakeSource:

    def __init__(self, branch=None, revision=None, repository=None,
                 codebase=None, project=None):
        self.changes = []
        self.branch = branch
        self.revision = revision
        self.repository = repository
        self.codebase = codebase
        self.project = project
        self.patch_info = None
        self.patch = None


class TestMailNotifier(ConfigErrorsMixin, unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self)

    def do_test_createEmail_cte(self, funnyChars, expEncoding):
        builds = [FakeBuildStatus(name='build')]
        msgdict = create_msgdict(funnyChars)
        mn = MailNotifier('from@example.org')
        d = mn.createEmail(msgdict, u'builder-name', u'project-name',
                           SUCCESS, builds)

        @d.addCallback
        def callback(m):
            cte_lines = [l for l in m.as_string().split("\n")
                         if l.startswith('Content-Transfer-Encoding:')]
            self.assertEqual(cte_lines,
                             ['Content-Transfer-Encoding: %s' % expEncoding],
                             repr(m.as_string()))
        return d

    def test_createEmail_message_content_transfer_encoding_7bit(self):
        return self.do_test_createEmail_cte(u"old fashioned ascii",
                                            '7bit' if py_27 else 'base64')

    def test_createEmail_message_content_transfer_encoding_8bit(self):
        return self.do_test_createEmail_cte(u"\U0001F4A7",
                                            '8bit' if py_27 else 'base64')

    def test_createEmail_message_without_patch_and_log_contains_unicode(self):
        builds = [FakeBuildStatus(name="build")]
        msgdict = create_msgdict()
        mn = MailNotifier('from@example.org')
        d = mn.createEmail(msgdict, u'builder-n\u00E5me', u'project-n\u00E5me',
                           SUCCESS, builds)

        @d.addCallback
        def callback(m):
            try:
                m.as_string()
            except UnicodeEncodeError:
                self.fail('Failed to call as_string() on email message.')
        return d

    def test_createEmail_extraHeaders_one_build(self):
        builds = [FakeBuildStatus(name="build")]
        builds[0].properties = properties.Properties()
        builds[0].setProperty('hhh', 'vvv')
        msgdict = create_msgdict()
        mn = MailNotifier('from@example.org', extraHeaders=dict(hhh='vvv'))
        # add some Unicode to detect encoding problems
        d = mn.createEmail(msgdict, u'builder-n\u00E5me', u'project-n\u00E5me',
                           SUCCESS, builds)

        @d.addCallback
        def callback(m):
            txt = m.as_string()
            self.assertIn('hhh: vvv', txt)
        return d

    def test_createEmail_extraHeaders_two_builds(self):
        builds = [FakeBuildStatus(name="build1"),
                  FakeBuildStatus(name="build2")]
        msgdict = create_msgdict()
        mn = MailNotifier('from@example.org', extraHeaders=dict(hhh='vvv'))
        d = mn.createEmail(msgdict, u'builder-n\u00E5me', u'project-n\u00E5me',
                           SUCCESS, builds)

        @d.addCallback
        def callback(m):
            txt = m.as_string()
            # note that the headers are *not* rendered
            self.assertIn('hhh: vvv', txt)
        return d

    def test_createEmail_message_with_patch_and_log_containing_unicode(self):
        builds = [FakeBuildStatus(name="build")]
        msgdict = create_msgdict()
        patches = [['', u'\u00E5\u00E4\u00F6', '']]
        msg = u'Unicode log with non-ascii (\u00E5\u00E4\u00F6).'
        # add msg twice: as unicode and already encoded
        logs = [FakeLog(msg), FakeLog(msg.encode('utf-8'))]
        mn = MailNotifier('from@example.org', addLogs=True)
        d = mn.createEmail(msgdict, u'builder-n\u00E5me',
                           u'project-n\u00E5me', SUCCESS,
                           builds, patches, logs)

        @d.addCallback
        def callback(m):
            try:
                m.as_string()
            except UnicodeEncodeError:
                self.fail('Failed to call as_string() on email message.')
        return d

    def test_createEmail_message_with_nonascii_patch(self):
        builds = [FakeBuildStatus(name="build")]
        msgdict = create_msgdict()
        patches = [['', '\x99\xaa', '']]
        logs = [FakeLog('simple log')]
        mn = MailNotifier('from@example.org', addLogs=True)
        d = mn.createEmail(msgdict, u'builder', u'pr', SUCCESS,
                           builds, patches, logs)

        @d.addCallback
        def callback(m):
            txt = m.as_string()
            self.assertIn('application/octet-stream', txt)
        return d

    def test_init_enforces_tags_and_builders_are_mutually_exclusive(self):
        self.assertRaises(config.ConfigErrors,
                          MailNotifier, 'from@example.org',
                          tags=['fast', 'slow'], builders=['a', 'b'])

    def test_init_enforces_categories_and_builders_are_mutually_exclusive(self):
        # categories are deprecated, but allow them until they're removed.
        self.assertRaises(config.ConfigErrors,
                          MailNotifier, 'from@example.org',
                          categories=['fast', 'slow'], builders=['a', 'b'])

    def test_init_warns_notifier_mode_all_in_iter(self):
        self.assertRaisesConfigError("mode 'all' is not valid in an iterator and must be passed in as a separate string",
                                     lambda: MailNotifier('from@example.org', mode=['all']))

    def test_builderAdded_ignores_unspecified_tags(self):
        mn = MailNotifier('from@example.org', tags=['fast'])

        builder = fakemaster.FakeBuilderStatus(self.master)
        builder.setTags(['slow'])

        self.assertEqual(None, mn.builderAdded('dummyBuilder', builder))
        self.assert_(builder not in mn.watched)

    def test_builderAdded_ignores_unspecified_categories(self):
        # categories are deprecated, but leave a test for it until we remove it
        mn = MailNotifier('from@example.org', categories=['fast'])

        builder = fakemaster.FakeBuilderStatus(self.master)
        builder.setTags(['slow'])

        self.assertEqual(None, mn.builderAdded('dummyBuilder', builder))
        self.assert_(builder not in mn.watched)

    def test_builderAdded_subscribes_to_all_builders_by_default(self):
        mn = MailNotifier('from@example.org')

        builder = fakemaster.FakeBuilderStatus(self.master)
        builder.setTags(['slow'])

        builder2 = fakemaster.FakeBuilderStatus(self.master)
        # No tags set.

        self.assertEqual(mn, mn.builderAdded('dummyBuilder', builder))
        self.assertEqual(mn, mn.builderAdded('dummyBuilder2', builder2))
        self.assertTrue(builder in mn.watched)
        self.assertTrue(builder2 in mn.watched)

    def test_buildFinished_ignores_unspecified_builders(self):
        mn = MailNotifier('from@example.org', builders=['a', 'b'])

        build = FakeBuildStatus()
        build.builder = Mock()

        self.assertEqual(None, mn.buildFinished('dummyBuilder', build, SUCCESS))

    def test_buildsetComplete_sends_email(self):
        fakeBuildMessage = Mock()
        mn = MailNotifier('from@example.org',
                          buildSetSummary=True,
                          mode=("failing", "passing", "warnings"),
                          builders=["Builder1", "Builder2"])

        mn.buildMessage = fakeBuildMessage

        builder1 = Mock()
        builder1.getBuild = lambda number: build1
        builder1.name = "Builder1"

        build1 = FakeBuildStatus()
        build1.results = FAILURE
        build1.finished = True
        build1.reason = "testReason"
        build1.getBuilder.return_value = builder1
        build1.getResults.return_value = build1.results

        builder2 = Mock()
        builder2.getBuild = lambda number: build2
        builder2.name = "Builder2"

        build2 = FakeBuildStatus()
        build2.results = FAILURE
        build2.finished = True
        build2.reason = "testReason"
        build2.getBuilder.return_value = builder1
        build2.getResults.return_value = build2.results

        def fakeGetBuilder(buildername):
            return {"Builder1": builder1, "Builder2": builder2}[buildername]

        self.db = fakedb.FakeDBConnector(self)
        self.db.insertTestData([fakedb.SourceStampSet(id=127),
                                fakedb.Buildset(id=99, sourcestampsetid=127,
                                                results=SUCCESS,
                                                reason="testReason"),
                                fakedb.BuildRequest(id=11, buildsetid=99,
                                                    buildername='Builder1'),
                                fakedb.Build(number=0, brid=11),
                                fakedb.BuildRequest(id=12, buildsetid=99,
                                                    buildername='Builder2'),
                                fakedb.Build(number=0, brid=12),
                                ])
        mn.master = self  # FIXME: Should be FakeMaster

        self.status = Mock()
        mn.master_status = Mock()
        mn.master_status.getBuilder = fakeGetBuilder
        mn.buildMessageDict = Mock()
        mn.buildMessageDict.return_value = {"body": "body", "type": "text",
                                            "subject": "subject"}

        mn._buildsetComplete(99, FAILURE)
        fakeBuildMessage.assert_called_with("(whole buildset)",
                                            [build1, build2], SUCCESS)

    def test_buildsetComplete_doesnt_send_email(self):
        fakeBuildMessage = Mock()
        mn = MailNotifier('from@example.org',
                          buildSetSummary=True,
                          mode=("failing", "warnings"),
                          builders=["Builder"])
        mn.buildMessage = fakeBuildMessage

        def fakeGetBuild(number):
            return build

        def fakeGetBuilder(buildername):
            if buildername == builder.name:
                return builder
            return None

        def fakeGetBuildRequests(self, bsid):
            return defer.succeed([{"buildername": "Builder", "brid": 1}])

        builder = Mock()
        builder.getBuild = fakeGetBuild
        builder.name = "Builder"

        build = FakeBuildStatus()
        build.results = SUCCESS
        build.finished = True
        build.reason = "testReason"
        build.getBuilder.return_value = builder
        build.getResults.return_value = build.results

        self.db = fakedb.FakeDBConnector(self)
        self.db.insertTestData([fakedb.SourceStampSet(id=127),
                                fakedb.Buildset(id=99, sourcestampsetid=127,
                                                results=SUCCESS,
                                                reason="testReason"),
                                fakedb.BuildRequest(id=11, buildsetid=99,
                                                    buildername='Builder'),
                                fakedb.Build(number=0, brid=11),
                                ])
        mn.master = self

        self.status = Mock()
        mn.master_status = Mock()
        mn.master_status.getBuilder = fakeGetBuilder
        mn.buildMessageDict = Mock()
        mn.buildMessageDict.return_value = {"body": "body", "type": "text",
                                            "subject": "subject"}

        mn._buildsetComplete(99, FAILURE)
        self.assertFalse(fakeBuildMessage.called)

    def test_getCustomMesgData_multiple_sourcestamps(self):
        self.passedAttrs = {}

        def fakeCustomMessage(attrs):
            self.passedAttrs = attrs
            return ("", "")

        mn = MailNotifier('from@example.org',
                          buildSetSummary=True,
                          mode=("failing", "passing", "warnings"),
                          builders=["Builder"])

        def fakeBuildMessage(name, builds, results):
            for build in builds:
                mn.buildMessageDict(name=build.getBuilder().name,
                                    build=build, results=build.results)

        mn.buildMessage = fakeBuildMessage
        mn.customMesg = fakeCustomMessage

        def fakeGetBuild(number):
            return build

        def fakeGetBuilder(buildername):
            if buildername == builder.name:
                return builder
            return None

        def fakeGetBuildRequests(self, bsid):
            return defer.succeed([{"buildername": "Builder", "brid": 1}])

        self.db = fakedb.FakeDBConnector(self)
        self.db.insertTestData([fakedb.SourceStampSet(id=127),
                                fakedb.Buildset(id=99, sourcestampsetid=127,
                                                results=SUCCESS,
                                                reason="testReason"),
                                fakedb.BuildRequest(id=11, buildsetid=99,
                                                    buildername='Builder'),
                                fakedb.Build(number=0, brid=11),
                                ])
        mn.master = self

        builder = Mock()
        builder.getBuild = fakeGetBuild
        builder.name = "Builder"

        build = FakeBuildStatus()
        build.results = FAILURE
        build.finished = True
        build.reason = "testReason"
        build.getLogs.return_value = []
        build.getBuilder.return_value = builder
        build.getResults.return_value = build.results

        self.status = Mock()
        mn.master_status = Mock()
        mn.master_status.getBuilder = fakeGetBuilder

        ss1 = FakeSource(revision='111222', codebase='testlib1')
        ss2 = FakeSource(revision='222333', codebase='testlib2')
        build.getSourceStamps.return_value = [ss1, ss2]

        mn._buildsetComplete(99, FAILURE)

        self.assertTrue('revision' in self.passedAttrs, "No revision entry found in attrs")
        self.assertTrue(isinstance(self.passedAttrs['revision'], dict))
        self.assertEqual(self.passedAttrs['revision']['testlib1'], '111222')
        self.assertEqual(self.passedAttrs['revision']['testlib2'], '222333')

    def test_getCustomMesgData_single_sourcestamp(self):
        self.passedAttrs = {}

        def fakeCustomMessage(attrs):
            self.passedAttrs = attrs
            return ("", "")

        mn = MailNotifier('from@example.org',
                          buildSetSummary=True,
                          mode=("failing", "passing", "warnings"),
                          builders=["Builder"])

        def fakeBuildMessage(name, builds, results):
            for build in builds:
                mn.buildMessageDict(name=build.getBuilder().name,
                                    build=build, results=build.results)

        mn.buildMessage = fakeBuildMessage
        mn.customMesg = fakeCustomMessage

        def fakeGetBuild(number):
            return build

        def fakeGetBuilder(buildername):
            if buildername == builder.name:
                return builder
            return None

        def fakeGetBuildRequests(self, bsid):
            return defer.succeed([{"buildername": "Builder", "brid": 1}])

        self.db = fakedb.FakeDBConnector(self)
        self.db.insertTestData([fakedb.SourceStampSet(id=127),
                                fakedb.Buildset(id=99, sourcestampsetid=127,
                                                results=SUCCESS,
                                                reason="testReason"),
                                fakedb.BuildRequest(id=11, buildsetid=99,
                                                    buildername='Builder'),
                                fakedb.Build(number=0, brid=11),
                                ])
        mn.master = self

        builder = Mock()
        builder.getBuild = fakeGetBuild
        builder.name = "Builder"

        build = FakeBuildStatus()
        build.results = FAILURE
        build.finished = True
        build.reason = "testReason"
        build.getLogs.return_value = []
        build.getBuilder.return_value = builder
        build.getResults.return_value = build.results

        self.status = Mock()
        mn.master_status = Mock()
        mn.master_status.getBuilder = fakeGetBuilder

        ss1 = FakeSource(revision='111222', codebase='testlib1')
        build.getSourceStamps.return_value = [ss1]

        mn._buildsetComplete(99, FAILURE)

        self.assertTrue('builderName' in self.passedAttrs, "No builderName entry found in attrs")
        self.assertEqual(self.passedAttrs['builderName'], 'Builder')
        self.assertTrue('revision' in self.passedAttrs, "No revision entry found in attrs")
        self.assertTrue(isinstance(self.passedAttrs['revision'], str))
        self.assertEqual(self.passedAttrs['revision'], '111222')

    def test_buildFinished_ignores_unspecified_tags(self):
        mn = MailNotifier('from@example.org', tags=['fast'])

        build = FakeBuildStatus(name="build")
        build.builder = fakemaster.FakeBuilderStatus(self.master)
        build.builder.setTags(['slow'])
        build.getBuilder = lambda: build.builder

        self.assertEqual(None, mn.buildFinished('dummyBuilder', build, SUCCESS))

    def test_buildFinished_ignores_unspecified_categories(self):
        # categories are deprecated, but test them until they're removed
        mn = MailNotifier('from@example.org', categories=['fast'])

        build = FakeBuildStatus(name="build")
        build.builder = fakemaster.FakeBuilderStatus(self.master)
        build.builder.setTags(['slow'])
        build.getBuilder = lambda: build.builder

        self.assertEqual(None, mn.buildFinished('dummyBuilder', build, SUCCESS))

    def run_simple_test_sends_email_for_mode(self, mode, result):
        mock_method = Mock()
        self.patch(MailNotifier, "buildMessage", mock_method)
        mn = MailNotifier('from@example.org', mode=mode)

        build = FakeBuildStatus(name="build")
        mn.buildFinished('dummyBuilder', build, result)

        mock_method.assert_called_with('dummyBuilder', [build], result)

    def run_simple_test_ignores_email_for_mode(self, mode, result):
        mock_method = Mock()
        self.patch(MailNotifier, "buildMessage", mock_method)
        mn = MailNotifier('from@example.org', mode=mode)

        build = FakeBuildStatus(name="build")
        mn.buildFinished('dummyBuilder', build, result)

        self.assertFalse(mock_method.called)

    def test_buildFinished_mode_all_for_success(self):
        self.run_simple_test_sends_email_for_mode("all", SUCCESS)

    def test_buildFinished_mode_all_for_failure(self):
        self.run_simple_test_sends_email_for_mode("all", FAILURE)

    def test_buildFinished_mode_all_for_warnings(self):
        self.run_simple_test_sends_email_for_mode("all", WARNINGS)

    def test_buildFinished_mode_all_for_exception(self):
        self.run_simple_test_sends_email_for_mode("all", EXCEPTION)

    def test_buildFinished_mode_failing_for_success(self):
        self.run_simple_test_ignores_email_for_mode("failing", SUCCESS)

    def test_buildFinished_mode_failing_for_failure(self):
        self.run_simple_test_sends_email_for_mode("failing", FAILURE)

    def test_buildFinished_mode_failing_for_warnings(self):
        self.run_simple_test_ignores_email_for_mode("failing", WARNINGS)

    def test_buildFinished_mode_failing_for_exception(self):
        self.run_simple_test_ignores_email_for_mode("failing", EXCEPTION)

    def test_buildFinished_mode_exception_for_success(self):
        self.run_simple_test_ignores_email_for_mode("exception", SUCCESS)

    def test_buildFinished_mode_exception_for_failure(self):
        self.run_simple_test_ignores_email_for_mode("exception", FAILURE)

    def test_buildFinished_mode_exception_for_warnings(self):
        self.run_simple_test_ignores_email_for_mode("exception", WARNINGS)

    def test_buildFinished_mode_exception_for_exception(self):
        self.run_simple_test_sends_email_for_mode("exception", EXCEPTION)

    def test_buildFinished_mode_warnings_for_success(self):
        self.run_simple_test_ignores_email_for_mode("warnings", SUCCESS)

    def test_buildFinished_mode_warnings_for_failure(self):
        self.run_simple_test_sends_email_for_mode("warnings", FAILURE)

    def test_buildFinished_mode_warnings_for_warnings(self):
        self.run_simple_test_sends_email_for_mode("warnings", WARNINGS)

    def test_buildFinished_mode_warnings_for_exception(self):
        self.run_simple_test_ignores_email_for_mode("warnings", EXCEPTION)

    def test_buildFinished_mode_passing_for_success(self):
        self.run_simple_test_sends_email_for_mode("passing", SUCCESS)

    def test_buildFinished_mode_passing_for_failure(self):
        self.run_simple_test_ignores_email_for_mode("passing", FAILURE)

    def test_buildFinished_mode_passing_for_warnings(self):
        self.run_simple_test_ignores_email_for_mode("passing", WARNINGS)

    def test_buildFinished_mode_passing_for_exception(self):
        self.run_simple_test_ignores_email_for_mode("passing", EXCEPTION)

    def test_buildFinished_mode_failing_ignores_successful_build(self):
        mn = MailNotifier('from@example.org', mode=("failing",))

        build = FakeBuildStatus(name="build")

        self.assertEqual(None, mn.buildFinished('dummyBuilder', build, SUCCESS))

    def test_buildFinished_mode_passing_ignores_failed_build(self):
        mn = MailNotifier('from@example.org', mode=("passing",))

        build = FakeBuildStatus(name="build")

        self.assertEqual(None, mn.buildFinished('dummyBuilder', build, FAILURE))

    def test_buildFinished_mode_problem_ignores_successful_build(self):
        mn = MailNotifier('from@example.org', mode=("problem",))

        build = FakeBuildStatus(name="build")

        self.assertEqual(None, mn.buildFinished('dummyBuilder', build, SUCCESS))

    def test_buildFinished_mode_problem_ignores_two_failed_builds_in_sequence(self):
        mn = MailNotifier('from@example.org', mode=("problem",))

        build = FakeBuildStatus(name="build")
        old_build = FakeBuildStatus(name="old_build")
        build.getPreviousBuild.return_value = old_build
        old_build.getResults.return_value = FAILURE

        self.assertEqual(None, mn.buildFinished('dummyBuilder', build, FAILURE))

    def test_buildFinished_mode_change_ignores_first_build(self):
        mn = MailNotifier('from@example.org', mode=("change",))

        build = FakeBuildStatus(name="build")
        build.getPreviousBuild.return_value = None

        self.assertEqual(None, mn.buildFinished('dummyBuilder', build, FAILURE))
        self.assertEqual(None, mn.buildFinished('dummyBuilder', build, SUCCESS))

    def test_buildFinished_mode_change_ignores_same_result_in_sequence(self):
        mn = MailNotifier('from@example.org', mode=("change",))

        build = FakeBuildStatus(name="build")
        old_build = FakeBuildStatus(name="old_build")
        build.getPreviousBuild.return_value = old_build
        old_build.getResults.return_value = FAILURE

        build2 = FakeBuildStatus(name="build2")
        old_build2 = FakeBuildStatus(name="old_build2")
        build2.getPreviousBuild.return_value = old_build2
        old_build2.getResults.return_value = SUCCESS

        self.assertEqual(None, mn.buildFinished('dummyBuilder', build, FAILURE))
        self.assertEqual(None, mn.buildFinished('dummyBuilder', build2, SUCCESS))

    def test_buildMessage_addLogs(self):
        mn = MailNotifier('from@example.org', mode=("change",), addLogs=True)

        mn.buildMessageDict = Mock()
        mn.buildMessageDict.return_value = {"body": "body", "type": "text",
                                            "subject": "subject"}

        mn.createEmail = Mock("createEmail")

        mn._gotRecipients = Mock("_gotReceipients")
        mn._gotRecipients.return_value = None

        mn.master_status = Mock()
        mn.master_status.getTitle.return_value = 'TITLE'

        bldr = Mock(name="builder")
        builds = [FakeBuildStatus(name='build1'),
                  FakeBuildStatus(name='build2')]
        logs = [FakeLog('log1'), FakeLog('log2')]
        for b, l in zip(builds, logs):
            b.builder = bldr
            b.results = 0
            ss = Mock(name='ss')
            b.getSourceStamps.return_value = [ss]
            ss.patch = None
            ss.changes = []
            b.getLogs.return_value = [l]
        d = mn.buildMessage("mybldr", builds, 0)

        def check(_):
            mn.createEmail.assert_called_with(
                dict(body='body\n\nbody\n\n', type='text', subject='subject'),
                'mybldr', 'TITLE', 0, builds, [], logs)
        d.addCallback(check)
        return d

    def do_test_sendToInterestedUsers(self, lookup=None, extraRecipients=[],
                                      sendToInterestedUsers=True,
                                      exp_called_with=None, exp_TO=None,
                                      exp_CC=None):
        from email.message import Message
        m = Message()

        mn = MailNotifier(fromaddr='from@example.org',
                          lookup=lookup,
                          sendToInterestedUsers=sendToInterestedUsers,
                          extraRecipients=extraRecipients)
        mn.sendMessage = Mock()

        def fakeGetBuild(number):
            return build

        def fakeGetBuilder(buildername):
            if buildername == builder.name:
                return builder
            return None

        def fakeGetBuildRequests(self, bsid):
            return defer.succeed([{"buildername": "Builder", "brid": 1}])

        builder = Mock()
        builder.getBuild = fakeGetBuild
        builder.name = "Builder"

        build = FakeBuildStatus(name="build")
        build.result = FAILURE
        build.finished = True
        build.reason = "testReason"
        build.builder = builder

        def fakeCreateEmail(msgdict, builderName, title, results, builds=None,
                            patches=None, logs=None):
            # only concerned with m['To'] and m['CC'], which are added in
            # _got_recipients later
            return defer.succeed(m)
        mn.createEmail = fakeCreateEmail

        self.db = fakedb.FakeDBConnector(self)
        self.db.insertTestData([fakedb.SourceStampSet(id=1099),
                                fakedb.Buildset(id=99, sourcestampsetid=1099,
                                                results=SUCCESS,
                                                reason="testReason"),
                                fakedb.BuildRequest(id=11, buildsetid=99,
                                                    buildername='Builder'),
                                fakedb.Build(number=0, brid=11),
                                fakedb.Change(changeid=9123),
                                fakedb.ChangeUser(changeid=9123, uid=1),
                                fakedb.User(uid=1, identifier="tdurden"),
                                fakedb.UserInfo(uid=1, attr_type='svn',
                                                attr_data="tdurden"),
                                fakedb.UserInfo(uid=1, attr_type='email',
                                                attr_data="tyler@mayhem.net")
                                ])

        # fake sourcestamp with relevant user bits
        ss = Mock(name="sourcestamp")
        fake_change = Mock(name="change")
        fake_change.number = 9123
        ss.changes = [fake_change]
        ss.patch, ss.addPatch = None, None

        def fakeGetSSlist():
            return [ss]
        build.getSourceStamps = fakeGetSSlist

        def _getInterestedUsers():
            # 'narrator' in this case is the owner, which tests the lookup
            return ["narrator"]
        build.getInterestedUsers = _getInterestedUsers

        def _getResponsibleUsers():
            return ["Big Bob <bob@mayhem.net>"]
        build.getResponsibleUsers = _getResponsibleUsers

        mn.master = self  # FIXME: Should be FakeMaster
        self.status = mn.master_status = mn.buildMessageDict = Mock()
        mn.master_status.getBuilder = fakeGetBuilder
        mn.buildMessageDict.return_value = {"body": "body", "type": "text"}

        mn.buildMessage(builder.name, [build], build.result)
        mn.sendMessage.assert_called_with(m, exp_called_with)
        self.assertEqual(m['To'], exp_TO)
        self.assertEqual(m['CC'], exp_CC)

    def test_sendToInterestedUsers_lookup(self):
        self.do_test_sendToInterestedUsers(
            lookup="example.org",
            exp_called_with=['Big Bob <bob@mayhem.net>',
                             'narrator@example.org'],
            exp_TO="Big Bob <bob@mayhem.net>, "
            "narrator@example.org")

    def test_buildMessage_sendToInterestedUsers_no_lookup(self):
        self.do_test_sendToInterestedUsers(
            exp_called_with=['tyler@mayhem.net'],
            exp_TO="tyler@mayhem.net")

    def test_buildMessage_sendToInterestedUsers_extraRecipients(self):
        self.do_test_sendToInterestedUsers(
            extraRecipients=["marla@mayhem.net"],
            exp_called_with=['tyler@mayhem.net',
                             'marla@mayhem.net'],
            exp_TO="tyler@mayhem.net",
            exp_CC="marla@mayhem.net")

    def test_sendToInterestedUsers_False(self):
        self.do_test_sendToInterestedUsers(
            extraRecipients=["marla@mayhem.net"],
            sendToInterestedUsers=False,
            exp_called_with=['marla@mayhem.net'],
            exp_TO="marla@mayhem.net")

    def test_sendToInterestedUsers_two_builds(self):
        from email.message import Message
        m = Message()

        mn = MailNotifier(fromaddr="from@example.org", lookup=None)
        mn.sendMessage = Mock()

        def fakeGetBuilder(buildername):
            if buildername == builder.name:
                return builder
            return None

        def fakeGetBuildRequests(self, bsid):
            return defer.succeed([{"buildername": "Builder", "brid": 1}])

        builder = Mock()
        builder.name = "Builder"

        build1 = FakeBuildStatus(name="build")
        build1.result = FAILURE
        build1.finished = True
        build1.reason = "testReason"
        build1.builder = builder

        build2 = FakeBuildStatus(name="build")
        build2.result = FAILURE
        build2.finished = True
        build2.reason = "testReason"
        build2.builder = builder

        def fakeCreateEmail(msgdict, builderName, title, results, builds=None,
                            patches=None, logs=None):
            # only concerned with m['To'] and m['CC'], which are added in
            # _got_recipients later
            return defer.succeed(m)
        mn.createEmail = fakeCreateEmail

        self.db = fakedb.FakeDBConnector(self)
        self.db.insertTestData([fakedb.SourceStampSet(id=1099),
                                fakedb.Buildset(id=99, sourcestampsetid=1099,
                                                results=SUCCESS,
                                                reason="testReason"),
                                fakedb.BuildRequest(id=11, buildsetid=99,
                                                    buildername='Builder'),
                                fakedb.Build(number=0, brid=11),
                                fakedb.Build(number=1, brid=11),
                                fakedb.Change(changeid=9123),
                                fakedb.Change(changeid=9124),
                                fakedb.ChangeUser(changeid=9123, uid=1),
                                fakedb.ChangeUser(changeid=9124, uid=2),
                                fakedb.User(uid=1, identifier="tdurden"),
                                fakedb.User(uid=2, identifier="user2"),
                                fakedb.UserInfo(uid=1, attr_type='email',
                                                attr_data="tyler@mayhem.net"),
                                fakedb.UserInfo(uid=2, attr_type='email',
                                                attr_data="user2@example.net")
                                ])

        def _getInterestedUsers():
            # 'narrator' in this case is the owner, which tests the lookup
            return ["narrator"]
        build1.getInterestedUsers = _getInterestedUsers
        build2.getInterestedUsers = _getInterestedUsers

        def _getResponsibleUsers():
            return ["Big Bob <bob@mayhem.net>"]
        build1.getResponsibleUsers = _getResponsibleUsers
        build2.getResponsibleUsers = _getResponsibleUsers

        # fake sourcestamp with relevant user bits
        ss1 = Mock(name="sourcestamp")
        fake_change1 = Mock(name="change")
        fake_change1.number = 9123
        ss1.changes = [fake_change1]
        ss1.patch, ss1.addPatch = None, None

        ss2 = Mock(name="sourcestamp")
        fake_change2 = Mock(name="change")
        fake_change2.number = 9124
        ss2.changes = [fake_change2]
        ss2.patch, ss1.addPatch = None, None

        def fakeGetSSlist(ss):
            return lambda: [ss]
        build1.getSourceStamps = fakeGetSSlist(ss1)
        build2.getSourceStamps = fakeGetSSlist(ss2)

        mn.master = self  # FIXME: Should be FakeMaster
        self.status = mn.master_status = mn.buildMessageDict = Mock()
        mn.master_status.getBuilder = fakeGetBuilder
        mn.buildMessageDict.return_value = {"body": "body", "type": "text"}

        mn.buildMessage(builder.name, [build1, build2], build1.result)
        self.assertEqual(m['To'], "tyler@mayhem.net, user2@example.net")

    def test_valid_emails(self):
        valid_emails = [
            'foo+bar@example.com',            # + comment in local part
            'nobody@example.com.',            # root dot
            'My Name <my.name@example.com>',  # With full name
            '<my.name@example.com>',          # With <>
            'My Name <my.name@example.com.>',  # With full name (root dot)
            'egypt@example.xn--wgbh1c']       # IDN TLD (.misr, Egypt)

        # If any of these email addresses fail, the test fails by
        # MailNotifier raising a ConfigErrors exception.
        MailNotifier('foo@example.com', extraRecipients=valid_emails)

    def test_invalid_email(self):
        for invalid in ['@', 'foo', 'foo@', '@example.com', 'foo@invalid',
                        'foobar@ex+ample.com',        # + in domain part
                        'foo bar@example.net',        # whitespace in local part
                        'Foo\nBar <foo@example.org>',  # newline in name
                        'test@example..invalid']:     # empty label (..)
            self.assertRaises(
                ConfigErrors, MailNotifier,
                'foo@example.com', extraRecipients=[invalid])


def create_msgdict(funny_chars=u'\u00E5\u00E4\u00F6'):
    unibody = u'Unicode body with non-ascii (%s).' % funny_chars
    msg_dict = dict(body=unibody, type='plain')
    return msg_dict


# Test buildbot.status.mail._defaultMessageIntro() function
class TestDefaultMessageIntro(unittest.TestCase):
    # Set-up a mocked build status object.
    # If previousBuildResult is specified, create a mocked previous
    # build with the specified build result.

    def setUpBuild(self, previousBuildResult=None):
        prev_build = None
        if previousBuildResult is not None:
            prev_build = Mock()
            prev_build.getResults = Mock(return_value=previousBuildResult)

        build = Mock()
        build.getPreviousBuild = Mock(return_value=prev_build)

        return build

    def testFailureChangeModeFirstBuild(self):
        build = self.setUpBuild()
        self.assertEqual("The Buildbot has detected a failed build",
                         mail._defaultMessageIntro("change", FAILURE, build))

    def testFailureChangeModeNewResult(self):
        build = self.setUpBuild(SUCCESS)
        self.assertEqual("The Buildbot has detected a new failure",
                         mail._defaultMessageIntro("change", FAILURE, build))

    def testFailureProblemModeFirstBuild(self):
        build = self.setUpBuild()
        self.assertEqual("The Buildbot has detected a failed build",
                         mail._defaultMessageIntro("problem", FAILURE, build))

    def testFailureProblemModeNewFailure(self):
        build = self.setUpBuild(SUCCESS)
        self.assertEqual("The Buildbot has detected a new failure",
                         mail._defaultMessageIntro("problem", FAILURE, build))

    def testFailureProblemModeOldFailure(self):
        build = self.setUpBuild(FAILURE)
        self.assertEqual("The Buildbot has detected a failed build",
                         mail._defaultMessageIntro("problem", FAILURE, build))

    def testWarnings(self):
        build = self.setUpBuild()
        self.assertEqual("The Buildbot has detected a problem in the build",
                         mail._defaultMessageIntro("all", WARNINGS, build))

    def testSuccessChangeModeFirstBuild(self):
        build = self.setUpBuild()
        self.assertEqual("The Buildbot has detected a passing build",
                         mail._defaultMessageIntro("change", SUCCESS, build))

    def testSuccessChangeModeNewSuccess(self):
        build = self.setUpBuild(FAILURE)
        self.assertEqual("The Buildbot has detected a restored build",
                         mail._defaultMessageIntro("change", SUCCESS, build))

    def testSuccessChangeModeSuccessAgain(self):
        build = self.setUpBuild(SUCCESS)
        self.assertEqual("The Buildbot has detected a passing build",
                         mail._defaultMessageIntro("change", SUCCESS, build))

    def testException(self):
        build = self.setUpBuild()
        self.assertEqual("The Buildbot has detected a build exception",
                         mail._defaultMessageIntro("all", EXCEPTION, build))


# Test buildbot.status.mail._defaultMessageProjects() function
class TestDefaultMessageProjects(unittest.TestCase):
    # test the case when source stamp does not specify a project

    def testNoSorceStampsProject(self):
        source_stamp = Mock()
        source_stamp.project = None

        master_status = Mock()
        master_status.getTitle = Mock(return_value="test-title")

        self.assertEqual("test-title",
                         mail._defaultMessageProjects([source_stamp],
                                                      master_status))

    # test the case where single source stamp specifies a project
    def testSingleSourceStampProject(self):
        source_stamp = Mock()
        source_stamp.project = "source-stamp-title"

        self.assertEqual("source-stamp-title",
                         mail._defaultMessageProjects([source_stamp], Mock()))

    # test the case where multiple source stamps specifies a project
    def testMultiSourceStampsProject(self):
        source_stamp1 = Mock()
        source_stamp1.project = "title-a"

        # second source stamp specifies same project as first source stamp
        source_stamp2 = Mock()
        source_stamp2.project = "title-a"

        source_stamp3 = Mock()
        source_stamp3.project = "title-b"

        self.assertEqual("title-a, title-b",
                         mail._defaultMessageProjects([source_stamp1,
                                                      source_stamp2,
                                                      source_stamp3],
                                                      Mock()))


# Test buildbot.status.mail._defaultMessageURLs() function
class TestDefaultMessageURLs(unittest.TestCase):

    def setUpStatus(self, build_url, buildbot_url):
        master_status = Mock()

        master_status.getURLForThing = Mock(return_value=build_url)
        master_status.getBuildbotURL = Mock(return_value=buildbot_url)

        return master_status

    # test the case when both build and buildbot URLs are available
    def testAllURLs(self):
        master_status = self.setUpStatus("build_url", "buildbot_url")

        r = (".*Full details are available at:(.|\\n)*build_url(.|\\n)*"
             "Buildbot URL: buildbot_url.*")
        msg = mail._defaultMessageURLs(master_status, Mock())
        self.failUnless(re.search(r, msg), "%r does not match %r" % (msg, r))

    # test the case when build URL is not available
    def testNoBuildURL(self):
        master_status = self.setUpStatus(None, "buildbot_url")

        self.assertEqual(mail._defaultMessageURLs(master_status, Mock()),
                         "\nBuildbot URL: buildbot_url\n\n")

    # test the case when buildbot URL is not available
    def testNoBuildbotURL(self):
        master_status = self.setUpStatus("build_url", None)

        self.assertEqual(mail._defaultMessageURLs(master_status, Mock()),
                         " Full details are available at:\n    build_url\n\n")

    # test the case when no URLs are available
    def testNoURLs(self):
        master_status = self.setUpStatus(None, None)

        self.assertEqual(mail._defaultMessageURLs(master_status, Mock()), "\n")


# Test buildbot.status.mail._defaultMessageSourceStamps() function
class TestDefaultMessageSourceStamps(unittest.TestCase):

    # utility function to create mocked source stamp object
    def setUpSourceStamp(self, branch=None, revision=None, patch=None,
                         codebase=""):

        source_stamp = Mock()
        source_stamp.branch = branch
        source_stamp.revision = revision
        source_stamp.patch = patch
        source_stamp.codebase = codebase

        return source_stamp

    # test the case where build does not have any source stamps
    def testNoSourceStamps(self):
        self.assertEqual(mail._defaultMessageSourceStamps([]), "")

    # test the case with one single minimal source stamp
    def testOneSourceStamp(self):
        source_stamp = self.setUpSourceStamp()

        self.assertEqual("Build Source Stamp: HEAD\n",
                         mail._defaultMessageSourceStamps([source_stamp]))

    # test the case with multiple source stamps, with branches, revisions,
    # patch and codebase specifications
    def testMultipleSourceStamps(self):
        sstamp1 = self.setUpSourceStamp(branch="branch1", revision="rev1")
        sstamp2 = self.setUpSourceStamp(branch="branch2", revision="rev2",
                                        patch="dummy", codebase="base1")

        self.assertEqual("Build Source Stamp: [branch branch1] rev1\n"
                         "Build Source Stamp 'base1': [branch branch2] rev2 "
                         "(plus patch)\n",
                         mail._defaultMessageSourceStamps([sstamp1, sstamp2]))


# Test buildbot.status.mail._defaultMessageSummary() function
class TestDefaultMessageSummary(unittest.TestCase):

    def setUp(self):
        self.build = Mock()
        self.build.getText = Mock(return_value=None)

    def testSuccess(self):
        self.assertEqual("Build succeeded!\n",
                         mail._defaultMessageSummary(self.build, SUCCESS))

    def testWarnings(self):
        self.assertEqual("Build Had Warnings\n",
                         mail._defaultMessageSummary(self.build, WARNINGS))

    def testException(self):
        self.assertEqual("BUILD FAILED\n",
                         mail._defaultMessageSummary(self.build, EXCEPTION))

    def testFailure(self):
        self.assertEqual("BUILD FAILED\n",
                         mail._defaultMessageSummary(self.build, FAILURE))

    # test failed build with text contributed by two steps
    def testFailureStepsText(self):
        self.build.getText = Mock(return_value=["step1", "step2"])
        self.assertEqual("BUILD FAILED: step1 step2\n",
                         mail._defaultMessageSummary(self.build, FAILURE))


# Test buildbot.status.mail.defaultMessage() function
class TestDefaultMessage(unittest.TestCase):

    def testMessage(self):

        # patch private functions
        self.patch(mail, "_defaultMessageIntro", Mock(return_value="intro"))
        self.patch(mail, "_defaultMessageProjects", Mock(return_value="project"))
        self.patch(mail, "_defaultMessageURLs", Mock(return_value="\nurl\n"))
        self.patch(mail, "_defaultMessageSourceStamps", Mock(return_value="source-stamp"))
        self.patch(mail, "_defaultMessageSummary", Mock(return_value="summary"))

        # set-up mock build
        build = Mock()
        build.getSourceStamps = Mock()
        build.getSlavename = Mock(return_value="slave-name")
        build.getReason = Mock(return_value="build-reason")
        build.getResponsibleUsers = Mock(return_value=["usr1", "usr2"])

        message = mail.defaultMessage(("all"), "test-build", build,
                                      SUCCESS, Mock())

        expected_message = dict(type="plain",
                                body="intro on builder test-build while building project.\n"
                                "url\nBuildslave for this Build: slave-name\n\n"
                                "Build Reason: build-reason\n"
                                "source-stampBlamelist: usr1,usr2\n\nsummary\n"
                                "Sincerely,\n -The Buildbot\n\n")
        self.assertEqual(message, expected_message)
