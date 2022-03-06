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
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import ExpectCpdir
from buildbot.test.steps import ExpectDownloadFile
from buildbot.test.steps import ExpectRemoteRef
from buildbot.test.steps import ExpectRmdir
from buildbot.test.steps import ExpectShell
from buildbot.test.steps import ExpectStat
from buildbot.test.util import sourcesteps


class TestBzr(sourcesteps.SourceStepMixin, TestReactorMixin,
              unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setUpSourceStep()

    def tearDown(self):
        return self.tearDownSourceStep()

    def test_mode_full(self):
        self.setup_step(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='fresh'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectStat(file='wkdir/.bzr', log_environ=True)
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
        self.expect_outcome(result=SUCCESS, state_string="update")
        self.expect_property('got_revision', '100', 'Bzr')
        return self.run_step()

    def test_mode_full_win32path(self):
        self.setup_step(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='fresh'))
        self.build.path_module = namedModule('ntpath')
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file=r'wkdir\.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectStat(file=r'wkdir\.bzr', log_environ=True)
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
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_full_timeout(self):
        self.setup_step(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='fresh', timeout=1))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectStat(file='wkdir/.bzr', log_environ=True)
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
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '100', 'Bzr')
        return self.run_step()

    def test_mode_full_revision(self):
        self.setup_step(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='fresh'),
            args=dict(revision='3730'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectStat(file='wkdir/.bzr', log_environ=True)
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
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '100', 'Bzr')
        return self.run_step()

    def test_mode_full_clean(self):
        self.setup_step(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='clean'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectStat(file='wkdir/.bzr', log_environ=True)
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
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '100', 'Bzr')
        return self.run_step()

    def test_mode_full_clean_patched(self):
        self.setup_step(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='clean'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(0),
            # clean up the applied patch
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'clean-tree', '--ignored', '--force'])
            .exit(0),
            ExpectStat(file='wkdir/.bzr', log_environ=True)
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
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '100', 'Bzr')
        return self.run_step()

    def test_mode_full_clean_patch(self):
        self.setup_step(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='clean'), patch=(1, 'patch'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectStat(file='wkdir/.bzr', log_environ=True)
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
            ExpectRmdir(dir='wkdir/.buildbot-diff', log_environ=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            .stdout('100')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '100', 'Bzr')
        return self.run_step()

    def test_mode_full_clean_patch_worker_2_16(self):
        self.setup_step(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='clean'), patch=(1, 'patch'),
            worker_version={'*': '2.16'})
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectStat(file='wkdir/.bzr', log_environ=True)
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
            ExpectRmdir(dir='wkdir/.buildbot-diff', log_environ=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            .stdout('100')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '100', 'Bzr')
        return self.run_step()

    def test_mode_full_clean_revision(self):
        self.setup_step(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='clean'),
            args=dict(revision='2345'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectStat(file='wkdir/.bzr', log_environ=True)
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
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '100', 'Bzr')
        return self.run_step()

    def test_mode_full_fresh(self):
        self.setup_step(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='fresh'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectStat(file='wkdir/.bzr', log_environ=True)
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
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '100', 'Bzr')
        return self.run_step()

    def test_mode_full_clobber(self):
        self.setup_step(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='clobber'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True)
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
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '100', 'Bzr')
        return self.run_step()

    def test_mode_full_clobber_retry(self):
        self.setup_step(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='clobber', retry=(0, 2)))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'checkout',
                                 'http://bzr.squid-cache.org/bzr/squid3/trunk', '.'])
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'checkout',
                                 'http://bzr.squid-cache.org/bzr/squid3/trunk', '.'])
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True)
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
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '100', 'Bzr')
        return self.run_step()

    def test_mode_full_clobber_revision(self):
        self.setup_step(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='clobber'),
            args=dict(revision='3730'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True)
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
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '100', 'Bzr')
        return self.run_step()

    def test_mode_full_clobber_baseurl(self):
        self.setup_step(
            bzr.Bzr(baseURL='http://bzr.squid-cache.org/bzr/squid3',
                    defaultBranch='trunk', mode='full', method='clobber'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True)
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
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '100', 'Bzr')
        return self.run_step()

    def test_mode_full_clobber_baseurl_nodefault(self):
        self.setup_step(
            bzr.Bzr(baseURL='http://bzr.squid-cache.org/bzr/squid3',
                    defaultBranch='trunk', mode='full', method='clobber'),
            args=dict(branch='branches/SQUID_3_0'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True)
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
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '100', 'Bzr')
        return self.run_step()

    def test_mode_full_copy(self):
        self.setup_step(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='copy'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='build', log_environ=True)
            .exit(0),
            ExpectStat(file='source/.bzr', log_environ=True)
            .exit(0),
            ExpectShell(workdir='source',
                        command=['bzr', 'update'])
            .exit(0),
            ExpectCpdir(fromdir='source', log_environ=True, todir='build')
            .exit(0),
            ExpectShell(workdir='source',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            .stdout('100')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '100', 'Bzr')
        return self.run_step()

    def test_mode_incremental(self):
        self.setup_step(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='incremental'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectStat(file='wkdir/.bzr', log_environ=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'update'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            .stdout('100')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '100', 'Bzr')
        return self.run_step()

    def test_mode_incremental_revision(self):
        self.setup_step(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='incremental'),
            args=dict(revision='9384'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectStat(file='wkdir/.bzr', log_environ=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'update', '-r', '9384'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            .stdout('100')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '100', 'Bzr')
        return self.run_step()

    def test_mode_incremental_no_existing_repo(self):
        self.setup_step(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='incremental'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectStat(file='wkdir/.bzr', log_environ=True)
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
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '100\n', 'Bzr')
        return self.run_step()

    def test_mode_incremental_retry(self):
        self.setup_step(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='incremental', retry=(0, 1)))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectStat(file='wkdir/.bzr', log_environ=True)
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'checkout',
                                 'http://bzr.squid-cache.org/bzr/squid3/trunk', '.'])
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True)
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
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '100\n', 'Bzr')
        return self.run_step()

    def test_bad_revparse(self):
        self.setup_step(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='incremental'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectStat(file='wkdir/.bzr', log_environ=True)
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
        self.expect_outcome(result=FAILURE)
        return self.run_step()

    def test_bad_checkout(self):
        self.setup_step(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='incremental'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectStat(file='wkdir/.bzr', log_environ=True)
            .exit(1),
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'checkout',
                                 'http://bzr.squid-cache.org/bzr/squid3/trunk', '.'])
            .stderr('failed\n')
            .exit(128)
        )
        self.expect_outcome(result=FAILURE)
        return self.run_step()

    def test_worker_connection_lost(self):
        self.setup_step(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='fresh'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            .error(error.ConnectionLost())
        )
        self.expect_outcome(result=RETRY,
                           state_string="update (retry)")
        return self.run_step()
