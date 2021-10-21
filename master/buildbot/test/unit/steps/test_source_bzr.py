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

from twisted.internet import error
from twisted.python.reflect import namedModule
from twisted.trial import unittest

from buildbot.process import remotetransfer
from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SUCCESS
from buildbot.steps.source import bzr
from buildbot.test.fake.remotecommand import ExpectCpdir
from buildbot.test.fake.remotecommand import ExpectDownloadFile
from buildbot.test.fake.remotecommand import ExpectRemoteRef
from buildbot.test.fake.remotecommand import ExpectRmdir
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.fake.remotecommand import ExpectStat
from buildbot.test.util import sourcesteps
from buildbot.test.util.misc import TestReactorMixin


class TestBzr(sourcesteps.SourceStepMixin, TestReactorMixin,
              unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        return self.setUpSourceStep()

    def tearDown(self):
        return self.tearDownSourceStep()

    def test_mode_full(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='fresh'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.bzr', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'clean-tree', '--force'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'update'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            .stdout('100')
            .exit(0)
        )
        self.expectOutcome(result=SUCCESS, state_string="update")
        self.expectProperty('got_revision', '100', 'Bzr')
        return self.runStep()

    def test_mode_full_win32path(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='fresh'))
        self.build.path_module = namedModule('ntpath')
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file=r'wkdir\.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file=r'wkdir\.bzr', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'clean-tree', '--force'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'update'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            .stdout('100')
            .exit(0)
        )
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_mode_full_timeout(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='fresh', timeout=1))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.bzr', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['bzr', 'clean-tree', '--force'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['bzr', 'update'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            .stdout('100')
            .exit(0)
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'Bzr')
        return self.runStep()

    def test_mode_full_revision(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='fresh'),
            args=dict(revision='3730'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.bzr', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'clean-tree', '--force'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'update', '-r', '3730'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            .stdout('100')
            .exit(0)
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'Bzr')
        return self.runStep()

    def test_mode_full_clean(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='clean'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.bzr', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'clean-tree', '--ignored', '--force'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'update'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            .stdout('100')
            .exit(0)
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'Bzr')
        return self.runStep()

    def test_mode_full_clean_patched(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='clean'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(0),
            # clean up the applied patch
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'clean-tree', '--ignored', '--force'])
            .exit(0),
            ExpectStat(file='wkdir/.bzr', logEnviron=True)
            .exit(0),
            # this clean is from 'mode=clean'
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'clean-tree', '--ignored', '--force'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'update'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            .stdout('100')
            .exit(0)
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'Bzr')
        return self.runStep()

    def test_mode_full_clean_patch(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='clean'), patch=(1, 'patch'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.bzr', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'clean-tree', '--ignored', '--force'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'update'])
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.FileReader),
                               workerdest='.buildbot-diff', workdir='wkdir', mode=None)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.FileReader),
                               workerdest='.buildbot-patched', workdir='wkdir', mode=None)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['patch', '-p1', '--remove-empty-files',
                                 '--force', '--forward', '-i', '.buildbot-diff'])
            .exit(0),
            ExpectRmdir(dir='wkdir/.buildbot-diff', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            .stdout('100')
            .exit(0)
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'Bzr')
        return self.runStep()

    def test_mode_full_clean_patch_worker_2_16(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='clean'), patch=(1, 'patch'),
            worker_version={'*': '2.16'})
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.bzr', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'clean-tree', '--ignored', '--force'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'update'])
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.FileReader),
                               slavedest='.buildbot-diff', workdir='wkdir', mode=None)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.FileReader),
                               slavedest='.buildbot-patched', workdir='wkdir', mode=None)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['patch', '-p1', '--remove-empty-files',
                                 '--force', '--forward', '-i', '.buildbot-diff'])
            .exit(0),
            ExpectRmdir(dir='wkdir/.buildbot-diff', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            .stdout('100')
            .exit(0)
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'Bzr')
        return self.runStep()

    def test_mode_full_clean_revision(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='clean'),
            args=dict(revision='2345'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.bzr', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'clean-tree', '--ignored', '--force'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'update', '-r', '2345'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            .stdout('100')
            .exit(0)
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'Bzr')
        return self.runStep()

    def test_mode_full_fresh(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='fresh'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.bzr', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'clean-tree', '--force'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'update'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            .stdout('100')
            .exit(0)
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'Bzr')
        return self.runStep()

    def test_mode_full_clobber(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='clobber'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'checkout',
                                 'http://bzr.squid-cache.org/bzr/squid3/trunk', '.'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            .stdout('100')
            .exit(0)
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'Bzr')
        return self.runStep()

    def test_mode_full_clobber_retry(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='clobber', retry=(0, 2)))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'checkout',
                                 'http://bzr.squid-cache.org/bzr/squid3/trunk', '.'])
            .exit(1),
            ExpectRmdir(dir='wkdir', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'checkout',
                                 'http://bzr.squid-cache.org/bzr/squid3/trunk', '.'])
            .exit(1),
            ExpectRmdir(dir='wkdir', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'checkout',
                                 'http://bzr.squid-cache.org/bzr/squid3/trunk', '.'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            .stdout('100')
            .exit(0)
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'Bzr')
        return self.runStep()

    def test_mode_full_clobber_revision(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='clobber'),
            args=dict(revision='3730'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'checkout',
                                 'http://bzr.squid-cache.org/bzr/squid3/trunk',
                                 '.', '-r', '3730'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            .stdout('100')
            .exit(0)
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'Bzr')
        return self.runStep()

    def test_mode_full_clobber_baseurl(self):
        self.setupStep(
            bzr.Bzr(baseURL='http://bzr.squid-cache.org/bzr/squid3',
                    defaultBranch='trunk', mode='full', method='clobber'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'checkout',
                                 os.path.join('http://bzr.squid-cache.org/bzr/squid3', 'trunk'),
                                 '.'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            .stdout('100')
            .exit(0)
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'Bzr')
        return self.runStep()

    def test_mode_full_clobber_baseurl_nodefault(self):
        self.setupStep(
            bzr.Bzr(baseURL='http://bzr.squid-cache.org/bzr/squid3',
                    defaultBranch='trunk', mode='full', method='clobber'),
            args=dict(branch='branches/SQUID_3_0'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'checkout',
                                 os.path.join('http://bzr.squid-cache.org/bzr/squid3',
                                 'branches/SQUID_3_0'), '.'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            .stdout('100')
            .exit(0)
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'Bzr')
        return self.runStep()

    def test_mode_full_copy(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='copy'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectRmdir(dir='build', logEnviron=True)
            .exit(0),
            ExpectStat(file='source/.bzr', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='source',
                        command=['bzr', 'update'])
            .exit(0),
            ExpectCpdir(fromdir='source', logEnviron=True, todir='build')
            .exit(0),
            ExpectShell(workdir='source',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            .stdout('100')
            .exit(0)
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'Bzr')
        return self.runStep()

    def test_mode_incremental(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='incremental'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.bzr', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'update'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            .stdout('100')
            .exit(0)
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'Bzr')
        return self.runStep()

    def test_mode_incremental_revision(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='incremental'),
            args=dict(revision='9384'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.bzr', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'update', '-r', '9384'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            .stdout('100')
            .exit(0)
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'Bzr')
        return self.runStep()

    def test_mode_incremental_no_existing_repo(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='incremental'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.bzr', logEnviron=True)
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'checkout',
                                 'http://bzr.squid-cache.org/bzr/squid3/trunk', '.'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            .stdout('100\n')
            .exit(0)
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100\n', 'Bzr')
        return self.runStep()

    def test_mode_incremental_retry(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='incremental', retry=(0, 1)))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.bzr', logEnviron=True)
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'checkout',
                                 'http://bzr.squid-cache.org/bzr/squid3/trunk', '.'])
            .exit(1),
            ExpectRmdir(dir='wkdir', logEnviron=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'checkout',
                                 'http://bzr.squid-cache.org/bzr/squid3/trunk', '.'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            .stdout('100\n')
            .exit(0)
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100\n', 'Bzr')
        return self.runStep()

    def test_bad_revparse(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='incremental'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.bzr', logEnviron=True)
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'checkout',
                                 'http://bzr.squid-cache.org/bzr/squid3/trunk', '.'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            .stdout('oiasdfj010laksjfd')
            .exit(0)
        )
        self.expectOutcome(result=FAILURE)
        return self.runStep()

    def test_bad_checkout(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='incremental'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', logEnviron=True)
            .exit(1),
            ExpectStat(file='wkdir/.bzr', logEnviron=True)
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'checkout',
                                 'http://bzr.squid-cache.org/bzr/squid3/trunk', '.'])
            .stderr('failed\n')
            .exit(128)
        )
        self.expectOutcome(result=FAILURE)
        return self.runStep()

    def test_worker_connection_lost(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='fresh'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .add(('err', error.ConnectionLost())),
        )
        self.expectOutcome(result=RETRY,
                           state_string="update (retry)")
        return self.runStep()
