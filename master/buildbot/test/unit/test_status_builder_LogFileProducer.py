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
from buildbot.status import builder

class TestLogFileProducer(unittest.TestCase):
    def make_static_logfile(self, contents):
        "make a fake logfile with the given contents"
        logfile = mock.Mock()
        logfile.getFile = lambda : cStringIO.StringIO(contents)
        logfile.waitUntilFinished = lambda : defer.succeed(None) # already finished
        logfile.runEntries = []
        return logfile

    def test_getChunks_static_helloworld(self):
        logfile = self.make_static_logfile("13:0hello world!,")
        lfp = builder.LogFileProducer(logfile, mock.Mock())
        chunks = list(lfp.getChunks())
        self.assertEqual(chunks, [ (0, 'hello world!') ])

    def test_getChunks_static_multichannel(self):
        logfile = self.make_static_logfile("2:0a,3:1xx,2:0c,")
        lfp = builder.LogFileProducer(logfile, mock.Mock())
        chunks = list(lfp.getChunks())
        self.assertEqual(chunks, [ (0, 'a'), (1, 'xx'), (0, 'c') ])

    # Remainder of LogFileProduer has a wacky interface that's not
    # well-defined, so it's not tested yet
