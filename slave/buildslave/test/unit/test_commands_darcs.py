import os

from twisted.trial import unittest
from twisted.python import runtime

from buildslave.test.fake.runprocess import Expect
from buildslave.test.util.sourcecommand import SourceCommandTestMixin
from buildslave.commands import darcs

class TestDarcs(SourceCommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    def test_simple(self):
        self.patch_getCommand('darcs', 'path/to/darcs')
        self.clean_environ()
        self.make_command(darcs.Darcs, dict(
            workdir='workdir',
            mode='copy',
            revision=None,
            repourl='http://darcs.net',
        ))

        exp_environ = dict(PWD='.', LC_MESSAGES='C')
        expects = [
            Expect([ 'clobber', 'workdir' ],
                self.basedir)
                + 0,
            Expect([ 'clobber', 'source' ],
                self.basedir)
                + 0,
            Expect([ 'path/to/darcs', 'get', '--verbose', '--partial', '--repo-name',
                     'source', 'http://darcs.net'],
                self.basedir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect([ 'path/to/darcs', 'changes', '--context' ],
                os.path.join(self.basedir, 'source'),
                sendRC=False, timeout=120, usePTY=False, keepStdout=True,
                environ=exp_environ, sendStderr=False, sendStdout=False)
                + { 'stdout' : '9753\n' }
                + 0,
            Expect([ 'copy', 'source', 'workdir'],
                self.basedir)
                + 0,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata, "http://darcs.net\n")
        return d

