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

from twisted.internet import error
from twisted.python.reflect import namedModule
from twisted.trial import unittest

from buildbot import config
from buildbot.process import remotetransfer
from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SUCCESS
from buildbot.steps.source import mercurial
from buildbot.test.fake.remotecommand import ExpectDownloadFile
from buildbot.test.fake.remotecommand import ExpectRemoteRef
from buildbot.test.fake.remotecommand import ExpectRmdir
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.fake.remotecommand import ExpectStat
from buildbot.test.util import sourcesteps
from buildbot.test.util.misc import TestReactorMixin


class TestMercurial(sourcesteps.SourceStepMixin, TestReactorMixin,
                    unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        return self.setUpSourceStep()

    def tearDown(self):
        return self.tearDownSourceStep()

    def patch_workerVersionIsOlderThan(self, result):
        self.patch(
            mercurial.Mercurial, 'workerVersionIsOlderThan', lambda x, y, z: result)

    def test_no_repourl(self):
        with self.assertRaises(config.ConfigErrors):
            mercurial.Mercurial(mode="full")

    def test_incorrect_mode(self):
        with self.assertRaises(config.ConfigErrors):
            mercurial.Mercurial(repourl='http://hg.mozilla.org', mode='invalid')

    def test_incorrect_method(self):
        with self.assertRaises(config.ConfigErrors):
            mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                method='invalid')

    def test_incorrect_branchType(self):
        with self.assertRaises(config.ConfigErrors):
            mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                branchType='invalid')

    def test_mode_full_clean(self):
        self.setup_step(
            mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                mode='full', method='clean', branchType='inrepo'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.hg', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--config',
                                 'extensions.purge=', 'purge'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'pull',
                                 'http://hg.mozilla.org', '--rev', 'default'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'identify', '--branch'])
            .stdout('default')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'locate', 'set:added()'])
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'update',
                                 '--clean', '--rev', 'default'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'parents',
                                 '--template', '{node}\\n'])
            .stdout('\n')
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_full_clean_win32path(self):
        self.setup_step(
            mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                mode='full', method='clean', branchType='inrepo'))
        self.build.path_module = namedModule('ntpath')
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--version'])
            .exit(0),
            ExpectStat(file=r'wkdir\.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file=r'wkdir\.hg', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--config',
                                 'extensions.purge=', 'purge'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'pull',
                                 'http://hg.mozilla.org', '--rev', 'default'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'identify', '--branch'])
            .stdout('default')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'locate', 'set:added()'])
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'update',
                                 '--clean', '--rev', 'default'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'parents',
                                 '--template', '{node}\\n'])
            .stdout('\n')
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_full_clean_timeout(self):
        self.setup_step(
            mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                timeout=1,
                                mode='full', method='clean', branchType='inrepo'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['hg', '--verbose', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.hg', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['hg', '--verbose', '--config',
                                 'extensions.purge=', 'purge'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['hg', '--verbose', 'pull',
                                 'http://hg.mozilla.org', '--rev', 'default'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['hg', '--verbose', 'identify', '--branch'])
            .stdout('default')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['hg', '--verbose', 'locate', 'set:added()'])
            .exit(1),
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['hg', '--verbose', 'update',
                                 '--clean', '--rev', 'default'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['hg', '--verbose', 'parents',
                                 '--template', '{node}\\n'])
            .stdout('\n')
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_full_clean_patch(self):
        self.setup_step(
            mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                mode='full', method='clean', branchType='inrepo'),
            patch=(1, 'patch'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(0),
            ExpectStat(file='wkdir/.hg', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--config',
                                 'extensions.purge=', 'purge'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'pull',
                                 'http://hg.mozilla.org', '--rev', 'default'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'identify', '--branch'])
            .stdout('default')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'locate', 'set:added()'])
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'update',
                                 '--clean', '--rev', 'default'])
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest='.buildbot-diff', workdir='wkdir', mode=None)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest='.buildbot-patched', workdir='wkdir', mode=None)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=[
                            'hg', '--verbose', 'import', '--no-commit', '-p', '1', '-'],
                        initialStdin='patch')
            .exit(0),
            ExpectRmdir(dir='wkdir/.buildbot-diff', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'parents',
                                 '--template', '{node}\\n'])
            .stdout('\n')
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_full_clean_patch_worker_2_16(self):
        self.setup_step(
            mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                mode='full', method='clean', branchType='inrepo'),
            patch=(1, 'patch'),
            worker_version={'*': '2.16'})
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(0),
            ExpectStat(file='wkdir/.hg', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--config',
                                 'extensions.purge=', 'purge'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'pull',
                                 'http://hg.mozilla.org', '--rev', 'default'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'identify', '--branch'])
            .stdout('default')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'locate', 'set:added()'])
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'update',
                                 '--clean', '--rev', 'default'])
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               slavedest='.buildbot-diff', workdir='wkdir', mode=None)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               slavedest='.buildbot-patched', workdir='wkdir', mode=None)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=[
                            'hg', '--verbose', 'import', '--no-commit', '-p', '1', '-'],
                        initialStdin='patch')
            .exit(0),
            ExpectRmdir(dir='wkdir/.buildbot-diff', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'parents',
                                 '--template', '{node}\\n'])
            .stdout('\n')
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_full_clean_patch_fail(self):
        self.setup_step(
            mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                mode='full', method='clean', branchType='inrepo'),
            patch=(1, 'patch'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(0),
            ExpectStat(file='wkdir/.hg', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--config',
                                 'extensions.purge=', 'purge'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'pull',
                                 'http://hg.mozilla.org', '--rev', 'default'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'identify', '--branch'])
            .stdout('default')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'locate', 'set:added()'])
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'update',
                                 '--clean', '--rev', 'default'])
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest='.buildbot-diff', workdir='wkdir', mode=None)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest='.buildbot-patched', workdir='wkdir', mode=None)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=[
                            'hg', '--verbose', 'import', '--no-commit', '-p', '1', '-'],
                        initialStdin='patch')
            .exit(1)
        )
        self.expect_outcome(result=FAILURE, state_string="update (failure)")
        return self.run_step()

    def test_mode_full_clean_no_existing_repo(self):
        self.setup_step(
            mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                mode='full', method='clean', branchType='inrepo'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.hg', logEnviron=True)
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'clone', '--noupdate',
                                 'http://hg.mozilla.org', '.'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'update',
                                 '--clean', '--rev', 'default'],
                        logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'parents',
                                 '--template', '{node}\\n'])
            .stdout('\n')
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_full_clobber(self):
        self.setup_step(
            mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                mode='full', method='clobber', branchType='inrepo'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'clone', '--noupdate',
                                 'http://hg.mozilla.org', '.'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'update',
                                 '--clean', '--rev', 'default'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'parents',
                                 '--template', '{node}\\n'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_full_fresh(self):
        self.setup_step(
            mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                mode='full', method='fresh', branchType='inrepo'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.hg', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--config',
                                 'extensions.purge=', 'purge', '--all'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'pull',
                                 'http://hg.mozilla.org', '--rev', 'default'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'identify', '--branch'])
            .stdout('default')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'locate', 'set:added()'])
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'update',
                                 '--clean', '--rev', 'default'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'parents',
                                 '--template', '{node}\\n'])
            .stdout('\n')
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_full_fresh_no_existing_repo(self):
        self.setup_step(
            mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                mode='full', method='fresh', branchType='inrepo'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.hg', logEnviron=True)
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'clone', '--noupdate',
                                 'http://hg.mozilla.org', '.'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'update',
                                 '--clean', '--rev', 'default'],
                        logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'parents',
                                 '--template', '{node}\\n'])
            .stdout('\n')
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_full_fresh_retry(self):
        self.setup_step(
            mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                mode='full', method='fresh', branchType='inrepo',
                                retry=(0, 2)))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.hg', logEnviron=True)
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'clone', '--noupdate',
                                 'http://hg.mozilla.org', '.'])
            .exit(1),
            ExpectRmdir(dir='wkdir', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'clone', '--noupdate',
                                 'http://hg.mozilla.org', '.'])
            .exit(1),
            ExpectRmdir(dir='wkdir', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'clone', '--noupdate',
                                 'http://hg.mozilla.org', '.'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'update',
                                 '--clean', '--rev', 'default'],
                        logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'parents',
                                 '--template', '{node}\\n'])
            .stdout('\n')
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_incremental_no_existing_repo_dirname(self):
        self.setup_step(
            mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                mode='incremental', branchType='dirname'),
        )
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.hg', logEnviron=True)
            .exit(1),  # does not exist
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'clone', '--noupdate',
                                 'http://hg.mozilla.org', '.'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'locate', 'set:added()'])
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'update', '--clean'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'parents',
                                 '--template', '{node}\\n'])
            .stdout('\n')
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_incremental_retry(self):
        self.setup_step(
            mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                mode='incremental', branchType='dirname', retry=(0, 1)),
        )
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.hg', logEnviron=True)
            .exit(1),  # does not exist
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'clone', '--noupdate',
                                 'http://hg.mozilla.org', '.'])
            .exit(1),
            ExpectRmdir(dir='wkdir', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'clone', '--noupdate',
                                 'http://hg.mozilla.org', '.'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'locate', 'set:added()'])
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'update', '--clean'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'parents',
                                 '--template', '{node}\\n'])
            .stdout('\n')
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_incremental_branch_change_dirname(self):
        self.setup_step(
            mercurial.Mercurial(repourl='http://hg.mozilla.org/',
                                mode='incremental', branchType='dirname', defaultBranch='devel'),
            dict(branch='stable')
        )
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.hg', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'pull',
                                 'http://hg.mozilla.org/stable'])
            .exit(0),
            ExpectRmdir(dir='wkdir', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'clone', '--noupdate',
                                 'http://hg.mozilla.org/stable', '.'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'update',
                                 '--clean'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'parents',
                                 '--template', '{node}\\n'])
            .stdout('\n')
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_incremental_no_existing_repo_inrepo(self):
        self.setup_step(
            mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                mode='incremental', branchType='inrepo'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.hg', logEnviron=True)
            .exit(1),  # does not exist
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'clone', '--noupdate',
                                 'http://hg.mozilla.org', '.'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'identify', '--branch'])
            .stdout('default')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'locate', 'set:added()'])
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'update', '--clean',
                                 '--rev', 'default'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'parents',
                                 '--template', '{node}\\n'])
            .stdout('\n')
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_incremental_existing_repo(self):
        self.setup_step(
            mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                mode='incremental', branchType='inrepo'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.hg', logEnviron=True)
            .exit(0),  # directory exists
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'pull',
                                 'http://hg.mozilla.org', '--rev', 'default'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'identify', '--branch'])
            .stdout('default')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'locate', 'set:added()'])
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'update', '--clean',
                                 '--rev', 'default'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'parents',
                                 '--template', '{node}\\n'])
            .stdout('\n')
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_incremental_existing_repo_added_files(self):
        self.setup_step(
            mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                mode='incremental', branchType='inrepo'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.hg', logEnviron=True)
            .exit(0),  # directory exists
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'pull',
                                 'http://hg.mozilla.org', '--rev', 'default'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'identify', '--branch'])
            .stdout('default')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'locate', 'set:added()'])
            .stdout('foo\nbar/baz\n')
            .exit(1),
            ExpectRmdir(dir=['wkdir/foo', 'wkdir/bar/baz'], logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'update', '--clean',
                                 '--rev', 'default'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'parents',
                                 '--template', '{node}\\n'])
            .stdout('\n')
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_incremental_existing_repo_added_files_old_rmdir(self):
        self.setup_step(
            mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                mode='incremental', branchType='inrepo'))
        self.patch_workerVersionIsOlderThan(True)
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.hg', logEnviron=True)
            .exit(0),  # directory exists
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'pull',
                                 'http://hg.mozilla.org', '--rev', 'default'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'identify', '--branch'])
            .stdout('default')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'locate', 'set:added()'])
            .stdout('foo\nbar/baz\n')
            .exit(1),
            ExpectRmdir(dir='wkdir/foo', logEnviron=True)
            .exit(0),
            ExpectRmdir(dir='wkdir/bar/baz', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'update', '--clean',
                                 '--rev', 'default'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'parents',
                                 '--template', '{node}\\n'])
            .stdout('\n')
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_incremental_given_revision(self):
        self.setup_step(
            mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                mode='incremental', branchType='inrepo'), dict(
                revision='abcdef01',
            ))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.hg', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'pull',
                                 'http://hg.mozilla.org', '--rev', 'abcdef01'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'identify', '--branch'])
            .stdout('default')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'locate', 'set:added()'])
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'update', '--clean',
                                 '--rev', 'abcdef01'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'parents',
                                 '--template', '{node}\\n'])
            .stdout('\n')
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_incremental_branch_change(self):
        self.setup_step(
            mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                mode='incremental', branchType='inrepo'), dict(
                branch='stable',
            ))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.hg', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'pull',
                                 'http://hg.mozilla.org', '--rev', 'stable'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'identify', '--branch'])
            .stdout('default')
            .exit(0),
            ExpectRmdir(dir='wkdir', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'clone', '--noupdate',
                                 'http://hg.mozilla.org', '.'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'update',
                                 '--clean', '--rev', 'stable'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'parents',
                                 '--template', '{node}\\n'])
            .stdout('\n')
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_incremental_branch_change_no_clobberOnBranchChange(self):
        self.setup_step(
            mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                mode='incremental', branchType='inrepo',
                                clobberOnBranchChange=False), dict(
                branch='stable',
            ))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.hg', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'pull',
                                 'http://hg.mozilla.org', '--rev', 'stable'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'identify', '--branch'])
            .stdout('default')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'locate', 'set:added()'])
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'update',
                                 '--clean', '--rev', 'stable'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'parents',
                                 '--template', '{node}\\n'])
            .stdout('\n')
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_full_clean_env(self):
        self.setup_step(
            mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                mode='full', method='clean', branchType='inrepo',
                                env={'abc': '123'}))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--version'], env={'abc': '123'})
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.hg', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--config',
                                 'extensions.purge=', 'purge'], env={'abc': '123'})
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'pull',
                                 'http://hg.mozilla.org', '--rev', 'default'], env={'abc': '123'})
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'identify', '--branch'],
                        env={'abc': '123'})
            .stdout('default')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'locate', 'set:added()'],
                        env={'abc': '123'})
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'update', '--clean',
                                 '--rev', 'default'], env={'abc': '123'})
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'parents',
                                 '--template', '{node}\\n'], env={'abc': '123'})
            .stdout('\n')
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_full_clean_logEnviron(self):
        self.setup_step(
            mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                mode='full', method='clean',
                                branchType='inrepo',
                                logEnviron=False))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--version'],
                        logEnviron=False)
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=False)
            .exit(1),
            ExpectStat(file='wkdir/.hg', logEnviron=False)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--config',
                                 'extensions.purge=', 'purge'],
                        logEnviron=False)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'pull',
                                 'http://hg.mozilla.org', '--rev', 'default'],
                        logEnviron=False)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'identify', '--branch'],
                        logEnviron=False)
            .stdout('default')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'locate', 'set:added()'],
                        logEnviron=False)
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'update',
                                 '--clean', '--rev', 'default'],
                        logEnviron=False)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', 'parents',
                                 '--template', '{node}\\n'],
                        logEnviron=False)
            .stdout('\n')
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_command_fails(self):
        self.setup_step(
            mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                mode='full', method='fresh', branchType='inrepo'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--version'])
            .exit(1)
        )
        self.expect_outcome(result=FAILURE)
        return self.run_step()

    def test_worker_connection_lost(self):
        self.setup_step(
            mercurial.Mercurial(repourl='http://hg.mozilla.org',
                                mode='full', method='clean', branchType='inrepo'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['hg', '--verbose', '--version'])
            .error(error.ConnectionLost())
        )
        self.expect_outcome(result=RETRY, state_string="update (retry)")
        return self.run_step()
