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

from buildbot.status.results import FAILURE
from buildbot.status.results import RETRY
from buildbot.status.results import SUCCESS
from buildbot.steps.source import mtn
from buildbot.steps.transfer import _FileReader
from buildbot.test.fake.remotecommand import Expect
from buildbot.test.fake.remotecommand import ExpectRemoteRef
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.util import config
from buildbot.test.util import sourcesteps
from twisted.internet import error


class TestMonotone(sourcesteps.SourceStepMixin, config.ConfigErrorsMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpSourceStep()

    def tearDown(self):
        return self.tearDownSourceStep()

    def test_mode_full_clean(self):
        self.setupStep(
            mtn.Monotone(repourl='mtn://localhost/monotone',
                         mode='full', method='clean', branch='master'))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['mtn', '--version'])
            + ExpectShell.log('stdio',
                              stdout='monotone 1.0 (base revision: a7c3a1d9de1ba7a62c9dd9efee17252234bb502c)')
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'db', 'info', '--db', '../db.mtn'])
            + ExpectShell.log('stdio',
                              stdout='')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file='wkdir/_MTN',
                                logEnviron=True))
            + 0,
            Expect('stat', dict(file='db.mtn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'ls', 'unknown'])
            + ExpectShell.log('stdio',
                              stdout='file1\nfile2')
            + 0,
            Expect('rmdir', dict(dir=['wkdir/file1', 'wkdir/file2'],
                                 logEnviron=True, timeout=1200))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'pull', 'mtn://localhost/monotone?master',
                                 '--db=../db.mtn', '--ticker=dot'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'update', '--db=../db.mtn', '-r', 'h:master', '-b', 'master'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'automate', 'select', 'w:'])
            + ExpectShell.log('stdio',
                              stdout='95215e2a9a9f8b6f5c9664e3807cd34617ea928c')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        self.expectProperty('got_revision', '95215e2a9a9f8b6f5c9664e3807cd34617ea928c', 'Monotone')
        return self.runStep()

    def test_mode_full_clean_patch(self):
        self.setupStep(
            mtn.Monotone(repourl='mtn://localhost/monotone',
                         mode='full', method='clean', branch='master'),
            patch=(1, 'patch'))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['mtn', '--version'])
            + ExpectShell.log('stdio',
                              stdout='monotone 1.0 (base revision: a7c3a1d9de1ba7a62c9dd9efee17252234bb502c)')
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'db', 'info', '--db', '../db.mtn'])
            + ExpectShell.log('stdio',
                              stdout='')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file='wkdir/_MTN',
                                logEnviron=True))
            + 0,
            Expect('stat', dict(file='db.mtn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'ls', 'unknown'])
            + ExpectShell.log('stdio',
                              stdout='file1\nfile2')
            + 0,
            Expect('rmdir', dict(dir=['wkdir/file1', 'wkdir/file2'],
                                 logEnviron=True, timeout=1200))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'pull', 'mtn://localhost/monotone?master',
                                 '--db=../db.mtn', '--ticker=dot'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'update', '--db=../db.mtn', '-r', 'h:master', '-b', 'master'])
            + 0,
            Expect('downloadFile', dict(blocksize=16384, maxsize=None,
                                        reader=ExpectRemoteRef(_FileReader),
                                        slavedest='.buildbot-diff', workdir='wkdir',
                                        mode=None))
            + 0,
            Expect('downloadFile', dict(blocksize=16384, maxsize=None,
                                        reader=ExpectRemoteRef(_FileReader),
                                        slavedest='.buildbot-patched', workdir='wkdir',
                                        mode=None))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['patch', '-p1', '--remove-empty-files',
                                 '--force', '--forward', '-i', '.buildbot-diff'])
            + 0,
            Expect('rmdir', dict(dir='wkdir/.buildbot-diff',
                                 logEnviron=True, timeout=1200))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'automate', 'select', 'w:'])
            + ExpectShell.log('stdio',
                              stdout='95215e2a9a9f8b6f5c9664e3807cd34617ea928c')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        self.expectProperty('got_revision', '95215e2a9a9f8b6f5c9664e3807cd34617ea928c', 'Monotone')
        return self.runStep()

    def test_mode_full_clean_patch_fail(self):
        self.setupStep(
            mtn.Monotone(repourl='mtn://localhost/monotone',
                         mode='full', method='clean', branch='master'),
            patch=(1, 'patch'))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['mtn', '--version'])
            + ExpectShell.log('stdio',
                              stdout='monotone 1.0 (base revision: a7c3a1d9de1ba7a62c9dd9efee17252234bb502c)')
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'db', 'info', '--db', '../db.mtn'])
            + ExpectShell.log('stdio',
                              stdout='')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file='wkdir/_MTN',
                                logEnviron=True))
            + 0,
            Expect('stat', dict(file='db.mtn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'ls', 'unknown'])
            + ExpectShell.log('stdio',
                              stdout='file1\nfile2')
            + 0,
            Expect('rmdir', dict(dir=['wkdir/file1', 'wkdir/file2'],
                                 logEnviron=True, timeout=1200))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'pull', 'mtn://localhost/monotone?master',
                                 '--db=../db.mtn', '--ticker=dot'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'update', '--db=../db.mtn', '-r', 'h:master', '-b', 'master'])
            + 0,
            Expect('downloadFile', dict(blocksize=16384, maxsize=None,
                                        reader=ExpectRemoteRef(_FileReader),
                                        slavedest='.buildbot-diff', workdir='wkdir',
                                        mode=None))
            + 0,
            Expect('downloadFile', dict(blocksize=16384, maxsize=None,
                                        reader=ExpectRemoteRef(_FileReader),
                                        slavedest='.buildbot-patched', workdir='wkdir',
                                        mode=None))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['patch', '-p1', '--remove-empty-files',
                                 '--force', '--forward', '-i', '.buildbot-diff'])
            + 0,
            Expect('rmdir', dict(dir='wkdir/.buildbot-diff',
                                 logEnviron=True, timeout=1200))
            + 1,
        )
        self.expectOutcome(result=FAILURE, status_text=["updating"])
        return self.runStep()

    def test_mode_full_clean_no_existing_repo(self):
        self.setupStep(
            mtn.Monotone(repourl='mtn://localhost/monotone',
                         mode='full', method='clean', branch='master'))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['mtn', '--version'])
            + ExpectShell.log('stdio',
                              stdout='monotone 1.0 (base revision: a7c3a1d9de1ba7a62c9dd9efee17252234bb502c)')
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'db', 'info', '--db', '../db.mtn'])
            + ExpectShell.log('stdio',
                              stdout='')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file='wkdir/_MTN',
                                logEnviron=True))
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'db', 'init', '--db', '../db.mtn'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'pull', 'mtn://localhost/monotone?master',
                                 '--db=../db.mtn', '--ticker=dot'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'checkout', '.', '--db=../db.mtn', '--branch', 'master'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'automate', 'select', 'w:'])
            + ExpectShell.log('stdio',
                              stdout='95215e2a9a9f8b6f5c9664e3807cd34617ea928c')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        self.expectProperty('got_revision', '95215e2a9a9f8b6f5c9664e3807cd34617ea928c', 'Monotone')
        return self.runStep()

    def test_mode_full_clobber(self):
        self.setupStep(
            mtn.Monotone(repourl='mtn://localhost/monotone',
                         mode='full', method='clobber', branch='master'))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['mtn', '--version'])
            + ExpectShell.log('stdio',
                              stdout='monotone 1.0 (base revision: a7c3a1d9de1ba7a62c9dd9efee17252234bb502c)')
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'db', 'info', '--db', '../db.mtn'])
            + ExpectShell.log('stdio',
                              stdout='')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True, timeout=1200))
            + 0,
            Expect('rmdir', dict(dir='db.mtn',
                                 logEnviron=True, timeout=1200))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'db', 'init', '--db', '../db.mtn'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'pull', 'mtn://localhost/monotone?master',
                                 '--db=../db.mtn', '--ticker=dot'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'checkout', '.', '--db=../db.mtn', '--branch', 'master'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'automate', 'select', 'w:'])
            + ExpectShell.log('stdio',
                              stdout='95215e2a9a9f8b6f5c9664e3807cd34617ea928c')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        self.expectProperty('got_revision', '95215e2a9a9f8b6f5c9664e3807cd34617ea928c', 'Monotone')
        return self.runStep()

    def test_mode_incremental_repo_non_existing(self):
        self.setupStep(
            mtn.Monotone(repourl='mtn://localhost/monotone',
                         mode='incremental', branch='master'))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['mtn', '--version'])
            + ExpectShell.log('stdio',
                              stdout='monotone 1.0 (base revision: a7c3a1d9de1ba7a62c9dd9efee17252234bb502c)')
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'db', 'info', '--db', '../db.mtn'])
            + ExpectShell.log('stdio',
                              stdout='')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file='wkdir/_MTN',
                                logEnviron=True))
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'db', 'init', '--db', '../db.mtn'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'pull', 'mtn://localhost/monotone?master',
                                 '--db=../db.mtn', '--ticker=dot'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'checkout', '.', '--db=../db.mtn', '--branch', 'master'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'automate', 'select', 'w:'])
            + ExpectShell.log('stdio',
                              stdout='95215e2a9a9f8b6f5c9664e3807cd34617ea928c')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        self.expectProperty('got_revision', '95215e2a9a9f8b6f5c9664e3807cd34617ea928c', 'Monotone')
        return self.runStep()

    def test_mode_incremental(self):
        self.setupStep(
            mtn.Monotone(repourl='mtn://localhost/monotone',
                         mode='incremental', branch='master'))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['mtn', '--version'])
            + ExpectShell.log('stdio',
                              stdout='monotone 1.0 (base revision: a7c3a1d9de1ba7a62c9dd9efee17252234bb502c)')
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'db', 'info', '--db', '../db.mtn'])
            + ExpectShell.log('stdio',
                              stdout='')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file='wkdir/_MTN',
                                logEnviron=True))
            + 0,
            Expect('stat', dict(file='db.mtn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'pull', 'mtn://localhost/monotone?master',
                                 '--db=../db.mtn', '--ticker=dot'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'update', '--db=../db.mtn', '-r', 'h:master', '-b', 'master'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'automate', 'select', 'w:'])
            + ExpectShell.log('stdio',
                              stdout='95215e2a9a9f8b6f5c9664e3807cd34617ea928c')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        self.expectProperty('got_revision', '95215e2a9a9f8b6f5c9664e3807cd34617ea928c', 'Monotone')
        return self.runStep()

    def test_mode_incremental_retry(self):
        self.setupStep(
            mtn.Monotone(repourl='mtn://localhost/monotone',
                         mode='incremental', branch='master', retry=(0, 1)))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['mtn', '--version'])
            + ExpectShell.log('stdio',
                              stdout='monotone 1.0 (base revision: a7c3a1d9de1ba7a62c9dd9efee17252234bb502c)')
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'db', 'info', '--db', '../db.mtn'])
            + ExpectShell.log('stdio',
                              stdout='')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file='wkdir/_MTN',
                                logEnviron=True))
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'db', 'init', '--db', '../db.mtn'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'pull', 'mtn://localhost/monotone?master',
                                 '--db=../db.mtn', '--ticker=dot'])
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True, timeout=1200))
            + 0,
            Expect('rmdir', dict(dir='db.mtn',
                                 logEnviron=True, timeout=1200))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'db', 'init', '--db', '../db.mtn'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'pull', 'mtn://localhost/monotone?master',
                                 '--db=../db.mtn', '--ticker=dot'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'checkout', '.', '--db=../db.mtn', '--branch', 'master'])
            + 0,

            ExpectShell(workdir='wkdir',
                        command=['mtn', 'automate', 'select', 'w:'])
            + ExpectShell.log('stdio',
                              stdout='95215e2a9a9f8b6f5c9664e3807cd34617ea928c')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        self.expectProperty('got_revision', '95215e2a9a9f8b6f5c9664e3807cd34617ea928c', 'Monotone')
        return self.runStep()

    def test_mode_full_fresh(self):
        self.setupStep(
            mtn.Monotone(repourl='mtn://localhost/monotone',
                         mode='full', method='fresh', branch='master'))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['mtn', '--version'])
            + ExpectShell.log('stdio',
                              stdout='monotone 1.0 (base revision: a7c3a1d9de1ba7a62c9dd9efee17252234bb502c)')
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'db', 'info', '--db', '../db.mtn'])
            + ExpectShell.log('stdio',
                              stdout='')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file='wkdir/_MTN',
                                logEnviron=True))
            + 0,
            Expect('stat', dict(file='db.mtn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'ls', 'unknown'])
            + ExpectShell.log('stdio',
                              stdout='file1\nfile2')
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'ls', 'ignored'])
            + ExpectShell.log('stdio',
                              stdout='file3\nfile4')
            + 0,
            Expect('rmdir', dict(dir=['wkdir/file1', 'wkdir/file2', 'wkdir/file3', 'wkdir/file4'],
                                 logEnviron=True, timeout=1200))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'pull', 'mtn://localhost/monotone?master',
                                 '--db=../db.mtn', '--ticker=dot'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'update', '--db=../db.mtn', '-r', 'h:master', '-b', 'master'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'automate', 'select', 'w:'])
            + ExpectShell.log('stdio',
                              stdout='95215e2a9a9f8b6f5c9664e3807cd34617ea928c')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        self.expectProperty('got_revision', '95215e2a9a9f8b6f5c9664e3807cd34617ea928c', 'Monotone')
        return self.runStep()

    def test_mode_incremental_given_revision(self):
        self.setupStep(
            mtn.Monotone(repourl='mtn://localhost/monotone',
                         mode='full', method='clean', branch='master'),
            dict(revision='abcdef01',))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['mtn', '--version'])
            + ExpectShell.log('stdio',
                              stdout='monotone 1.0 (base revision: a7c3a1d9de1ba7a62c9dd9efee17252234bb502c)')
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'db', 'info', '--db', '../db.mtn'])
            + ExpectShell.log('stdio',
                              stdout='')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file='wkdir/_MTN',
                                logEnviron=True))
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'db', 'init', '--db', '../db.mtn'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'pull', 'mtn://localhost/monotone?master',
                                 '--db=../db.mtn', '--ticker=dot'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'checkout', '.', '--db=../db.mtn',
                                 '--revision', 'abcdef01', '--branch', 'master'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'automate', 'select', 'w:'])
            + ExpectShell.log('stdio',
                              stdout='95215e2a9a9f8b6f5c9664e3807cd34617ea928c')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        self.expectProperty('got_revision', '95215e2a9a9f8b6f5c9664e3807cd34617ea928c', 'Monotone')
        return self.runStep()

    def test_mode_full_copy(self):
        self.setupStep(
            mtn.Monotone(repourl='mtn://localhost/monotone',
                         mode='full', method='copy', branch='master'))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['mtn', '--version'])
            + ExpectShell.log('stdio',
                              stdout='monotone 1.0 (base revision: a7c3a1d9de1ba7a62c9dd9efee17252234bb502c)')
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'db', 'info', '--db', '../db.mtn'])
            + ExpectShell.log('stdio',
                              stdout='')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
            + 0,
            Expect('stat', dict(file='source/_MTN',
                                logEnviron=True))
            + 0,
            Expect('stat', dict(file='db.mtn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='source',
                        command=['mtn', 'pull', 'mtn://localhost/monotone?master',
                                 '--db=../db.mtn', '--ticker=dot'])
            + 0,
            ExpectShell(workdir='source',
                        command=['mtn', 'update', '--db=../db.mtn', '-r', 'h:master',
                                 '-b', 'master'])
            + 0,
            Expect('cpdir', {'fromdir': 'source', 'todir': 'build',
                             'logEnviron': True, 'timeout': 1200})
            + 0,
            ExpectShell(workdir='build',
                        command=['mtn', 'automate', 'select', 'w:'])
            + ExpectShell.log('stdio',
                              stdout='95215e2a9a9f8b6f5c9664e3807cd34617ea928c')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        self.expectProperty('got_revision', '95215e2a9a9f8b6f5c9664e3807cd34617ea928c', 'Monotone')
        return self.runStep()

    def test_mode_full_no_method(self):
        self.setupStep(
            mtn.Monotone(repourl='mtn://localhost/monotone',
                         mode='full', branch='master'))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['mtn', '--version'])
            + ExpectShell.log('stdio',
                              stdout='monotone 1.0 (base revision: a7c3a1d9de1ba7a62c9dd9efee17252234bb502c)')
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'db', 'info', '--db', '../db.mtn'])
            + ExpectShell.log('stdio',
                              stdout='')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
            + 0,
            Expect('stat', dict(file='source/_MTN',
                                logEnviron=True))
            + 0,
            Expect('stat', dict(file='db.mtn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='source',
                        command=['mtn', 'pull', 'mtn://localhost/monotone?master',
                                 '--db=../db.mtn', '--ticker=dot'])
            + 0,
            ExpectShell(workdir='source',
                        command=['mtn', 'update', '--db=../db.mtn', '-r', 'h:master',
                                 '-b', 'master'])
            + 0,
            Expect('cpdir', {'fromdir': 'source', 'todir': 'build',
                             'logEnviron': True, 'timeout': 1200})
            + 0,
            ExpectShell(workdir='build',
                        command=['mtn', 'automate', 'select', 'w:'])
            + ExpectShell.log('stdio',
                              stdout='95215e2a9a9f8b6f5c9664e3807cd34617ea928c')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        self.expectProperty('got_revision', '95215e2a9a9f8b6f5c9664e3807cd34617ea928c', 'Monotone')
        return self.runStep()

    def test_incorrect_method(self):
        self.assertRaisesConfigError("Invalid method for mode == full", lambda:
                                     mtn.Monotone(repourl='mtn://localhost/monotone',
                                                  mode='full', method='wrongmethod', branch='master'))

    def test_incremental_invalid_method(self):
        self.assertRaisesConfigError("Incremental mode does not require method", lambda:
                                     mtn.Monotone(repourl='mtn://localhost/monotone',
                                                  mode='incremental', method='fresh', branch="master"))

    def test_repourl(self):
        self.assertRaisesConfigError("must provide repourl", lambda:
                                     mtn.Monotone(mode="full", branch="master"))

    def test_branch(self):
        self.assertRaisesConfigError("must provide branch", lambda:
                                     mtn.Monotone(repourl='mtn://localhost/monotone', mode="full",))

    def test_mode_incremental_patched(self):
        self.setupStep(
            mtn.Monotone(repourl='mtn://localhost/monotone',
                         mode='incremental', branch='master'))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['mtn', '--version'])
            + ExpectShell.log('stdio',
                              stdout='monotone 1.0 (base revision: a7c3a1d9de1ba7a62c9dd9efee17252234bb502c)')
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'db', 'info', '--db', '../db.mtn'])
            + ExpectShell.log('stdio',
                              stdout='')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'ls', 'unknown'])
            + ExpectShell.log('stdio',
                              stdout='file1\nfile2')
            + 0,
            Expect('rmdir', dict(dir=['wkdir/file1', 'wkdir/file2'],
                                 logEnviron=True, timeout=1200))
            + 0,
            Expect('stat', dict(file='wkdir/_MTN',
                                logEnviron=True))
            + 0,
            Expect('stat', dict(file='db.mtn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'pull', 'mtn://localhost/monotone?master',
                                 '--db=../db.mtn', '--ticker=dot'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'update', '--db=../db.mtn', '-r', 'h:master', '-b', 'master'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mtn', 'automate', 'select', 'w:'])
            + ExpectShell.log('stdio',
                              stdout='95215e2a9a9f8b6f5c9664e3807cd34617ea928c')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        self.expectProperty('got_revision', '95215e2a9a9f8b6f5c9664e3807cd34617ea928c', 'Monotone')
        return self.runStep()

    def test_slave_connection_lost(self):
        self.setupStep(
            mtn.Monotone(repourl='mtn://localhost/monotone',
                         mode='full', method='clean', branch='master'))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['mtn', '--version'])
            + ExpectShell.log('stdio',
                              stdout='monotone 1.0 (base revision: a7c3a1d9de1ba7a62c9dd9efee17252234bb502c)')
            + ('err', error.ConnectionLost()),
        )
        self.expectOutcome(result=RETRY,
                           status_text=["update", "exception", "slave", "lost"])
        return self.runStep()
