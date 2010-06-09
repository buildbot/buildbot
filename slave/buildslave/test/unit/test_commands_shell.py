from twisted.trial import unittest
from twisted.internet import task, defer
from twisted.python import runtime

from buildslave.test.fake.runprocess import Expect
from buildslave.test.util.command import CommandTestMixin
from buildslave.commands import shell

def filter_hdr(updates):
    def f(u):
        if 'header' in u:
            return 'hdr'
        return u
    return [ f(u) for u in updates ]

class TestSlaveShellCommand(CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    def test_simple(self):
        self.make_command(shell.SlaveShellCommand, dict(
            command=[ 'echo', 'hello' ],
            workdir='workdir',
        ))

        self.patch_runprocess(
            Expect([ 'echo', 'hello' ], self.basedir_workdir)
            + { 'hdr' : 'headers' } + { 'stdout' : 'hello\n' } + { 'rc' : 0 }
            + 0,
        )

        d = self.run_command()

        # note that SlaveShellCommand does not add any extra updates of it own
        def check(_):
            self.assertEqual(filter_hdr(self.get_updates()),
                    [{'hdr': 'headers'}, {'stdout': 'hello\n'}, {'rc': 0}],
                    self.builder.show())
        d.addCallback(check)
        return d

    # TODO: test all functionality that SlaveShellCommand adds atop RunProcess
