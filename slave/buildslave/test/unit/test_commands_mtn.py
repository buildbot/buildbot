# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

import os
import mock

from twisted.trial import unittest
from twisted.internet import defer

from buildslave.test.fake.runprocess import Expect
from buildslave.test.util.sourcecommand import SourceCommandTestMixin
from buildslave.commands import mtn

class TestMonotone(SourceCommandTestMixin, unittest.TestCase):
    repourl='mtn://code.monotone.ca/sandbox'
    branch='ca.monotone.sandbox.buildbot'

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    def patch_sourcedirIsUpdateable(self, result):
        self.cmd.sourcedirIsUpdateable = lambda : result


    def test_no_db(self):
        "Test a basic invocation with mode=copy and no existing sourcedir"
        self.patch_getCommand('mtn', 'path/to/mtn')
        self.clean_environ()
        self.make_command(mtn.Monotone, dict(
            workdir='workdir',
            mode='copy',
            revision=None,
            repourl=self.repourl,
            branch=self.branch
        ),
            # no sourcedata -> will do fresh checkout
            initial_sourcedata = None,
        )
        exp_environ = dict(PWD='.', LC_MESSAGES='C')
        expects = [
            Expect(['path/to/mtn', 'db', 'info',
                    '--db', os.path.join(self.basedir, 'db.mtn')],
                   self.basedir,
                   keepStdout=True, sendRC=False, sendStderr=False,
                   usePTY=False, environ=exp_environ) + 1,
            Expect(['path/to/mtn', 'db', 'init',
                    '--db', os.path.join(self.basedir, 'db.mtn')],
                   self.basedir,
                   sendRC=False, usePTY=False,
                   environ=exp_environ) + 1,
            Expect([ 'clobber', 'workdir' ],
                   self.basedir) + 0,
            Expect([ 'clobber', 'source' ],
                   self.basedir) + 0,
            Expect(['path/to/mtn', 'pull', self.repourl+"?"+self.branch,
                     '--db', os.path.join(self.basedir, 'db.mtn'),
                     '--ticker=none'],
                   self.basedir,
                   keepStdout=True, sendRC=False, timeout=120, usePTY=False,
                   environ=exp_environ) + 0,
            Expect(['path/to/mtn', 'checkout', self.basedir_source,
                    '--db', os.path.join(self.basedir, 'db.mtn'),
                    '--branch', 'ca.monotone.sandbox.buildbot'],
                   self.basedir,
                   keepStdout=True, sendRC=False, timeout=120, usePTY=False,
                   environ=exp_environ) + 0,
            Expect(['path/to/mtn', 'automate', 'select', 'w:'],
                   self.basedir_source,
                   keepStdout=True, sendRC=False, timeout=120, usePTY=False)
                   + 0,
            Expect([ 'copy', 'source', 'workdir'],
                   self.basedir)
                   + 0,
            ]

        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata, self.repourl+"?"+self.branch)
        return d

    def test_db_needs_migrating(self):
        "Test a basic invocation with mode=copy and no existing sourcedir"
        self.patch_getCommand('mtn', 'path/to/mtn')
        self.clean_environ()
        self.make_command(mtn.Monotone, dict(
            workdir='workdir',
            mode='copy',
            revision=None,
            repourl=self.repourl,
            branch=self.branch
        ),
            # no sourcedata -> will do fresh checkout
            initial_sourcedata = None,
        )
        exp_environ = dict(PWD='.', LC_MESSAGES='C')
        expects = [
            Expect([ 'path/to/mtn', 'db', 'info',
                     '--db', os.path.join(self.basedir, 'db.mtn') ],
                   self.basedir,
                   keepStdout=True, sendRC=False, sendStderr=False,
                   usePTY=False, environ=exp_environ)
            + { 'stdout' : 'blah blah (migration needed)\n' }
            + 0,
            Expect([ 'path/to/mtn', 'db', 'migrate',
                     '--db', os.path.join(self.basedir, 'db.mtn') ],
                   self.basedir,
                   sendRC=False, usePTY=False,
                   environ=exp_environ) + 0,
            Expect([ 'clobber', 'workdir' ],
                   self.basedir) + 0,
            Expect([ 'clobber', 'source' ],
                   self.basedir) + 0,
            Expect(['path/to/mtn', 'pull', self.repourl+"?"+self.branch,
                     '--db', os.path.join(self.basedir, 'db.mtn'),
                     '--ticker=none'],
                   self.basedir,
                   keepStdout=True, sendRC=False, timeout=120, usePTY=False,
                   environ=exp_environ) + 0,
            Expect(['path/to/mtn', 'checkout', self.basedir_source,
                    '--db', os.path.join(self.basedir, 'db.mtn'),
                    '--branch', 'ca.monotone.sandbox.buildbot'],
                   self.basedir,
                   keepStdout=True, sendRC=False, timeout=120, usePTY=False,
                   environ=exp_environ) + 0,
            Expect(['path/to/mtn', 'automate', 'select', 'w:'],
                   self.basedir_source,
                   keepStdout=True, sendRC=False, timeout=120, usePTY=False)
                   + 0,
            Expect([ 'copy', 'source', 'workdir'],
                   self.basedir)
                   + 0,
            ]

        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata, self.repourl+"?"+self.branch)
        return d

    def test_db_too_new(self):
        "Test a basic invocation with mode=copy and no existing sourcedir"
        self.patch_getCommand('mtn', 'path/to/mtn')
        self.clean_environ()
        self.make_command(mtn.Monotone, dict(
            workdir='workdir',
            mode='copy',
            revision=None,
            repourl=self.repourl,
            branch=self.branch
        ),
            # no sourcedata -> will do fresh checkout
            initial_sourcedata = None,
        )

        exp_environ = dict(PWD='.', LC_MESSAGES='C')
        expects = [
            Expect([ 'path/to/mtn', 'db', 'info',
                     '--db', os.path.join(self.basedir, 'db.mtn') ],
                   self.basedir,
                   keepStdout=True, sendRC=False, sendStderr=False,
                   usePTY=False, environ=exp_environ)
            + { 'stdout' : 'blah blah (too new, cannot use)\n' }
            + 0
            ]

        self.patch_runprocess(*expects)

        d = self.run_command()
        return self.assertFailure(d, mtn.MonotoneError)

    def test_run_mode_copy_fresh_sourcedir(self):
        "Test a basic invocation with mode=copy and no existing sourcedir"
        self.patch_getCommand('mtn', 'path/to/mtn')
        self.clean_environ()
        self.make_command(mtn.Monotone, dict(
            workdir='workdir',
            mode='copy',
            revision=None,
            repourl=self.repourl,
            branch=self.branch
        ),
            # no sourcedata -> will do fresh checkout
            initial_sourcedata = None,
        )

        exp_environ = dict(PWD='.', LC_MESSAGES='C')
        expects = [
            Expect(['path/to/mtn', 'db', 'info',
                    '--db', os.path.join(self.basedir, 'db.mtn')],
                   self.basedir,
                   keepStdout=True, sendRC=False, sendStderr=False,
                   usePTY=False, environ=exp_environ) + 0,
            Expect([ 'clobber', 'workdir' ],
                   self.basedir) + 0,
            Expect([ 'clobber', 'source' ],
                   self.basedir) + 0,
            Expect(['path/to/mtn', 'pull', self.repourl+"?"+self.branch,
                     '--db', os.path.join(self.basedir, 'db.mtn'),
                     '--ticker=none'],
                   self.basedir,
                   keepStdout=True, sendRC=False, timeout=120, usePTY=False,
                   environ=exp_environ) + 0,
            Expect(['path/to/mtn', 'checkout', self.basedir_source,
                    '--db', os.path.join(self.basedir, 'db.mtn'),
                    '--branch', 'ca.monotone.sandbox.buildbot'],
                   self.basedir,
                   keepStdout=True, sendRC=False, timeout=120, usePTY=False,
                   environ=exp_environ) + 0,
            Expect(['path/to/mtn', 'automate', 'select', 'w:'],
                   self.basedir_source,
                   keepStdout=True, sendRC=False, timeout=120, usePTY=False)
                   + 0,
            Expect([ 'copy', 'source', 'workdir'],
                   self.basedir)
                   + 0,
            ]

        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata, self.repourl+"?"+self.branch)
        return d

    def test_run_mode_copy_update_sourcedir(self):
        """test a copy where the sourcedata indicates that the source directory
        can be updated"""
        self.patch_getCommand('mtn', 'path/to/mtn')
        self.clean_environ()
        self.make_command(mtn.Monotone, dict(
            workdir='workdir',
            mode='copy',
            revision=None,
            repourl=self.repourl,
            branch=self.branch,
            progress=True, # added here for better coverage
        ),
            initial_sourcedata = self.repourl+"?"+self.branch
        )
        self.patch_sourcedirIsUpdateable(True)

        exp_environ = dict(PWD='.', LC_MESSAGES='C')
        expects = [
            Expect([ 'path/to/mtn', 'db', 'info',
                     '--db', os.path.join(self.basedir, 'db.mtn')],
                   self.basedir,
                   keepStdout=True, sendRC=False, sendStderr=False,
                   usePTY=False, environ=exp_environ) + 0,
            Expect([ 'clobber', 'workdir' ],
                   self.basedir) + 0,
            Expect([ 'path/to/mtn', 'pull', self.repourl+"?"+self.branch,
                     '--db', os.path.join(self.basedir, 'db.mtn'),
                     '--ticker=dot'],
                   self.basedir,
                   keepStdout=True, sendRC=False, timeout=120, usePTY=False,
                   environ=exp_environ) + 0,
            Expect([ 'path/to/mtn', 'update',
                     '--db', os.path.join(self.basedir, 'db.mtn'),
                     '-r', 'h:ca.monotone.sandbox.buildbot',
                     '-b', 'ca.monotone.sandbox.buildbot'],
                   self.basedir_source,
                   keepStdout=True, sendRC=False, timeout=120, usePTY=False,
                   environ=exp_environ) + 0,
            Expect(['path/to/mtn', 'automate', 'select', 'w:'],
                   self.basedir_source,
                   keepStdout=True, sendRC=False, timeout=120, usePTY=False)
                   + 0,
            Expect([ 'copy', 'source', 'workdir'],
                   self.basedir)
                   + 0,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata, self.repourl+"?"+self.branch)
        return d

    def test_run_mode_update_fresh(self):
        self.patch_getCommand('mtn', 'path/to/mtn')
        self.clean_environ()
        self.make_command(mtn.Monotone, dict(
            workdir='workdir',
            mode='update',
            revision=None,
            repourl=self.repourl,
            branch=self.branch,
            progress=True, # added here for better coverage
        ),
            initial_sourcedata = self.repourl+"?"+self.branch
        )
        self.patch_sourcedirIsUpdateable(False)

        exp_environ = dict(PWD='.', LC_MESSAGES='C')
        expects = [
            Expect([ 'path/to/mtn', 'db', 'info',
                     '--db', os.path.join(self.basedir, 'db.mtn')],
                   self.basedir,
                   keepStdout=True, sendRC=False, sendStderr=False,
                   usePTY=False, environ=exp_environ) + 0,
            Expect([ 'clobber', 'workdir' ],
                   self.basedir) + 0,
            Expect([ 'path/to/mtn', 'pull', self.repourl+"?"+self.branch,
                     '--db', os.path.join(self.basedir, 'db.mtn'),
                     '--ticker=dot'],
                   self.basedir,
                   keepStdout=True, sendRC=False, timeout=120, usePTY=False,
                   environ=exp_environ) + 0,
            Expect(['path/to/mtn', 'checkout', self.basedir_workdir,
                    '--db', os.path.join(self.basedir, 'db.mtn'),
                    '--branch', 'ca.monotone.sandbox.buildbot'],
                   self.basedir,
                   keepStdout=True, sendRC=False, timeout=120, usePTY=False,
                   environ=exp_environ) + 0,
            Expect(['path/to/mtn', 'automate', 'select', 'w:'],
                   self.basedir_workdir,
                   keepStdout=True, sendRC=False, timeout=120, usePTY=False)
                   + 0,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata, self.repourl+"?"+self.branch)
        return d

    def test_run_mode_update_existing(self):
        self.patch_getCommand('mtn', 'path/to/mtn')
        self.clean_environ()
        self.make_command(mtn.Monotone, dict(
            workdir='workdir',
            mode='update',
            revision=None,
            repourl=self.repourl,
            branch=self.branch,
            progress=True, # added here for better coverage
        ),
            initial_sourcedata = self.repourl+"?"+self.branch
        )
        self.patch_sourcedirIsUpdateable(True)

        exp_environ = dict(PWD='.', LC_MESSAGES='C')
        expects = [
            Expect([ 'path/to/mtn', 'db', 'info',
                     '--db', os.path.join(self.basedir, 'db.mtn')],
                   self.basedir,
                   keepStdout=True, sendRC=False, sendStderr=False,
                   usePTY=False, environ=exp_environ) + 0,
            Expect([ 'path/to/mtn', 'pull', self.repourl+"?"+self.branch,
                     '--db', os.path.join(self.basedir, 'db.mtn'),
                     '--ticker=dot'],
                   self.basedir,
                   keepStdout=True, sendRC=False, timeout=120, usePTY=False,
                   environ=exp_environ) + 0,
            Expect([ 'path/to/mtn', 'update',
                     '--db', os.path.join(self.basedir, 'db.mtn'),
                     '-r', 'h:ca.monotone.sandbox.buildbot',
                     '-b', 'ca.monotone.sandbox.buildbot'],
                   self.basedir_workdir,
                   keepStdout=True, sendRC=False, timeout=120, usePTY=False,
                   environ=exp_environ) + 0,
            Expect(['path/to/mtn', 'automate', 'select', 'w:'],
                   self.basedir_workdir,
                   keepStdout=True, sendRC=False, timeout=120, usePTY=False)
                   + 0,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata, self.repourl+"?"+self.branch)
        return d

    def test_run_mode_update_existing_known_rev(self):
        self.patch_getCommand('mtn', 'path/to/mtn')
        self.clean_environ()
        self.make_command(mtn.Monotone, dict(
            workdir='workdir',
            mode='update',
            revision='abcdef01',
            repourl=self.repourl,
            branch=self.branch,
            progress=True, # added here for better coverage
        ),
            initial_sourcedata = self.repourl+"?"+self.branch
        )
        self.patch_sourcedirIsUpdateable(True)

        exp_environ = dict(PWD='.', LC_MESSAGES='C')
        expects = [
            Expect([ 'path/to/mtn', 'db', 'info',
                     '--db', os.path.join(self.basedir, 'db.mtn')],
                   self.basedir,
                   keepStdout=True, sendRC=False, sendStderr=False,
                   usePTY=False, environ=exp_environ) + 0,
            Expect([ 'path/to/mtn', 'pull', self.repourl+"?"+self.branch,
                     '--db', os.path.join(self.basedir, 'db.mtn'),
                     '--ticker=dot'],
                   self.basedir,
                   keepStdout=True, sendRC=False, timeout=120, usePTY=False,
                   environ=exp_environ) + 0,
            Expect([ 'path/to/mtn', 'update',
                     '--db', os.path.join(self.basedir, 'db.mtn'),
                     '--revision', 'abcdef01',
                     '-b', 'ca.monotone.sandbox.buildbot'],
                   self.basedir_workdir,
                   keepStdout=True, sendRC=False, timeout=120, usePTY=False,
                   environ=exp_environ) + 0,
            Expect(['path/to/mtn', 'automate', 'select', 'w:'],
                   self.basedir_workdir,
                   keepStdout=True, sendRC=False, timeout=120, usePTY=False)
                   + 0,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata, self.repourl+"?"+self.branch)
        return d

    def test_run_mode_update_existing_unknown_rev(self):
        self.patch_getCommand('mtn', 'path/to/mtn')
        self.clean_environ()
        self.make_command(mtn.Monotone, dict(
            workdir='workdir',
            mode='update',
            revision='abcdef01',
            repourl=self.repourl,
            branch=self.branch,
            progress=True, # added here for better coverage
        ),
            initial_sourcedata = self.repourl+"?"+self.branch
        )
        self.patch_sourcedirIsUpdateable(True)

        exp_environ = dict(PWD='.', LC_MESSAGES='C')
        expects = [
            Expect([ 'path/to/mtn', 'db', 'info',
                     '--db', os.path.join(self.basedir, 'db.mtn')],
                   self.basedir,
                   keepStdout=True, sendRC=False, sendStderr=False,
                   usePTY=False, environ=exp_environ) + 0,
            Expect([ 'path/to/mtn', 'pull', self.repourl+"?"+self.branch,
                     '--db', os.path.join(self.basedir, 'db.mtn'),
                     '--ticker=dot'],
                   self.basedir,
                   keepStdout=True, sendRC=False, timeout=120, usePTY=False,
                   environ=exp_environ) + 0,
            Expect([ 'path/to/mtn', 'update',
                     '--db', os.path.join(self.basedir, 'db.mtn'),
                     '--revision', 'abcdef01',
                     '-b', 'ca.monotone.sandbox.buildbot'],
                   self.basedir_workdir,
                   keepStdout=True, sendRC=False, timeout=120, usePTY=False,
                   environ=exp_environ) + 1,
            Expect([ 'clobber', 'workdir' ],
                   self.basedir) + 0,
            Expect([ 'path/to/mtn', 'pull', self.repourl+"?"+self.branch,
                     '--db', os.path.join(self.basedir, 'db.mtn'),
                     '--ticker=dot'],
                   self.basedir,
                   keepStdout=True, sendRC=False, timeout=120, usePTY=False,
                   environ=exp_environ) + 0,
            Expect(['path/to/mtn', 'checkout', self.basedir_workdir,
                    '--db', os.path.join(self.basedir, 'db.mtn'),
                    '--revision', 'abcdef01',
                    '--branch', 'ca.monotone.sandbox.buildbot'],
                   self.basedir,
                   keepStdout=True, sendRC=False, timeout=120, usePTY=False,
                   environ=exp_environ) + 0,
            Expect(['path/to/mtn', 'automate', 'select', 'w:'],
                   self.basedir_workdir,
                   keepStdout=True, sendRC=False, timeout=120, usePTY=False)
                   + 0,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata, self.repourl+"?"+self.branch)
        return d

