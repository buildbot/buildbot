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
import copy
import sys
from email import charset

from mock import Mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.config import ConfigErrors
from buildbot.process import properties
from buildbot.process.results import SUCCESS
from buildbot.reporters import mail
from buildbot.reporters.mail import ESMTPSenderFactory
from buildbot.reporters.mail import MailNotifier
from buildbot.test.fake import fakemaster
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.test.util.notifier import NotifierTestMixin
from buildbot.util import bytes2unicode
from buildbot.util import ssl

py_27 = sys.version_info[0] > 2 or (sys.version_info[0] == 2
                                    and sys.version_info[1] >= 7)


class TestMailNotifier(ConfigErrorsMixin, unittest.TestCase, NotifierTestMixin):

    if not ESMTPSenderFactory:
        skip = ("twisted-mail unavailable, "
                "see: https://twistedmatrix.com/trac/ticket/8770")

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self,
                                             wantData=True, wantDb=True, wantMq=True)

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
        return self.do_test_createEmail_cte(u"old fashioned ascii",
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
        return self.do_test_createEmail_cte(u"\U0001F4A7",
                                            expEncoding)

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
                logStr = bytes2unicode(base64.b64encode(b"Unicode log")[:-1])
                self.assertIn(logStr, s)

            self.assertIn(
                'Content-Disposition: attachment; filename="fakestep.stdio"', s)
        except UnicodeEncodeError:
            self.fail('Failed to call as_string() on email message.')

    @defer.inlineCallbacks
    def setupBuildMessage(self, **mnKwargs):

        _, builds = yield self.setupBuildResults(SUCCESS)

        mn = yield self.setupMailNotifier('from@example.org', **mnKwargs)

        mn.messageFormatter = Mock(spec=mn.messageFormatter)
        mn.messageFormatter.formatMessageForBuildResults.return_value = {"body": "body", "type": "text",
                                                                         "subject": "subject"}

        mn.findInterrestedUsersEmails = Mock(
            spec=mn.findInterrestedUsersEmails)
        mn.findInterrestedUsersEmails.return_value = "<recipients>"

        mn.processRecipients = Mock(spec=mn.processRecipients)
        mn.processRecipients.return_value = "<processedrecipients>"

        mn.createEmail = Mock(spec=mn.createEmail)
        mn.createEmail.return_value = "<email>"
        mn.sendMail = Mock(spec=mn.sendMail)
        yield mn.buildMessage("mybldr", builds, SUCCESS)
        defer.returnValue((mn, builds))

    @defer.inlineCallbacks
    def test_buildMessage(self):
        mn, builds = yield self.setupBuildMessage(mode=("change",))

        build = builds[0]
        mn.messageFormatter.formatMessageForBuildResults.assert_called_with(
            ('change',), 'mybldr', build['buildset'], build, self.master,
            None, [u'me@foo'])

        mn.findInterrestedUsersEmails.assert_called_with([u'me@foo'])
        mn.processRecipients.assert_called_with('<recipients>', '<email>')
        mn.sendMail.assert_called_with('<email>', '<processedrecipients>')
        self.assertEqual(mn.createEmail.call_count, 1)

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
        self.assertEqual(sorted(all_recipients), sorted(exp_called_with))
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

    @defer.inlineCallbacks
    def do_test_sendMessage(self, **mnKwargs):
        fakeSenderFactory = Mock()
        fakeSenderFactory.side_effect = lambda *args, **kwargs: args[
            5].callback(True)
        self.patch(mail, 'ESMTPSenderFactory', fakeSenderFactory)

        _, builds = yield self.setupBuildResults(SUCCESS)
        mn = yield self.setupMailNotifier('from@example.org', **mnKwargs)

        mn.messageFormatter = Mock(spec=mn.messageFormatter)
        mn.messageFormatter.formatMessageForBuildResults.return_value = {"body": "body", "type": "text",
                                                                         "subject": "subject"}

        mn.findInterrestedUsersEmails = Mock(
            spec=mn.findInterrestedUsersEmails)
        mn.findInterrestedUsersEmails.return_value = "<recipients>"

        mn.processRecipients = Mock(spec=mn.processRecipients)
        mn.processRecipients.return_value = "<processedrecipients>"

        mn.createEmail = Mock(spec=mn.createEmail)
        mn.createEmail.return_value.as_string = Mock(return_value="<email>")

        yield mn.buildMessage("mybldr", builds, SUCCESS)
        defer.returnValue((mn, builds))

    @defer.inlineCallbacks
    def test_sendMessageOverTcp(self):
        fakereactor = Mock()
        self.patch(mail, 'reactor', fakereactor)

        mn, builds = yield self.do_test_sendMessage()

        self.assertEqual(1, len(fakereactor.method_calls))
        self.assertIn(('connectTCP', ('localhost', 25, None), {}),
                      fakereactor.method_calls)

    @ssl.skipUnless
    @defer.inlineCallbacks
    def test_sendMessageOverSsl(self):
        fakereactor = Mock()
        self.patch(mail, 'reactor', fakereactor)

        mn, builds = yield self.do_test_sendMessage(useSmtps=True)

        self.assertEqual(1, len(fakereactor.method_calls))
        self.assertIn(('connectSSL', ('localhost', 25, None, fakereactor.connectSSL.call_args[
                      0][3]), {}), fakereactor.method_calls)


def create_msgdict(funny_chars=u'\u00E5\u00E4\u00F6'):
    unibody = u'Unicode body with non-ascii (%s).' % funny_chars
    msg_dict = dict(body=unibody, type='plain')
    return msg_dict
