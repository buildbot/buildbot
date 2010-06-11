import os

from twisted.trial import unittest
from twisted.python import runtime

from buildslave.test.fake.runprocess import Expect
from buildslave.test.util.sourcecommand import SourceCommandTestMixin
from buildslave.commands import svn

class TestSVN(SourceCommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    def test_simple(self):
        self.patch_getCommand('svn', 'path/to/svn')
        self.patch_getCommand('svnversion', 'path/to/svnversion')
        self.clean_environ()
        self.make_command(svn.SVN, dict(
            workdir='workdir',
            mode='copy',
            revision=None,
            svnurl='http://svn.local/app/trunk',
        ))

        exp_environ = dict(PWD='.', LC_MESSAGES='C')
        expects = [
            Expect([ 'clobber', 'workdir' ],
                self.basedir)
                + 0,
            Expect([ 'clobber', 'source' ],
                self.basedir)
                + 0,
            Expect([ 'path/to/svn', 'checkout', '--non-interactive', '--no-auth-cache',
                     '--revision', 'HEAD', 'http://svn.local/app/trunk', 'source' ],
                self.basedir,
                sendRC=False, timeout=120, usePTY=False, environ=exp_environ)
                + 0,
            Expect([ 'path/to/svnversion', '.' ],
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
        d.addCallback(self.check_sourcedata, "http://svn.local/app/trunk\n")
        return d
