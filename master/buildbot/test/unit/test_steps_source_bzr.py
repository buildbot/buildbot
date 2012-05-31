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
from buildbot.steps.source import bzr
from buildbot.status.results import SUCCESS, FAILURE
from buildbot.test.util import sourcesteps
from buildbot.test.fake.remotecommand import ExpectShell, Expect

class TestBzr(sourcesteps.SourceStepMixin, unittest.TestCase):

    def setUp(self):
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
            + 0,
            Expect('stat', dict(file='wkdir/.bzr',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'clean-tree', '--force'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'update'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            + ExpectShell.log('stdio',
                stdout='100')
            + 0,
                    )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_revision(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='fresh'),
            args=dict(revision='3730'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.bzr',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'clean-tree', '--force'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'update', '-r', '3730'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            + ExpectShell.log('stdio',
                stdout='100')
            + 0,
                    )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_clean(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='clean'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.bzr',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'clean-tree', '--ignored', '--force'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'update'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            + ExpectShell.log('stdio',
                stdout='100')
            + 0,
                    )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_clean_revision(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='clean'),
            args=dict(revision='2345'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.bzr',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'clean-tree', '--ignored', '--force'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'update', '-r', '2345'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            + ExpectShell.log('stdio',
                stdout='100')
            + 0,
                    )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_fresh(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='fresh'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.bzr',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'clean-tree', '--force'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'update'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            + ExpectShell.log('stdio',
                stdout='100')
            + 0,
                    )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_clobber(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='clobber'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'checkout',
                                'http://bzr.squid-cache.org/bzr/squid3/trunk', '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            + ExpectShell.log('stdio',
                stdout='100')
            + 0,
                    )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()


    def test_mode_full_clobber_revision(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='clobber'),
            args=dict(revision='3730'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'checkout',
                                'http://bzr.squid-cache.org/bzr/squid3/trunk',
                                '.', '-r', '3730'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            + ExpectShell.log('stdio',
                stdout='100')
            + 0,
                    )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()


    def test_mode_full_copy(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='full', method='copy'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            + 0,
            Expect('rmdir', dict(dir='build',
                                 logEnviron=True))
            + 0,
            Expect('stat', dict(file='source/.bzr',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='source',
                        command=['bzr', 'update'])
            + 0,
            Expect('cpdir', {'fromdir': 'source',
                             'logEnviron': True,
                             'todir': 'build'})
            + 0,
            ExpectShell(workdir='source',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            + ExpectShell.log('stdio',
                stdout='100')
            + 0,
            )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_incremental(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='incremental'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.bzr',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'update'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            + ExpectShell.log('stdio',
                stdout='100')
            + 0,
            )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_incremental_revision(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='incremental'),
            args=dict(revision='9384'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.bzr',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'update', '-r', '9384'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            + ExpectShell.log('stdio',
                stdout='100')
            + 0,
            )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_incremental_no_existing_repo(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='incremental'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.bzr',
                                logEnviron=True))
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'checkout',
                                'http://bzr.squid-cache.org/bzr/squid3/trunk', '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            + ExpectShell.log('stdio',
                stdout='100\n')
            + 0,
            )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_bad_revparse(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='incremental'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.bzr',
                                logEnviron=True))
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'checkout',
                                'http://bzr.squid-cache.org/bzr/squid3/trunk', '.'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'version-info', '--custom', "--template='{revno}"])
            + ExpectShell.log('stdio',
                stdout='oiasdfj010laksjfd')
            + 0,
            )
        self.expectOutcome(result=FAILURE, status_text=["updating"])
        return self.runStep()

    def test_bad_checkout(self):
        self.setupStep(
            bzr.Bzr(repourl='http://bzr.squid-cache.org/bzr/squid3/trunk',
                    mode='incremental'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['bzr', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.bzr',
                                logEnviron=True))
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['bzr', 'checkout',
                                'http://bzr.squid-cache.org/bzr/squid3/trunk', '.'])
            + ExpectShell.log('stdio',
                stderr='failed\n')
            + 128,
            )
        self.expectOutcome(result=FAILURE, status_text=["updating"])
        return self.runStep()
