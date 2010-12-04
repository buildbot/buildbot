import mock
import cStringIO
from twisted.trial import unittest
from buildbot.status import builder

from twisted.internet import defer, reactor
from twisted.python import log
from buildbot.test.util import changesource
from buildbot.changes import base

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
