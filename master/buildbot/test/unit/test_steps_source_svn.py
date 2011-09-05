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
from buildbot.steps.source import svn
from buildbot.status.results import SUCCESS, FAILURE
from buildbot.test.util import sourcesteps
from buildbot.process import buildstep
from buildbot.test.fake.remotecommand import ExpectShell, ExpectLogged

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
        svn.SVN.slaveVersionIsOlderThan = lambda x, y, z: result

    def test_repourl_and_baseURL(self):
        self.assertRaises(ValueError, lambda :
                svn.SVN(svnurl='http://svn.local/app/trunk@HEAD',
                        baseURL='http://svn.local/app/trunk@HEAD'))

    def test_no_repourl_and_baseURL(self):
        self.assertRaises(ValueError, lambda :
                svn.SVN())

    def test_mode_incremental(self):
        self.setupStep(
                svn.SVN(svnurl='http://svn.local/app/trunk@HEAD',
                        mode='incremental',username='user',
                        password='pass', extra_args=['--random']))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            ExpectLogged('stat', dict(file='wkdir/.svn',
                                      logEnviron=True))
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

    def test_mode_incremental_baseURL(self):
        self.setupStep(
                svn.SVN(baseURL='http://svn.local/', mode='incremental',
                        defaultBranch='trunk'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            ExpectLogged('stat', dict(file='wkdir/.svn',
                                      logEnviron=True))
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

    def test_mode_incremental_baseURL_not_updatable(self):
        self.setupStep(
                svn.SVN(baseURL='http://svn.local/%%BRANCH%%/app', mode='incremental',
                        defaultBranch='trunk'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            ExpectLogged('stat', dict(file='wkdir/.svn',
                                      logEnviron=True))
            + 1,
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
                svn.SVN(svnurl='http://svn.local/app/trunk@HEAD',
                                    mode='incremental'), dict(
                revision='100',
                ))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            ExpectLogged('stat', dict(file='wkdir/.svn',
                                      logEnviron=True))
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
                svn.SVN(svnurl='http://svn.local/app/trunk@HEAD',
                                    mode='full', method='clobber'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            ExpectLogged('rmdir', {'dir': 'wkdir',
                                   'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'checkout',
                                 'http://svn.local/app/trunk@HEAD', '.',
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
                svn.SVN(svnurl='http://svn.local/app/trunk@HEAD',
                                    mode='full', method='fresh', depth='infinite'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            ExpectLogged('stat', {'file': 'wkdir/.svn',
                                  'logEnviron': True})
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

    def test_mode_full_fresh_keep_on_purge(self):
        self.setupStep(
                svn.SVN(svnurl='http://svn.local/app/trunk@HEAD',
                        mode='full',
                        keep_on_purge=['svn_external_path/unversioned_file1']))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            ExpectLogged('stat', {'file': 'wkdir/.svn',
                                  'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn',
                                 'status', '--xml', '--no-ignore',
                                 '--non-interactive', '--no-auth-cache'])
            + ExpectShell.log('stdio',
                stdout=self.svn_st_xml)
            + 0,
            ExpectLogged('rmdir', {'dir':
                                   'wkdir/svn_external_path/unversioned_file2',
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
                svn.SVN(svnurl='http://svn.local/app/trunk@HEAD',
                                    mode='full', method='clean'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            ExpectLogged('stat', {'file': 'wkdir/.svn',
                                  'logEnviron': True})
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

    def test_mode_full_not_updatable(self):
        self.setupStep(
                svn.SVN(svnurl='http://svn.local/app/trunk@HEAD',
                                    mode='full', method='clean'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            ExpectLogged('stat', {'file': 'wkdir/.svn',
                                  'logEnviron': True})
            + 1,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'checkout', 'http://svn.local/app/trunk@HEAD',
                                 '.', '--non-interactive', '--no-auth-cache'])
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
                svn.SVN(svnurl='http://svn.local/app/trunk@HEAD',
                                    mode='full', method='clean'))
        self.patch_slaveVersionIsOlderThan(False)
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            ExpectLogged('stat', {'file': 'wkdir/.svn',
                                  'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn',
                                 'status', '--xml',
                                 '--non-interactive', '--no-auth-cache'])
            + ExpectShell.log('stdio',
                stdout=self.svn_st_xml)
            + 0,
            ExpectLogged('rmdir', {'dir':
                                   'wkdir/svn_external_path/unversioned_file1',
                                   'logEnviron': True})
            + 0,
            ExpectLogged('rmdir', {'dir':
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
                svn.SVN(svnurl='http://svn.local/app/trunk@HEAD',
                                    mode='full', method='clean'))

        self.patch_slaveVersionIsOlderThan(True)
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            ExpectLogged('stat', {'file': 'wkdir/.svn',
                                  'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn',
                                 'status', '--xml',
                                 '--non-interactive', '--no-auth-cache'])
            + ExpectShell.log('stdio',
                stdout=self.svn_st_xml)
            + 0,
            ExpectLogged('rmdir', {'dir':
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

    def test_mode_copy(self):
        self.setupStep(
                svn.SVN(svnurl='http://svn.local/app/trunk@HEAD',
                                    mode='full', method='copy'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            ExpectLogged('rmdir', dict(dir='wkdir',
                                       logEnviron=True))
            + 0,
            ExpectLogged('stat', dict(file='source/.svn',
                                      logEnviron=True))
            + 0,
            ExpectShell(workdir='source',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache'])
            + 0,
            ExpectLogged('cpdir', {'fromdir': 'source',
                                   'todir': 'build',
                                   'logEnviron': True})
            + 0,
            ExpectShell(workdir='build',
                        command=['svnversion'])
            + ExpectShell.log('stdio',
                stdout='100')
            + 0,
        )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_incremental_with_env(self):
        self.setupStep(
                svn.SVN(svnurl='http://svn.local/app/trunk@HEAD',
                        mode='incremental',username='user',
                        password='pass', extra_args=['--random'],
                        env={'abc': '123'}))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'],
                        env={'abc': '123'})
            + 0,
            ExpectLogged('stat', dict(file='wkdir/.svn',
                                      logEnviron=True))
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
                svn.SVN(svnurl='http://svn.local/app/trunk@HEAD',
                        mode='incremental',username='user',
                        password='pass', extra_args=['--random'],
                        logEnviron=False))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'],
                        logEnviron=False)
            + 0,
            ExpectLogged('stat', dict(file='wkdir/.svn',
                                      logEnviron=False))
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
                svn.SVN(svnurl='http://svn.local/app/trunk@HEAD',
                        mode='incremental',username='user',
                        password='pass', extra_args=['--random'],
                        logEnviron=False))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'],
                        logEnviron=False)
            + 0,
            ExpectLogged('stat', dict(file='wkdir/.svn',
                                      logEnviron=False))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', 'pass', '--random'],
                        logEnviron=False)
            + 1,
        )
        self.expectOutcome(result=FAILURE, status_text=["updating"])
        return self.runStep()

    def test_bogus_svnversion(self):
        self.setupStep(
                svn.SVN(svnurl='http://svn.local/app/trunk@HEAD',
                        mode='incremental',username='user',
                        password='pass', extra_args=['--random']))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            ExpectLogged('stat', dict(file='wkdir/.svn',
                                      logEnviron=True))
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
                svn.SVN(svnurl='http://svn.local/app/trunk@HEAD',
                                    mode='full', method='clobber'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            ExpectLogged('rmdir', {'dir': 'wkdir',
                                   'logEnviron': True})
            + 1,
        )
        self.expectOutcome(result=FAILURE, status_text=["updating"])
        return self.runStep()

    def test_rmdir_fails_copy(self):
        self.setupStep(
                svn.SVN(svnurl='http://svn.local/app/trunk@HEAD',
                                    mode='full', method='copy'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            ExpectLogged('rmdir', dict(dir='wkdir',
                                       logEnviron=True))
            + 1,
        )
        self.expectOutcome(result=FAILURE, status_text=["updating"])
        return self.runStep()

    def test_cpdir_fails_copy(self):
        self.setupStep(
                svn.SVN(svnurl='http://svn.local/app/trunk@HEAD',
                                    mode='full', method='copy'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            ExpectLogged('rmdir', dict(dir='wkdir',
                                       logEnviron=True))
            + 0,
            ExpectLogged('stat', dict(file='source/.svn',
                                      logEnviron=True))
            + 0,
            ExpectShell(workdir='source',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache'])
            + 0,
            ExpectLogged('cpdir', {'fromdir': 'source',
                                   'todir': 'build',
                                   'logEnviron': True})
            + 1,
        )
        self.expectOutcome(result=FAILURE, status_text=["updating"])
        return self.runStep()

    def test_rmdir_fails_purge(self):
        self.setupStep(
                svn.SVN(svnurl='http://svn.local/app/trunk@HEAD',
                        mode='full',
                        keep_on_purge=['svn_external_path/unversioned_file1']))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            ExpectLogged('stat', {'file': 'wkdir/.svn',
                                  'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn',
                                 'status', '--xml', '--no-ignore',
                                 '--non-interactive', '--no-auth-cache'])
            + ExpectShell.log('stdio',
                stdout=self.svn_st_xml)
            + 0,
            ExpectLogged('rmdir', {'dir':
                                   'wkdir/svn_external_path/unversioned_file2',
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

