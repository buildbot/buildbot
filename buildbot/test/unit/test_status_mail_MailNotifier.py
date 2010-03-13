# -*- coding: utf-8 -*-

from twisted.trial import unittest

from buildbot.status.builder import SUCCESS
from buildbot.status.mail import MailNotifier

class FakeLog(object):
    def __init__(self, text):
        self.text = text

    def getName(self):
        return 'log-name'

    def getStep(self):
        class FakeStep():
            def getName(self):
                return 'step-name'
        return FakeStep()

    def getText(self):
        return self.text

class TestMailNotifier(unittest.TestCase):
    def test_createEmail_message_without_patch_and_log_contains_unicode(self):
        msgdict = dict(body=u'Unicode body with non-ascii (åäö).',
                       type='plain')
        mn = MailNotifier('from@example.org')
        m = mn.createEmail(msgdict, u'builder-näme', u'project-näme', SUCCESS)
        try:
            print m.as_string()
        except UnicodeEncodeError:
            self.fail('Failed to call as_string() on email message.')

    def test_createEmail_message_with_patch_and_log_contains_unicode(self):
        msgdict = dict(body=u'Unicode body with non-ascii (åäö).',
                       type='plain')
        patch = ['', u'åäö', '']
        logs = [FakeLog(u'Unicode log with non-ascii (åäö).')]
        mn = MailNotifier('from@example.org', addLogs=True)
        m = mn.createEmail(msgdict, u'builder-näme', u'project-näme', SUCCESS,
                           patch, logs)
        try:
            m.as_string()
        except UnicodeEncodeError:
            self.fail('Failed to call as_string() on email message.')
