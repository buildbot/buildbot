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
import copy
import sys

from mock import Mock
from twisted.internet import defer
from twisted.trial import unittest

from buildbot import config
from buildbot.config import ConfigErrors
from buildbot.process import properties
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.reporters import utils
from buildbot.reporters.mail import MailNotifier
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util.config import ConfigErrorsMixin

py_27 = sys.version_info[0] > 2 or (sys.version_info[0] == 2
                                    and sys.version_info[1] >= 7)


class TestMailNotifier(ConfigErrorsMixin, unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self,
                                             wantData=True, wantDb=True, wantMq=True)

    @defer.inlineCallbacks
    def setupBuildResults(self, results, wantPreviousBuild=False):
        # this testsuite always goes through setupBuildResults so that
        # the data is sure to be the real data schema known coming from data
        # api

        self.db = self.master.db
        self.db.insertTestData([
            fakedb.Master(id=92),
            fakedb.Worker(id=13, name='sl'),
            fakedb.Buildset(id=98, results=results, reason="testReason1"),
            fakedb.Builder(id=80, name='Builder1'),
            fakedb.BuildRequest(id=11, buildsetid=98, builderid=80),
            fakedb.Build(id=20, number=0, builderid=80, buildrequestid=11, workerid=13,
                         masterid=92, results=results),
            fakedb.Step(id=50, buildid=20, number=5, name='make'),
            fakedb.BuildsetSourceStamp(buildsetid=98, sourcestampid=234),
            fakedb.SourceStamp(id=234, patchid=99),
            fakedb.Change(changeid=13, branch=u'trunk', revision=u'9283', author='me@foo',
                          repository=u'svn://...', codebase=u'cbsvn',
                          project=u'world-domination', sourcestampid=234),
            fakedb.Log(id=60, stepid=50, name='stdio', slug='stdio', type='s',
                       num_lines=7),
            fakedb.LogChunk(logid=60, first_line=0, last_line=1, compressed=0,
                            content=u'Unicode log with non-ascii (\u00E5\u00E4\u00F6).'),
            fakedb.Patch(id=99, patch_base64='aGVsbG8sIHdvcmxk',
                         patch_author='him@foo', patch_comment='foo', subdir='/foo',
                         patchlevel=3),
        ])
        for _id in (20,):
            self.db.insertTestData([
                fakedb.BuildProperty(
                    buildid=_id, name="workername", value="sl"),
                fakedb.BuildProperty(
                    buildid=_id, name="reason", value="because"),
            ])
        res = yield utils.getDetailsForBuildset(self.master, 98, wantProperties=True,
                                                wantPreviousBuild=wantPreviousBuild)
        builds = res['builds']
        buildset = res['buildset']

        @defer.inlineCallbacks
        def getChangesForBuild(buildid):
            assert buildid == 20
            ch = yield self.master.db.changes.getChange(13)
            defer.returnValue([ch])

        self.master.db.changes.getChangesForBuild = getChangesForBuild
        defer.returnValue((buildset, builds))

    @defer.inlineCallbacks
    def setupMailNotifier(self, *args, **kwargs):
        mn = MailNotifier(*args, **kwargs)
        yield mn.setServiceParent(self.master)
        yield mn.startService()
        defer.returnValue(mn)

    @defer.inlineCallbacks
    def do_test_createEmail_cte(self, funnyChars, expEncoding):
        _, builds = yield self.setupBuildResults(SUCCESS)
        msgdict = create_msgdict(funnyChars)
        mn = yield self.setupMailNotifier('from@example.org')
        m = yield mn.createEmail(msgdict, u'builder-name', u'project-name',
                                 SUCCESS, builds)

        cte_lines = [l for l in m.as_string().split("\n")
                     if l.startswith('Content-Transfer-Encoding:')]
        self.assertEqual(cte_lines,
                         ['Content-Transfer-Encoding: %s' % expEncoding],
                         repr(m.as_string()))

    def test_createEmail_message_content_transfer_encoding_7bit(self):
        return self.do_test_createEmail_cte(u"old fashioned ascii",
                                            '7bit' if py_27 else 'base64')

    def test_createEmail_message_content_transfer_encoding_8bit(self):
        return self.do_test_createEmail_cte(u"\U0001F4A7",
                                            '8bit' if py_27 else 'base64')

    @defer.inlineCallbacks
    def test_createEmail_message_without_patch_and_log_contains_unicode(self):
        _, builds = yield self.setupBuildResults(SUCCESS)
        msgdict = create_msgdict()
        mn = yield self.setupMailNotifier('from@example.org')
        m = yield mn.createEmail(msgdict, u'builder-n\u00E5me', u'project-n\u00E5me',
                                 SUCCESS, builds)

        try:
            m.as_string()
        except UnicodeEncodeError:
            self.fail('Failed to call as_string() on email message.')

    @defer.inlineCallbacks
    def test_createEmail_extraHeaders_one_build(self):
        _, builds = yield self.setupBuildResults(SUCCESS)
        builds[0]['properties']['hhh'] = ('vvv', 'fake')
        msgdict = create_msgdict()
        mn = yield self.setupMailNotifier('from@example.org', extraHeaders=dict(hhh=properties.Property('hhh')))
        # add some Unicode to detect encoding problems
        m = yield mn.createEmail(msgdict, u'builder-n\u00E5me', u'project-n\u00E5me',
                                 SUCCESS, builds)

        txt = m.as_string()
        # note that the headers *are* rendered
        self.assertIn('hhh: vvv', txt)

    @defer.inlineCallbacks
    def test_createEmail_extraHeaders_two_builds(self):
        _, builds = yield self.setupBuildResults(SUCCESS)
        builds.append(copy.deepcopy(builds[0]))
        builds[1]['builder']['name'] = 'builder2'
        msgdict = create_msgdict()
        mn = yield self.setupMailNotifier('from@example.org', extraHeaders=dict(hhh='vvv'))
        m = yield mn.createEmail(msgdict, u'builder-n\u00E5me', u'project-n\u00E5me',
                                 SUCCESS, builds)

        txt = m.as_string()
        # note that the headers are *not* rendered
        self.assertIn('hhh: vvv', txt)

    @defer.inlineCallbacks
    def test_createEmail_message_with_patch_and_log_containing_unicode(self):
        _, builds = yield self.setupBuildResults(SUCCESS)
        msgdict = create_msgdict()
        patches = [{'body': u'\u00E5\u00E4\u00F6'}]
        logs = yield self.master.data.get(("steps", 50, 'logs'))
        for l in logs:
            l['stepname'] = "fakestep"
            l['content'] = yield self.master.data.get(("logs", l['logid'], 'contents'))

        mn = yield self.setupMailNotifier('from@example.org', addLogs=True)
        m = yield mn.createEmail(msgdict, u'builder-n\u00E5me',
                                 u'project-n\u00E5me', SUCCESS,
                                 builds, patches, logs)

        try:
            s = m.as_string()
            # python 2.6 default transfer in base64 for utf-8
            if "base64" not in s:
                self.assertIn("Unicode log", s)
            else:  # b64encode and remove '=' padding (hence [:-1])
                self.assertIn(base64.b64encode("Unicode log")[:-1], s)

            self.assertIn(
                'Content-Disposition: attachment; filename="fakestep.stdio"', s)
        except UnicodeEncodeError:
            self.fail('Failed to call as_string() on email message.')

    def test_init_enforces_tags_and_builders_are_mutually_exclusive(self):
        self.assertRaises(config.ConfigErrors,
                          MailNotifier, 'from@example.org',
                          tags=['fast', 'slow'], builders=['a', 'b'])

    def test_init_warns_notifier_mode_all_in_iter(self):
        self.assertRaisesConfigError(
            "mode 'all' is not valid in an iterator and must be passed in as a separate string",
            lambda: MailNotifier('from@example.org', mode=['all']))

    @defer.inlineCallbacks
    def test_buildsetComplete_sends_email(self):
        _, builds = yield self.setupBuildResults(SUCCESS)
        mn = yield self.setupMailNotifier('from@example.org',
                                          buildSetSummary=True,
                                          mode=(
                                              "failing", "passing", "warnings"),
                                          builders=["Builder1", "Builder2"])

        mn.buildMessage = Mock()
        yield mn.buildsetComplete('buildset.98.complete',
                                  dict(bsid=98))

        mn.buildMessage.assert_called_with(
            "(whole buildset)",
            builds, SUCCESS)
        self.assertEqual(mn.buildMessage.call_count, 1)

    @defer.inlineCallbacks
    def test_buildsetComplete_doesnt_send_email(self):
        _, builds = yield self.setupBuildResults(SUCCESS)
        # disable passing...
        mn = yield self.setupMailNotifier('from@example.org',
                                          buildSetSummary=True,
                                          mode=("failing", "warnings"),
                                          builders=["Builder1", "Builder2"])

        mn.buildMessage = Mock()
        yield mn.buildsetComplete('buildset.98.complete',
                                  dict(bsid=98))

        self.assertFalse(mn.buildMessage.called)

    @defer.inlineCallbacks
    def test_isMailNeeded_ignores_unspecified_tags(self):
        _, builds = yield self.setupBuildResults(SUCCESS)

        build = builds[0]
        # force tags
        build['builder']['tags'] = ['slow']
        mn = yield self.setupMailNotifier('from@example.org',
                                          tags=["fast"])
        self.assertFalse(mn.isMailNeeded(build))

    @defer.inlineCallbacks
    def test_isMailNeeded_tags(self):
        _, builds = yield self.setupBuildResults(SUCCESS)

        build = builds[0]
        # force tags
        build['builder']['tags'] = ['fast']
        mn = yield self.setupMailNotifier('from@example.org',
                                          tags=["fast"])
        self.assertTrue(mn.isMailNeeded(build))

    @defer.inlineCallbacks
    def run_simple_test_sends_email_for_mode(self, mode, result, shouldSend=True):
        _, builds = yield self.setupBuildResults(result)

        mn = yield self.setupMailNotifier('from@example.org', mode=mode)

        self.assertEqual(mn.isMailNeeded(builds[0]), shouldSend)

    def run_simple_test_ignores_email_for_mode(self, mode, result):
        return self.run_simple_test_sends_email_for_mode(mode, result, False)

    def test_isMailNeeded_mode_all_for_success(self):
        return self.run_simple_test_sends_email_for_mode("all", SUCCESS)

    def test_isMailNeeded_mode_all_for_failure(self):
        return self.run_simple_test_sends_email_for_mode("all", FAILURE)

    def test_isMailNeeded_mode_all_for_warnings(self):
        return self.run_simple_test_sends_email_for_mode("all", WARNINGS)

    def test_isMailNeeded_mode_all_for_exception(self):
        return self.run_simple_test_sends_email_for_mode("all", EXCEPTION)

    def test_isMailNeeded_mode_all_for_cancelled(self):
        return self.run_simple_test_sends_email_for_mode("all", CANCELLED)

    def test_isMailNeeded_mode_failing_for_success(self):
        return self.run_simple_test_ignores_email_for_mode("failing", SUCCESS)

    def test_isMailNeeded_mode_failing_for_failure(self):
        return self.run_simple_test_sends_email_for_mode("failing", FAILURE)

    def test_isMailNeeded_mode_failing_for_warnings(self):
        return self.run_simple_test_ignores_email_for_mode("failing", WARNINGS)

    def test_isMailNeeded_mode_failing_for_exception(self):
        return self.run_simple_test_ignores_email_for_mode("failing", EXCEPTION)

    def test_isMailNeeded_mode_exception_for_success(self):
        return self.run_simple_test_ignores_email_for_mode("exception", SUCCESS)

    def test_isMailNeeded_mode_exception_for_failure(self):
        return self.run_simple_test_ignores_email_for_mode("exception", FAILURE)

    def test_isMailNeeded_mode_exception_for_warnings(self):
        return self.run_simple_test_ignores_email_for_mode("exception", WARNINGS)

    def test_isMailNeeded_mode_exception_for_exception(self):
        return self.run_simple_test_sends_email_for_mode("exception", EXCEPTION)

    def test_isMailNeeded_mode_warnings_for_success(self):
        return self.run_simple_test_ignores_email_for_mode("warnings", SUCCESS)

    def test_isMailNeeded_mode_warnings_for_failure(self):
        return self.run_simple_test_sends_email_for_mode("warnings", FAILURE)

    def test_isMailNeeded_mode_warnings_for_warnings(self):
        return self.run_simple_test_sends_email_for_mode("warnings", WARNINGS)

    def test_isMailNeeded_mode_warnings_for_exception(self):
        return self.run_simple_test_ignores_email_for_mode("warnings", EXCEPTION)

    def test_isMailNeeded_mode_passing_for_success(self):
        return self.run_simple_test_sends_email_for_mode("passing", SUCCESS)

    def test_isMailNeeded_mode_passing_for_failure(self):
        return self.run_simple_test_ignores_email_for_mode("passing", FAILURE)

    def test_isMailNeeded_mode_passing_for_warnings(self):
        return self.run_simple_test_ignores_email_for_mode("passing", WARNINGS)

    def test_isMailNeeded_mode_passing_for_exception(self):
        return self.run_simple_test_ignores_email_for_mode("passing", EXCEPTION)

    @defer.inlineCallbacks
    def run_sends_email_for_problems(self, mode, results1, results2, shouldSend=True):
        _, builds = yield self.setupBuildResults(results2)

        mn = yield self.setupMailNotifier('from@example.org', mode=mode)

        build = builds[0]
        if results1 is not None:
            build['prev_build'] = copy.deepcopy(builds[0])
            build['prev_build']['results'] = results1
        else:
            build['prev_build'] = None
        self.assertEqual(mn.isMailNeeded(builds[0]), shouldSend)

    def test_isMailNeeded_mode_problem_sends_on_problem(self):
        return self.run_sends_email_for_problems("problem", SUCCESS, FAILURE, True)

    def test_isMailNeeded_mode_problem_ignores_successful_build(self):
        return self.run_sends_email_for_problems("problem", SUCCESS, SUCCESS, False)

    def test_isMailNeeded_mode_problem_ignores_two_failed_builds_in_sequence(self):
        return self.run_sends_email_for_problems("problem", FAILURE, FAILURE, False)

    def test_isMailNeeded_mode_change_sends_on_change(self):
        return self.run_sends_email_for_problems("change", FAILURE, SUCCESS, True)

    def test_isMailNeeded_mode_change_sends_on_failure(self):
        return self.run_sends_email_for_problems("change", SUCCESS, FAILURE, True)

    def test_isMailNeeded_mode_change_ignores_first_build(self):
        return self.run_sends_email_for_problems("change", None, FAILURE, False)

    def test_isMailNeeded_mode_change_ignores_first_build2(self):
        return self.run_sends_email_for_problems("change", None, SUCCESS, False)

    def test_isMailNeeded_mode_change_ignores_same_result_in_sequence(self):
        return self.run_sends_email_for_problems("change", SUCCESS, SUCCESS, False)

    def test_isMailNeeded_mode_change_ignores_same_result_in_sequence2(self):
        return self.run_sends_email_for_problems("change", FAILURE, FAILURE, False)

    @defer.inlineCallbacks
    def setupBuildMessage(self, **mnKwargs):

        _, builds = yield self.setupBuildResults(SUCCESS)

        mn = yield self.setupMailNotifier('from@example.org', **mnKwargs)

        mn.messageFormatter = Mock(spec=mn.messageFormatter)
        mn.messageFormatter.return_value = {"body": "body", "type": "text",
                                            "subject": "subject"}

        mn.findInterrestedUsersEmails = Mock(
            spec=mn.findInterrestedUsersEmails)
        mn.findInterrestedUsersEmails.return_value = "<recipients>"

        mn.processRecipients = Mock(spec=mn.processRecipients)
        mn.processRecipients.return_value = "<processedrecipients>"

        mn.createEmail = Mock(spec=mn.createEmail)
        mn.createEmail.return_value = "<email>"
        mn.sendMessage = Mock(spec=mn.sendMessage)
        yield mn.buildMessage("mybldr", builds, SUCCESS)
        defer.returnValue((mn, builds))

    @defer.inlineCallbacks
    def test_buildMessage_nominal(self):
        mn, builds = yield self.setupBuildMessage(mode=("change",))

        build = builds[0]
        mn.messageFormatter.assert_called_with(('change',), 'mybldr', build['buildset'], build, self.master,
                                               None, [u'me@foo'])

        mn.findInterrestedUsersEmails.assert_called_with([u'me@foo'])
        mn.processRecipients.assert_called_with('<recipients>', '<email>')
        mn.sendMessage.assert_called_with('<email>', '<processedrecipients>')
        self.assertEqual(mn.createEmail.call_count, 1)

    @defer.inlineCallbacks
    def test_buildMessage_addLogs(self):
        mn, builds = yield self.setupBuildMessage(mode=("change",), addLogs=True)
        self.assertEqual(mn.createEmail.call_count, 1)
        # make sure the logs are send
        self.assertEqual(mn.createEmail.call_args[0][6][0]['logid'], 60)
        # make sure the log has content
        self.assertIn(
            "log with", mn.createEmail.call_args[0][6][0]['content']['content'])

    @defer.inlineCallbacks
    def test_buildMessage_addPatch(self):
        mn, builds = yield self.setupBuildMessage(mode=("change",), addPatch=True)
        self.assertEqual(mn.createEmail.call_count, 1)
        # make sure the patch are sent
        self.assertEqual(mn.createEmail.call_args[0][5],
                         [{'author': u'him@foo',
                           'body': 'hello, world',
                           'comment': u'foo',
                           'level': 3,
                           'patchid': 99,
                           'subdir': u'/foo'}])

    @defer.inlineCallbacks
    def test_buildMessage_addPatchNoPatch(self):
        SourceStamp = fakedb.SourceStamp

        class NoPatchSourcestamp(SourceStamp):

            def __init__(self, id, patchid):
                SourceStamp.__init__(self, id=id)
        self.patch(fakedb, 'SourceStamp', NoPatchSourcestamp)
        mn, builds = yield self.setupBuildMessage(mode=("change",), addPatch=True)
        self.assertEqual(mn.createEmail.call_count, 1)
        # make sure no patches are sent
        self.assertEqual(mn.createEmail.call_args[0][5],
                         [])

    @defer.inlineCallbacks
    def do_test_sendToInterestedUsers(self, lookup=None, extraRecipients=[],
                                      sendToInterestedUsers=True,
                                      exp_called_with=None, exp_TO=None,
                                      exp_CC=None):
        _, builds = yield self.setupBuildResults(SUCCESS)

        mn = yield self.setupMailNotifier('from@example.org', lookup=lookup, extraRecipients=extraRecipients,
                                          sendToInterestedUsers=sendToInterestedUsers)

        recipients = yield mn.findInterrestedUsersEmails(['Big Bob <bob@mayhem.net>', 'narrator'])
        m = {'To': None, 'CC': None}
        all_recipients = mn.processRecipients(recipients, m)
        self.assertEqual(all_recipients, exp_called_with)
        self.assertEqual(m['To'], exp_TO)
        self.assertEqual(m['CC'], exp_CC)

    def test_sendToInterestedUsers_lookup(self):
        return self.do_test_sendToInterestedUsers(
            lookup="example.org",
            exp_called_with=['Big Bob <bob@mayhem.net>',
                             'narrator@example.org'],
            exp_TO="Big Bob <bob@mayhem.net>, "
            "narrator@example.org")

    def test_buildMessage_sendToInterestedUsers_no_lookup(self):
        return self.do_test_sendToInterestedUsers(
            exp_called_with=['Big Bob <bob@mayhem.net>'],
            exp_TO="Big Bob <bob@mayhem.net>")

    def test_buildMessage_sendToInterestedUsers_extraRecipients(self):
        return self.do_test_sendToInterestedUsers(
            extraRecipients=["marla@mayhem.net"],
            exp_called_with=['Big Bob <bob@mayhem.net>', 'marla@mayhem.net'],
            exp_TO="Big Bob <bob@mayhem.net>",
            exp_CC="marla@mayhem.net")

    def test_sendToInterestedUsers_False(self):
        return self.do_test_sendToInterestedUsers(
            extraRecipients=["marla@mayhem.net"],
            sendToInterestedUsers=False,
            exp_called_with=['marla@mayhem.net'],
            exp_TO="marla@mayhem.net")

    def test_valid_emails(self):
        valid_emails = [
            'foo+bar@example.com',            # + comment in local part
            'nobody@example.com.',            # root dot
            'My Name <my.name@example.com>',  # With full name
            '<my.name@example.com>',          # With <>
            'My Name <my.name@example.com.>',  # With full name (root dot)
            'egypt@example.xn--wgbh1c']       # IDN TLD (.misr, Egypt)

        # If any of these email addresses fail, the test fails by
        # yield self.setupMailNotifier raising a ConfigErrors exception.
        MailNotifier('foo@example.com', extraRecipients=valid_emails)

    def test_invalid_email(self):
        for invalid in ['@', 'foo', 'foo@', '@example.com', 'foo@invalid',
                        'foobar@ex+ample.com',        # + in domain part
                        # whitespace in local part
                        'foo bar@example.net',
                        'Foo\nBar <foo@example.org>',  # newline in name
                        'test@example..invalid']:     # empty label (..)
            self.assertRaises(
                ConfigErrors, MailNotifier,
                'foo@example.com', extraRecipients=[invalid])


def create_msgdict(funny_chars=u'\u00E5\u00E4\u00F6'):
    unibody = u'Unicode body with non-ascii (%s).' % funny_chars
    msg_dict = dict(body=unibody, type='plain')
    return msg_dict
