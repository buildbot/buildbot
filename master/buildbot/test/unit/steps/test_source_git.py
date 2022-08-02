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

from parameterized import parameterized

from twisted.internet import defer
from twisted.internet import error
from twisted.trial import unittest

from buildbot import config as bbconfig
from buildbot.interfaces import WorkerSetupError
from buildbot.process import remotetransfer
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SUCCESS
from buildbot.steps.source import git
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import ExpectCpdir
from buildbot.test.steps import ExpectDownloadFile
from buildbot.test.steps import ExpectListdir
from buildbot.test.steps import ExpectMkdir
from buildbot.test.steps import ExpectRemoteRef
from buildbot.test.steps import ExpectRmdir
from buildbot.test.steps import ExpectShell
from buildbot.test.steps import ExpectStat
from buildbot.test.steps import TestBuildStepMixin
from buildbot.test.util import config
from buildbot.test.util import sourcesteps
from buildbot.util import unicode2bytes


class TestGit(sourcesteps.SourceStepMixin,
              config.ConfigErrorsMixin,
              TestReactorMixin,
              unittest.TestCase):

    stepClass = git.Git

    def setUp(self):
        self.setup_test_reactor()
        self.sourceName = self.stepClass.__name__
        return self.setUpSourceStep()

    def tearDown(self):
        return self.tearDownSourceStep()

    def test_mode_full_filters_2_26(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean', filters=['tree:0']))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 2.26.0')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files()
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git', '.', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_full_filters_2_27(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean', filters=['tree:0']))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 2.27.0')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files()
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone', '--filter', 'tree:0',
                                 'http://github.com/buildbot/buildbot.git', '.', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_full_clean(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_clean_progress_False(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean', progress=False))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_clean_ssh_key_2_10(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean', sshPrivateKey='sshkey'))

        ssh_workdir = '/wrk/.bldr.wkdir.buildbot'
        ssh_key_path = '/wrk/.bldr.wkdir.buildbot/ssh-key'
        ssh_command_config = f'core.sshCommand=ssh -o "BatchMode=yes" -i "{ssh_key_path}"'

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 2.10.0')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectMkdir(dir=ssh_workdir, log_environ=True)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_key_path, workdir='wkdir', mode=0o400)
            .exit(0),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', '-c', ssh_command_config,
                                 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0),
            ExpectRmdir(dir=ssh_workdir, log_environ=True)
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_clean_ssh_key_2_3(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean', sshPrivateKey='sshkey'))

        ssh_workdir = '/wrk/.bldr.wkdir.buildbot'
        ssh_key_path = '/wrk/.bldr.wkdir.buildbot/ssh-key'
        ssh_command = f'ssh -o "BatchMode=yes" -i "{ssh_key_path}"'

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 2.3.0')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectMkdir(dir=ssh_workdir, log_environ=True)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_key_path, workdir='wkdir', mode=0o400)
            .exit(0),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'],
                        env={'GIT_SSH_COMMAND': ssh_command})
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0),
            ExpectRmdir(dir=ssh_workdir, log_environ=True)
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    @defer.inlineCallbacks
    def test_mode_full_clean_ssh_key_1_7(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean', sshPrivateKey='sshkey'))

        ssh_workdir = '/wrk/.bldr.wkdir.buildbot'
        ssh_key_path = '/wrk/.bldr.wkdir.buildbot/ssh-key'
        ssh_wrapper_path = '/wrk/.bldr.wkdir.buildbot/ssh-wrapper.sh'

        # A place to store what gets read
        read = []

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.0')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectMkdir(dir=ssh_workdir, log_environ=True)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_key_path, workdir='wkdir', mode=0o400)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_wrapper_path, workdir='wkdir', mode=0o700)
            .download_string(read.append)
            .exit(0),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'],
                        env={'GIT_SSH': ssh_wrapper_path})
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0),
            ExpectRmdir(dir=ssh_workdir, log_environ=True)
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        yield self.run_step()

        expected = f'#!/bin/sh\nssh -o "BatchMode=yes" -i "{ssh_key_path}" "$@"\n'
        self.assertEqual(b''.join(read), unicode2bytes(expected))

    @parameterized.expand([
        ('host_key', dict(sshHostKey='sshhostkey')),
        ('known_hosts', dict(sshKnownHosts='known_hosts')),
    ])
    def test_mode_full_clean_ssh_host_key_2_10(self, name, class_params):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean', sshPrivateKey='sshkey', **class_params))

        ssh_workdir = '/wrk/.bldr.wkdir.buildbot'
        ssh_key_path = '/wrk/.bldr.wkdir.buildbot/ssh-key'
        ssh_known_hosts_path = '/wrk/.bldr.wkdir.buildbot/ssh-known-hosts'
        ssh_command_config = \
            f'core.sshCommand=ssh -o "BatchMode=yes" -i "{ssh_key_path}" ' \
            f'-o "UserKnownHostsFile={ssh_known_hosts_path}"'

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 2.10.0')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectMkdir(dir=ssh_workdir, log_environ=True)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_key_path, workdir='wkdir', mode=0o400)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_known_hosts_path, workdir='wkdir', mode=0o400)
            .exit(0),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', '-c', ssh_command_config,
                                 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0),
            ExpectRmdir(dir=ssh_workdir, log_environ=True)
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_clean_ssh_host_key_2_3(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean', sshPrivateKey='sshkey',
                           sshHostKey='sshhostkey'))

        ssh_workdir = '/wrk/.bldr.wkdir.buildbot'
        ssh_key_path = '/wrk/.bldr.wkdir.buildbot/ssh-key'
        ssh_known_hosts_path = '/wrk/.bldr.wkdir.buildbot/ssh-known-hosts'
        ssh_command = \
            f'ssh -o "BatchMode=yes" -i "{ssh_key_path}" ' \
            f'-o "UserKnownHostsFile={ssh_known_hosts_path}"'

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 2.3.0')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectMkdir(dir=ssh_workdir, log_environ=True)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_key_path, workdir='wkdir', mode=0o400)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_known_hosts_path, workdir='wkdir', mode=0o400)
            .exit(0),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'],
                        env={'GIT_SSH_COMMAND': ssh_command})
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0),
            ExpectRmdir(dir=ssh_workdir, log_environ=True)
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    @defer.inlineCallbacks
    def test_mode_full_clean_ssh_host_key_1_7(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean', sshPrivateKey='sshkey',
                           sshHostKey='sshhostkey'))

        ssh_workdir = '/wrk/.bldr.wkdir.buildbot'
        ssh_key_path = '/wrk/.bldr.wkdir.buildbot/ssh-key'
        ssh_wrapper_path = '/wrk/.bldr.wkdir.buildbot/ssh-wrapper.sh'
        ssh_known_hosts_path = '/wrk/.bldr.wkdir.buildbot/ssh-known-hosts'

        # A place to store what gets read
        read = []

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.0')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectMkdir(dir=ssh_workdir, log_environ=True)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_key_path, workdir='wkdir', mode=0o400)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_known_hosts_path, workdir='wkdir', mode=0o400)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_wrapper_path, workdir='wkdir', mode=0o700)
            .download_string(read.append)
            .exit(0),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'],
                        env={'GIT_SSH': ssh_wrapper_path})
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0),
            ExpectRmdir(dir=ssh_workdir, log_environ=True)
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        yield self.run_step()

        expected = (
            '#!/bin/sh\n'
            f'ssh -o "BatchMode=yes" -i "{ssh_key_path}" -o '
            f'"UserKnownHostsFile={ssh_known_hosts_path}" "$@"\n'
        )
        self.assertEqual(b''.join(read), unicode2bytes(expected))

    def test_mode_full_clean_ssh_host_key_1_7_progress(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean', sshPrivateKey='sshkey',
                           sshHostKey='sshhostkey', progress=True))

        ssh_workdir = '/wrk/.bldr.wkdir.buildbot'
        ssh_key_path = '/wrk/.bldr.wkdir.buildbot/ssh-key'
        ssh_wrapper_path = '/wrk/.bldr.wkdir.buildbot/ssh-wrapper.sh'
        ssh_known_hosts_path = '/wrk/.bldr.wkdir.buildbot/ssh-known-hosts'

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.0')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectMkdir(dir=ssh_workdir, log_environ=True)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_key_path, workdir='wkdir', mode=0o400)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_known_hosts_path, workdir='wkdir', mode=0o400)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_wrapper_path, workdir='wkdir', mode=0o700)
            .exit(0),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'],
                        env={'GIT_SSH': ssh_wrapper_path})
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0),
            ExpectRmdir(dir=ssh_workdir, log_environ=True)
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_clean_ssh_host_key_2_10_abs_workdir(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean', sshPrivateKey='sshkey',
                           sshHostKey='sshhostkey'),
            want_default_work_dir=False)
        workdir = '/myworkdir/workdir'
        self.build.workdir = workdir

        ssh_workdir = '/myworkdir/.bldr.workdir.buildbot'
        ssh_key_path = '/myworkdir/.bldr.workdir.buildbot/ssh-key'
        ssh_known_hosts_path = '/myworkdir/.bldr.workdir.buildbot/ssh-known-hosts'
        ssh_command_config = \
            f'core.sshCommand=ssh -o "BatchMode=yes" -i "{ssh_key_path}" ' \
            f'-o "UserKnownHostsFile={ssh_known_hosts_path}"'

        self.expect_commands(
            ExpectShell(workdir=workdir,
                        command=['git', '--version'])
            .stdout('git version 2.10.0')
            .exit(0),
            ExpectStat(file='/myworkdir/workdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectMkdir(dir=ssh_workdir, log_environ=True)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_key_path, workdir=workdir, mode=0o400)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_known_hosts_path, workdir=workdir, mode=0o400)
            .exit(0),
            ExpectListdir(dir=workdir)
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir=workdir,
                        command=['git', 'clean', '-f', '-f', '-d'])
            .exit(0),
            ExpectShell(workdir=workdir,
                        command=['git', '-c', ssh_command_config,
                                 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir=workdir,
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir=workdir,
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0),
            ExpectRmdir(dir=ssh_workdir, log_environ=True)
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_clean_win32path(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean'))
        self.change_worker_system('win32')
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file=r'wkdir\.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_clean_win32path_ssh_key_2_10(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean', sshPrivateKey='sshkey'))
        self.change_worker_system('win32')

        ssh_workdir = '\\wrk\\.bldr.wkdir.buildbot'
        ssh_key_path = '\\wrk\\.bldr.wkdir.buildbot\\ssh-key'
        ssh_command_config = f'core.sshCommand=ssh -o "BatchMode=yes" -i "{ssh_key_path}"'

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 2.10.0')
            .exit(0),
            ExpectStat(file='wkdir\\.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectMkdir(dir=ssh_workdir, log_environ=True)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_key_path, workdir='wkdir', mode=0o400)
            .exit(0),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', '-c', ssh_command_config,
                                 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0),
            ExpectRmdir(dir=ssh_workdir, log_environ=True)
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_clean_win32path_ssh_key_2_3(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean', sshPrivateKey='sshkey'))
        self.change_worker_system('win32')

        ssh_workdir = '\\wrk\\.bldr.wkdir.buildbot'
        ssh_key_path = '\\wrk\\.bldr.wkdir.buildbot\\ssh-key'
        ssh_command = f'ssh -o "BatchMode=yes" -i "{ssh_key_path}"'

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 2.3.0')
            .exit(0),
            ExpectStat(file='wkdir\\.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectMkdir(dir=ssh_workdir, log_environ=True)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_key_path, workdir='wkdir', mode=0o400)
            .exit(0),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'],
                        env={'GIT_SSH_COMMAND': ssh_command})
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0),
            ExpectRmdir(dir=ssh_workdir, log_environ=True)
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_clean_win32path_ssh_key_1_7(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean', sshPrivateKey='sshkey'))
        self.change_worker_system('win32')

        ssh_workdir = '\\wrk\\.bldr.wkdir.buildbot'
        ssh_key_path = '\\wrk\\.bldr.wkdir.buildbot\\ssh-key'
        ssh_wrapper_path = '\\wrk\\.bldr.wkdir.buildbot\\ssh-wrapper.sh'

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.0')
            .exit(0),
            ExpectStat(file='wkdir\\.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectMkdir(dir=ssh_workdir, log_environ=True)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_key_path, workdir='wkdir', mode=0o400)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_wrapper_path, workdir='wkdir', mode=0o700)
            .exit(0),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'],
                        env={'GIT_SSH': ssh_wrapper_path})
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0),
            ExpectRmdir(dir=ssh_workdir, log_environ=True)
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_clean_timeout(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           timeout=1,
                           mode='full', method='clean'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['git', 'clean', '-f', '-f', '-d'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_clean_patch(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean'),
            patch=(1, 'patch'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d', '-x'],
                        log_environ=True)
            .exit(0),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
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
                        command=['git', 'update-index', '--refresh'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'apply', '--index', '-p', '1'],
                        initial_stdin='patch')
            .exit(0),
            ExpectRmdir(dir='wkdir/.buildbot-diff', log_environ=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_clean_patch_worker_2_16(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean'),
            patch=(1, 'patch'),
            worker_version={'*': '2.16'})
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d', '-x'],
                        log_environ=True)
            .exit(0),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
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
                        command=['git', 'update-index', '--refresh'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'apply', '--index', '-p', '1'],
                        initial_stdin='patch')
            .exit(0),
            ExpectRmdir(dir='wkdir/.buildbot-diff', log_environ=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_clean_patch_fail(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean'),
            patch=(1, 'patch'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
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
                        command=['git', 'update-index', '--refresh'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'apply', '--index', '-p', '1'],
                        initial_stdin='patch')
            .exit(1)
        )
        self.expect_outcome(result=FAILURE)
        self.expect_no_property('got_revision')
        return self.run_step()

    def test_mode_full_clean_branch(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean', branch='test-branch'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'test-branch', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-B', 'test-branch'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_clean_non_empty_builddir(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean', branch='test-branch'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['file1', 'file2'])
            .exit(0),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone', '--branch', 'test-branch',
                                 'http://github.com/buildbot/buildbot.git', '.', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_clean_parsefail(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .stderr("fatal: Could not parse object "
                    "'b08076bc71c7813038f2cefedff9c5b678d225a8'.\n")
            .exit(128)
        )
        self.expect_outcome(result=FAILURE)
        self.expect_no_property('got_revision')
        return self.run_step()

    def test_mode_full_clean_no_existing_repo(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files()
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git', '.', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_full_clean_no_existing_repo_with_reference(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean', reference='path/to/reference/repo'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files()
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone', '--reference', 'path/to/reference/repo',
                                 'http://github.com/buildbot/buildbot.git', '.', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_full_clean_no_existing_repo_branch(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean', branch='test-branch'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files()
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 '--branch', 'test-branch',
                                 'http://github.com/buildbot/buildbot.git', '.', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_full_clean_no_existing_repo_with_origin(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean', origin='foo', progress=True))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files()
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone', '--origin', 'foo',
                                 'http://github.com/buildbot/buildbot.git', '.', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_full_clean_submodule(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean', submodules=True, progress=True))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'submodule', 'sync'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'submodule', 'update', '--init', '--recursive'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'submodule', 'foreach', '--recursive',
                                 'git clean -f -f -d'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_clean_submodule_remotes(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean', submodules=True, progress=True,
                           remoteSubmodules=True))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'submodule', 'sync'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'submodule', 'update', '--init', '--recursive', '--remote'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'submodule', 'foreach', '--recursive',
                                 'git clean -f -f -d'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_clobber_submodule_remotes(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clobber', submodules=True, progress=True,
                           remoteSubmodules=True))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'submodule', 'update', '--init', '--recursive', '--remote'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_clobber(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clobber', progress=True))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_clone_fails(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clobber', progress=True))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            .exit(1)  # clone fails
        )
        self.expect_outcome(result=FAILURE, state_string="update (failure)")
        self.expect_no_property('got_revision')
        return self.run_step()

    def test_mode_full_clobber_branch(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clobber', progress=True, branch='test-branch'))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 '--branch', 'test-branch',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_clobber_no_branch_support(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clobber', branch='test-branch'))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.5.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'test-branch'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-B', 'test-branch'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_incremental_oldworker(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental', progress=True))
        self.step.build.getWorkerCommandVersion = lambda cmd, oldversion: "2.15"
        self.expect_commands(
            ExpectShell(workdir='wkdir', interrupt_signal='TERM',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectStat(file='wkdir/.git', log_environ=True)
            .exit(0),
            ExpectShell(workdir='wkdir', interrupt_signal='TERM',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir', interrupt_signal='TERM',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir', interrupt_signal='TERM',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_incremental(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental', progress=True))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_version_format(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5.1')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_incremental_retry(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental', retry=(0, 1)))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files()
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_incremental_branch(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental', branch='test-branch'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'test-branch', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-B', 'test-branch'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_incremental_branch_ssh_key_2_10(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental', branch='test-branch',
                           sshPrivateKey='ssh-key', progress=True))

        ssh_workdir = '/wrk/.bldr.wkdir.buildbot'
        ssh_key_path = '/wrk/.bldr.wkdir.buildbot/ssh-key'
        ssh_command_config = \
            f'core.sshCommand=ssh -o "BatchMode=yes" -i "{ssh_key_path}"'

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 2.10.0')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectMkdir(dir=ssh_workdir, log_environ=True)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_key_path, workdir='wkdir', mode=0o400)
            .exit(0),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', '-c', ssh_command_config,
                                 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'test-branch', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-B', 'test-branch'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0),
            ExpectRmdir(dir=ssh_workdir, log_environ=True)
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_fresh(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='fresh'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d', '-x'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_fresh_clean_fails(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='fresh'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d', '-x'])
            .exit(1),  # clean fails -> clobber
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_incremental_given_revision(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental'), dict(
                revision='abcdef01',
            ))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'cat-file', '-e', 'abcdef01'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'abcdef01'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_incremental_given_revision_not_exists(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental'), dict(
                revision='abcdef01',
            ))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'cat-file', '-e', 'abcdef01'])
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'abcdef01'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_fresh_submodule(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='fresh', submodules=True))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d', '-x'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'submodule', 'sync'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'submodule', 'update', '--init', '--recursive'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'submodule', 'foreach', '--recursive',
                                 'git clean -f -f -d -x'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d', '-x'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="update")
        self.expect_property('got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d',
                            self.sourceName)
        return self.run_step()

    def test_mode_full_fresh_submodule_git_newer_1_7_6(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='fresh', submodules=True))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.6')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d', '-x'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'submodule', 'sync'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'submodule', 'update', '--init', '--recursive', '--force'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'submodule', 'foreach', '--recursive',
                                 'git clean -f -f -d -x'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d', '-x'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_fresh_submodule_v1_7_8(self):
        """This tests the same as test_mode_full_fresh_submodule, but the
        "submodule update" command should be different for Git v1.7.8+."""
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='fresh', submodules=True))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.8')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d', '-x'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'submodule', 'sync'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'submodule', 'update', '--init', '--recursive',
                                 '--force', '--checkout'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'submodule', 'foreach', '--recursive',
                                 'git clean -f -f -d -x'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d', '-x'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_clobber_shallow(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clobber', shallow=True))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone', '--depth', '1',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_clobber_shallow_depth(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clobber', shallow="100"))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone', '--depth', '100',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_clobber_no_shallow(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clobber'))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_incremental_retryFetch(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental', retryFetch=True))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_incremental_retryFetch_branch(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental', retryFetch=True, branch='test-branch'))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'test-branch', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'test-branch', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-B', 'test-branch'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_incremental_clobberOnFailure(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental', clobberOnFailure=True))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_incremental_clobberOnFailure_branch(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental', clobberOnFailure=True, branch='test-branch'))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'test-branch', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 '--branch', 'test-branch',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_copy(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='copy'))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200),
            ExpectListdir(dir='source')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='source',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='source',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectCpdir(fromdir='source', todir='wkdir', log_environ=True, timeout=1200)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_copy_ssh_key_2_10(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='copy', sshPrivateKey='sshkey'))

        ssh_workdir = '/wrk/.bldr.source.buildbot'
        ssh_key_path = '/wrk/.bldr.source.buildbot/ssh-key'
        ssh_command_config = \
            f'core.sshCommand=ssh -o "BatchMode=yes" -i "{ssh_key_path}"'

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 2.10.0')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectMkdir(dir=ssh_workdir, log_environ=True)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_key_path, workdir='source', mode=0o400)
            .exit(0),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200),
            ExpectListdir(dir='source')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='source',
                        command=['git', '-c', ssh_command_config,
                                 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='source',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectCpdir(fromdir='source', todir='wkdir', log_environ=True, timeout=1200)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0),
            ExpectRmdir(dir=ssh_workdir, log_environ=True)
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_copy_shallow(self):
        with self.assertRaisesConfigError(
                "shallow only possible with mode 'full' and method 'clobber'"):
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                        mode='full', method='copy', shallow=True)

    def test_mode_incremental_no_existing_repo(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files()
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_incremental_no_existing_repo_oldworker(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental'))
        self.step.build.getWorkerCommandVersion = lambda cmd, oldversion: "2.15"
        self.expect_commands(
            ExpectShell(workdir='wkdir', interrupt_signal='TERM',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectStat(file='wkdir/.git', log_environ=True)
            .exit(1),
            ExpectShell(workdir='wkdir', interrupt_signal='TERM',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir', interrupt_signal='TERM',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_clobber_given_revision(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clobber', progress=True), dict(
                revision='abcdef01',
            ))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'abcdef01'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_revparse_failure(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clobber', progress=True), dict(
                revision='abcdef01',
            ))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'abcdef01'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ada95a1d')  # too short
            .exit(0)
        )
        self.expect_outcome(result=FAILURE)
        self.expect_no_property('got_revision')
        return self.run_step()

    def test_mode_full_clobber_submodule(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clobber', submodules=True))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git', '.', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'submodule', 'update',
                                 '--init', '--recursive'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_repourl(self):
        with self.assertRaisesConfigError("must provide repourl"):
            self.stepClass(mode="full")

    def test_mode_full_fresh_revision(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='fresh', progress=True), dict(
                revision='abcdef01',
            ))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files()
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'abcdef01'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_fresh_retry(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='fresh', retry=(0, 2)))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files()
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_fresh_clobberOnFailure(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='fresh', clobberOnFailure=True))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files()
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_no_method(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d', '-x'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_with_env(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', env={'abc': '123'}))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'],
                        env={'abc': '123'})
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d', '-x'],
                        env={'abc': '123'})
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'],
                        env={'abc': '123'})
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'],
                        env={'abc': '123'})
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'],
                        env={'abc': '123'})
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_log_environ(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', logEnviron=False))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'],
                        log_environ=False)
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=False)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d', '-x'],
                        log_environ=False)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'],
                        log_environ=False)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'],
                        log_environ=False)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'],
                        log_environ=False)
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_wkdir_doesnt_exist(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_getDescription(self):
        # clone of: test_mode_incremental
        # only difference is to set the getDescription property

        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental',
                           getDescription=True))
        self.expect_commands(
            # copied from test_mode_incremental:
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0),

            # plus this to test describe:
            ExpectShell(workdir='wkdir',
                        command=['git', 'describe', 'HEAD'])
            .stdout('Tag-1234')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        self.expect_property('commit-description', 'Tag-1234', self.sourceName)
        return self.run_step()

    def test_getDescription_failed(self):
        # clone of: test_mode_incremental
        # only difference is to set the getDescription property

        # this tests when 'git describe' fails; for example, there are no
        # tags in the repository

        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental',
                           getDescription=True))
        self.expect_commands(
            # copied from test_mode_incremental:
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0),

            # plus this to test describe:
            ExpectShell(workdir='wkdir',
                        command=['git', 'describe', 'HEAD'])
            .stdout('')
            .exit(128)  # error, but it's suppressed
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        self.expect_no_property('commit-description')
        return self.run_step()

    def setup_getDescription_test(self, setup_args, output_args,
                                  expect_head=True, codebase=None):
        # clone of: test_mode_full_clobber
        # only difference is to set the getDescription property

        kwargs = {}
        if codebase is not None:
            kwargs.update(codebase=codebase)

        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clobber', progress=True,
                           getDescription=setup_args,
                           **kwargs))

        self.expect_commands(
            # copied from test_mode_full_clobber:
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0),

            # plus this to test describe:
            ExpectShell(workdir='wkdir',
                        command=['git', 'describe'] +
                                output_args +
                                (['HEAD'] if expect_head else []))
            .stdout('Tag-1234')
            .exit(0)
        )

        if codebase:
            self.expect_outcome(result=SUCCESS,
                               state_string="update " + codebase)
            self.expect_property('got_revision',
                                {codebase: 'f6ad368298bd941e934a41f3babc827b2aa95a1d'},
                                self.sourceName)
            self.expect_property(
                'commit-description', {codebase: 'Tag-1234'}, self.sourceName)
        else:
            self.expect_outcome(result=SUCCESS,
                               state_string="update")
            self.expect_property(
                'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
            self.expect_property('commit-description', 'Tag-1234', self.sourceName)

    def test_getDescription_empty_dict(self):
        self.setup_getDescription_test(
            setup_args={},
            output_args=[]
        )
        return self.run_step()

    def test_getDescription_empty_dict_with_codebase(self):
        self.setup_getDescription_test(
            setup_args={},
            output_args=[],
            codebase='baz'
        )
        return self.run_step()

    def test_getDescription_match(self):
        self.setup_getDescription_test(
            setup_args={'match': 'stuff-*'},
            output_args=['--match', 'stuff-*']
        )
        return self.run_step()

    def test_getDescription_match_false(self):
        self.setup_getDescription_test(
            setup_args={'match': None},
            output_args=[]
        )
        return self.run_step()

    def test_getDescription_tags(self):
        self.setup_getDescription_test(
            setup_args={'tags': True},
            output_args=['--tags']
        )
        return self.run_step()

    def test_getDescription_tags_false(self):
        self.setup_getDescription_test(
            setup_args={'tags': False},
            output_args=[]
        )
        return self.run_step()

    def test_getDescription_all(self):
        self.setup_getDescription_test(
            setup_args={'all': True},
            output_args=['--all']
        )
        return self.run_step()

    def test_getDescription_all_false(self):
        self.setup_getDescription_test(
            setup_args={'all': False},
            output_args=[]
        )
        return self.run_step()

    def test_getDescription_abbrev(self):
        self.setup_getDescription_test(
            setup_args={'abbrev': 7},
            output_args=['--abbrev=7']
        )
        return self.run_step()

    def test_getDescription_abbrev_zero(self):
        self.setup_getDescription_test(
            setup_args={'abbrev': 0},
            output_args=['--abbrev=0']
        )
        return self.run_step()

    def test_getDescription_abbrev_false(self):
        self.setup_getDescription_test(
            setup_args={'abbrev': False},
            output_args=[]
        )
        return self.run_step()

    def test_getDescription_dirty(self):
        self.setup_getDescription_test(
            setup_args={'dirty': True},
            output_args=['--dirty'],
            expect_head=False
        )
        return self.run_step()

    def test_getDescription_dirty_empty_str(self):
        self.setup_getDescription_test(
            setup_args={'dirty': ''},
            output_args=['--dirty'],
            expect_head=False
        )
        return self.run_step()

    def test_getDescription_dirty_str(self):
        self.setup_getDescription_test(
            setup_args={'dirty': 'foo'},
            output_args=['--dirty=foo'],
            expect_head=False
        )
        return self.run_step()

    def test_getDescription_dirty_false(self):
        self.setup_getDescription_test(
            setup_args={'dirty': False},
            output_args=[],
            expect_head=True
        )
        return self.run_step()

    def test_getDescription_dirty_none(self):
        self.setup_getDescription_test(
            setup_args={'dirty': None},
            output_args=[],
            expect_head=True
        )
        return self.run_step()

    def test_getDescription_contains(self):
        self.setup_getDescription_test(
            setup_args={'contains': True},
            output_args=['--contains']
        )
        return self.run_step()

    def test_getDescription_contains_false(self):
        self.setup_getDescription_test(
            setup_args={'contains': False},
            output_args=[]
        )
        return self.run_step()

    def test_getDescription_candidates(self):
        self.setup_getDescription_test(
            setup_args={'candidates': 7},
            output_args=['--candidates=7']
        )
        return self.run_step()

    def test_getDescription_candidates_zero(self):
        self.setup_getDescription_test(
            setup_args={'candidates': 0},
            output_args=['--candidates=0']
        )
        return self.run_step()

    def test_getDescription_candidates_false(self):
        self.setup_getDescription_test(
            setup_args={'candidates': False},
            output_args=[]
        )
        return self.run_step()

    def test_getDescription_exact_match(self):
        self.setup_getDescription_test(
            setup_args={'exact-match': True},
            output_args=['--exact-match']
        )
        return self.run_step()

    def test_getDescription_exact_match_false(self):
        self.setup_getDescription_test(
            setup_args={'exact-match': False},
            output_args=[]
        )
        return self.run_step()

    def test_getDescription_debug(self):
        self.setup_getDescription_test(
            setup_args={'debug': True},
            output_args=['--debug']
        )
        return self.run_step()

    def test_getDescription_debug_false(self):
        self.setup_getDescription_test(
            setup_args={'debug': False},
            output_args=[]
        )
        return self.run_step()

    def test_getDescription_long(self):
        self.setup_getDescription_test(
            setup_args={'long': True},
            output_args=['--long']
        )

    def test_getDescription_long_false(self):
        self.setup_getDescription_test(
            setup_args={'long': False},
            output_args=[]
        )
        return self.run_step()

    def test_getDescription_always(self):
        self.setup_getDescription_test(
            setup_args={'always': True},
            output_args=['--always']
        )

    def test_getDescription_always_false(self):
        self.setup_getDescription_test(
            setup_args={'always': False},
            output_args=[]
        )
        return self.run_step()

    def test_getDescription_lotsa_stuff(self):
        self.setup_getDescription_test(
            setup_args={'match': 'stuff-*',
                        'abbrev': 6,
                        'exact-match': True},
            output_args=['--exact-match',
                         '--match', 'stuff-*',
                         '--abbrev=6'],
            codebase='baz'
        )
        return self.run_step()

    def test_config_option(self):
        name = 'url.http://github.com.insteadOf'
        value = 'blahblah'
        self.setup_step(
            self.stepClass(repourl=f'{value}/buildbot/buildbot.git',
                           mode='full', method='clean',
                           config={name: value}))
        prefix = ['git', '-c', f'{name}={value}']
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=prefix + ['--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=prefix + ['clean', '-f', '-f', '-d'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=prefix + ['fetch', '-f', '-t',
                                          f'{value}/buildbot/buildbot.git',
                                          'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=prefix + ['checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=prefix + ['rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_worker_connection_lost(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .error(error.ConnectionLost())
        )
        self.expect_outcome(result=RETRY, state_string="update (retry)")
        return self.run_step()

    @defer.inlineCallbacks
    def _test_WorkerSetupError(self, _dovccmd, step, msg):

        self.patch(self.stepClass, "_dovccmd", _dovccmd)
        gitStep = self.setup_step(step)

        with self.assertRaisesRegex(WorkerSetupError, msg):
            yield gitStep.run_vc("branch", "revision", "patch")

    def test_noGitCommandInstalled(self):
        @defer.inlineCallbacks
        def _dovccmd(command, abandonOnFailure=True, collectStdout=False,
                     initialStdin=None):
            """
            Simulate the case where there is no git command.
            """
            yield
            return "command not found:"

        step = self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                              mode='full', method='clean')
        msg = 'git is not installed on worker'
        return self._test_WorkerSetupError(_dovccmd, step, msg)

    def test_gitCommandOutputShowsNoVersion(self):
        @defer.inlineCallbacks
        def _dovccmd(command, abandonOnFailure=True, collectStdout=False,
                     initialStdin=None):
            """
            Instead of outputting something like "git version 2.11",
            simulate truncated output which has no version string,
            to exercise error handling.
            """
            yield
            return "git "

        step = self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                              mode='full', method='clean')
        msg = 'git is not installed on worker'
        return self._test_WorkerSetupError(_dovccmd, step, msg)

    def test_config_get_description_not_dict_or_boolean(self):
        with self.assertRaisesConfigError("Git: getDescription must be a boolean or a dict."):
            self.stepClass(repourl="http://github.com/buildbot/buildbot.git",
                           getDescription=["list"])

    def test_config_invalid_method_with_full(self):
        with self.assertRaisesConfigError("Git: invalid method for mode 'full'."):
            self.stepClass(repourl="http://github.com/buildbot/buildbot.git",
                           mode='full', method='unknown')

    def test_mode_full_copy_recursive(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='copy', submodules='True'))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200),
            ExpectListdir(dir='source')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='source',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            ExpectShell(workdir='source',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),

            ExpectShell(workdir='source',
                        command=['git', 'submodule', 'sync'])
            .exit(0),

            ExpectShell(workdir='source',
                        command=['git', 'submodule', 'update', '--init', '--recursive'])
            .exit(0),

            ExpectCpdir(fromdir='source', todir='wkdir', log_environ=True, timeout=1200)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.run_step()

    def test_mode_full_copy_recursive_fetch_fail(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='copy', submodules='True'))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200),
            ExpectListdir(dir='source')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='source',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(1)
        )
        self.expect_outcome(result=FAILURE)
        return self.run_step()

    def test_mode_full_copy_recursive_fetch_fail_retry_fail(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='copy', submodules='True', retryFetch=True))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200),
            ExpectListdir(dir='source')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='source',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(1),
            ExpectShell(workdir='source',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(1)
        )
        self.expect_outcome(result=FAILURE)
        return self.run_step()

    def test_mode_full_copy_recursive_fetch_fail_retry_succeed(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='copy', submodules='True', retryFetch=True))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200),
            ExpectListdir(dir='source')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='source',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(1),
            # retry Fetch
            ExpectShell(workdir='source',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(0),
            # continue as normal
            ExpectShell(workdir='source',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),

            ExpectShell(workdir='source',
                        command=['git', 'submodule', 'sync'])
            .exit(0),

            ExpectShell(workdir='source',
                        command=['git', 'submodule', 'update', '--init', '--recursive'])
            .exit(0),

            ExpectCpdir(fromdir='source', todir='wkdir', log_environ=True, timeout=1200)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_full_copy_recursive_fetch_fail_clobberOnFailure(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='copy', submodules='True', clobberOnFailure=True))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=1200),
            ExpectListdir(dir='source')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='source',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD', '--progress'])
            .exit(1),

            # clobber and re-clone the source dir here
            ExpectRmdir(dir='source', log_environ=True, timeout=1200)
            .exit(0),
            ExpectShell(workdir='source',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            .exit(0),
            ExpectShell(workdir='source',
                        command=['git', 'submodule', 'update', '--init', '--recursive'])
            .exit(0),
            ExpectShell(workdir='source',
                        command=['git', 'submodule', 'sync'])
            .exit(0),
            ExpectShell(workdir='source',
                        command=['git', 'submodule', 'update', '--init', '--recursive'])
            .exit(0),
            ExpectCpdir(fromdir='source', todir='wkdir', log_environ=True, timeout=1200)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()


class TestGitPush(TestBuildStepMixin, config.ConfigErrorsMixin,
                  TestReactorMixin,
                  unittest.TestCase):
    stepClass = git.GitPush

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_push_simple(self):
        url = 'ssh://github.com/test/test.git'

        self.setup_step(
            self.stepClass(workdir='wkdir', repourl=url,
                           branch='testbranch'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'push', url, 'testbranch'])
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_push_force(self):
        url = 'ssh://github.com/test/test.git'

        self.setup_step(
            self.stepClass(workdir='wkdir', repourl=url,
                           branch='testbranch', force=True))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'push', url, 'testbranch', '--force'])
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_push_fail(self):
        url = 'ssh://github.com/test/test.git'

        self.setup_step(
            self.stepClass(workdir='wkdir', repourl=url,
                           branch='testbranch', force=True))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'push', url, 'testbranch', '--force'])
            .stderr("error: failed to push some refs to <url>\n")
            .exit(1)
        )
        self.expect_outcome(result=FAILURE)
        return self.run_step()

    def test_push_ssh_key_2_10(self):
        url = 'ssh://github.com/test/test.git'

        self.setup_step(
            self.stepClass(workdir='wkdir', repourl=url,
                           branch='testbranch', sshPrivateKey='sshKey'))

        ssh_workdir = '/wrk/.bldr.wkdir.buildbot'
        ssh_key_path = '/wrk/.bldr.wkdir.buildbot/ssh-key'
        ssh_command_config = \
            f'core.sshCommand=ssh -o "BatchMode=yes" -i "{ssh_key_path}"'

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 2.10.0')
            .exit(0),
            ExpectMkdir(dir=ssh_workdir, log_environ=True)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_key_path, workdir='wkdir', mode=0o400)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', '-c', ssh_command_config,
                                 'push', url, 'testbranch'])
            .exit(0),
            ExpectRmdir(dir=ssh_workdir, log_environ=True)
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_push_ssh_key_2_3(self):
        url = 'ssh://github.com/test/test.git'

        self.setup_step(
            self.stepClass(workdir='wkdir', repourl=url,
                           branch='testbranch', sshPrivateKey='sshKey'))

        ssh_workdir = '/wrk/.bldr.wkdir.buildbot'
        ssh_key_path = '/wrk/.bldr.wkdir.buildbot/ssh-key'
        ssh_command = f'ssh -o "BatchMode=yes" -i "{ssh_key_path}"'

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 2.3.0')
            .exit(0),
            ExpectMkdir(dir=ssh_workdir, log_environ=True)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_key_path, workdir='wkdir', mode=0o400)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'push', url, 'testbranch'],
                        env={'GIT_SSH_COMMAND': ssh_command})
            .exit(0),
            ExpectRmdir(dir=ssh_workdir, log_environ=True)
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_push_ssh_key_1_7(self):
        url = 'ssh://github.com/test/test.git'

        self.setup_step(
            self.stepClass(workdir='wkdir', repourl=url,
                           branch='testbranch', sshPrivateKey='sshKey'))

        ssh_workdir = '/wrk/.bldr.wkdir.buildbot'
        ssh_key_path = '/wrk/.bldr.wkdir.buildbot/ssh-key'
        ssh_wrapper_path = '/wrk/.bldr.wkdir.buildbot/ssh-wrapper.sh'

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.0')
            .exit(0),
            ExpectMkdir(dir=ssh_workdir, log_environ=True)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_key_path, workdir='wkdir', mode=0o400)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_wrapper_path, workdir='wkdir', mode=0o700)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'push', url, 'testbranch'],
                        env={'GIT_SSH': ssh_wrapper_path})
            .exit(0),
            ExpectRmdir(dir=ssh_workdir, log_environ=True)
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_push_ssh_host_key_2_10(self):
        url = 'ssh://github.com/test/test.git'
        self.setup_step(
            self.stepClass(workdir='wkdir', repourl=url,
                           branch='testbranch', sshPrivateKey='sshkey',
                           sshHostKey='sshhostkey'))

        ssh_workdir = '/wrk/.bldr.wkdir.buildbot'
        ssh_key_path = '/wrk/.bldr.wkdir.buildbot/ssh-key'
        ssh_known_hosts_path = '/wrk/.bldr.wkdir.buildbot/ssh-known-hosts'
        ssh_command_config = \
            f'core.sshCommand=ssh -o "BatchMode=yes" -i "{ssh_key_path}" ' \
            f'-o "UserKnownHostsFile={ssh_known_hosts_path}"'

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 2.10.0')
            .exit(0),
            ExpectMkdir(dir=ssh_workdir, log_environ=True)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_key_path, workdir='wkdir', mode=0o400)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_known_hosts_path, workdir='wkdir', mode=0o400)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', '-c', ssh_command_config,
                                 'push', url, 'testbranch'])
            .exit(0),
            ExpectRmdir(dir=ssh_workdir, log_environ=True)
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_push_ssh_host_key_2_3(self):
        url = 'ssh://github.com/test/test.git'
        self.setup_step(
            self.stepClass(workdir='wkdir', repourl=url,
                           branch='testbranch', sshPrivateKey='sshkey',
                           sshHostKey='sshhostkey'))

        ssh_workdir = '/wrk/.bldr.wkdir.buildbot'
        ssh_key_path = '/wrk/.bldr.wkdir.buildbot/ssh-key'
        ssh_known_hosts_path = '/wrk/.bldr.wkdir.buildbot/ssh-known-hosts'
        ssh_command = \
            f'ssh -o "BatchMode=yes" -i "{ssh_key_path}" ' \
            f'-o "UserKnownHostsFile={ssh_known_hosts_path}"'

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 2.3.0')
            .exit(0),
            ExpectMkdir(dir=ssh_workdir, log_environ=True)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_key_path, workdir='wkdir', mode=0o400)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_known_hosts_path, workdir='wkdir', mode=0o400)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'push', url, 'testbranch'],
                        env={'GIT_SSH_COMMAND': ssh_command})
            .exit(0),
            ExpectRmdir(dir=ssh_workdir, log_environ=True)
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_push_ssh_host_key_1_7(self):
        url = 'ssh://github.com/test/test.git'
        self.setup_step(
            self.stepClass(workdir='wkdir', repourl=url,
                           branch='testbranch', sshPrivateKey='sshkey',
                           sshHostKey='sshhostkey'))

        ssh_workdir = '/wrk/.bldr.wkdir.buildbot'
        ssh_key_path = '/wrk/.bldr.wkdir.buildbot/ssh-key'
        ssh_wrapper_path = '/wrk/.bldr.wkdir.buildbot/ssh-wrapper.sh'
        ssh_known_hosts_path = '/wrk/.bldr.wkdir.buildbot/ssh-known-hosts'

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.0')
            .exit(0),
            ExpectMkdir(dir=ssh_workdir, log_environ=True)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_key_path, workdir='wkdir', mode=0o400)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_known_hosts_path, workdir='wkdir', mode=0o400)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest=ssh_wrapper_path, workdir='wkdir', mode=0o700)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'push', url, 'testbranch'],
                        env={'GIT_SSH': ssh_wrapper_path})
            .exit(0),
            ExpectRmdir(dir=ssh_workdir, log_environ=True)
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_raise_no_git(self):
        @defer.inlineCallbacks
        def _checkFeatureSupport(self):
            yield
            return False

        url = 'ssh://github.com/test/test.git'
        step = self.stepClass(workdir='wkdir', repourl=url, branch='testbranch')
        self.patch(self.stepClass, "checkFeatureSupport", _checkFeatureSupport)
        self.setup_step(step)
        self.expect_outcome(result=EXCEPTION)
        self.run_step()
        self.flushLoggedErrors(WorkerSetupError)

    def test_config_fail_no_branch(self):
        with self.assertRaisesConfigError("GitPush: must provide branch"):
            self.stepClass(workdir='wkdir', repourl="url")


