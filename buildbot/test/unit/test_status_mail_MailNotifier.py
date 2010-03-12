# -*- coding: utf-8 -*-

from twisted.trial import unittest

from buildbot.status.builder import SUCCESS
from buildbot.status.mail import MailNotifier

class TestMailNotifier(unittest.TestCase):
    def test_sendMessage_message_contains_unicode(self):
        msgdict = dict(body=u'Unicode body with non-ascii (åäö).',
                       type='plain')
        mn = MailNotifier('from@example.org')
        m = mn.createEmail(msgdict, u'builder-näme', u'project-näme', SUCCESS)
        try:
            m.as_string()
        except UnicodeEncodeError:
            self.fail('Failed to call as_string() on email message.')
