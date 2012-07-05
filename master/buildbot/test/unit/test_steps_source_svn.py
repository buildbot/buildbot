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

import textwrap
from twisted.trial import unittest
from buildbot.steps.source import svn
from buildbot.status.results import SUCCESS, FAILURE
from buildbot.test.util import sourcesteps
from buildbot.process import buildstep
from buildbot.test.fake.remotecommand import ExpectShell, Expect
from buildbot.test.util.properties import ConstantRenderable
from buildbot import config

class TestSVN(sourcesteps.SourceStepMixin, unittest.TestCase):

    svn_st_xml = """<?xml version="1.0"?>
        <status>
            <target path=".">
                <entry path="svn_external_path">
                    <wc-status props="none" item="external">
                    </wc-status>
                </entry>
                <entry path="svn_external_path/unversioned_file1">
                    <wc-status props="none" item="unversioned">
                    </wc-status>
                </entry>
                <entry path="svn_external_path/unversioned_file2">
                    <wc-status props="none" item="unversioned">
                    </wc-status>
                </entry>
            </target>
        </status>
        """
    svn_st_xml_empty = """<?xml version="1.0"?>
                          <status>
                          <target path=".">
                          </target>
                          </status>"""
    def setUp(self):
        return self.setUpSourceStep()

    def tearDown(self):
        return self.tearDownSourceStep()

    def patch_slaveVersionIsOlderThan(self, result):
        self.patch(svn.SVN, 'slaveVersionIsOlderThan', lambda x, y, z: result)

    def test_no_repourl(self):
        self.assertRaises(config.ConfigErrors, lambda :
                svn.SVN())

    def test_incorrect_mode(self):
        self.assertRaises(config.ConfigErrors, lambda :
                svn.SVN(repourl='http://svn.local/app/trunk',
                        mode='invalid'))

    def test_incorrect_method(self):
        self.assertRaises(config.ConfigErrors, lambda :
                svn.SVN(repourl='http://svn.local/app/trunk',
                        method='invalid'))

    def test_mode_incremental(self):
        self.setupStep(
                svn.SVN(repourl='http://svn.local/app/trunk',
                        mode='incremental',username='user',
                        password='pass', extra_args=['--random']))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', 'pass', '--random'])
            + ExpectShell.log('stdio',
                stdout="URL: http://svn.local/app/trunk")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', 'pass', '--random'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svnversion'])
            + ExpectShell.log('stdio',
                stdout='100')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_incremental_timeout(self):
        self.setupStep(
                svn.SVN(repourl='http://svn.local/app/trunk',
                        mode='incremental',username='user',
                        timeout=1,
                        password='pass', extra_args=['--random']))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['svn', 'info', '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', 'pass', '--random'])
            + ExpectShell.log('stdio',
                stdout="URL: http://svn.local/app/trunk")
            + 0,
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', 'pass', '--random'])
            + 0,
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['svnversion'])
            + ExpectShell.log('stdio',
                stdout='100')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_incremental_repourl_renderable(self):
        self.setupStep(
                svn.SVN(repourl=ConstantRenderable('http://svn.local/trunk'),
                        mode='incremental'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--non-interactive',
                                 '--no-auth-cache'])
            + ExpectShell.log('stdio',
                stdout="URL: http://svn.local/trunk")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svnversion'])
            + ExpectShell.log('stdio',
                stdout='100')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_incremental_repourl_not_updatable(self):
        self.setupStep(
                svn.SVN(repourl=ConstantRenderable('http://svn.local/trunk/app'),
                        mode='incremental',))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.svn',
                                logEnviron=True))
            + 1,
            Expect('rmdir', {'dir': 'wkdir', 'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'checkout', 'http://svn.local/trunk/app',
                                 '.', '--non-interactive', '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svnversion'])
            + ExpectShell.log('stdio',
                stdout='100')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_incremental_repourl_not_updatable_svninfo_mismatch(self):
        self.setupStep(
                svn.SVN(repourl=ConstantRenderable('http://svn.local/trunk/app'),
                    mode='incremental'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--non-interactive',
                                 '--no-auth-cache'])
            + ExpectShell.log('stdio', # expecting ../trunk/app
                stdout="URL: http://svn.local/branch/foo/app")
            + 0,
            Expect('rmdir', {'dir': 'wkdir', 'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'checkout', 'http://svn.local/trunk/app',
                                 '.', '--non-interactive', '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svnversion'])
            + ExpectShell.log('stdio',
                stdout='100')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_incremental_given_revision(self):
        self.setupStep(
                svn.SVN(repourl='http://svn.local/app/trunk',
                                    mode='incremental'), dict(
                revision='100',
                ))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--non-interactive',
                                 '--no-auth-cache'])
            + ExpectShell.log('stdio',
                stdout="URL: http://svn.local/app/trunk")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update', '--revision', '100',
                                 '--non-interactive', '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svnversion'])
            + ExpectShell.log('stdio',
                stdout='100')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_clobber(self):
        self.setupStep(
                svn.SVN(repourl='http://svn.local/app/trunk',
                                    mode='full', method='clobber'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('rmdir', {'dir': 'wkdir',
                             'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'checkout',
                                 'http://svn.local/app/trunk', '.',
                                 '--non-interactive', '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svnversion'])
            + ExpectShell.log('stdio',
                stdout='100')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_clobber_given_revision(self):
        self.setupStep(
                svn.SVN(repourl='http://svn.local/app/trunk',
                                    mode='full', method='clobber'),dict(
                revision='100',
                ))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('rmdir', {'dir': 'wkdir',
                             'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'checkout',
                                 'http://svn.local/app/trunk', '.',
                                 '--revision', '100',
                                 '--non-interactive', '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svnversion'])
            + ExpectShell.log('stdio',
                stdout='100')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_fresh(self):
        self.setupStep(
                svn.SVN(repourl='http://svn.local/app/trunk',
                                    mode='full', method='fresh', depth='infinite'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', {'file': 'wkdir/.svn',
                            'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--non-interactive',
                                 '--no-auth-cache', '--depth', 'infinite' ])
            + ExpectShell.log('stdio',
                stdout="URL: http://svn.local/app/trunk")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn',
                                 'status', '--xml', '--no-ignore',
                                 '--non-interactive', '--no-auth-cache',
                                 '--depth', 'infinite'])
            + ExpectShell.log('stdio',
                stdout=self.svn_st_xml_empty)
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update',
                                 '--non-interactive', '--no-auth-cache', '--depth', 'infinite'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svnversion'])
            + ExpectShell.log('stdio', stdout='100')
            + ExpectShell.log('stdio', stdout='\n')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_fresh_given_revision(self):
        self.setupStep(
                svn.SVN(repourl='http://svn.local/app/trunk',
                        mode='full', method='fresh', depth='infinite'),dict(
                revision='100',
                ))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', {'file': 'wkdir/.svn',
                            'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--non-interactive',
                                 '--no-auth-cache', '--depth', 'infinite' ])
            + ExpectShell.log('stdio',
                stdout="URL: http://svn.local/app/trunk")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn',
                                 'status', '--xml', '--no-ignore',
                                 '--non-interactive', '--no-auth-cache',
                                 '--depth', 'infinite'])
            + ExpectShell.log('stdio',
                stdout=self.svn_st_xml_empty)
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update', '--revision', '100',
                                 '--non-interactive', '--no-auth-cache', '--depth', 'infinite'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svnversion'])
            + ExpectShell.log('stdio', stdout='100')
            + ExpectShell.log('stdio', stdout='\n')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_fresh_keep_on_purge(self):
        self.setupStep(
                svn.SVN(repourl='http://svn.local/app/trunk',
                        mode='full',
                        keep_on_purge=['svn_external_path/unversioned_file1']))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', {'file': 'wkdir/.svn',
                            'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--non-interactive',
                                 '--no-auth-cache' ])
            + ExpectShell.log('stdio',
                stdout="URL: http://svn.local/app/trunk")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn',
                                 'status', '--xml', '--no-ignore',
                                 '--non-interactive', '--no-auth-cache'])
            + ExpectShell.log('stdio',
                stdout=self.svn_st_xml)
            + 0,
            Expect('rmdir', {'dir':
                             ['wkdir/svn_external_path/unversioned_file2'],
                             'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update',
                                 '--non-interactive', '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svnversion'])
            + ExpectShell.log('stdio', stdout='100\n')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_clean(self):
        self.setupStep(
                svn.SVN(repourl='http://svn.local/app/trunk',
                                    mode='full', method='clean'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', {'file': 'wkdir/.svn',
                            'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--non-interactive',
                                 '--no-auth-cache' ])
            + ExpectShell.log('stdio',
                stdout="URL: http://svn.local/app/trunk")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn',
                                 'status', '--xml',
                                 '--non-interactive', '--no-auth-cache'])
            + ExpectShell.log('stdio',
                stdout=self.svn_st_xml_empty)
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update',
                                 '--non-interactive', '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svnversion'])
            + ExpectShell.log('stdio', stdout='100\n')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_clean_given_revision(self):
        self.setupStep(
                svn.SVN(repourl='http://svn.local/app/trunk',
                        mode='full', method='clean'),dict(
                revision='100',
                ))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', {'file': 'wkdir/.svn',
                            'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--non-interactive',
                                 '--no-auth-cache' ])
            + ExpectShell.log('stdio',
                stdout="URL: http://svn.local/app/trunk")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn',
                                 'status', '--xml',
                                 '--non-interactive', '--no-auth-cache'])
            + ExpectShell.log('stdio',
                stdout=self.svn_st_xml_empty)
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update', '--revision', '100',
                                 '--non-interactive', '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svnversion'])
            + ExpectShell.log('stdio', stdout='100\n')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_not_updatable(self):
        self.setupStep(
                svn.SVN(repourl='http://svn.local/app/trunk',
                                    mode='full', method='clean'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', {'file': 'wkdir/.svn',
                            'logEnviron': True})
            + 1,
            Expect('rmdir', {'dir': 'wkdir', 'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'checkout', 'http://svn.local/app/trunk',
                                 '.', '--non-interactive', '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svnversion'])
            + ExpectShell.log('stdio', stdout='100')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_not_updatable_given_revision(self):
        self.setupStep(
                svn.SVN(repourl='http://svn.local/app/trunk',
                                    mode='full', method='clean'),dict(
                revision='100',
                ))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', {'file': 'wkdir/.svn',
                            'logEnviron': True})
            + 1,
            Expect('rmdir', {'dir': 'wkdir', 'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'checkout', 'http://svn.local/app/trunk',
                                 '.', '--revision', '100',
                                 '--non-interactive', '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svnversion'])
            + ExpectShell.log('stdio', stdout='100')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_clean_old_rmdir(self):
        self.setupStep(
                svn.SVN(repourl='http://svn.local/app/trunk',
                                    mode='full', method='clean'))
        self.patch_slaveVersionIsOlderThan(True)
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', {'file': 'wkdir/.svn',
                            'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--non-interactive',
                                 '--no-auth-cache' ])
            + ExpectShell.log('stdio',
                stdout="URL: http://svn.local/app/trunk")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn',
                                 'status', '--xml',
                                 '--non-interactive', '--no-auth-cache'])
            + ExpectShell.log('stdio',
                stdout=self.svn_st_xml)
            + 0,
            Expect('rmdir', {'dir':
                             'wkdir/svn_external_path/unversioned_file1',
                                   'logEnviron': True})
            + 0,
            Expect('rmdir', {'dir':
                             'wkdir/svn_external_path/unversioned_file2',
                                   'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update',
                                 '--non-interactive', '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svnversion'])
            + ExpectShell.log('stdio', stdout='100')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_clean_new_rmdir(self):
        self.setupStep(
                svn.SVN(repourl='http://svn.local/app/trunk',
                                    mode='full', method='clean'))

        self.patch_slaveVersionIsOlderThan(False)
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', {'file': 'wkdir/.svn',
                            'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--non-interactive',
                                 '--no-auth-cache' ])
            + ExpectShell.log('stdio',
                stdout="URL: http://svn.local/app/trunk")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn',
                                 'status', '--xml',
                                 '--non-interactive', '--no-auth-cache'])
            + ExpectShell.log('stdio',
                stdout=self.svn_st_xml)
            + 0,
            Expect('rmdir', {'dir':
                             ['wkdir/svn_external_path/unversioned_file1',
                             'wkdir/svn_external_path/unversioned_file2'],
                             'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update',
                                 '--non-interactive', '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svnversion'])
            + ExpectShell.log('stdio', stdout='100')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_copy(self):
        self.setupStep(
                svn.SVN(repourl='http://svn.local/app/trunk',
                                    mode='full', method='copy'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True))
            + 0,
            Expect('stat', dict(file='source/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='source',
                        command=['svn', 'info', '--non-interactive',
                                 '--no-auth-cache' ])
            + ExpectShell.log('stdio',
                stdout="URL: http://svn.local/app/trunk")
            + 0,
            ExpectShell(workdir='source',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache'])
            + 0,
            Expect('cpdir', {'fromdir': 'source',
                             'todir': 'wkdir',
                             'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svnversion'])
            + ExpectShell.log('stdio',
                stdout='100')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_copy_given_revision(self):
        self.setupStep(
                svn.SVN(repourl='http://svn.local/app/trunk',
                        mode='full', method='copy'),dict(
                revision='100',
                ))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True))
            + 0,
            Expect('stat', dict(file='source/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='source',
                        command=['svn', 'info', '--non-interactive',
                                 '--no-auth-cache' ])
            + ExpectShell.log('stdio',
                stdout="URL: http://svn.local/app/trunk")
            + 0,
            ExpectShell(workdir='source',
                        command=['svn', 'update', '--revision', '100',
                                 '--non-interactive', '--no-auth-cache'])
            + 0,
            Expect('cpdir', {'fromdir': 'source',
                             'todir': 'wkdir',
                             'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svnversion'])
            + ExpectShell.log('stdio',
                stdout='100')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_export(self):
        self.setupStep(
                svn.SVN(repourl='http://svn.local/app/trunk',
                                    mode='full', method='export'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True))
            + 0,
            Expect('stat', dict(file='source/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='source',
                        command=['svn', 'info', '--non-interactive',
                                 '--no-auth-cache' ])
            + ExpectShell.log('stdio',
                stdout="URL: http://svn.local/app/trunk")
            + 0,
            ExpectShell(workdir='source',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='',
                        command=['svn', 'export', 'source', 'wkdir'])
            + 0,
            ExpectShell(workdir='source',
                        command=['svnversion'])
            + ExpectShell.log('stdio',
                stdout='100')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_export_timeout(self):
        self.setupStep(
                svn.SVN(repourl='http://svn.local/app/trunk',
                                    timeout=1,
                                    mode='full', method='export'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['svn', '--version'])
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True))
            + 0,
            Expect('stat', dict(file='source/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='source',
                        timeout=1,
                        command=['svn', 'info', '--non-interactive',
                                 '--no-auth-cache' ])
            + ExpectShell.log('stdio',
                stdout="URL: http://svn.local/app/trunk")
            + 0,
            ExpectShell(workdir='source',
                        timeout=1,
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='',
                        timeout=1,
                        command=['svn', 'export', 'source', 'wkdir'])
            + 0,
            ExpectShell(workdir='source',
                        timeout=1,
                        command=['svnversion'])
            + ExpectShell.log('stdio',
                stdout='100')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_export_given_revision(self):
        self.setupStep(
                svn.SVN(repourl='http://svn.local/app/trunk',
                        mode='full', method='export'),dict(
                revision='100',
                ))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True))
            + 0,
            Expect('stat', dict(file='source/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='source',
                        command=['svn', 'info', '--non-interactive',
                                 '--no-auth-cache' ])
            + ExpectShell.log('stdio',
                stdout="URL: http://svn.local/app/trunk")
            + 0,
            ExpectShell(workdir='source',
                        command=['svn', 'update', '--revision', '100',
                                 '--non-interactive', '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='',
                        command=['svn', 'export', '--revision', '100',
                                 'source', 'wkdir'])
            + 0,
            ExpectShell(workdir='source',
                        command=['svnversion'])
            + ExpectShell.log('stdio',
                stdout='100')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_incremental_with_env(self):
        self.setupStep(
                svn.SVN(repourl='http://svn.local/app/trunk',
                        mode='incremental',username='user',
                        password='pass', extra_args=['--random'],
                        env={'abc': '123'}))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'],
                        env={'abc': '123'})
            + 0,
            Expect('stat', dict(file='wkdir/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', 'pass', '--random'],
                        env={'abc': '123'})
            + ExpectShell.log('stdio',
                stdout="URL: http://svn.local/app/trunk")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', 'pass', '--random'],
                        env={'abc': '123'})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svnversion'],
                        env={'abc': '123'})
            + ExpectShell.log('stdio',
                stdout='100')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()
    
    def test_mode_incremental_logEnviron(self):
        self.setupStep(
                svn.SVN(repourl='http://svn.local/app/trunk',
                        mode='incremental',username='user',
                        password='pass', extra_args=['--random'],
                        logEnviron=False))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'],
                        logEnviron=False)
            + 0,
            Expect('stat', dict(file='wkdir/.svn',
                                logEnviron=False))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', 'pass', '--random'],
                        logEnviron=False)
            + ExpectShell.log('stdio',
                stdout="URL: http://svn.local/app/trunk")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', 'pass', '--random'],
                        logEnviron=False)
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svnversion'],
                        logEnviron=False)
            + ExpectShell.log('stdio',
                stdout='100')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_command_fails(self):
        self.setupStep(
                svn.SVN(repourl='http://svn.local/app/trunk',
                        mode='incremental',username='user',
                        password='pass', extra_args=['--random']))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', 'pass', '--random'])
            + ExpectShell.log('stdio',
                stdout="URL: http://svn.local/app/trunk")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', 'pass', '--random'])
            + 1,
        )
        self.expectOutcome(result=FAILURE, status_text=["updating"])
        return self.runStep()

    def test_bogus_svnversion(self):
        self.setupStep(
                svn.SVN(repourl='http://svn.local/app/trunk',
                        mode='incremental',username='user',
                        password='pass', extra_args=['--random']))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', 'pass', '--random'])
            + ExpectShell.log('stdio', stdout=textwrap.dedent("""\
                    Path: /a/b/c
                    URL: http://svn.local/app/trunk"""))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', 'pass', '--random'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svnversion'])
            + ExpectShell.log('stdio',
                stdout='1x0y0')
            + 0,
        )
        self.expectOutcome(result=FAILURE, status_text=["updating"])
        return self.runStep()

    def test_rmdir_fails_clobber(self):
        self.setupStep(
                svn.SVN(repourl='http://svn.local/app/trunk',
                                    mode='full', method='clobber'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('rmdir', {'dir': 'wkdir',
                             'logEnviron': True})
            + 1,
        )
        self.expectOutcome(result=FAILURE, status_text=["updating"])
        return self.runStep()

    def test_rmdir_fails_copy(self):
        self.setupStep(
                svn.SVN(repourl='http://svn.local/app/trunk',
                                    mode='full', method='copy'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True))
            + 1,
        )
        self.expectOutcome(result=FAILURE, status_text=["updating"])
        return self.runStep()

    def test_cpdir_fails_copy(self):
        self.setupStep(
                svn.SVN(repourl='http://svn.local/app/trunk',
                                    mode='full', method='copy'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True))
            + 0,
            Expect('stat', dict(file='source/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='source',
                        command=['svn', 'info', '--non-interactive',
                                 '--no-auth-cache' ])
            + ExpectShell.log('stdio', # note \r\n here, for variety
                stdout="URL: http://svn.local/app/trunk\r\nTrailing: ..")
            + 0,
            ExpectShell(workdir='source',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache'])
            + 0,
            Expect('cpdir', {'fromdir': 'source',
                             'todir': 'wkdir',
                             'logEnviron': True})
            + 1,
        )
        self.expectOutcome(result=FAILURE, status_text=["updating"])
        return self.runStep()

    def test_rmdir_fails_purge(self):
        self.setupStep(
                svn.SVN(repourl='http://svn.local/app/trunk',
                        mode='full',
                        keep_on_purge=['svn_external_path/unversioned_file1']))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', {'file': 'wkdir/.svn',
                            'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--non-interactive',
                                 '--no-auth-cache' ])
            + ExpectShell.log('stdio',
                stdout="URL: http://svn.local/app/trunk")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn',
                                 'status', '--xml', '--no-ignore',
                                 '--non-interactive', '--no-auth-cache'])
            + ExpectShell.log('stdio',
                stdout=self.svn_st_xml)
            + 0,
            Expect('rmdir', {'dir':
                             ['wkdir/svn_external_path/unversioned_file2'],
                             'logEnviron': True})
            + 1,
        )
        self.expectOutcome(result=FAILURE, status_text=["updating"])
        return self.runStep()