class TestGitTag(TestBuildStepMixin, config.ConfigErrorsMixin,
                 TestReactorMixin, unittest.TestCase):
    stepClass = git.GitTag

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_tag_annotated(self):
        messages = ['msg1', 'msg2']

        self.setup_step(
            self.stepClass(workdir='wkdir', tagName='myTag', annotated=True, messages=messages))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'tag', '-a', 'myTag', '-m', 'msg1', '-m', 'msg2'])
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_tag_simple(self):
        self.setup_step(
            self.stepClass(workdir='wkdir',
                           tagName='myTag'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'tag', 'myTag'])
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_tag_force(self):
        self.setup_step(
            self.stepClass(workdir='wkdir',
                           tagName='myTag', force=True))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'tag', 'myTag', '--force'])
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_tag_fail_already_exist(self):
        self.setup_step(
            self.stepClass(workdir='wkdir',
                           tagName='myTag'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'tag', 'myTag'])
            .stderr("fatal: tag \'%s\' already exist\n")
            .exit(1)
        )
        self.expect_outcome(result=FAILURE)
        return self.run_step()

    def test_config_annotated_no_messages(self):
        with self.assertRaises(bbconfig.ConfigErrors):
            self.setup_step(
                self.stepClass(workdir='wkdir', tagName='myTag', annotated=True))

    def test_config_no_tag_name(self):
        with self.assertRaises(bbconfig.ConfigErrors):
            self.setup_step(
                self.stepClass(workdir='wkdir'))

    def test_config_not_annotated_but_meessages(self):
        with self.assertRaises(bbconfig.ConfigErrors):
            self.setup_step(
                self.stepClass(workdir='wkdir', tagName='myTag', messages=['msg']))

    def test_config_annotated_message_not_list(self):
        with self.assertRaises(bbconfig.ConfigErrors):
            self.setup_step(
                self.stepClass(workdir='wkdir', tagName='myTag', annotated=True, messages="msg"))

    def test_raise_no_git(self):
        @defer.inlineCallbacks
        def _checkFeatureSupport(self):
            yield
            return False

        step = self.stepClass(workdir='wdir', tagName='myTag')
        self.patch(self.stepClass, "checkFeatureSupport", _checkFeatureSupport)
        self.setup_step(step)
        self.expect_outcome(result=EXCEPTION)
        self.run_step()
        self.flushLoggedErrors(WorkerSetupError)


