from twisted.trial import unittest

from buildbot.status.builder import SUCCESS
from buildbot.status.mail import MailNotifier

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

class TestMailNotifier(unittest.TestCase):
    def test_createEmail_message_without_patch_and_log_contains_unicode(self):
        msgdict = dict(body=u'Unicode body with non-ascii (\u00E5\u00E4\u00F6).',
                       type='plain')
        mn = MailNotifier('from@example.org')
        m = mn.createEmail(msgdict, u'builder-n\u00E5me', u'project-n\u00E5me', SUCCESS)
        try:
            m.as_string()
        except UnicodeEncodeError:
            self.fail('Failed to call as_string() on email message.')

    def test_createEmail_message_with_patch_and_log_contains_unicode(self):
        msgdict = dict(body=u'Unicode body with non-ascii (\u00E5\u00E4\u00F6).',
                       type='plain')
        patch = ['', u'\u00E5\u00E4\u00F6', '']
        logs = [FakeLog(u'Unicode log with non-ascii (\u00E5\u00E4\u00F6).')]
        mn = MailNotifier('from@example.org', addLogs=True)
        m = mn.createEmail(msgdict, u'builder-n\u00E5me', u'project-n\u00E5me', SUCCESS,
                           patch, logs)
        try:
            m.as_string()
        except UnicodeEncodeError:
            self.fail('Failed to call as_string() on email message.')
