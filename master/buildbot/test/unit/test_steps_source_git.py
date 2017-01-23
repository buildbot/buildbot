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

from __future__ import absolute_import
from __future__ import print_function

from twisted.internet import error
from twisted.python.reflect import namedModule
from twisted.trial import unittest

from buildbot.process import remotetransfer
from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SUCCESS
from buildbot.steps.source import git
from buildbot.test.fake.remotecommand import Expect
from buildbot.test.fake.remotecommand import ExpectRemoteRef
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.util import config
from buildbot.test.util import sourcesteps


class TestGit(sourcesteps.SourceStepMixin, config.ConfigErrorsMixin, unittest.TestCase):
    stepClass = git.Git

    def setUp(self):
        self.sourceName = self.stepClass.__name__
        return self.setUpSourceStep()

    def tearDown(self):
        return self.tearDownSourceStep()

    def test_mode_full_clean(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', ['.git'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_full_clean_win32path(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean'))
        self.build.path_module = namedModule('ntpath')
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file=r'wkdir\.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', ['.git'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_full_clean_timeout(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           timeout=1,
                           mode='full', method='clean'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1})
            + Expect.update('files', ['.git'])
            + 0,
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['git', 'clean', '-f', '-f', '-d'])
            + 0,
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'])
            + 0,
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_full_clean_patch(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean'),
            patch=(1, 'patch'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d', '-x'],
                        logEnviron=True)
            + 0,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', ['.git'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'])
            + 0,
            Expect('downloadFile', dict(blocksize=16384, maxsize=None,
                                        reader=ExpectRemoteRef(
                                            remotetransfer.StringFileReader),
                                        workerdest='.buildbot-diff', workdir='wkdir',
                                        mode=None))
            + 0,
            Expect('downloadFile', dict(blocksize=16384, maxsize=None,
                                        reader=ExpectRemoteRef(
                                            remotetransfer.StringFileReader),
                                        workerdest='.buildbot-patched', workdir='wkdir',
                                        mode=None))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'update-index', '--refresh'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'apply', '--index', '-p', '1'],
                        initialStdin='patch')
            + 0,
            Expect('rmdir', dict(dir='wkdir/.buildbot-diff',
                                 logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_full_clean_patch_worker_2_16(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean'),
            patch=(1, 'patch'),
            worker_version={'*': '2.16'})
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d', '-x'],
                        logEnviron=True)
            + 0,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', ['.git'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'])
            + 0,
            Expect('downloadFile', dict(blocksize=16384, maxsize=None,
                                        reader=ExpectRemoteRef(
                                            remotetransfer.StringFileReader),
                                        slavedest='.buildbot-diff', workdir='wkdir',
                                        mode=None))
            + 0,
            Expect('downloadFile', dict(blocksize=16384, maxsize=None,
                                        reader=ExpectRemoteRef(
                                            remotetransfer.StringFileReader),
                                        slavedest='.buildbot-patched', workdir='wkdir',
                                        mode=None))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'update-index', '--refresh'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'apply', '--index', '-p', '1'],
                        initialStdin='patch')
            + 0,
            Expect('rmdir', dict(dir='wkdir/.buildbot-diff',
                                 logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_full_clean_patch_fail(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean'),
            patch=(1, 'patch'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', ['.git'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'])
            + 0,
            Expect('downloadFile', dict(blocksize=16384, maxsize=None,
                                        reader=ExpectRemoteRef(
                                            remotetransfer.StringFileReader),
                                        workerdest='.buildbot-diff', workdir='wkdir',
                                        mode=None))
            + 0,
            Expect('downloadFile', dict(blocksize=16384, maxsize=None,
                                        reader=ExpectRemoteRef(
                                            remotetransfer.StringFileReader),
                                        workerdest='.buildbot-patched', workdir='wkdir',
                                        mode=None))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'update-index', '--refresh'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'apply', '--index', '-p', '1'],
                        initialStdin='patch')
            + 1,
        )
        self.expectOutcome(result=FAILURE)
        self.expectNoProperty('got_revision')
        return self.runStep()

    def test_mode_full_clean_branch(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean', branch='test-branch'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', ['.git'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'test-branch'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'])
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
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_full_clean_non_empty_builddir(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean', branch='test-branch'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', ['file1', 'file2'])
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone', '--branch', 'test-branch',
                                 'http://github.com/buildbot/buildbot.git', '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_full_clean_parsefail(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', ['.git'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'])
            + ExpectShell.log('stdio',
                              stderr="fatal: Could not parse object "
                              "'b08076bc71c7813038f2cefedff9c5b678d225a8'.\n")
            + 128,
        )
        self.expectOutcome(result=FAILURE)
        self.expectNoProperty('got_revision')
        return self.runStep()

    def test_mode_full_clean_no_existing_repo(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', [])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git', '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_mode_full_clean_no_existing_repo_with_reference(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean', reference='path/to/reference/repo'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', [])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone', '--reference', 'path/to/reference/repo',
                                 'http://github.com/buildbot/buildbot.git', '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_mode_full_clean_no_existing_repo_branch(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean', branch='test-branch'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', [])
            + 0,
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
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_mode_full_clean_no_existing_repo_with_origin(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean', origin='foo'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', [])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone', '--origin', 'foo',
                                 'http://github.com/buildbot/buildbot.git', '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_mode_full_clobber(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clobber', progress=True))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_full_clone_fails(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clobber', progress=True))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            + 1,  # clone fails
        )
        self.expectOutcome(result=FAILURE, state_string="update (failure)")
        self.expectNoProperty('got_revision')
        return self.runStep()

    def test_mode_full_clobber_branch(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clobber', progress=True, branch='test-branch'))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
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
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_full_clobber_no_branch_support(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clobber', progress=True, branch='test-branch'))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.5.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_incremental_oldworker(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental'))
        self.step.build.getWorkerCommandVersion = lambda cmd, oldversion: "2.15"
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file='wkdir/.git',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,

        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_incremental(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', ['.git'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,

        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_version_format(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5.1')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', ['.git'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,

        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_incremental_retry(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental', retry=(0, 1)))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', [])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.'])
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_incremental_branch(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental', branch='test-branch'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', ['.git'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'test-branch'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'])
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
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_full_fresh(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='fresh'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', ['.git'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d', '-x'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_full_fresh_clean_fails(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='fresh'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', ['.git'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d', '-x'])
            + 1,  # clean fails -> clobber
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_incremental_given_revision(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental'), dict(
                revision='abcdef01',
            ))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', ['.git'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'cat-file', '-e', 'abcdef01'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'abcdef01', '--'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_incremental_given_revision_not_exists(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental'), dict(
                revision='abcdef01',
            ))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', ['.git'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'cat-file', '-e', 'abcdef01'])
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'abcdef01', '--'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_full_fresh_submodule(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='fresh', submodules=True))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', ['.git'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d', '-x'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'submodule', 'sync'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'submodule', 'update', '--init', '--recursive', '--force'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'submodule', 'foreach', '--recursive', 'git', 'clean',
                                 '-f', '-f', '-d', '-x'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_full_fresh_submodule_v1_7_8(self):
        """This tests the same as test_mode_full_fresh_submodule, but the
        "submodule update" command should be different for Git v1.7.8+."""
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='fresh', submodules=True))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.8')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', ['.git'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d', '-x'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'submodule', 'sync'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'submodule', 'update', '--init', '--recursive',
                                 '--force', '--checkout'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'submodule', 'foreach', '--recursive', 'git', 'clean',
                                 '-f', '-f', '-d', '-x'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_full_clobber_shallow(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clobber', shallow=True))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone', '--depth', '1',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_full_clobber_shallow_depth(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clobber', shallow="100"))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone', '--depth', '100',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_full_clobber_no_shallow(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clobber'))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_incremental_retryFetch(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental', retryFetch=True))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', ['.git'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'])
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_incremental_retryFetch_branch(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental', retryFetch=True, branch='test-branch'))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', ['.git'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'test-branch'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'])
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'test-branch'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'])
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
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_incremental_clobberOnFailure(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental', clobberOnFailure=True))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', ['.git'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'])
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_incremental_clobberOnFailure_branch(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental', clobberOnFailure=True, branch='test-branch'))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', ['.git'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'test-branch'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'])
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
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
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_full_copy(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='copy'))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200)),
            Expect('listdir', {'dir': 'source', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', ['.git'])
            + 0,
            ExpectShell(workdir='source',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='source',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'])
            + 0,
            Expect('cpdir', {'fromdir': 'source', 'todir': 'wkdir',
                             'logEnviron': True, 'timeout': 1200})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_full_copy_shallow(self):
        self.assertRaisesConfigError("shallow only possible with mode 'full' and method 'clobber'", lambda:
                                     self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                                                    mode='full', method='copy', shallow=True))

    def test_mode_incremental_no_existing_repo(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', [])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git', '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,

        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_incremental_no_existing_repo_oldworker(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental'))
        self.step.build.getWorkerCommandVersion = lambda cmd, oldversion: "2.15"
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file='wkdir/.git',
                                logEnviron=True))
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git', '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,

        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_full_clobber_given_revision(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clobber', progress=True), dict(
                revision='abcdef01',
            ))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'abcdef01', '--'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_revparse_failure(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clobber', progress=True), dict(
                revision='abcdef01',
            ))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'abcdef01', '--'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ada95a1d')  # too short
            + 0,
        )
        self.expectOutcome(result=FAILURE)
        self.expectNoProperty('got_revision')
        return self.runStep()

    def test_mode_full_clobber_submodule(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clobber', submodules=True))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
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
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_repourl(self):
        self.assertRaisesConfigError("must provide repourl", lambda:
                                     self.stepClass(mode="full"))

    def test_mode_full_fresh_revision(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='fresh', progress=True), dict(
                revision='abcdef01',
            ))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', [])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'abcdef01', '--'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_full_fresh_retry(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='fresh', retry=(0, 2)))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', [])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git', '.'])
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.'])
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_full_fresh_clobberOnFailure(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='fresh', clobberOnFailure=True))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', [])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git', '.'])
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_full_no_method(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', ['.git'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d', '-x'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_full_with_env(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', env={'abc': '123'}))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'],
                        env={'abc': '123'})
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', ['.git'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d', '-x'],
                        env={'abc': '123'})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'],
                        env={'abc': '123'})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'],
                        env={'abc': '123'})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'],
                        env={'abc': '123'})
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_mode_full_logEnviron(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', logEnviron=False))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'],
                        logEnviron=False)
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=False))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': False,
                               'timeout': 1200})
            + Expect.update('files', ['.git'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d', '-x'],
                        logEnviron=False)
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'],
                        logEnviron=False)
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'],
                        logEnviron=False)
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'],
                        logEnviron=False)
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_wkdir_doesnt_exist(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        return self.runStep()

    def test_getDescription(self):
        # clone of: test_mode_incremental
        # only difference is to set the getDescription property

        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental',
                           getDescription=True))
        self.expectCommands(
            # copied from test_mode_incremental:
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', ['.git'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,

            # plus this to test describe:
            ExpectShell(workdir='wkdir',
                        command=['git', 'describe', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='Tag-1234')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        self.expectProperty('commit-description', 'Tag-1234', self.sourceName)
        return self.runStep()

    def test_getDescription_failed(self):
        # clone of: test_mode_incremental
        # only difference is to set the getDescription property

        # this tests when 'git describe' fails; for example, there are no
        # tags in the repository

        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='incremental',
                           getDescription=True))
        self.expectCommands(
            # copied from test_mode_incremental:
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', ['.git'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,

            # plus this to test describe:
            ExpectShell(workdir='wkdir',
                        command=['git', 'describe', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='')
            + 128,  # error, but it's suppressed
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
        self.expectNoProperty('commit-description')
        return self.runStep()

    def setup_getDescription_test(self, setup_args, output_args,
                                  expect_head=True, codebase=None):
        # clone of: test_mode_full_clobber
        # only difference is to set the getDescription property

        kwargs = {}
        if codebase is not None:
            kwargs.update(codebase=codebase)

        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clobber', progress=True,
                           getDescription=setup_args,
                           **kwargs))

        self.expectCommands(
            # copied from test_mode_full_clobber:
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clone',
                                 'http://github.com/buildbot/buildbot.git',
                                 '.', '--progress'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,

            # plus this to test describe:
            ExpectShell(workdir='wkdir',
                        command=['git', 'describe'] +
                                output_args +
                                (['HEAD'] if expect_head else []))
            + ExpectShell.log('stdio',
                              stdout='Tag-1234')
            + 0,
        )

        if codebase:
            self.expectOutcome(result=SUCCESS,
                               state_string="update " + codebase)
            self.expectProperty(
                'got_revision', {codebase: 'f6ad368298bd941e934a41f3babc827b2aa95a1d'}, self.sourceName)
            self.expectProperty(
                'commit-description', {codebase: 'Tag-1234'}, self.sourceName)
        else:
            self.expectOutcome(result=SUCCESS,
                               state_string="update")
            self.expectProperty(
                'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName)
            self.expectProperty('commit-description', 'Tag-1234', self.sourceName)

    def test_getDescription_empty_dict(self):
        self.setup_getDescription_test(
            setup_args={},
            output_args=[]
        )
        return self.runStep()

    def test_getDescription_empty_dict_with_codebase(self):
        self.setup_getDescription_test(
            setup_args={},
            output_args=[],
            codebase='baz'
        )
        return self.runStep()

    def test_getDescription_match(self):
        self.setup_getDescription_test(
            setup_args={'match': 'stuff-*'},
            output_args=['--match', 'stuff-*']
        )
        return self.runStep()

    def test_getDescription_match_false(self):
        self.setup_getDescription_test(
            setup_args={'match': None},
            output_args=[]
        )
        return self.runStep()

    def test_getDescription_tags(self):
        self.setup_getDescription_test(
            setup_args={'tags': True},
            output_args=['--tags']
        )
        return self.runStep()

    def test_getDescription_tags_false(self):
        self.setup_getDescription_test(
            setup_args={'tags': False},
            output_args=[]
        )
        return self.runStep()

    def test_getDescription_all(self):
        self.setup_getDescription_test(
            setup_args={'all': True},
            output_args=['--all']
        )
        return self.runStep()

    def test_getDescription_all_false(self):
        self.setup_getDescription_test(
            setup_args={'all': False},
            output_args=[]
        )
        return self.runStep()

    def test_getDescription_abbrev(self):
        self.setup_getDescription_test(
            setup_args={'abbrev': 7},
            output_args=['--abbrev=7']
        )
        return self.runStep()

    def test_getDescription_abbrev_zero(self):
        self.setup_getDescription_test(
            setup_args={'abbrev': 0},
            output_args=['--abbrev=0']
        )
        return self.runStep()

    def test_getDescription_abbrev_false(self):
        self.setup_getDescription_test(
            setup_args={'abbrev': False},
            output_args=[]
        )
        return self.runStep()

    def test_getDescription_dirty(self):
        self.setup_getDescription_test(
            setup_args={'dirty': True},
            output_args=['--dirty'],
            expect_head=False
        )
        return self.runStep()

    def test_getDescription_dirty_empty_str(self):
        self.setup_getDescription_test(
            setup_args={'dirty': ''},
            output_args=['--dirty'],
            expect_head=False
        )
        return self.runStep()

    def test_getDescription_dirty_str(self):
        self.setup_getDescription_test(
            setup_args={'dirty': 'foo'},
            output_args=['--dirty=foo'],
            expect_head=False
        )
        return self.runStep()

    def test_getDescription_dirty_false(self):
        self.setup_getDescription_test(
            setup_args={'dirty': False},
            output_args=[],
            expect_head=True
        )
        return self.runStep()

    def test_getDescription_dirty_none(self):
        self.setup_getDescription_test(
            setup_args={'dirty': None},
            output_args=[],
            expect_head=True
        )
        return self.runStep()

    def test_getDescription_contains(self):
        self.setup_getDescription_test(
            setup_args={'contains': True},
            output_args=['--contains']
        )
        return self.runStep()

    def test_getDescription_contains_false(self):
        self.setup_getDescription_test(
            setup_args={'contains': False},
            output_args=[]
        )
        return self.runStep()

    def test_getDescription_candidates(self):
        self.setup_getDescription_test(
            setup_args={'candidates': 7},
            output_args=['--candidates=7']
        )
        return self.runStep()

    def test_getDescription_candidates_zero(self):
        self.setup_getDescription_test(
            setup_args={'candidates': 0},
            output_args=['--candidates=0']
        )
        return self.runStep()

    def test_getDescription_candidates_false(self):
        self.setup_getDescription_test(
            setup_args={'candidates': False},
            output_args=[]
        )
        return self.runStep()

    def test_getDescription_exact_match(self):
        self.setup_getDescription_test(
            setup_args={'exact-match': True},
            output_args=['--exact-match']
        )
        return self.runStep()

    def test_getDescription_exact_match_false(self):
        self.setup_getDescription_test(
            setup_args={'exact-match': False},
            output_args=[]
        )
        return self.runStep()

    def test_getDescription_debug(self):
        self.setup_getDescription_test(
            setup_args={'debug': True},
            output_args=['--debug']
        )
        return self.runStep()

    def test_getDescription_debug_false(self):
        self.setup_getDescription_test(
            setup_args={'debug': False},
            output_args=[]
        )
        return self.runStep()

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
        return self.runStep()

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
        return self.runStep()

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
        return self.runStep()

    def test_config_option(self):
        name = 'url.http://github.com.insteadOf'
        value = 'blahblah'
        self.setupStep(
            self.stepClass(repourl='%s/buildbot/buildbot.git' % (value,),
                           mode='full', method='clean',
                           config={name: value}))
        prefix = ['git', '-c', '%s=%s' % (name, value)]
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=prefix + ['--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', ['.git'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=prefix + ['clean', '-f', '-f', '-d'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=prefix + ['fetch', '-t',
                                          '%s/buildbot/buildbot.git' % (
                                              value,),
                                          'HEAD'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=prefix + ['reset', '--hard',
                                          'FETCH_HEAD', '--'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=prefix + ['rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_worker_connection_lost(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + ('err', error.ConnectionLost())
        )
        self.expectOutcome(result=RETRY, state_string="update (retry)")
        return self.runStep()
