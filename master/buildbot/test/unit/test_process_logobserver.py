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

from buildbot.process import logobserver
from twisted.trial import unittest


class BufferedLogObserver(unittest.TestCase):

    def setUp(self):
        self.log = logobserver.BufferLogObserver(wantStdout=True, wantStderr=True)

    def test_get_stdout_unicode(self):
        self.log.outReceived('str')
        self.log.errReceived(u'str')

        self.assertEqual(u'str', self.log.getStdout())
        self.assertEqual(u'str', self.log.getStderr())
        self.assertTrue(isinstance(self.log.getStdout(), unicode))
        self.assertTrue(isinstance(self.log.getStderr(), unicode))

        self.log.outReceived(u'str')
        self.log.errReceived(u'str')

        self.assertEqual(u'strstr', self.log.getStdout())
        self.assertEqual(u'strstr', self.log.getStderr())
        self.assertTrue(isinstance(self.log.getStdout(), unicode))
        self.assertTrue(isinstance(self.log.getStderr(), unicode))

        self.log.outReceived(u'\u2602')
        self.log.errReceived(u'\u2602')

        self.assertEqual(u'strstr\u2602', self.log.getStdout())
        self.assertEqual(u'strstr\u2602', self.log.getStderr())
        self.assertTrue(isinstance(self.log.getStdout(), unicode))
        self.assertTrue(isinstance(self.log.getStderr(), unicode))
