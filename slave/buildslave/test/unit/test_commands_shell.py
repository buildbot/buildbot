import sys, re
import pprint
import time

from twisted.trial import unittest
from twisted.internet import task, defer
from twisted.python import runtime

from buildslave.test.fake.slavebuilder import FakeSlaveBuilder
from buildslave.test.util.misc import nl
from buildslave.commands.registry import commandRegistry
from buildslave.commands import shell # for side-effect

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
        factory, version = commandRegistry['shell']
        b = self.builder = FakeSlaveBuilder()
        self.stepid = str(time.time())
        self.cmd = factory(b, self.stepid, args)
        return self.cmd

    def test_simple(self):
        cmd = self.makeCommand(dict(
            command=stdoutCommand("world"),
            workdir='test_simple',
        ))

        # start the command
        d = cmd.doStart()
        def check(_):
            self.assertEqual(filter_hdr(self.builder.updates),
                    [ 'hdr', { 'stdout' : nl('world\n') }, { 'rc' : 0 }, 'hdr' ],
                    self.builder.show())
        d.addCallback(check)
        return d
