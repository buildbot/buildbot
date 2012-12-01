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
from buildbot.steps.source import git
from buildbot.status.results import SUCCESS, FAILURE
from buildbot.test.util import sourcesteps
from buildbot.test.fake.remotecommand import ExpectShell, Expect

class TestGit(sourcesteps.SourceStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpSourceStep()

    def tearDown(self):
        return self.tearDownSourceStep()

    def test_mode_full_clean(self):
        self.setupStep(
                git.Git(repourl='http://github.com/buildbot/buildbot.git',
                                    mode='full', method='clean'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.git',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-d'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_clean_patch(self):
        self.setupStep(
                git.Git(repourl='http://github.com/buildbot/buildbot.git',
                                    mode='full', method='clean'),
                patch = 'patch')
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.git',
                                      logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-d'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'apply', '--index'],
                        initial_stdin='patch')
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_clean_patch_fail(self):
        self.setupStep(
                git.Git(repourl='http://github.com/buildbot/buildbot.git',
                                    mode='full', method='clean'),
                patch = 'patch')
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.git',
                                      logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-d'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'apply', '--index'],
                        initial_stdin='patch')
            + 1,
        )
        self.expectOutcome(result=FAILURE, status_text=["updating"])
        return self.runStep()

    def test_mode_full_clean_branch(self):
        self.setupStep(
                git.Git(repourl='http://github.com/buildbot/buildbot.git',
                                    mode='full', method='clean', branch='test-branch'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.git',
                                      logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-d'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'test-branch'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'branch', '-M', 'test-branch'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_clean_parsefail(self):
        self.setupStep(
                git.Git(repourl='http://github.com/buildbot/buildbot.git',
                                    mode='full', method='clean'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.git',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-d'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD'])
            + ExpectShell.log('stdio',
                stderr="fatal: Could not parse object " 
                    "'b08076bc71c7813038f2cefedff9c5b678d225a8'.\n")
            + 128,
        )
        self.expectOutcome(result=FAILURE, status_text=["updating"])
        return self.runStep()

    def test_mode_full_clean_no_existing_repo(self):
        self.setupStep(
                git.Git(repourl='http://github.com/buildbot/buildbot.git',
                                    mode='full', method='clean'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + 0,

            Expect('stat', dict(file='wkdir/.git',
                                logEnviron=True))
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 '--branch', 'HEAD',
                                 'http://github.com/buildbot/buildbot.git', '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_clean_no_existing_repo_branch(self):
        self.setupStep(
                git.Git(repourl='http://github.com/buildbot/buildbot.git',
                                    mode='full', method='clean', branch='test-branch'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + 0,

            Expect('stat', dict(file='wkdir/.git',
                                      logEnviron=True))
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 '--branch', 'test-branch',
                                 'http://github.com/buildbot/buildbot.git', '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_clobber(self):
        self.setupStep(
                git.Git(repourl='http://github.com/buildbot/buildbot.git',
                        mode='full', method='clobber', progress=True))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 '--branch', 'HEAD',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_clobber_branch(self):
        self.setupStep(
                git.Git(repourl='http://github.com/buildbot/buildbot.git',
                        mode='full', method='clobber', progress=True, branch='test-branch'))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                       logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 '--branch', 'test-branch',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_incremental(self):
        self.setupStep(
                git.Git(repourl='http://github.com/buildbot/buildbot.git',
                                    mode='incremental'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.git',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,

        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_incremental_branch(self):
        self.setupStep(
                git.Git(repourl='http://github.com/buildbot/buildbot.git',
                                    mode='incremental', branch='test-branch'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.git',
                                      logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'test-branch'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'branch', '-M', 'test-branch'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,

        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_fresh(self):
        self.setupStep(
                git.Git(repourl='http://github.com/buildbot/buildbot.git',
                                    mode='full', method='fresh'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.git',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-d', '-x'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_incremental_given_revision(self):
        self.setupStep(
                git.Git(repourl='http://github.com/buildbot/buildbot.git',
                                    mode='incremental'), dict(
                revision='abcdef01',
                ))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.git',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'cat-file', '-e', 'abcdef01'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'abcdef01'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_fresh_submodule(self):
        self.setupStep(
                git.Git(repourl='http://github.com/buildbot/buildbot.git',
                                    mode='full', method='fresh', submodules=True))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.git',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-d', '-x'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'submodule', 'update', '--recursive'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'submodule', 'foreach', 'git', 'clean',
                                 '-f', '-d', '-x'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_clobber_shallow(self):
        self.setupStep(
                git.Git(repourl='http://github.com/buildbot/buildbot.git',
                        mode='full', method='clobber', shallow=True))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone', '--depth', '1',
                                 '--branch', 'HEAD',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_incremental_retryFetch(self):
        self.setupStep(
                git.Git(repourl='http://github.com/buildbot/buildbot.git',
                        mode='incremental', retryFetch=True))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.git',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD'])
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_incremental_retryFetch_branch(self):
        self.setupStep(
                git.Git(repourl='http://github.com/buildbot/buildbot.git',
                        mode='incremental', retryFetch=True, branch='test-branch'))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.git',
                                      logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'test-branch'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD'])
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'test-branch'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'branch', '-M', 'test-branch'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_incremental_clobberOnFailure(self):
        self.setupStep(
                git.Git(repourl='http://github.com/buildbot/buildbot.git',
                        mode='incremental', clobberOnFailure=True))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.git',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD'])
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                       logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 '--branch', 'HEAD',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_incremental_clobberOnFailure_branch(self):
        self.setupStep(
                git.Git(repourl='http://github.com/buildbot/buildbot.git',
                        mode='incremental', clobberOnFailure=True, branch = 'test-branch'))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.git',
                                      logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'test-branch'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD'])
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 '--branch', 'test-branch',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_copy(self):
        self.setupStep(
                git.Git(repourl='http://github.com/buildbot/buildbot.git',
                        mode='full', method='copy', shallow=True))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True)),
            Expect('stat', dict(file='source/.git',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='source',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='source',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD'])
            + 0,
            Expect('cpdir', {'fromdir': 'source', 'todir': 'build',
                             'logEnviron': True})
            + 0,
            ExpectShell(workdir='build',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()


    def test_mode_incremental_no_existing_repo(self):
        self.setupStep(
                git.Git(repourl='http://github.com/buildbot/buildbot.git',
                                    mode='incremental'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.git',
                                logEnviron=True))
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 '--branch', 'HEAD',
                                 'http://github.com/buildbot/buildbot.git', '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,

        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_clobber_given_revision(self):
        self.setupStep(
                git.Git(repourl='http://github.com/buildbot/buildbot.git',
                        mode='full', method='clobber', progress=True), dict(
                revision='abcdef01',
                ))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 '--branch', 'HEAD',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'abcdef01'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_revparse_failure(self):
        self.setupStep(
                git.Git(repourl='http://github.com/buildbot/buildbot.git',
                        mode='full', method='clobber', progress=True), dict(
                revision='abcdef01',
                ))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 '--branch', 'HEAD',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'abcdef01'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                stdout='f6ada95a1d') # too short
            + 0,
        )
        self.expectOutcome(result=FAILURE, status_text=["updating"])
        return self.runStep()

    def test_mode_full_clobber_submodule(self):
        self.setupStep(
                git.Git(repourl='http://github.com/buildbot/buildbot.git',
                        mode='full', method='clobber', submodules=True))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 '--branch', 'HEAD',
                                 'http://github.com/buildbot/buildbot.git', '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'submodule', 'update',
                                 '--init', '--recursive'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_repourl(self):
        self.assertRaises(AssertionError, lambda :
                git.Git(mode="full"))

    def test_mode_full_fresh_revision(self):
        self.setupStep(
                git.Git(repourl='http://github.com/buildbot/buildbot.git',
                        mode='full', method='fresh', progress=True), dict(
                revision='abcdef01',
                ))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.git',
                                logEnviron=True))
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 '--branch', 'HEAD',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'abcdef01'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_fresh_clobberOnFailure(self):
        self.setupStep(
                git.Git(repourl='http://github.com/buildbot/buildbot.git',
                        mode='full', method='fresh', clobberOnFailure=True))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.git',
                                logEnviron=True))
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 '--branch', 'HEAD',
                                 'http://github.com/buildbot/buildbot.git', '.'])
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone', 
                                 '--branch', 'HEAD',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_no_method(self):
        self.setupStep(
                git.Git(repourl='http://github.com/buildbot/buildbot.git',
                                    mode='full'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.git',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-d', '-x'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_with_env(self):
        self.setupStep(
                git.Git(repourl='http://github.com/buildbot/buildbot.git',
                        mode='full', env={'abc': '123'}))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'],
                        env={'abc': '123'})
            + 0,
            Expect('stat', dict(file='wkdir/.git',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-d', '-x'],
                        env={'abc': '123'})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'],
                        env={'abc': '123'})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD'],
                        env={'abc': '123'})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'],
                        env={'abc': '123'})
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_logEnviron(self):
        self.setupStep(
                git.Git(repourl='http://github.com/buildbot/buildbot.git',
                        mode='full', logEnviron=False))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'],
                        logEnviron=False)
            + 0,
            Expect('stat', dict(file='wkdir/.git',
                                logEnviron=False))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-d', '-x'],
                        logEnviron=False)
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'],
                        logEnviron=False)
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD'],
                        logEnviron=False)
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'],
                        logEnviron=False)
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()
