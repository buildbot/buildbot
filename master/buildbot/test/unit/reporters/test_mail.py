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
from email import charset

from mock import Mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.config import ConfigErrors
from buildbot.process import properties
from buildbot.process.properties import Interpolate
from buildbot.process.results import SUCCESS
from buildbot.reporters import mail
from buildbot.reporters import utils
from buildbot.reporters.generators.build import BuildStatusGenerator
from buildbot.reporters.mail import MailNotifier
from buildbot.reporters.message import MessageFormatter
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.test.util.reporter import ReporterTestMixin
from buildbot.util import bytes2unicode
from buildbot.util import ssl


class TestMailNotifier(ConfigErrorsMixin, TestReactorMixin,
                       unittest.TestCase, ReporterTestMixin):

    def setUp(self):
        self.setup_test_reactor()
        self.setup_reporter_test()
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True,
                                             wantMq=True)

    @defer.inlineCallbacks
    def setupMailNotifier(self, *args, **kwargs):
        mn = MailNotifier(*args, **kwargs)
        yield mn.setServiceParent(self.master)
        yield mn.startService()
        return mn

    @defer.inlineCallbacks
    def test_change_name(self):
        mn = yield self.setupMailNotifier('from@example.org', name="custom_name")
        self.assertEqual(mn.name, "custom_name")

    @defer.inlineCallbacks
    def do_test_createEmail_cte(self, funnyChars, expEncoding):
        build = yield self.insert_build_finished(SUCCESS)

        yield utils.getDetailsForBuild(self.master, build, want_properties=True)

        msgdict = create_msgdict(funnyChars)
        mn = yield self.setupMailNotifier('from@example.org')
        m = yield mn.createEmail(msgdict, 'project-name', SUCCESS, [build])

        cte_lines = [l for l in m.as_string().split("\n")
                     if l.startswith('Content-Transfer-Encoding:')]
        self.assertEqual(cte_lines,
                         [f'Content-Transfer-Encoding: {expEncoding}'],
                         repr(m.as_string()))

    def test_createEmail_message_content_transfer_encoding_7bit(self):
        # buildbot.reporters.mail.ENCODING is 'utf8'
        # On Python 3, the body_encoding for 'utf8' is base64.
        # On Python 2, the body_encoding for 'utf8' is None.
        # If the body_encoding is None, the email package
        # will try to deduce the 'Content-Transfer-Encoding'
        # by calling email.encoders.encode_7or8bit().
        # If the foo.encode('ascii') works on the body, it
        # is assumed '7bit'.  If it fails, it is assumed '8bit'.
        input_charset = charset.Charset(mail.ENCODING)
        if input_charset.body_encoding == charset.BASE64:
            expEncoding = 'base64'
        elif input_charset.body_encoding is None:
            expEncoding = '7bit'
        return self.do_test_createEmail_cte("old fashioned ascii",
                                            expEncoding)

    def test_createEmail_message_content_transfer_encoding_8bit(self):
        # buildbot.reporters.mail.ENCODING is 'utf8'
        # On Python 3, the body_encoding for 'utf8' is base64.
        # On Python 2, the body_encoding for 'utf8' is None.
        # If the body_encoding is None, the email package
        # will try to deduce the 'Content-Transfer-Encoding'
        # by calling email.encoders.encode_7or8bit().
        # If the foo.encode('ascii') works on the body, it
        input_charset = charset.Charset(mail.ENCODING)
        if input_charset.body_encoding == charset.BASE64:
            expEncoding = 'base64'
        elif input_charset.body_encoding is None:
            expEncoding = '8bit'
        return self.do_test_createEmail_cte("\U0001F4A7",
                                            expEncoding)

    @defer.inlineCallbacks
    def test_createEmail_message_without_patch_and_log_contains_unicode(self):
        build = yield self.insert_build_finished(SUCCESS)
        msgdict = create_msgdict()
        mn = yield self.setupMailNotifier('from@example.org')
        m = yield mn.createEmail(msgdict, 'project-n\u00E5me', SUCCESS, [build])

        try:
            m.as_string()
        except UnicodeEncodeError:
            self.fail('Failed to call as_string() on email message.')

    @defer.inlineCallbacks
    def test_createEmail_extraHeaders_one_build(self):
        build = yield self.insert_build_finished(SUCCESS)
        build['properties']['hhh'] = ('vvv', 'fake')
        msgdict = create_msgdict()
        mn = yield self.setupMailNotifier('from@example.org',
                                          extraHeaders=dict(hhh=properties.Property('hhh')))
        # add some Unicode to detect encoding problems
        m = yield mn.createEmail(msgdict, 'project-n\u00E5me', SUCCESS, [build])

        txt = m.as_string()
        # note that the headers *are* rendered
        self.assertIn('hhh: vvv', txt)

    @defer.inlineCallbacks
    def test_createEmail_extraHeaders_two_builds(self):
        build = yield self.insert_build_finished(SUCCESS)
        yield utils.getDetailsForBuild(self.master, build, want_properties=True)

        builds = [build, copy.deepcopy(build)]
        builds[1]['builder']['name'] = 'builder2'
        msgdict = create_msgdict()
        mn = yield self.setupMailNotifier('from@example.org', extraHeaders=dict(hhh='vvv'))
        m = yield mn.createEmail(msgdict, 'project-n\u00E5me', SUCCESS, builds)

        txt = m.as_string()
        # note that the headers are *not* rendered
        self.assertIn('hhh: vvv', txt)

    @defer.inlineCallbacks
    def test_createEmail_message_with_patch_and_log_containing_unicode(self):
        build = yield self.insert_build_finished(SUCCESS)
        msgdict = create_msgdict()
        patches = [{'body': '\u00E5\u00E4\u00F6'}]
        logs = yield self.master.data.get(("steps", 50, 'logs'))
        for l in logs:
            l['stepname'] = "fakestep"
            l['content'] = yield self.master.data.get(("logs", l['logid'], 'contents'))

        mn = yield self.setupMailNotifier('from@example.org',
                                          generators=[BuildStatusGenerator(add_logs=True)])

        m = yield mn.createEmail(msgdict, 'project-n\u00E5me', SUCCESS, [build], patches, logs)

        try:
            s = m.as_string()
            # The default transfer encoding is base64 for utf-8 even when it could be represented
            # accurately by quoted 7bit encoding. TODO: it is possible to override it,
            # see https://bugs.python.org/issue12552
            if "base64" not in s:
                self.assertIn("Unicode log", s)
            else:  # b64encode and remove '=' padding (hence [:-1])
                logStr = bytes2unicode(base64.b64encode(b"Unicode log")[:-1])
                self.assertIn(logStr, s)

            self.assertIn(
                'Content-Disposition: attachment; filename="fakestep.stdio"', s)
        except UnicodeEncodeError:
            self.fail('Failed to call as_string() on email message.')

    @defer.inlineCallbacks
    def setupBuildMessage(self, **generator_kwargs):

        build = yield self.insert_build_finished(SUCCESS)

        formatter = Mock(spec=MessageFormatter)
        formatter.format_message_for_build.return_value = {
            "body": "body",
            "type": "text",
            "subject": "subject"
        }
        formatter.want_properties = False
        formatter.want_steps = False
        formatter.want_logs = False
        formatter.want_logs_content = False

        generator = BuildStatusGenerator(message_formatter=formatter, **generator_kwargs)

        mn = yield self.setupMailNotifier('from@example.org', generators=[generator])

        mn.findInterrestedUsersEmails = Mock(
            spec=mn.findInterrestedUsersEmails)
        mn.findInterrestedUsersEmails.return_value = "<recipients>"

        mn.processRecipients = Mock(spec=mn.processRecipients)
        mn.processRecipients.return_value = "<processedrecipients>"

        mn.createEmail = Mock(spec=mn.createEmail)
        mn.createEmail.return_value = "<email>"
        mn.sendMail = Mock(spec=mn.sendMail)
        yield mn._got_event(('builds', 10, 'finished'), build)
        return (mn, build, formatter)

    @defer.inlineCallbacks
    def test_buildMessage(self):
        mn, build, formatter = yield self.setupBuildMessage(mode=("passing",))

        formatter.format_message_for_build.assert_called_with(self.master, build, is_buildset=False,
                                                              mode=('passing',), users=['me@foo'])

        mn.findInterrestedUsersEmails.assert_called_with(['me@foo'])
        mn.processRecipients.assert_called_with('<recipients>', '<email>')
        mn.sendMail.assert_called_with('<email>', '<processedrecipients>')
        self.assertEqual(mn.createEmail.call_count, 1)

    @defer.inlineCallbacks
    def do_test_sendToInterestedUsers(self, lookup=None, extraRecipients=None,
                                      sendToInterestedUsers=True,
                                      exp_called_with=None, exp_TO=None,
                                      exp_CC=None):
        if extraRecipients is None:
            extraRecipients = []
        _ = yield self.insert_build_finished(SUCCESS)

        mn = yield self.setupMailNotifier('from@example.org', lookup=lookup,
                                          extraRecipients=extraRecipients,
                                          sendToInterestedUsers=sendToInterestedUsers)

        recipients = yield mn.findInterrestedUsersEmails(['Big Bob <bob@mayhem.net>', 'narrator'])
        m = {'To': None, 'CC': None}
        all_recipients = mn.processRecipients(recipients, m)
        self.assertEqual(sorted(all_recipients), sorted(exp_called_with))
        self.assertEqual(m['To'], exp_TO)
        self.assertEqual(m['CC'], exp_CC)

    def test_sendToInterestedUsers_lookup(self):
        return self.do_test_sendToInterestedUsers(
            lookup="example.org",
            exp_called_with=['Big Bob <bob@mayhem.net>',
                             'narrator@example.org'],
            exp_TO='"=?utf-8?q?Big_Bob?=" <bob@mayhem.net>, '
            'narrator@example.org')

    def test_buildMessage_sendToInterestedUsers_no_lookup(self):
        return self.do_test_sendToInterestedUsers(
            exp_called_with=['Big Bob <bob@mayhem.net>'],
            exp_TO='"=?utf-8?q?Big_Bob?=" <bob@mayhem.net>')

    def test_buildMessage_sendToInterestedUsers_extraRecipients(self):
        return self.do_test_sendToInterestedUsers(
            extraRecipients=["marla@mayhem.net"],
            exp_called_with=['Big Bob <bob@mayhem.net>', 'marla@mayhem.net'],
            exp_TO='"=?utf-8?q?Big_Bob?=" <bob@mayhem.net>',
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
            with self.assertRaises(ConfigErrors):
                MailNotifier('foo@example.com', extraRecipients=[invalid])

    @defer.inlineCallbacks
    def test_sendMail_real_name_addresses(self):
        fakeSenderFactory = Mock()
        fakeSenderFactory.side_effect = lambda *args, **kwargs: args[
            5].callback(True)
        self.patch(mail, 'ESMTPSenderFactory', fakeSenderFactory)
        self.patch(mail, 'reactor', Mock())
        msg = Mock()
        msg.as_string = Mock(return_value='<email>')

        mn = yield self.setupMailNotifier('John Doe <john.doe@domain.tld>')
        yield mn.sendMail(msg, ['Jane Doe <jane.doe@domain.tld>'])

        self.assertIsInstance(fakeSenderFactory.call_args, tuple)
        self.assertTrue(len(fakeSenderFactory.call_args) > 0)
        self.assertTrue(len(fakeSenderFactory.call_args[0]) > 3)
        self.assertEquals(fakeSenderFactory.call_args[0][2],
                          'john.doe@domain.tld')
        self.assertEquals(fakeSenderFactory.call_args[0][3],
                          ['jane.doe@domain.tld'])

    @defer.inlineCallbacks
    def do_test_sendMessage(self, **mn_kwargs):
        fakeSenderFactory = Mock()
        fakeSenderFactory.side_effect = lambda *args, **kwargs: args[
            5].callback(True)
        self.patch(mail, 'ESMTPSenderFactory', fakeSenderFactory)

        build = yield self.insert_build_finished(SUCCESS)

        formatter = Mock(spec=MessageFormatter)
        formatter.format_message_for_build.return_value = {
            "body": "body",
            "type": "text",
            "subject": "subject"
        }
        formatter.want_properties = False
        formatter.want_steps = False
        formatter.want_logs = False
        formatter.want_logs_content = False

        generator = BuildStatusGenerator(message_formatter=formatter)

        mn = yield self.setupMailNotifier('from@example.org', generators=[generator], **mn_kwargs)

        mn.findInterrestedUsersEmails = Mock(
            spec=mn.findInterrestedUsersEmails)
        mn.findInterrestedUsersEmails.return_value = list("<recipients>")

        mn.processRecipients = Mock(spec=mn.processRecipients)
        mn.processRecipients.return_value = list("<processedrecipients>")

        mn.createEmail = Mock(spec=mn.createEmail)
        mn.createEmail.return_value.as_string = Mock(return_value="<email>")

        yield mn._got_event(('builds', 10, 'finished'), build)
        return (mn, build)

    @defer.inlineCallbacks
    def test_sendMessageOverTcp(self):
        fakereactor = Mock()
        self.patch(mail, 'reactor', fakereactor)

        yield self.do_test_sendMessage()

        self.assertEqual(1, len(fakereactor.method_calls))
        self.assertIn(('connectTCP', ('localhost', 25, None), {}),
                      fakereactor.method_calls)

    @defer.inlineCallbacks
    def test_sendMessageWithInterpolatedConfig(self):
        """Test that the secrets parameters are properly interpolated at reconfig stage

        Note: in the unit test, we don't test that it is interpolated with secret.
        That would require setting up secret manager.
        We just test that the interpolation works.
        """
        fakereactor = Mock()
        self.patch(mail, 'reactor', fakereactor)
        mn, _ = yield self.do_test_sendMessage(smtpUser=Interpolate("u$er"),
                                               smtpPassword=Interpolate("pa$$word"))

        self.assertEqual(mn.smtpUser, "u$er")
        self.assertEqual(mn.smtpPassword, "pa$$word")
        self.assertEqual(1, len(fakereactor.method_calls))
        self.assertIn(('connectTCP', ('localhost', 25, None), {}),
                      fakereactor.method_calls)

    @ssl.skipUnless
    @defer.inlineCallbacks
    def test_sendMessageOverSsl(self):
        fakereactor = Mock()
        self.patch(mail, 'reactor', fakereactor)

        yield self.do_test_sendMessage(useSmtps=True)

        self.assertEqual(1, len(fakereactor.method_calls))
        self.assertIn(('connectSSL', ('localhost', 25, None, fakereactor.connectSSL.call_args[
                      0][3]), {}), fakereactor.method_calls)


def create_msgdict(funny_chars='\u00E5\u00E4\u00F6'):
    unibody = f'Unicode body with non-ascii ({funny_chars}).'
    msg_dict = {
        "body": unibody,
        "subject": "testsubject",
        "type": 'plain'
    }
    return msg_dict
