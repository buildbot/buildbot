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
from buildslave.commands import git

class TestGit(SourceCommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    def patch_sourcedirIsUpdateable(self, result):
        self.cmd.sourcedirIsUpdateable = lambda : result

    # tests

    def test_run_mode_copy_fresh_sourcedir(self):
        "Test a basic invocation with mode=copy and no existing sourcedir"
        self.patch_getCommand('git', 'path/to/git')
        self.clean_environ()
        self.make_command(git.Git, dict(
            workdir='workdir',
            mode='copy',
            revision=None,
            repourl='git://github.com/djmitche/buildbot.git',
        ),
            # no sourcedata -> will do fresh checkout
            initial_sourcedata = None,
        )

        expects = [
            Expect([ 'clobber', 'workdir' ],
                self.basedir)
                + 0,
            Expect([ 'clobber', 'source' ],
                self.basedir)
                + 0,
            # TODO: capture makedirs invocation here
            Expect([ 'path/to/git', 'init'],
                self.basedir_source,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect([ 'path/to/git', 'fetch', '-t',
                     'git://github.com/djmitche/buildbot.git', '+master' ],
                self.basedir_source,
                sendRC=False, timeout=120, usePTY=False, keepStderr=True)
                + { 'stderr' : '' }
                + 0,
            Expect(['path/to/git', 'reset', '--hard', 'FETCH_HEAD'],
                self.basedir_source,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect(['path/to/git', 'branch', '-M', 'master'],
                self.basedir_source,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect([ 'path/to/git', 'rev-parse', 'HEAD' ],
                self.basedir_source,
                sendRC=False, timeout=120, usePTY=False, keepStdout=True)
                + { 'stdout' : '4026d33b0532b11f36b0875f63699adfa8ee8662\n' }
                + 0,
            Expect([ 'copy', 'source', 'workdir'],
                self.basedir)
                + 0,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata, "git://github.com/djmitche/buildbot.git master\n")
        return d


    def test_run_mode_copy_update_sourcedir(self):
        """test a copy where the sourcedata indicates that the source directory
        can be updated"""
        self.patch_getCommand('git', 'path/to/git')
        self.clean_environ()
        self.make_command(git.Git, dict(
            workdir='workdir',
            mode='copy',
            revision=None,
            repourl='git://github.com/djmitche/buildbot.git',
            progress=True, # added here for better coverage
          ),
            initial_sourcedata = "git://github.com/djmitche/buildbot.git master\n",
        )
        self.patch_sourcedirIsUpdateable(True)

        expects = [
            Expect([ 'clobber', 'workdir' ],
                self.basedir)
                + 0,
            Expect([ 'path/to/git', 'fetch', '-t',
                     'git://github.com/djmitche/buildbot.git', '+master',
                     '--progress' ],
                self.basedir_source,
                sendRC=False, timeout=120, usePTY=False, keepStderr=True)
                + { 'stderr' : '' }
                + 0,
            Expect(['path/to/git', 'reset', '--hard', 'FETCH_HEAD'],
                self.basedir_source,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect(['path/to/git', 'branch', '-M', 'master'],
                self.basedir_source,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect([ 'path/to/git', 'rev-parse', 'HEAD' ],
                self.basedir_source,
                sendRC=False, timeout=120, usePTY=False, keepStdout=True)
                + { 'stdout' : '4026d33b0532b11f36b0875f63699adfa8ee8662\n' }
                + 0,
            Expect([ 'copy', 'source', 'workdir'],
                self.basedir)
                + 0,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata, "git://github.com/djmitche/buildbot.git master\n")
        return d

    def test_run_mode_copy_nonexistant_ref(self):
        self.patch_getCommand('git', 'path/to/git')
        self.clean_environ()
        self.make_command(git.Git, dict(
            workdir='workdir',
            mode='copy',
            revision=None,
            branch='bogusref',
            repourl='git://github.com/djmitche/buildbot.git',
        ))
        self.patch_sourcedirIsUpdateable(True)

        expects = [
            Expect([ 'clobber', 'workdir' ],
                self.basedir)
                + 0,
            Expect([ 'path/to/git', 'clean', '-f', '-d', '-x'],
                self.basedir_source,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect([ 'path/to/git', 'fetch', '-t',
                     'git://github.com/djmitche/buildbot.git', '+bogusref' ],
                self.basedir_source,
                sendRC=False, timeout=120, usePTY=False, keepStderr=True)
                + { 'stderr' : "fatal: Couldn't find remote ref bogusref\n" }
                + { 'rc': 128 }
                + 128,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        return d

    def test_run_mode_copy_gerrit_branch(self):
        self.patch_getCommand('git', 'path/to/git')
        self.clean_environ()
        self.make_command(git.Git, dict(
            workdir='workdir',
            mode='copy',
            revision=None,
            branch='local-branch',
            gerrit_branch='real-branch',
            repourl='git://github.com/djmitche/buildbot.git',
        ))
        self.patch_sourcedirIsUpdateable(True)

        expects = [
            Expect([ 'clobber', 'workdir' ],
                self.basedir)
                + 0,
            Expect([ 'path/to/git', 'clean', '-f', '-d', '-x'],
                self.basedir_source,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect([ 'path/to/git', 'fetch', '-t',
                     'git://github.com/djmitche/buildbot.git', '+real-branch' ],
                self.basedir_source,
                sendRC=False, timeout=120, usePTY=False, keepStderr=True)
                + { 'stderr' : '' }
                + 0,
            Expect(['path/to/git', 'reset', '--hard', 'FETCH_HEAD'],
                self.basedir_source,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect(['path/to/git', 'branch', '-M', 'local-branch'], # note, not the same branch
                self.basedir_source,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect([ 'path/to/git', 'rev-parse', 'HEAD' ],
                self.basedir_source,
                sendRC=False, timeout=120, usePTY=False, keepStdout=True)
                + { 'stdout' : '4026d33b0532b11f36b0875f63699adfa8ee8662\n' }
                + 0,
            Expect([ 'copy', 'source', 'workdir'],
                self.basedir)
                + 0,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        return d

    def test_run_mode_update_fresh(self):
        self.patch_getCommand('git', 'path/to/git')
        self.clean_environ()
        self.make_command(git.Git, dict(
            workdir='workdir',
            mode='update',
            revision=None,
            repourl='git://github.com/djmitche/buildbot.git',
          ),
            initial_sourcedata = "git://github.com/djmitche/buildbot.git master\n",
        )
        self.patch_sourcedirIsUpdateable(False)

        expects = [
            Expect([ 'clobber', 'workdir' ],
                self.basedir)
                + 0,
            Expect([ 'path/to/git', 'init'],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect([ 'path/to/git', 'fetch', '-t',
                     'git://github.com/djmitche/buildbot.git', '+master' ],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False, keepStderr=True)
                + { 'stderr' : '' }
                + 0,
            Expect(['path/to/git', 'reset', '--hard', 'FETCH_HEAD'],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect(['path/to/git', 'branch', '-M', 'master'],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect([ 'path/to/git', 'rev-parse', 'HEAD' ],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False, keepStdout=True)
                + { 'stdout' : '4026d33b0532b11f36b0875f63699adfa8ee8662\n' }
                + 0,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata, "git://github.com/djmitche/buildbot.git master\n")
        return d

    def test_run_mode_update_existing(self):
        self.patch_getCommand('git', 'path/to/git')
        self.clean_environ()
        self.make_command(git.Git, dict(
            workdir='workdir',
            mode='update',
            revision=None,
            repourl='git://github.com/djmitche/buildbot.git',
          ),
            initial_sourcedata = "git://github.com/djmitche/buildbot.git master\n",
        )
        self.patch_sourcedirIsUpdateable(True)

        expects = [
            Expect([ 'path/to/git', 'fetch', '-t',
                     'git://github.com/djmitche/buildbot.git', '+master' ],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False, keepStderr=True)
                + { 'stderr' : '' }
                + 0,
            Expect(['path/to/git', 'reset', '--hard', 'FETCH_HEAD'],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect(['path/to/git', 'branch', '-M', 'master'],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect([ 'path/to/git', 'rev-parse', 'HEAD' ],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False, keepStdout=True)
                + { 'stdout' : '4026d33b0532b11f36b0875f63699adfa8ee8662\n' }
                + 0,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata, "git://github.com/djmitche/buildbot.git master\n")
        return d

    def test_run_mode_update_existing_known_rev(self):
        self.patch_getCommand('git', 'path/to/git')
        self.clean_environ()
        self.make_command(git.Git, dict(
            workdir='workdir',
            mode='update',
            revision='abcdef01',
            repourl='git://github.com/djmitche/buildbot.git',
          ),
            initial_sourcedata = "git://github.com/djmitche/buildbot.git master\n",
        )
        self.patch_sourcedirIsUpdateable(True)

        expects = [
            Expect(['path/to/git', 'reset', '--hard', 'abcdef01'],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect([ 'path/to/git', 'rev-parse', 'HEAD' ],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False, keepStdout=True)
                + { 'stdout' : '4026d33b0532b11f36b0875f63699adfa8ee8662\n' }
                + 0,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata, "git://github.com/djmitche/buildbot.git master\n")
        return d

    def test_run_mode_update_existing_unknown_rev(self):
        self.patch_getCommand('git', 'path/to/git')
        self.clean_environ()
        self.make_command(git.Git, dict(
            workdir='workdir',
            mode='update',
            revision='abcdef01',
            repourl='git://github.com/djmitche/buildbot.git',
          ),
            initial_sourcedata = "git://github.com/djmitche/buildbot.git master\n",
        )
        self.patch_sourcedirIsUpdateable(True)

        expects = [
            Expect(['path/to/git', 'reset', '--hard', 'abcdef01'],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False)
                + 1,
            Expect([ 'path/to/git', 'fetch', '-t',
                     'git://github.com/djmitche/buildbot.git', '+master' ],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False, keepStderr=True)
                + { 'stderr' : '' }
                + 0,
            Expect(['path/to/git', 'reset', '--hard', 'abcdef01'],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect(['path/to/git', 'branch', '-M', 'master'],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect([ 'path/to/git', 'rev-parse', 'HEAD' ],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False, keepStdout=True)
                + { 'stdout' : '4026d33b0532b11f36b0875f63699adfa8ee8662\n' }
                + 0,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata, "git://github.com/djmitche/buildbot.git master\n")
        return d

    def test_run_with_reference(self):
        self.patch_getCommand('git', 'path/to/git')
        self.clean_environ()
        self.make_command(git.Git, dict(
            workdir='workdir',
            mode='update',
            revision=None,
            reference='/other/repo',
            repourl='git://github.com/djmitche/buildbot.git',
          ),
            initial_sourcedata = "git://github.com/djmitche/buildbot.git master\n",
        )
        self.patch_sourcedirIsUpdateable(False)

        expects = [
            Expect([ 'clobber', 'workdir' ],
                self.basedir)
                + 0,
            Expect([ 'path/to/git', 'init'],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect([ 'setFileContents',
                     os.path.join(self.basedir_workdir,
                                  *'.git/objects/info/alternates'.split('/')),
                     os.path.join('/other/repo', 'objects'), ],
                self.basedir)
                + 0,
            Expect([ 'path/to/git', 'fetch', '-t',
                     'git://github.com/djmitche/buildbot.git', '+master' ],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False, keepStderr=True)
                + { 'stderr' : '' }
                + 0,
            Expect(['path/to/git', 'reset', '--hard', 'FETCH_HEAD'],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect(['path/to/git', 'branch', '-M', 'master'],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect([ 'path/to/git', 'rev-parse', 'HEAD' ],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False, keepStdout=True)
                + { 'stdout' : '4026d33b0532b11f36b0875f63699adfa8ee8662\n' }
                + 0,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata, "git://github.com/djmitche/buildbot.git master\n")
        return d

    def test_run_with_shallow_and_rev(self):
        self.patch_getCommand('git', 'path/to/git')
        self.clean_environ()
        self.make_command(git.Git, dict(
            workdir='workdir',
            mode='update',
            revision='deadbeef',
            shallow=True,
            repourl='git://github.com/djmitche/buildbot.git',
          ),
            initial_sourcedata = "git://github.com/djmitche/buildbot.git master\n",
        )
        self.patch_sourcedirIsUpdateable(False)

        expects = [
            Expect([ 'clobber', 'workdir' ],
                self.basedir)
                + 0,
            Expect([ 'path/to/git', 'init'],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect(['path/to/git', 'reset', '--hard', 'deadbeef'],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect([ 'path/to/git', 'rev-parse', 'HEAD' ],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False, keepStdout=True)
                + { 'stdout' : '4026d33b0532b11f36b0875f63699adfa8ee8662\n' }
                + 0,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata, "git://github.com/djmitche/buildbot.git master\n")
        return d

    def test_run_with_shallow(self):
        self.patch_getCommand('git', 'path/to/git')
        self.clean_environ()
        self.make_command(git.Git, dict(
            workdir='workdir',
            mode='update',
            revision=None,
            shallow=True,
            repourl='git://github.com/djmitche/buildbot.git',
          ),
            initial_sourcedata = "git://github.com/djmitche/buildbot.git master\n",
        )
        self.patch_sourcedirIsUpdateable(False)

        expects = [
            Expect([ 'clobber', 'workdir' ],
                self.basedir)
                + 0,
            Expect(['path/to/git', 'clone', '--depth', '1',
                    'git://github.com/djmitche/buildbot.git',
                    self.basedir_workdir],
                self.basedir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect([ 'path/to/git', 'fetch', '-t',
                     'git://github.com/djmitche/buildbot.git', '+master' ],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False, keepStderr=True)
                + { 'stderr' : '' }
                + 0,
            Expect(['path/to/git', 'reset', '--hard', 'FETCH_HEAD'],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect(['path/to/git', 'branch', '-M', 'master'],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect([ 'path/to/git', 'rev-parse', 'HEAD' ],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False, keepStdout=True)
                + { 'stdout' : '4026d33b0532b11f36b0875f63699adfa8ee8662\n' }
                + 0,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata, "git://github.com/djmitche/buildbot.git master\n")
        return d

    def test_run_with_shallow_and_reference(self):
        self.patch_getCommand('git', 'path/to/git')
        self.clean_environ()
        self.make_command(git.Git, dict(
            workdir='workdir',
            mode='update',
            revision=None,
            shallow=True,
            reference="/some/repo",
            repourl='git://github.com/djmitche/buildbot.git',
          ),
            initial_sourcedata = "git://github.com/djmitche/buildbot.git master\n",
        )
        self.patch_sourcedirIsUpdateable(False)

        expects = [
            Expect([ 'clobber', 'workdir' ],
                self.basedir)
                + 0,
            Expect(['path/to/git', 'clone', '--depth', '1',
                    '--reference', '/some/repo', # note: no ../objects
                    'git://github.com/djmitche/buildbot.git',
                    self.basedir_workdir],
                self.basedir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect([ 'setFileContents',
                     os.path.join(self.basedir_workdir,
                                  *'.git/objects/info/alternates'.split('/')),
                     os.path.join('/some/repo', 'objects'), ],
                self.basedir)
                + 0,
            Expect([ 'path/to/git', 'fetch', '-t',
                     'git://github.com/djmitche/buildbot.git', '+master' ],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False, keepStderr=True)
                + { 'stderr' : '' }
                + 0,
            Expect(['path/to/git', 'reset', '--hard', 'FETCH_HEAD'],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect(['path/to/git', 'branch', '-M', 'master'],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect([ 'path/to/git', 'rev-parse', 'HEAD' ],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False, keepStdout=True)
                + { 'stdout' : '4026d33b0532b11f36b0875f63699adfa8ee8662\n' }
                + 0,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata, "git://github.com/djmitche/buildbot.git master\n")
        return d

    def test_run_with_submodules(self):
        self.patch_getCommand('git', 'path/to/git')
        self.clean_environ()
        self.make_command(git.Git, dict(
            workdir='workdir',
            mode='update',
            revision=None,
            submodules=True,
            repourl='git://github.com/djmitche/buildbot.git',
          ),
            initial_sourcedata = "git://github.com/djmitche/buildbot.git master\n",
        )
        self.patch_sourcedirIsUpdateable(False)

        expects = [
            Expect([ 'clobber', 'workdir' ],
                self.basedir)
                + 0,
            Expect([ 'path/to/git', 'init'],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect([ 'path/to/git', 'fetch', '-t',
                     'git://github.com/djmitche/buildbot.git', '+master' ],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False, keepStderr=True)
                + { 'stderr' : '' }
                + 0,
            Expect(['path/to/git', 'reset', '--hard', 'FETCH_HEAD'],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect(['path/to/git', 'branch', '-M', 'master'],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect([ 'path/to/git', 'submodule', 'init' ],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect([ 'path/to/git', 'submodule', 'update' ],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect([ 'path/to/git', 'submodule', 'foreach',
                                'git', 'clean', '-f', '-d', '-x'],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect([ 'path/to/git', 'rev-parse', 'HEAD' ],
                self.basedir_workdir,
                sendRC=False, timeout=120, usePTY=False, keepStdout=True)
                + { 'stdout' : '4026d33b0532b11f36b0875f63699adfa8ee8662\n' }
                + 0,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata, "git://github.com/djmitche/buildbot.git master\n")
        return d

    def test_sourcedataMatches_no_file(self):
        self.make_command(git.Git, dict(
            workdir='workdir',
            mode='copy',
            revision=None,
            repourl='git://github.com/djmitche/buildbot.git',
        ), initial_sourcedata=None)
        self.assertFalse(self.cmd.sourcedataMatches())

    def test_sourcedataMatches_ok(self):
        self.make_command(git.Git, dict(
            workdir='workdir',
            mode='copy',
            revision=None,
            repourl='git://github.com/djmitche/buildbot.git',
            # git command doesn't care what the contents of the sourcedata file is
        ), initial_sourcedata='xyz')
        self.assertTrue(self.cmd.sourcedataMatches())

    def do_test_parseGotRevision(self, stdout, exp):
        self.make_command(git.Git, dict(
            workdir='workdir',
            repourl='git://github.com/djmitche/buildbot.git',
        ))
        def _dovccmd(cmd, callback, keepStdout=False):
            self.assertTrue(keepStdout)
            self.cmd.command = mock.Mock()
            self.cmd.command.stdout = stdout
            d = defer.succeed(None)
            d.addCallback(callback)
            return d
        self.cmd._dovccmd = _dovccmd

        d = self.cmd.parseGotRevision()
        def check(res):
            self.assertEqual(res, exp)
        d.addCallback(check)
        return d

    def test_parseGotRevision_bogus(self):
        return self.do_test_parseGotRevision("fatal: Couldn't find revision 1234\n", None)

    def test_parseGotRevision_wrong_length(self):
        return self.do_test_parseGotRevision("\n1234abcd\n", None)

    def test_parseGotRevision_ok(self):
        return self.do_test_parseGotRevision(
                "\n4026d33b0532b11f36b0875f63699adfa8ee8662\n",
                  "4026d33b0532b11f36b0875f63699adfa8ee8662")

    # TODO: gerrit_branch
    # TODO: consolidate Expect objects
    # TODO: ignore_ignores (w/ submodules)
