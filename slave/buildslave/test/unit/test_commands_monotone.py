import os

from twisted.trial import unittest
from twisted.python import runtime

from buildslave.test.fake.runprocess import Expect
from buildslave.test.util.sourcecommand import SourceCommandTestMixin
from buildslave.commands import monotone

class TestMonotone(SourceCommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    def test_simple(self):
        self.patch_getCommand('mtn', 'path/to/mtn')
        self.clean_environ()
        self.make_command(monotone.Monotone, dict(
            workdir='workdir',
            mode='copy',
            revision='e831aa7c1baa0c545c5d1917364ff299cd79e174', # None is not supported
            server_addr='monotone.ca',
            branch='net.venge.monotone',
            db_path='/var/slave/mtn/monotone.db',
        ))

        exp_environ = dict(PWD='.', LC_MESSAGES='C')
        expects = [
            Expect([ 'clobber', 'workdir' ],
                self.basedir)
                + 0,
            Expect([ 'clobber', 'source' ],
                self.basedir)
                + 0,
            Expect(['path/to/mtn', 'db', 'init', '--db=/var/slave/mtn/monotone.db'],
                self.basedir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect(['path/to/mtn', '--db=/var/slave/mtn/monotone.db', 'pull',
                    '--ticker=dot', 'monotone.ca', 'net.venge.monotone'],
                self.basedir,
                sendRC=False, timeout=3*60*60, usePTY=False)
                + 0,
            Expect(['path/to/mtn', '--db=/var/slave/mtn/monotone.db', 'checkout',
                    '-r', 'e831aa7c1baa0c545c5d1917364ff299cd79e174', '-b', 'net.venge.monotone',
                    '/tmp/trialtemp/basedir/source'],
                self.basedir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect([ 'copy', 'source', 'workdir'],
                self.basedir)
                + 0,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        # TODO: monotone doesn't believe in sourcedata?
        d.addCallback(self.check_sourcedata, "")
        return d