class TestGetUnversionedFiles(unittest.TestCase):
    def test_getUnversionedFiles_does_not_list_externals(self):
        svn_st_xml = """<?xml version="1.0"?>
        <status>
            <target path=".">
                <entry path="svn_external_path">
                    <wc-status props="none" item="external">
                    </wc-status>
                </entry>
                <entry path="svn_external_path/unversioned_file">
                    <wc-status props="none" item="unversioned">
                    </wc-status>
                </entry>
            </target>
        </status>
        """
        unversioned_files = list(svn.SVN.getUnversionedFiles(svn_st_xml, []))
        self.assertEquals(["svn_external_path/unversioned_file"], unversioned_files)

    def test_getUnversionedFiles_does_not_list_missing(self):
        svn_st_xml = """<?xml version="1.0"?>
        <status>
            <target path=".">
                <entry path="missing_file">
                    <wc-status props="none" item="missing"></wc-status>
                </entry>
            </target>
        </status>
        """
        unversioned_files = list(svn.SVN.getUnversionedFiles(svn_st_xml, []))
        self.assertEquals([], unversioned_files)

    def test_getUnversionedFiles_corrupted_xml(self):
        svn_st_xml = """<?xml version="1.0"?>
            <target path=".">
                <entry path="svn_external_path">
                    <wc-status props="none" item="external">
                    </wc-status>
                </entry>
                <entry path="svn_external_path/unversioned_file">
                    <wc-status props="none" item="unversioned">
                    </wc-status>
                </entry>
            </target>
        </status>
        """
        self.assertRaises(buildstep.BuildStepFailed,
                          lambda : list(svn.SVN.getUnversionedFiles(svn_st_xml, [])))

    def test_getUnversionedFiles_no_path(self):
        svn_st_xml = """<?xml version="1.0"?>
        <status>
            <target path=".">
                <entry path="svn_external_path">
                    <wc-status props="none" item="external">
                    </wc-status>
                </entry>
                <entry>
                    <wc-status props="none" item="unversioned">
                    </wc-status>
                </entry>
            </target>
        </status>
        """
        unversioned_files = list(svn.SVN.getUnversionedFiles(svn_st_xml, []))
        self.assertEquals([], unversioned_files)

    def test_getUnversionedFiles_no_item(self):
        svn_st_xml = """<?xml version="1.0"?>
        <status>
            <target path=".">
                <entry path="svn_external_path">
                    <wc-status props="none" item="external">
                    </wc-status>
                </entry>
                <entry path="svn_external_path/unversioned_file">
                    <wc-status props="none">
                    </wc-status>
                </entry>
            </target>
        </status>
        """
        unversioned_files = list(svn.SVN.getUnversionedFiles(svn_st_xml, []))
        self.assertEquals(["svn_external_path/unversioned_file"], unversioned_files)

