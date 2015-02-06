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
from buildbot.steps.source import mercurial
from buildbot.status.results import SUCCESS, FAILURE
from buildbot.test.util import sourcesteps
from buildbot.test.fake.remotecommand import ExpectShell, Expect
from buildbot import config
from twisted.internet import defer
from mock import Mock
from buildbot.process import buildstep

class TestMercurial(sourcesteps.SourceStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpSourceStep()

    def tearDown(self):
        return self.tearDownSourceStep()

    def patch_slaveVersionIsOlderThan(self, result):
        self.patch(mercurial.Mercurial, 'slaveVersionIsOlderThan', lambda x, y, z: result)

    def test_no_repourl(self):
        self.assertRaises(config.ConfigErrors, lambda :
                mercurial.Mercurial(mode="full"))

    def test_incorrect_mode(self):
        self.assertRaises(config.ConfigErrors, lambda :
                mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                    mode='invalid'))

    def test_incorrect_method(self):
        self.assertRaises(config.ConfigErrors, lambda :
                mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                    method='invalid'))

    def test_incorrect_branchType(self):
        self.assertRaises(config.ConfigErrors, lambda :
                mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                    branchType='invalid'))

    def test_mode_full_clean(self):
        self.setupStep(
                mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                    mode='full', method='clean', branchType='inrepo'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.hg/store/journal',
                                logEnviron=True))
            + 0,
            Expect('stat', dict(file='wkdir/.hg/store/lock',
                                logEnviron=True))
            + 0,
            Expect('stat', dict(file='wkdir/.hg/wlock',
                                logEnviron=True))
            + 0,
            Expect('rmdir', dict(dir='wkdir/.hg',
                                      logEnviron=True))
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                      logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'clone', '--uncompressed', '--noupdate',
                                 'http://hg.mozilla.org', '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'update',
                                 '--clean', '--rev', 'default'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'parents',
                                    '--template', '{node}\\n'])
            + ExpectShell.log('stdio', stdout='\n')
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_clean_timeout(self):
        self.setupStep(
                mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                    timeout=1,
                                    mode='full', method='clean', branchType='inrepo'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['hg', '--traceback', '--version'])
            + 0,
                        Expect('stat', dict(file='wkdir/.hg/store/journal',
                                logEnviron=True))
            + 0,
            Expect('stat', dict(file='wkdir/.hg/store/lock',
                                logEnviron=True))
            + 0,
            Expect('stat', dict(file='wkdir/.hg/wlock',
                                logEnviron=True))
            + 0,
            Expect('rmdir', dict(dir='wkdir/.hg',
                                      logEnviron=True))
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                      logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['hg', '--traceback', 'clone', '--uncompressed', '--noupdate',
                                 'http://hg.mozilla.org', '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['hg', '--traceback', 'update',
                                 '--clean', '--rev', 'default'])
            + 0,
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['hg', '--traceback', 'parents',
                                    '--template', '{node}\\n'])
            + ExpectShell.log('stdio', stdout='\n')
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_clean_patch(self):
        self.setupStep(
                mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                    mode='full', method='clean', branchType='inrepo'),
                patch=(1, 'patch'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.hg/store/journal',
                                logEnviron=True))
            + 0,
            Expect('stat', dict(file='wkdir/.hg/store/lock',
                                logEnviron=True))
            + 0,
            Expect('stat', dict(file='wkdir/.hg/wlock',
                                logEnviron=True))
            + 0,
            Expect('rmdir', dict(dir='wkdir/.hg',
                                      logEnviron=True))
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                      logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'clone', '--uncompressed', '--noupdate',
                                 'http://hg.mozilla.org', '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'update',
                                 '--clean', '--rev', 'default'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'import',
                                 '--no-commit', '-p', '1', '-'],
                        initialStdin='patch')
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'parents',
                                    '--template', '{node}\\n'])
            + ExpectShell.log('stdio', stdout='\n')
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()
    
    def test_mode_full_clean_patch_fail(self):
        self.setupStep(
                mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                    mode='full', method='clean', branchType='inrepo'),
                patch=(1, 'patch'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.hg/store/journal',
                                logEnviron=True))
            + 0,
            Expect('stat', dict(file='wkdir/.hg/store/lock',
                                logEnviron=True))
            + 0,
            Expect('stat', dict(file='wkdir/.hg/wlock',
                                      logEnviron=True))
            + 0,
            Expect('rmdir', dict(dir='wkdir/.hg',
                                      logEnviron=True))
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                      logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'clone', '--uncompressed', '--noupdate',
                                 'http://hg.mozilla.org', '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'update',
                                 '--clean', '--rev', 'default'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'import',
                                 '--no-commit', '-p', '1', '-'],
                        initialStdin='patch')
            + 1,
        )
        self.expectOutcome(result=FAILURE, status_text=["updating"])
        return self.runStep()

    def test_mode_full_clean_no_existing_repo(self):
        self.setupStep(
                mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                    mode='full', method='clean', branchType='inrepo'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.hg/store/journal',
                                logEnviron=True))
            + 0,
            Expect('stat', dict(file='wkdir/.hg/store/lock',
                                logEnviron=True))
            + 0,
            Expect('stat', dict(file='wkdir/.hg/wlock',
                                logEnviron=True))
            + 0,
            Expect('rmdir', dict(dir='wkdir/.hg',
                                      logEnviron=True))
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                      logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'clone', '--uncompressed', '--noupdate',
                                 'http://hg.mozilla.org', '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'update',
                                 '--clean', '--rev', 'default'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'parents',
                                    '--template', '{node}\\n'])
            + ExpectShell.log('stdio', stdout='\n')
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_clobber(self):
        self.setupStep(
                mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                    mode='full', method='clobber', branchType='inrepo'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', '--version'])
            + 0,
            Expect('rmdir', dict(dir='wkdir/.hg',
                                      logEnviron=True))
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'clone', '--uncompressed', '--noupdate',
                                    'http://hg.mozilla.org', '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'update',
                                 '--clean', '--rev', 'default'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'parents',
                                    '--template', '{node}\\n'])
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_fresh(self):
        self.setupStep(
                mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                    mode='full', method='fresh', branchType='inrepo'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.hg/store/journal',
                                logEnviron=True))
            + 0,
            Expect('stat', dict(file='wkdir/.hg/store/lock',
                                logEnviron=True))
            + 0,
            Expect('stat', dict(file='wkdir/.hg/wlock',
                                logEnviron=True))
            + 0,
            Expect('rmdir', dict(dir='wkdir/.hg',
                                      logEnviron=True))
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                      logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'clone', '--uncompressed', '--noupdate',
                                 'http://hg.mozilla.org', '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'update',
                                 '--clean', '--rev', 'default'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'parents',
                                    '--template', '{node}\\n'])
            + ExpectShell.log('stdio', stdout='\n')
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_fresh_no_existing_repo(self):
        self.setupStep(
                mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                    mode='full', method='fresh', branchType='inrepo'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', '--version'])
            + 0,
                        Expect('stat', dict(file='wkdir/.hg/store/journal',
                                logEnviron=True))
            + 0,
            Expect('stat', dict(file='wkdir/.hg/store/lock',
                                logEnviron=True))
            + 0,
            Expect('stat', dict(file='wkdir/.hg/wlock',
                                logEnviron=True))
            + 0,
            Expect('rmdir', dict(dir='wkdir/.hg',
                                      logEnviron=True))
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                      logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'clone', '--uncompressed', '--noupdate',
                                 'http://hg.mozilla.org', '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'update',
                                 '--clean', '--rev', 'default'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'parents',
                                    '--template', '{node}\\n'])
            + ExpectShell.log('stdio', stdout='\n')
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_incremental_no_existing_repo_dirname(self):
        self.setupStep(
                mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                    mode='incremental', branchType='dirname'),
            )
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.hg/hgrc',
                                logEnviron=True))
            + 1, # does not exist
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'clone', '--uncompressed',
                                 'http://hg.mozilla.org', '.', '--noupdate'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'locate', 'set:added()'])
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'update', '--clean'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'parents',
                                    '--template', '{node}\\n'])
            + ExpectShell.log('stdio', stdout='\n')
            + ExpectShell.log('stdio', 
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
            )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()


    def test_mode_incremental_branch_change_dirname(self):
        self.setupStep(
                mercurial.Mercurial(repourl='http://hg.mozilla.org/',
                                    mode='incremental', branchType='dirname', defaultBranch='devel'),
            dict(branch='stable')
            )
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.hg/hgrc',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'pull',
                                 'http://hg.mozilla.org/stable'])
            + 0,
            Expect('rmdir', dict(dir='wkdir/.hg',
                                      logEnviron=True))
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'clone', '--uncompressed', '--noupdate',
                                    'http://hg.mozilla.org/stable', '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'update',
                                 '--clean'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'parents',
                                    '--template', '{node}\\n'])
            + ExpectShell.log('stdio', stdout='\n')
            + ExpectShell.log('stdio', 
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
            )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_incremental_no_existing_repo_inrepo(self):
        self.setupStep(
                mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                    mode='incremental', branchType='inrepo'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.hg/hgrc',
                                logEnviron=True))
            + 1, # does not exist
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'clone', '--uncompressed',
                                 'http://hg.mozilla.org', '.', '--noupdate'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'identify', '--branch'])
            + ExpectShell.log('stdio', stdout='default')
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'locate', 'set:added()'])
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'update', '--clean',
                                 '--rev', 'default'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'parents',
                                    '--template', '{node}\\n'])
            + ExpectShell.log('stdio', stdout='\n')
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
            )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_incremental_existing_repo(self):
        self.setupStep(
                mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                    mode='incremental', branchType='inrepo'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.hg/hgrc',
                                logEnviron=True))
            + 0, # directory exists
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'pull',
                                 'http://hg.mozilla.org'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'identify', '--branch'])
            + ExpectShell.log('stdio', stdout='default')
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'locate', 'set:added()'])
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'update', '--clean',
                                 '--rev', 'default'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'parents',
                                    '--template', '{node}\\n'])
            + ExpectShell.log('stdio', stdout='\n')
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
            )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_incremental_existing_repo_added_files(self):
        self.setupStep(
                mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                    mode='incremental', branchType='inrepo'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.hg/hgrc',
                                logEnviron=True))
            + 0, # directory exists
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'pull',
                                 'http://hg.mozilla.org'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'identify', '--branch'])
            + ExpectShell.log('stdio', stdout='default')
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'locate', 'set:added()'])
            + ExpectShell.log('stdio', stdout='foo\nbar/baz\n')
            + 1,
            Expect('rmdir', dict(dir=['wkdir/foo','wkdir/bar/baz'],
                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'update', '--clean',
                                 '--rev', 'default'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'parents',
                                    '--template', '{node}\\n'])
            + ExpectShell.log('stdio', stdout='\n')
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
            )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()
    
    def test_mode_incremental_existing_repo_added_files_old_rmdir(self):
        self.setupStep(
                mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                    mode='incremental', branchType='inrepo'))
        self.patch_slaveVersionIsOlderThan(True)
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.hg/hgrc',
                                logEnviron=True))
            + 0, # directory exists
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'pull',
                                 'http://hg.mozilla.org'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'identify', '--branch'])
            + ExpectShell.log('stdio', stdout='default')
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'locate', 'set:added()'])
            + ExpectShell.log('stdio', stdout='foo\nbar/baz\n')
            + 1,
            Expect('rmdir', dict(dir='wkdir/foo',
                logEnviron=True))
            + 0,
            Expect('rmdir', dict(dir='wkdir/bar/baz',
                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'update', '--clean',
                                 '--rev', 'default'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'parents',
                                    '--template', '{node}\\n'])
            + ExpectShell.log('stdio', stdout='\n')
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
            )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_incremental_given_revision(self):
        self.setupStep(
                mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                    mode='incremental', branchType='inrepo'), dict(
                revision='abcdef01',
                ))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.hg/hgrc',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'pull',
                                 'http://hg.mozilla.org'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'identify', '--branch'])
            + ExpectShell.log('stdio', stdout='default')
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'locate', 'set:added()'])
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'update', '--clean',
                                 '--rev', 'abcdef01'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'parents',
                                    '--template', '{node}\\n'])
            + ExpectShell.log('stdio', stdout='\n')
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
            )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_incremental_branch_change(self):
        self.setupStep(
                mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                    mode='incremental', branchType='inrepo'), dict(
                branch='stable',
                ))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.hg/hgrc',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'pull',
                                 'http://hg.mozilla.org'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'identify', '--branch'])
            + ExpectShell.log('stdio', stdout='default')
            + 0,
            Expect('rmdir', dict(dir='wkdir/.hg',
                                      logEnviron=True))
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'clone', '--uncompressed', '--noupdate',
                                    'http://hg.mozilla.org', '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'update',
                                 '--clean', '--rev', 'stable'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'parents',
                                    '--template', '{node}\\n'])
            + ExpectShell.log('stdio', stdout='\n')
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
            )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_incremental_branch_change_no_clobberOnBranchChange(self):
        self.setupStep(
                mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                    mode='incremental', branchType='inrepo',
                                    clobberOnBranchChange=False), dict(
                branch='stable',
                ))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.hg/hgrc',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'pull',
                                 'http://hg.mozilla.org'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'identify', '--branch'])
            + ExpectShell.log('stdio', stdout='default')
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'locate', 'set:added()'])
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'update',
                                 '--clean', '--rev', 'stable'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'parents',
                                    '--template', '{node}\\n'])
            + ExpectShell.log('stdio', stdout='\n')
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
            )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_clean_env(self):
        self.setupStep(
                mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                    mode='full', method='clean', branchType='inrepo',
                                    env={'abc': '123'}))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', '--version'], env={'abc': '123'})
            + 0,
            Expect('stat', dict(file='wkdir/.hg/store/journal',
                                logEnviron=True))
            + 0,
            Expect('stat', dict(file='wkdir/.hg/store/lock',
                                logEnviron=True))
            + 0,
            Expect('stat', dict(file='wkdir/.hg/wlock',
                                logEnviron=True))
            + 0,
            Expect('rmdir', dict(dir='wkdir/.hg',
                                      logEnviron=True))
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                      logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'clone', '--uncompressed', '--noupdate',
                                 'http://hg.mozilla.org', '.'], env={'abc': '123'})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'update',
                                 '--clean', '--rev', 'default'], env={'abc': '123'})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'parents',
                                    '--template', '{node}\\n'], env={'abc': '123'})
            + ExpectShell.log('stdio', stdout='\n')
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_clean_logEnviron(self):
        self.setupStep(
                mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                    mode='full', method='clean',
                                    branchType='inrepo',
                                    logEnviron=False))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', '--version'],
                        logEnviron=False)
            + 0,
            Expect('stat', dict(file='wkdir/.hg/store/journal',
                    logEnviron=False))
            + 0,
            Expect('stat', dict(file='wkdir/.hg/store/lock',
                                logEnviron=False))
            + 0,
            Expect('stat', dict(file='wkdir/.hg/wlock',
                                logEnviron=False))
            + 0,
            Expect('rmdir', dict(dir='wkdir/.hg',
                                      logEnviron=False))
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                      logEnviron=False))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'clone', '--uncompressed', '--noupdate',
                                 'http://hg.mozilla.org', '.'],
                        logEnviron=False)
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'update',
                                 '--clean', '--rev', 'default'],
                        logEnviron=False)
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', 'parents',
                                    '--template', '{node}\\n'],
                        logEnviron=False)
            + ExpectShell.log('stdio', stdout='\n')
            + ExpectShell.log('stdio',
                stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_command_fails(self):
        self.setupStep(
                mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                    mode='full', method='fresh', branchType='inrepo'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--traceback', '--version'])
            + 1,
        )
        self.expectOutcome(result=FAILURE, status_text=["updating"])
        return self.runStep()

    def runCommand(self, c):
        for cmd in self.expected_commands:
            if cmd['command'] == [c.remote_command, c.args]:
                self.currentCommandRC = cmd['rc']
                return defer.succeed(cmd['rc'])

        return -1

    def checkDidFail(self):
        return self.currentCommandRC != 0

    def clobber(self, _):
        self.clobberRepository = True
        defer.succeed(None)

    def mockStatCommand(self, file, rc):
        return {'command': ['stat', {'logEnviron': True, 'file': file}],
                 'rc': rc}

    @defer.inlineCallbacks
    def test_mercurial_clobberIfContainsJournal(self):
        step = mercurial.Mercurial(repourl='http://hg.mozilla.org', mode='full', method='fresh', branchType='inrepo',
                          clobberOnBranchChange=False)

        step.workdir = "build"
        step.stdio_log = Mock()
        step.runCommand = self.runCommand
        self.currentCommandRC = -1
        self.clobberRepository = False

        self.patch(buildstep.RemoteCommand, "didFail", self.checkDidFail)

        self.expected_commands = [self.mockStatCommand('build/.hg/store/journal', 0)]
        self.expected_commands.append(self.mockStatCommand('build/.hg/store/lock', 1))
        self.expected_commands.append(self.mockStatCommand('build/.hg/wlock', 1))

        step.clobber = self.clobber

        yield step.full()

        self.assertTrue(self.clobberRepository)