# Testing parseGotRevision
    def do_test_parseGotRevision(self, stdout, exp):
        self.patch_getCommand('mtn', 'path/to/mtn')
        self.make_command(mtn.Monotone, dict(
            workdir='workdir',
            repourl=self.repourl,
            branch=self.branch
        ))
        def _dovccmd(fn, dopull, callback=None, keepStdout=False):
            #self.assertTrue(keepStdout)
            self.cmd.command = mock.Mock()
            self.cmd.command.stdout = stdout
            d = defer.succeed(None)
            d.addCallback(callback)
            return d
        self.cmd._dovccmd = _dovccmd
        self.cmd.srcdir = self.cmd.workdir

        d = self.cmd.parseGotRevision()
        def check(res):
            self.assertEqual(res, exp)
        d.addCallback(check)
        return d

    def test_parseGotRevision_bogus(self):
        return self.do_test_parseGotRevision("mtn: misuse: no match for selection '1234'\n", None)

    def test_parseGotRevision_wrong_length(self):
        return self.do_test_parseGotRevision("\n1234abcd\n", None)

    def test_parseGotRevision_ok(self):
        return self.do_test_parseGotRevision(
                "\n4026d33b0532b11f36b0875f63699adfa8ee8662\n",
                  "4026d33b0532b11f36b0875f63699adfa8ee8662")

