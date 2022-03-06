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
from twisted.trial import unittest

from buildbot import config
from buildbot.process import remotetransfer
from buildbot.process.results import RETRY
from buildbot.process.results import SUCCESS
from buildbot.steps.source import darcs
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import ExpectCpdir
from buildbot.test.steps import ExpectDownloadFile
from buildbot.test.steps import ExpectRemoteRef
from buildbot.test.steps import ExpectRmdir
from buildbot.test.steps import ExpectShell
from buildbot.test.steps import ExpectStat
from buildbot.test.util import sourcesteps


class TestDarcs(sourcesteps.SourceStepMixin, TestReactorMixin,
                unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setUpSourceStep()

    def tearDown(self):
        return self.tearDownSourceStep()

    def test_no_empty_step_config(self):
        with self.assertRaises(config.ConfigErrors):
            darcs.Darcs()

    def test_incorrect_method(self):
        with self.assertRaises(config.ConfigErrors):
            darcs.Darcs(repourl='http://localhost/darcs', mode='full',
                        method='fresh')

    def test_incremental_invalid_method(self):
        with self.assertRaises(config.ConfigErrors):
            darcs.Darcs(repourl='http://localhost/darcs', mode='incremental',
                        method='fresh')

    def test_no_repo_url(self):
        with self.assertRaises(config.ConfigErrors):
            darcs.Darcs(mode='full', method='fresh')

    def test_mode_full_clobber(self):
        self.setup_step(
            darcs.Darcs(repourl='http://localhost/darcs',
                        mode='full', method='clobber'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['darcs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True)
            .exit(0),
            ExpectShell(workdir='.',
                        command=['darcs', 'get', '--verbose', '--lazy',
                                 '--repo-name', 'wkdir', 'http://localhost/darcs'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['darcs', 'changes', '--max-count=1'])
            .stdout('Tue Aug 20 09:18:41 IST 2013 abc@gmail.com')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'Tue Aug 20 09:18:41 IST 2013 abc@gmail.com', 'Darcs')
        return self.run_step()

    def test_mode_full_copy(self):
        self.setup_step(
            darcs.Darcs(repourl='http://localhost/darcs',
                        mode='full', method='copy'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['darcs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200)
            .exit(0),
            ExpectStat(file='source/_darcs', log_environ=True)
            .exit(0),
            ExpectShell(workdir='source',
                        command=['darcs', 'pull', '--all', '--verbose'])
            .exit(0),
            ExpectCpdir(fromdir='source', todir='build', log_environ=True, timeout=1200)
            .exit(0),
            ExpectShell(workdir='build',
                        command=['darcs', 'changes', '--max-count=1'])
            .stdout('Tue Aug 20 09:18:41 IST 2013 abc@gmail.com')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'Tue Aug 20 09:18:41 IST 2013 abc@gmail.com', 'Darcs')
        return self.run_step()

    def test_mode_full_no_method(self):
        self.setup_step(
            darcs.Darcs(repourl='http://localhost/darcs',
                        mode='full'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['darcs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200)
            .exit(0),
            ExpectStat(file='source/_darcs', log_environ=True)
            .exit(0),
            ExpectShell(workdir='source',
                        command=['darcs', 'pull', '--all', '--verbose'])
            .exit(0),
            ExpectCpdir(fromdir='source', todir='build', log_environ=True, timeout=1200)
            .exit(0),
            ExpectShell(workdir='build',
                        command=['darcs', 'changes', '--max-count=1'])
            .stdout('Tue Aug 20 09:18:41 IST 2013 abc@gmail.com')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'Tue Aug 20 09:18:41 IST 2013 abc@gmail.com', 'Darcs')
        return self.run_step()

    def test_mode_incremental(self):
        self.setup_step(
            darcs.Darcs(repourl='http://localhost/darcs',
                        mode='incremental'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['darcs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectStat(file='wkdir/_darcs', log_environ=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['darcs', 'pull', '--all', '--verbose'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['darcs', 'changes', '--max-count=1'])
            .stdout('Tue Aug 20 09:18:41 IST 2013 abc@gmail.com')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'Tue Aug 20 09:18:41 IST 2013 abc@gmail.com', 'Darcs')
        return self.run_step()

    def test_mode_incremental_patched(self):
        self.setup_step(
            darcs.Darcs(repourl='http://localhost/darcs',
                        mode='incremental'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['darcs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(0),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200)
            .exit(0),
            ExpectStat(file='source/_darcs', log_environ=True)
            .exit(0),
            ExpectShell(workdir='source',
                        command=['darcs', 'pull', '--all', '--verbose'])
            .exit(0),
            ExpectCpdir(fromdir='source', todir='build', log_environ=True, timeout=1200)
            .exit(0),
            ExpectStat(file='build/_darcs', log_environ=True)
            .exit(0),
            ExpectShell(workdir='build',
                        command=['darcs', 'pull', '--all', '--verbose'])
            .exit(0),
            ExpectShell(workdir='build',
                        command=['darcs', 'changes', '--max-count=1'])
            .stdout('Tue Aug 20 09:18:41 IST 2013 abc@gmail.com')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'Tue Aug 20 09:18:41 IST 2013 abc@gmail.com', 'Darcs')
        return self.run_step()

    def test_mode_incremental_patch(self):
        self.setup_step(
            darcs.Darcs(repourl='http://localhost/darcs',
                        mode='incremental'),
            patch=(1, 'patch'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['darcs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectStat(file='wkdir/_darcs', log_environ=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['darcs', 'pull', '--all', '--verbose'])
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
                        command=['patch', '-p1', '--remove-empty-files',
                                 '--force', '--forward', '-i', '.buildbot-diff'])
            .exit(0),
            ExpectRmdir(dir='wkdir/.buildbot-diff', log_environ=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['darcs', 'changes', '--max-count=1'])
            .stdout('Tue Aug 20 09:18:41 IST 2013 abc@gmail.com')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'Tue Aug 20 09:18:41 IST 2013 abc@gmail.com', 'Darcs')
        return self.run_step()

    def test_mode_full_clobber_retry(self):
        self.setup_step(
            darcs.Darcs(repourl='http://localhost/darcs',
                        mode='full', method='clobber', retry=(0, 2)))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['darcs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True)
            .exit(0),
            ExpectShell(workdir='.',
                        command=['darcs', 'get', '--verbose', '--lazy',
                                 '--repo-name', 'wkdir', 'http://localhost/darcs'])
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True)
            .exit(0),
            ExpectShell(workdir='.',
                        command=['darcs', 'get', '--verbose', '--lazy',
                                 '--repo-name', 'wkdir', 'http://localhost/darcs'])
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True)
            .exit(0),
            ExpectShell(workdir='.',
                        command=['darcs', 'get', '--verbose', '--lazy',
                                 '--repo-name', 'wkdir', 'http://localhost/darcs'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['darcs', 'changes', '--max-count=1'])
            .stdout('Tue Aug 20 09:18:41 IST 2013 abc@gmail.com')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'Tue Aug 20 09:18:41 IST 2013 abc@gmail.com', 'Darcs')
        return self.run_step()

    def test_mode_full_clobber_revision(self):
        self.setup_step(
            darcs.Darcs(repourl='http://localhost/darcs',
                        mode='full', method='clobber'),
            dict(revision='abcdef01'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['darcs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest='.darcs-context', workdir='wkdir', mode=None)
            .exit(0),
            ExpectShell(workdir='.',
                        command=['darcs', 'get', '--verbose', '--lazy',
                                 '--repo-name', 'wkdir', '--context',
                                 '.darcs-context', 'http://localhost/darcs'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['darcs', 'changes', '--max-count=1'])
            .stdout('Tue Aug 20 09:18:41 IST 2013 abc@gmail.com')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'Tue Aug 20 09:18:41 IST 2013 abc@gmail.com', 'Darcs')
        return self.run_step()

    def test_mode_full_clobber_revision_worker_2_16(self):
        self.setup_step(
            darcs.Darcs(repourl='http://localhost/darcs',
                        mode='full', method='clobber'),
            dict(revision='abcdef01'),
            worker_version={'*': '2.16'})
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['darcs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               slavedest='.darcs-context', workdir='wkdir', mode=None)
            .exit(0),
            ExpectShell(workdir='.',
                        command=['darcs', 'get', '--verbose', '--lazy',
                                 '--repo-name', 'wkdir', '--context',
                                 '.darcs-context', 'http://localhost/darcs'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['darcs', 'changes', '--max-count=1'])
            .stdout('Tue Aug 20 09:18:41 IST 2013 abc@gmail.com')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'Tue Aug 20 09:18:41 IST 2013 abc@gmail.com', 'Darcs')
        return self.run_step()

    def test_mode_incremental_no_existing_repo(self):
        self.setup_step(
            darcs.Darcs(repourl='http://localhost/darcs',
                        mode='incremental'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['darcs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectStat(file='wkdir/_darcs', log_environ=True)
            .exit(1),
            ExpectShell(workdir='.',
                        command=['darcs', 'get', '--verbose', '--lazy',
                                 '--repo-name', 'wkdir', 'http://localhost/darcs'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['darcs', 'changes', '--max-count=1'])
            .stdout('Tue Aug 20 09:18:41 IST 2013 abc@gmail.com')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'Tue Aug 20 09:18:41 IST 2013 abc@gmail.com', 'Darcs')
        return self.run_step()

    def test_worker_connection_lost(self):
        self.setup_step(
            darcs.Darcs(repourl='http://localhost/darcs',
                        mode='full', method='clobber'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['darcs', '--version'])
            .error(error.ConnectionLost())
        )
        self.expect_outcome(result=RETRY, state_string="update (retry)")
        return self.run_step()
