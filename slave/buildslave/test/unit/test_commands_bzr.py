import os

from twisted.trial import unittest
from twisted.python import runtime

from buildslave.test.fake.runprocess import Expect
from buildslave.test.util.sourcecommand import SourceCommandTestMixin
from buildslave.commands import bzr

class TestBzr(SourceCommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    def test_simple(self):
        self.patch_getCommand('bzr', 'path/to/bzr')
        self.clean_environ()
        self.make_command(bzr.Bzr, dict(
            workdir='workdir',
            mode='copy',
            revision='12',
            repourl='http://bazaar.launchpad.net/~bzr/bzr-gtk/trunk',
        ))

        exp_environ = dict(PWD='.', LC_MESSAGES='C')
        expects = [
            Expect([ 'clobber', 'workdir' ],
                self.basedir)
                + 0,
            Expect([ 'clobber', 'source' ],
                self.basedir)
                + 0,
                Expect([ 'path/to/bzr', 'checkout', '--revision', '12',
                         'http://bazaar.launchpad.net/~bzr/bzr-gtk/trunk', 'source' ],
                self.basedir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect(['path/to/bzr', 'version-info'],
                os.path.join(self.basedir, 'source'),
                sendRC=False, usePTY=False, keepStdout=True,
                environ=exp_environ, sendStderr=False, sendStdout=False)
                + { 'stdout' : '9753\n' }
                + 0,
            Expect([ 'copy', 'source', 'workdir'],
                self.basedir)
                + 0,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata, "http://bazaar.launchpad.net/~bzr/bzr-gtk/trunk\n")
        return d

