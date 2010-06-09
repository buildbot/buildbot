import sys, re
import pprint
import time

from twisted.trial import unittest
from twisted.internet import task, defer
from twisted.python import runtime

from buildslave.test.fake.slavebuilder import FakeSlaveBuilder
from buildslave.test.util.misc import nl
from buildslave.commands.registry import commandRegistry
from buildslave.commands import vcs # for side-effect

def stdoutCommand(output):
    return [sys.executable, '-c', 'import sys; sys.stdout.write("%s\\n")' % output]

def filter_hdr(updates):
    def f(u):
        if 'header' in u:
            return 'hdr'
        return u
    return [ f(u) for u in updates ]

class TestSlaveShellCommand(unittest.TestCase):
    # note that, as a unit test, this depends on the RunProcess class's proper
    # functioning.  It does not re-test functionality provided by that class, though.

    def makeCommand(self, args):
        factory, version = commandRegistry['svn']
        b = self.builder = FakeSlaveBuilder()
        self.stepid = str(time.time())
        self.cmd = factory(b, self.stepid, args)
        return self.cmd

    def test_simple(self):
        cmd = self.makeCommand(dict(
            workdir='test_simple',
            mode='copy',
            revision=None,
            svnurl='http://svn.r.igoro.us/projects/toys/Processor/trunk',
        ))

        # start the command
        d = cmd.doStart()
        # just want it to succeed for now
        return d

    test_simple.skip = "Skip for now; assumes svn is installed"
