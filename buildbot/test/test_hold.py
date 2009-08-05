# -*- test-case-name: buildbot.test.test_hold -*-

from twisted.trial import unittest

from buildbot.steps.hold import decodeTimeToSeconds

class IRCContactWithHoldTest(unittest.TestCase):
    def testDecodeTimeToSeconds(self):
        self.failUnless(1, decodeTimeToSeconds('1s'))
        self.failUnless(60, decodeTimeToSeconds('1m'))
        self.failUnless(3600, decodeTimeToSeconds('1h'))
        self.failUnless(3600*24, decodeTimeToSeconds('1d'))
        self.assertRaises(Exception, decodeTimeToSeconds, '1')
        self.assertRaises(Exception, decodeTimeToSeconds, '10')
        self.assertRaises(Exception, decodeTimeToSeconds, 'abc')

