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

import mock
import cStringIO
from twisted.trial import unittest
from twisted.internet import defer
from buildbot.status import logfile

class TestLogFileProducer(unittest.TestCase):
    def make_static_logfile(self, contents):
        "make a fake logfile with the given contents"
        lf = mock.Mock()
        lf.getFile = lambda : cStringIO.StringIO(contents)
        lf.waitUntilFinished = lambda : defer.succeed(None) # already finished
        lf.runEntries = []
        return lf

    def test_getChunks_static_helloworld(self):
        lf = self.make_static_logfile("13:0hello world!,")
        lfp = logfile.LogFileProducer(lf, mock.Mock())
        chunks = list(lfp.getChunks())
        self.assertEqual(chunks, [ (0, 'hello world!') ])

    def test_getChunks_static_multichannel(self):
        lf = self.make_static_logfile("2:0a,3:1xx,2:0c,")
        lfp = logfile.LogFileProducer(lf, mock.Mock())
        chunks = list(lfp.getChunks())
        self.assertEqual(chunks, [ (0, 'a'), (1, 'xx'), (0, 'c') ])

    # Remainder of LogFileProduer has a wacky interface that's not
    # well-defined, so it's not tested yet
