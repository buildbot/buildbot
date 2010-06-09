import sys, re
import pprint
import time

from twisted.trial import unittest
from twisted.internet import task, defer
from twisted.python import runtime

from buildslave.test.fake.runprocess import Expect
from buildslave.test.util.command import CommandTestMixin
from buildslave.test.util.misc import nl
from buildslave.commands import shell

def filter_hdr(updates):
    def f(u):
        if 'header' in u:
            return 'hdr'
        return u
    return [ f(u) for u in updates ]

class TestSlaveShellCommand(CommandTestMixin, unittest.TestCase):
    # note that, as a unit test, this depends on the RunProcess class's proper
    # functioning.  It does not re-test functionality provided by that class, though.

    def tearDown(self):
        self.tearDownCommand()

    def test_simple(self):
        self.patch_runprocess(
            Expect([ 'echo', 'hello' ], '/slavebuilder/basedir/workdir')
            + { 'hdr' : 'headers' } + { 'stdout' : 'hello\n' } + { 'rc' : 0 }
            + 0,
        )

        cmd = self.make_command(shell.SlaveShellCommand, dict(
            command=[ 'echo', 'hello' ],
            workdir='workdir',
        ))

        d = self.run_command()

        def check(_):
            self.assertEqual(filter_hdr(self.get_updates()),
                    [{'hdr': 'headers'}, {'stdout': 'hello\n'}, {'rc': 0}],
                    self.builder.show())
        d.addCallback(check)
        return d
