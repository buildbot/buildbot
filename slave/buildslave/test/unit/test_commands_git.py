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

from twisted.trial import unittest

from buildslave.test.fake.runprocess import Expect
from buildslave.test.util.sourcecommand import SourceCommandTestMixin
from buildslave.commands import git

class TestGit(SourceCommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    def test_simple(self):
        self.patch_getCommand('git', 'path/to/git')
        self.clean_environ()
        self.make_command(git.Git, dict(
            workdir='workdir',
            mode='copy',
            revision=None,
            repourl='git://github.com/djmitche/buildbot.git',
        ))

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
            Expect([ 'path/to/git', 'clean', '-f', '-d', '-x'],
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


    # test a copy where the sourcedata indicates that the source directory can
    # be updated
    def test_copy_update_sourcedir(self):
        self.patch_getCommand('git', 'path/to/git')
        self.clean_environ()
        self.make_command(git.Git, dict(
            workdir='workdir',
            mode='copy',
            revision=None,
            repourl='git://github.com/djmitche/buildbot.git',
          ),
            initial_sourcedata = "git://github.com/djmitche/buildbot.git master\n",
        )

        # monkey-patch sourcedirIsUpdateable to think that it is updatable
        def sourcedirIsUpdateable():
            return True
        self.patch(self.cmd, "sourcedirIsUpdateable", sourcedirIsUpdateable)

        expects = [
            Expect([ 'clobber', 'workdir' ],
                self.basedir)
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

    def test_nonexistant_ref(self):
        self.patch_getCommand('git', 'path/to/git')
        self.clean_environ()
        self.make_command(git.Git, dict(
            workdir='workdir',
            mode='copy',
            revision=None,
            repourl='git://github.com/djmitche/buildbot.git',
        ))

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
            Expect([ 'path/to/git', 'clean', '-f', '-d', '-x'],
                self.basedir_source,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect([ 'path/to/git', 'fetch', '-t',
                     'git://github.com/djmitche/buildbot.git', '+master' ],
                self.basedir_source,
                sendRC=False, timeout=120, usePTY=False, keepStderr=True)
                + { 'stderr' : "fatal: Couldn't find remote ref master\n" }
                + { 'rc': 128 }
                + 128,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        return d

