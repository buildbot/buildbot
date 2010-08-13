import os

from twisted.trial import unittest
from twisted.python import runtime

from buildslave.test.fake.runprocess import Expect
from buildslave.test.util.sourcecommand import SourceCommandTestMixin
from buildslave.commands import arch

class TestArch(SourceCommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    def test_simple(self):
        self.patch_getCommand('tla', 'path/to/tla')
        self.clean_environ()
        self.make_command(arch.Arch, dict(
            workdir='workdir',
            mode='copy',
            url='ftp://somewhere.com/pub/archive',
            version='mainline',
            revision='patch-22',
            archive='funarchive',
        ))

        exp_environ = dict(PWD='.', LC_MESSAGES='C')
        expects = [
            Expect([ 'clobber', 'workdir' ],
                self.basedir)
                + 0,
            Expect([ 'clobber', 'source' ],
                self.basedir)
                + 0,
            Expect(['path/to/tla', 'register-archive', '--force',
                    'ftp://somewhere.com/pub/archive'],
                self.basedir,
                sendRC=False, timeout=120, usePTY=False, keepStdout=True)
                + { 'stdout' : 'Registering archive: funarchive\n' }
                + 0,
            Expect(['path/to/tla', 'get', '--archive', 'funarchive',
                    '--no-pristine', 'mainline--patch-22', 'source'],
                self.basedir,
                sendRC=False, usePTY=False, timeout=120)
                + { 'stdout' : '9753\n' }
                + 0,
            Expect(['path/to/tla', 'logs', '--full', '--reverse'],
                self.basedir_source,
                timeout=120, sendRC=False, usePTY=False, keepStdout=True,
                sendStdout=False, sendStderr=False, environ=exp_environ)
                + { 'stdout' : 'funarchive/mainline--patch-22\n' }
                + 0,
            Expect([ 'copy', 'source', 'workdir'],
                self.basedir)
                + 0,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata, "ftp://somewhere.com/pub/archive\nmainline\nNone\n")
        return d

class TestBazaar(SourceCommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    def test_simple(self):
        self.patch_getCommand('baz', 'path/to/baz')
        self.clean_environ()
        self.make_command(arch.Bazaar, dict(
            workdir='workdir',
            mode='copy',
            url='ftp://somewhere.com/pub/archive',
            version='mainline',
            revision='patch-22',
            archive='funarchive',
        ))

        exp_environ = dict(PWD='.', LC_MESSAGES='C')
        expects = [
            Expect([ 'clobber', 'workdir' ],
                self.basedir)
                + 0,
            Expect([ 'clobber', 'source' ],
                self.basedir)
                + 0,
            Expect(['path/to/baz', 'register-archive', '--force',
                    'ftp://somewhere.com/pub/archive'],
                self.basedir,
                sendRC=False, timeout=120, usePTY=False, keepStdout=True)
                + { 'stdout' : 'Registering archive: funarchive\n' }
                + 0,
            Expect(['path/to/baz', 'get', '--no-pristine',
                    'funarchive/mainline--patch-22', 'source'],
                self.basedir,
                sendRC=False, usePTY=False, timeout=120)
                + { 'stdout' : '9753\n' }
                + 0,
            Expect(['path/to/baz', 'tree-id'],
                self.basedir_source,
                timeout=120, sendRC=False, usePTY=False, keepStdout=True,
                sendStdout=False, sendStderr=False, environ=exp_environ)
                + { 'stdout' : 'funarchive/mainline--patch-22\n' }
                + 0,
            Expect([ 'copy', 'source', 'workdir'],
                self.basedir)
                + 0,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata, "ftp://somewhere.com/pub/archive\nmainline\nNone\n")
        return d