class TestGitCommit(TestBuildStepMixin, config.ConfigErrorsMixin,
                    TestReactorMixin,
                    unittest.TestCase):
    stepClass = git.GitCommit

    def setUp(self):
        self.setup_test_reactor()
        self.message_list = ['my commit', '42']
        self.path_list = ['file1.txt', 'file2.txt']

        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_add_fail(self):
        self.setup_step(
            self.stepClass(workdir='wkdir', paths=self.path_list, messages=self.message_list))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'symbolic-ref', 'HEAD'])
            .stdout('refs/head/myBranch')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'add', 'file1.txt', 'file2.txt'])
            .exit(1)
        )
        self.expect_outcome(result=FAILURE)
        return self.run_step()

    def test_commit(self):
        self.setup_step(
            self.stepClass(workdir='wkdir', paths=self.path_list, messages=self.message_list))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'symbolic-ref', 'HEAD'])
            .stdout('refs/head/myBranch')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'add', 'file1.txt', 'file2.txt'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'commit', '-m', 'my commit', '-m', '42'])
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_commit_noverify(self):
        self.setup_step(
            self.stepClass(workdir='wkdir', paths=self.path_list, messages=self.message_list,
                           no_verify=True))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'symbolic-ref', 'HEAD'])
            .stdout('refs/head/myBranch')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'add', 'file1.txt', 'file2.txt'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'commit', '-m', 'my commit', '-m', '42', '--no-verify'])
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_commit_empty_disallow(self):
        self.setup_step(
            self.stepClass(workdir='wkdir', paths=self.path_list, messages=self.message_list,
                           emptyCommits='disallow'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'symbolic-ref', 'HEAD'])
            .stdout('refs/head/myBranch')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'add', 'file1.txt', 'file2.txt'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'commit', '-m', 'my commit', '-m', '42'])
            .exit(1)
        )
        self.expect_outcome(result=FAILURE)
        return self.run_step()

    def test_commit_empty_allow(self):
        self.setup_step(
            self.stepClass(workdir='wkdir', paths=self.path_list, messages=self.message_list,
                           emptyCommits='create-empty-commit'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'symbolic-ref', 'HEAD'])
            .stdout('refs/head/myBranch')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'add', 'file1.txt', 'file2.txt'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'commit', '-m', 'my commit', '-m', '42', '--allow-empty'])
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_commit_empty_ignore_withcommit(self):
        self.setup_step(
            self.stepClass(workdir='wkdir', paths=self.path_list, messages=self.message_list,
                           emptyCommits='ignore'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'symbolic-ref', 'HEAD'])
            .stdout('refs/head/myBranch')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'add', 'file1.txt', 'file2.txt'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'status', '--porcelain=v1'])
            .stdout('MM file2.txt\n?? file3.txt')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'commit', '-m', 'my commit', '-m', '42'])
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_commit_empty_ignore_withoutcommit(self):
        self.setup_step(
            self.stepClass(workdir='wkdir', paths=self.path_list, messages=self.message_list,
                           emptyCommits='ignore'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'symbolic-ref', 'HEAD'])
            .stdout('refs/head/myBranch')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'add', 'file1.txt', 'file2.txt'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'status', '--porcelain=v1'])
            .stdout('?? file3.txt')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_commit_empty_ignore_witherror(self):
        self.setup_step(
            self.stepClass(workdir='wkdir', paths=self.path_list, messages=self.message_list,
                           emptyCommits='ignore'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'symbolic-ref', 'HEAD'])
            .stdout('refs/head/myBranch')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'add', 'file1.txt', 'file2.txt'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'status', '--porcelain=v1'])
            .exit(1)
        )
        self.expect_outcome(result=FAILURE)
        return self.run_step()

    def test_detached_head(self):
        self.setup_step(
            self.stepClass(workdir='wkdir', paths=self.path_list, messages=self.message_list))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'symbolic-ref', 'HEAD'])
            .stdout('')
            .exit(1)
        )
        self.expect_outcome(result=FAILURE)
        return self.run_step()

    def test_config_no_files_arg(self):
        with self.assertRaisesConfigError(
                "GitCommit: must provide paths"):
            self.stepClass(workdir='wkdir', messages=self.message_list)

    def test_config_files_not_a_list(self):
        with self.assertRaisesConfigError(
                "GitCommit: paths must be a list"):
            self.stepClass(workdir='wkdir', paths="test.txt", messages=self.message_list)

    def test_config_no_messages_arg(self):
        with self.assertRaisesConfigError(
                "GitCommit: must provide messages"):
            self.stepClass(workdir='wkdir', paths=self.path_list)

    def test_config_messages_not_a_list(self):
        with self.assertRaisesConfigError(
                "GitCommit: messages must be a list"):
            self.stepClass(workdir='wkdir', paths=self.path_list, messages="my message")

    def test_raise_no_git(self):
        @defer.inlineCallbacks
        def _checkFeatureSupport(self):
            yield
            return False

        step = self.stepClass(workdir='wkdir', paths=self.path_list, messages=self.message_list)
        self.patch(self.stepClass, "checkFeatureSupport", _checkFeatureSupport)
        self.setup_step(step)
        self.expect_outcome(result=EXCEPTION)
        self.run_step()
        self.flushLoggedErrors(WorkerSetupError)
