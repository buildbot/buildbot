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

from buildbot import config
from buildbot.process import buildstep
from buildbot.process import remotetransfer
from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SUCCESS
from buildbot.steps.source import svn
from buildbot.test.fake.remotecommand import Expect
from buildbot.test.fake.remotecommand import ExpectRemoteRef
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.util import sourcesteps
from buildbot.test.util.properties import ConstantRenderable


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
    svn_st_xml_corrupt = """<?xml version="1.0"?>
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
    svn_st_xml_empty = """<?xml version="1.0"?>
                          <status>
                          <target path=".">
                          </target>
                          </status>"""
    svn_info_stdout_xml = """<?xml version="1.0"?>
                            <info>
                            <entry
                               kind="dir"
                               path="."
                               revision="100">
                            <url>http://svn.red-bean.com/repos/test</url>
                            <repository>
                            <root>http://svn.red-bean.com/repos/test</root>
                            <uuid>5e7d134a-54fb-0310-bd04-b611643e5c25</uuid>
                            </repository>
                            <wc-info>
                            <schedule>normal</schedule>
                            <depth>infinity</depth>
                            </wc-info>
                            <commit
                               revision="90">
                            <author>sally</author>
                            <date>2003-01-15T23:35:12.847647Z</date>
                            </commit>
                            </entry>
                            </info>"""
    svn_info_stdout_xml_nonintegerrevision = """<?xml version="1.0"?>
                            <info>
                            <entry
                               kind="dir"
                               path="."
                               revision="a10">
                            <url>http://svn.red-bean.com/repos/test</url>
                            <repository>
                            <root>http://svn.red-bean.com/repos/test</root>
                            <uuid>5e7d134a-54fb-0310-bd04-b611643e5c25</uuid>
                            </repository>
                            <wc-info>
                            <schedule>normal</schedule>
                            <depth>infinity</depth>
                            </wc-info>
                            <commit
                               revision="a10">
                            <author>sally</author>
                            <date>2003-01-15T23:35:12.847647Z</date>
                            </commit>
                            </entry>
                            </info>"""

    def setUp(self):
        return self.setUpSourceStep()

    def tearDown(self):
        return self.tearDownSourceStep()

    def patch_workerVersionIsOlderThan(self, result):
        self.patch(svn.SVN, 'workerVersionIsOlderThan', lambda x, y, z: result)

    def test_no_repourl(self):
        self.assertRaises(config.ConfigErrors, lambda:
                          svn.SVN())

    def test_incorrect_mode(self):
        self.assertRaises(config.ConfigErrors, lambda:
                          svn.SVN(repourl='http://svn.local/app/trunk',
                                  mode='invalid'))

    def test_incorrect_method(self):
        self.assertRaises(config.ConfigErrors, lambda:
                          svn.SVN(repourl='http://svn.local/app/trunk',
                                  method='invalid'))

    def test_svn_not_installed(self):
        self.setupStep(svn.SVN(repourl='http://svn.local/app/trunk'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 1,
        )
        self.expectOutcome(result=FAILURE)
        return self.runStep()

    def test_corrupt_xml(self):
        self.setupStep(svn.SVN(repourl='http://svn.local/app/trunk'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file='wkdir/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio',
                              stdout=self.svn_st_xml_corrupt)
            + 0,
        )
        self.expectOutcome(result=FAILURE)
        return self.runStep()

    def test_revision_noninteger(self):
        svnTestStep = svn.SVN(repourl='http://svn.local/app/trunk')
        self.setupStep(svnTestStep)
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file='wkdir/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio',
                              stdout=self.svn_info_stdout_xml_nonintegerrevision)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', 'a10', 'SVN')
        d = self.runStep()

        def _checkType():
            revision = self.step.getProperty('got_revision')
            self.assertRaises(ValueError, lambda: int(revision))
        d.addCallback(lambda _: _checkType())
        return d

    def test_revision_missing(self):
        """Fail if 'revision' tag isn't there"""
        svn_info_stdout = self.svn_info_stdout_xml.replace('entry', 'Blah')

        svnTestStep = svn.SVN(repourl='http://svn.local/app/trunk')
        self.setupStep(svnTestStep)
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file='wkdir/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio',
                              stdout=svn_info_stdout)
            + 0,
        )
        self.expectOutcome(result=FAILURE)
        return self.runStep()

    def test_mode_incremental(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='incremental', username='user',
                    password='pass', extra_args=['--random']))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file='wkdir/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', ('obfuscated', 'pass', 'XXXXXX'), '--random'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', ('obfuscated', 'pass', 'XXXXXX'), '--random'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio',
                              stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
        return self.runStep()

    def test_mode_incremental_timeout(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='incremental', username='user',
                    timeout=1,
                    password='pass', extra_args=['--random']))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file='wkdir/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', ('obfuscated', 'pass', 'XXXXXX'), '--random'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
            + 0,
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', ('obfuscated', 'pass', 'XXXXXX'), '--random'])
            + 0,
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio',
                              stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
        return self.runStep()

    def test_mode_incremental_repourl_renderable(self):
        self.setupStep(
            svn.SVN(repourl=ConstantRenderable('http://svn.local/trunk'),
                    mode='incremental'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file='wkdir/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/trunk</url>""")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio',
                              stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
        return self.runStep()

    def test_mode_incremental_repourl_canonical(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/trunk/test app',
                    mode='incremental'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file='wkdir/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/trunk/test%20app</url>""")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio',
                              stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
        return self.runStep()

    def test_mode_incremental_repourl_not_updatable(self):
        self.setupStep(
            svn.SVN(repourl=ConstantRenderable('http://svn.local/trunk/app'),
                    mode='incremental',))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file='wkdir/.svn',
                                logEnviron=True))
            + 1,
            Expect('rmdir', {'dir': 'wkdir', 'logEnviron': True, 'timeout': 1200})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'checkout', 'http://svn.local/trunk/app',
                                 '.', '--non-interactive', '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio',
                              stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
        return self.runStep()

    def test_mode_incremental_retry(self):
        self.setupStep(
            svn.SVN(repourl=ConstantRenderable('http://svn.local/trunk/app'),
                    mode='incremental', retry=(0, 1)))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file='wkdir/.svn',
                                logEnviron=True))
            + 1,
            Expect('rmdir', {'dir': 'wkdir', 'logEnviron': True, 'timeout': 1200})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'checkout', 'http://svn.local/trunk/app',
                                 '.', '--non-interactive', '--no-auth-cache'])
            + 1,
            Expect('rmdir', {'dir': 'wkdir', 'logEnviron': True, 'timeout': 1200})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'checkout', 'http://svn.local/trunk/app',
                                 '.', '--non-interactive', '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio',
                              stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
        return self.runStep()

    def test_mode_incremental_repourl_not_updatable_svninfo_mismatch(self):
        self.setupStep(
            svn.SVN(repourl=ConstantRenderable('http://svn.local/trunk/app'),
                    mode='incremental'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file='wkdir/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache'])
            + ExpectShell.log('stdio',  # expecting ../trunk/app
                              stdout="""<?xml version="1.0"?><url>http://svn.local/branch/foo/app</url>""")
            + 0,
            Expect('rmdir', {'dir': 'wkdir', 'logEnviron': True, 'timeout': 1200})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'checkout', 'http://svn.local/trunk/app',
                                 '.', '--non-interactive', '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio',
                              stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
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
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file='wkdir/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update', '--revision', '100',
                                 '--non-interactive', '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio',
                              stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
        return self.runStep()

    def test_mode_incremental_win32path(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='incremental', username='user',
                    password='pass', extra_args=['--random']))
        self.build.path_module = namedModule("ntpath")
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file=r'wkdir\.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file=r'wkdir\.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', ('obfuscated', 'pass', 'XXXXXX'), '--random'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', ('obfuscated', 'pass', 'XXXXXX'), '--random'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio',
                              stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_mode_incremental_preferLastChangedRev(self):
        """Give the last-changed rev if 'preferLastChangedRev' is set"""
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='incremental', username='user',
                    preferLastChangedRev=True,
                    password='pass', extra_args=['--random']))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file='wkdir/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', ('obfuscated', 'pass', 'XXXXXX'), '--random'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', ('obfuscated', 'pass', 'XXXXXX'), '--random'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio',
                              stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '90', 'SVN')
        return self.runStep()

    def test_mode_incremental_preferLastChangedRev_butMissing(self):
        """If 'preferLastChangedRev' is set, but missing, fall back
        to the regular revision value."""
        svn_info_stdout = self.svn_info_stdout_xml.replace('commit', 'Blah')

        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='incremental', username='user',
                    preferLastChangedRev=True,
                    password='pass', extra_args=['--random']))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file='wkdir/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', ('obfuscated', 'pass', 'XXXXXX'), '--random'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', ('obfuscated', 'pass', 'XXXXXX'), '--random'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio',
                              stdout=svn_info_stdout)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
        return self.runStep()

    def test_mode_full_clobber(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='full', method='clobber'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', {'dir': 'wkdir',
                             'logEnviron': True,
                             'timeout': 1200})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'checkout',
                                 'http://svn.local/app/trunk', '.',
                                 '--non-interactive', '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio',
                              stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
        return self.runStep()

    def test_mode_full_clobber_given_revision(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='full', method='clobber'), dict(
                revision='100',
            ))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', {'dir': 'wkdir',
                             'logEnviron': True,
                             'timeout': 1200})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'checkout',
                                 'http://svn.local/app/trunk', '.',
                                 '--revision', '100',
                                 '--non-interactive', '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio',
                              stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
        return self.runStep()

    def test_mode_full_fresh(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='full', method='fresh', depth='infinite'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', {'file': 'wkdir/.svn',
                            'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache', '--depth', 'infinite'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
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
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio', stdout=self.svn_info_stdout_xml)
            + ExpectShell.log('stdio', stdout='\n')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
        return self.runStep()

    def test_mode_full_fresh_retry(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='full', method='fresh', retry=(0, 2)))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', {'file': 'wkdir/.svn',
                            'logEnviron': True})
            + 1,
            Expect('rmdir', {'dir': 'wkdir', 'logEnviron': True, 'timeout': 1200})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'checkout', 'http://svn.local/app/trunk',
                                 '.', '--non-interactive', '--no-auth-cache'])
            + 1,
            Expect('rmdir', {'dir': 'wkdir', 'logEnviron': True, 'timeout': 1200})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'checkout', 'http://svn.local/app/trunk',
                                 '.', '--non-interactive', '--no-auth-cache'])
            + 1,
            Expect('rmdir', {'dir': 'wkdir', 'logEnviron': True, 'timeout': 1200})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'checkout', 'http://svn.local/app/trunk',
                                 '.', '--non-interactive', '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio', stdout=self.svn_info_stdout_xml)
            + ExpectShell.log('stdio', stdout='\n')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
        return self.runStep()

    def test_mode_full_fresh_given_revision(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='full', method='fresh', depth='infinite'), dict(
                revision='100',
            ))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', {'file': 'wkdir/.svn',
                            'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache', '--depth', 'infinite'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
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
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio', stdout=self.svn_info_stdout_xml)
            + ExpectShell.log('stdio', stdout='\n')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
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
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', {'file': 'wkdir/.svn',
                            'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
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
                             'logEnviron': True,
                             'timeout': 1200})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update',
                                 '--non-interactive', '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio', stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
        return self.runStep()

    def test_mode_full_clean(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='full', method='clean'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', {'file': 'wkdir/.svn',
                            'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
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
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio', stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
        return self.runStep()

    def test_mode_full_clean_given_revision(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='full', method='clean'), dict(
                revision='100',
            ))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', {'file': 'wkdir/.svn',
                            'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
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
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio', stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
        return self.runStep()

    def test_mode_full_not_updatable(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='full', method='clean'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', {'file': 'wkdir/.svn',
                            'logEnviron': True})
            + 1,
            Expect('rmdir', {'dir': 'wkdir', 'logEnviron': True, 'timeout': 1200})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'checkout', 'http://svn.local/app/trunk',
                                 '.', '--non-interactive', '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio', stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
        return self.runStep()

    def test_mode_full_not_updatable_given_revision(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='full', method='clean'), dict(
                revision='100',
            ))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', {'file': 'wkdir/.svn',
                            'logEnviron': True})
            + 1,
            Expect('rmdir', {'dir': 'wkdir', 'logEnviron': True, 'timeout': 1200})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'checkout', 'http://svn.local/app/trunk',
                                 '.', '--revision', '100',
                                 '--non-interactive', '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio', stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
        return self.runStep()

    def test_mode_full_clean_old_rmdir(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='full', method='clean'))
        self.patch_workerVersionIsOlderThan(True)
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', {'file': 'wkdir/.svn',
                            'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
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
                             'logEnviron': True,
                             'timeout': 1200})
            + 0,
            Expect('rmdir', {'dir':
                             'wkdir/svn_external_path/unversioned_file2',
                             'logEnviron': True,
                             'timeout': 1200})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update',
                                 '--non-interactive', '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio', stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
        return self.runStep()

    def test_mode_full_clean_new_rmdir(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='full', method='clean'))

        self.patch_workerVersionIsOlderThan(False)
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', {'file': 'wkdir/.svn',
                            'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
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
                             'logEnviron': True,
                             'timeout': 1200})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update',
                                 '--non-interactive', '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio', stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
        return self.runStep()

    def test_mode_full_copy(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='full', method='copy',
                    codebase='app'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
            + 0,
            Expect('stat', dict(file='source/app/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='source/app',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
            + 0,
            ExpectShell(workdir='source/app',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache'])
            + 0,
            Expect('cpdir', {'fromdir': 'source/app',
                             'todir': 'wkdir',
                             'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio',
                              stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', {'app': '100'}, 'SVN')
        return self.runStep()

    def test_mode_full_copy_given_revision(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='full', method='copy'), dict(
                revision='100',
            ))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
            + 0,
            Expect('stat', dict(file='source/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='source',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
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
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio',
                              stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
        return self.runStep()

    def test_mode_full_export(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='full', method='export'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
            + 0,
            Expect('stat', dict(file='source/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='source',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
            + 0,
            ExpectShell(workdir='source',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='',
                        command=['svn', 'export', 'source', 'wkdir'])
            + 0,
            ExpectShell(workdir='source',
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio',
                              stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
        return self.runStep()

    def test_mode_full_export_patch(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='full', method='export'),
            patch=(1, 'patch'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn',
                                 'status', '--xml',
                                 '--non-interactive', '--no-auth-cache'])
            + ExpectShell.log('stdio',
                              stdout=self.svn_st_xml)
            + 0,
            Expect('rmdir', dict(dir=['wkdir/svn_external_path/unversioned_file1',
                                      'wkdir/svn_external_path/unversioned_file2'],
                                 logEnviron=True,
                                 timeout=1200))
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
            + 0,
            Expect('stat', dict(file='source/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='source',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
            + 0,
            ExpectShell(workdir='source',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='',
                        command=['svn', 'export', 'source', 'wkdir'])
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
                        command=['patch', '-p1', '--remove-empty-files',
                                 '--force', '--forward', '-i', '.buildbot-diff'])
            + 0,
            Expect('rmdir', dict(dir='wkdir/.buildbot-diff',
                                 logEnviron=True))
            + 0,
            ExpectShell(workdir='source',
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio',
                              stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
        return self.runStep()

    def test_mode_full_export_patch_worker_2_16(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='full', method='export'),
            patch=(1, 'patch'),
            worker_version={'*': '2.16'})
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn',
                                 'status', '--xml',
                                 '--non-interactive', '--no-auth-cache'])
            + ExpectShell.log('stdio',
                              stdout=self.svn_st_xml)
            + 0,
            Expect('rmdir', dict(dir=['wkdir/svn_external_path/unversioned_file1',
                                      'wkdir/svn_external_path/unversioned_file2'],
                                 logEnviron=True,
                                 timeout=1200))
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
            + 0,
            Expect('stat', dict(file='source/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='source',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
            + 0,
            ExpectShell(workdir='source',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache'])
            + 0,
            ExpectShell(workdir='',
                        command=['svn', 'export', 'source', 'wkdir'])
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
                        command=['patch', '-p1', '--remove-empty-files',
                                 '--force', '--forward', '-i', '.buildbot-diff'])
            + 0,
            Expect('rmdir', dict(dir='wkdir/.buildbot-diff',
                                 logEnviron=True))
            + 0,
            ExpectShell(workdir='source',
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio',
                              stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
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
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1))
            + 0,
            Expect('stat', dict(file='source/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='source',
                        timeout=1,
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
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
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio',
                              stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
        return self.runStep()

    def test_mode_full_export_given_revision(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='full', method='export'), dict(
                revision='100',
            ))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
            + 0,
            Expect('stat', dict(file='source/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='source',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
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
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio',
                              stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
        return self.runStep()

    def test_mode_full_export_auth(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='full', method='export', username='svn_username',
                    password='svn_password'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
            + 0,
            Expect('stat', dict(file='source/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='source',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache',
                                 '--username', 'svn_username',
                                 '--password', ('obfuscated', 'svn_password', 'XXXXXX')])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
            + 0,
            ExpectShell(workdir='source',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache',
                                 '--username', 'svn_username',
                                 '--password', ('obfuscated', 'svn_password', 'XXXXXX')])
            + 0,
            ExpectShell(workdir='',
                        command=['svn', 'export',
                                 '--username', 'svn_username',
                                 '--password', ('obfuscated', 'svn_password', 'XXXXXX'), 'source', 'wkdir'])
            + 0,
            ExpectShell(workdir='source',
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio',
                              stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
        return self.runStep()

    def test_mode_incremental_with_env(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='incremental', username='user',
                    password='pass', extra_args=['--random'],
                    env={'abc': '123'}))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'],
                        env={'abc': '123'})
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file='wkdir/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', ('obfuscated', 'pass', 'XXXXXX'), '--random'],
                        env={'abc': '123'})
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', ('obfuscated', 'pass', 'XXXXXX'), '--random'],
                        env={'abc': '123'})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml'],
                        env={'abc': '123'})
            + ExpectShell.log('stdio',
                              stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
        return self.runStep()

    def test_mode_incremental_logEnviron(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='incremental', username='user',
                    password='pass', extra_args=['--random'],
                    logEnviron=False))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'],
                        logEnviron=False)
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=False))
            + 1,
            Expect('stat', dict(file='wkdir/.svn',
                                logEnviron=False))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', ('obfuscated', 'pass', 'XXXXXX'), '--random'],
                        logEnviron=False)
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', ('obfuscated', 'pass', 'XXXXXX'), '--random'],
                        logEnviron=False)
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml'],
                        logEnviron=False)
            + ExpectShell.log('stdio',
                              stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'SVN')
        return self.runStep()

    def test_command_fails(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='incremental', username='user',
                    password='pass', extra_args=['--random']))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file='wkdir/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', ('obfuscated', 'pass', 'XXXXXX'), '--random'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', ('obfuscated', 'pass', 'XXXXXX'), '--random'])
            + 1,
        )
        self.expectOutcome(result=FAILURE)
        return self.runStep()

    def test_bogus_svnversion(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='incremental', username='user',
                    password='pass', extra_args=['--random']))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file='wkdir/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', ('obfuscated', 'pass', 'XXXXXX'), '--random'])
            +
            ExpectShell.log(
                'stdio', stdout="""<?xml version="1.0"?><entry kind="dir" path="/a/b/c" revision="1"><url>http://svn.local/app/trunk</url></entry>""")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', ('obfuscated', 'pass', 'XXXXXX'), '--random'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio',
                              stdout='1x0y0')
            + 0,
        )
        self.expectOutcome(result=FAILURE)
        return self.runStep()

    def test_rmdir_fails_clobber(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='full', method='clobber'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', {'dir': 'wkdir',
                             'logEnviron': True,
                             'timeout': 1200})
            + 1,
        )
        self.expectOutcome(result=FAILURE)
        return self.runStep()

    def test_rmdir_fails_copy(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='full', method='copy'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
            + 1,
        )
        self.expectOutcome(result=FAILURE)
        return self.runStep()

    def test_cpdir_fails_copy(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='full', method='copy'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=1200))
            + 0,
            Expect('stat', dict(file='source/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='source',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
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
        self.expectOutcome(result=FAILURE)
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
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', {'file': 'wkdir/.svn',
                            'logEnviron': True})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
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
                             'logEnviron': True,
                             'timeout': 1200})
            + 1,
        )
        self.expectOutcome(result=FAILURE)
        return self.runStep()

    def test_worker_connection_lost(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='incremental', username='user',
                    password='pass', extra_args=['--random']))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + ('err', error.ConnectionLost()),
        )
        self.expectOutcome(result=RETRY, state_string="update (retry)")
        return self.runStep()

    def test_empty_password(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='incremental', username='user',
                    password='', extra_args=['--random']))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file='wkdir/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', ('obfuscated', '', 'XXXXXX'), '--random'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--password', ('obfuscated', '', 'XXXXXX'), '--random'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio',
                              stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_omit_password(self):
        self.setupStep(
            svn.SVN(repourl='http://svn.local/app/trunk',
                    mode='incremental', username='user',
                    extra_args=['--random']))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['svn', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('stat', dict(file='wkdir/.svn',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml',
                                 '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--random'])
            + ExpectShell.log('stdio',
                              stdout="""<?xml version="1.0"?><url>http://svn.local/app/trunk</url>""")
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'update', '--non-interactive',
                                 '--no-auth-cache', '--username', 'user',
                                 '--random'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['svn', 'info', '--xml'])
            + ExpectShell.log('stdio',
                              stdout=self.svn_info_stdout_xml)
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
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
        self.assertEqual(
            ["svn_external_path/unversioned_file"], unversioned_files)

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
        self.assertEqual([], unversioned_files)

    def test_getUnversionedFiles_corrupted_xml(self):
        svn_st_xml_corrupt = """<?xml version="1.0"?>
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
                          lambda: list(svn.SVN.getUnversionedFiles(svn_st_xml_corrupt, [])))

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
        self.assertEqual([], unversioned_files)

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
        self.assertEqual(
            ["svn_external_path/unversioned_file"], unversioned_files)


class TestSvnUriCanonicalize(unittest.TestCase):
    # svn.SVN.svnUriCanonicalize() test method factory
    #
    # given input string and expected result create a test method that
    # will call svn.SVN.svnUriCanonicalize() with the input and check
    # that expected result is returned
    #
    # @param input: test input
    # @param exp: expected result

    def _makeSUCTest(input, exp):
        return lambda self: self.assertEqual(
            svn.SVN.svnUriCanonicalize(input), exp)

    test_empty = _makeSUCTest(
        "", "")
    test_canonical = _makeSUCTest(
        "http://foo.com/bar", "http://foo.com/bar")
    test_lc_scheme = _makeSUCTest(
        "hTtP://foo.com/bar", "http://foo.com/bar")
    test_trailing_dot = _makeSUCTest(
        "http://foo.com./bar", "http://foo.com/bar")
    test_lc_hostname = _makeSUCTest(
        "http://foO.COm/bar", "http://foo.com/bar")
    test_lc_hostname_with_user = _makeSUCTest(
        "http://Jimmy@fOO.Com/bar", "http://Jimmy@foo.com/bar")
    test_lc_hostname_with_user_pass = _makeSUCTest(
        "http://Jimmy:Sekrit@fOO.Com/bar", "http://Jimmy:Sekrit@foo.com/bar")
    test_trailing_slash = _makeSUCTest(
        "http://foo.com/bar/", "http://foo.com/bar")
    test_trailing_slash_scheme = _makeSUCTest(
        "http://", "http://")
    test_trailing_slash_hostname = _makeSUCTest(
        "http://foo.com/", "http://foo.com")
    test_trailing_double_slash = _makeSUCTest(
        "http://foo.com/x//", "http://foo.com/x")
    test_double_slash = _makeSUCTest(
        "http://foo.com/x//y", "http://foo.com/x/y")
    test_slash = _makeSUCTest(
        "/", "/")
    test_dot = _makeSUCTest(
        "http://foo.com/x/./y", "http://foo.com/x/y")
    test_dot_dot = _makeSUCTest(
        "http://foo.com/x/../y", "http://foo.com/y")
    test_double_dot_dot = _makeSUCTest(
        "http://foo.com/x/y/../../z", "http://foo.com/z")
    test_dot_dot_root = _makeSUCTest(
        "http://foo.com/../x/y", "http://foo.com/x/y")
    test_quote_spaces = _makeSUCTest(
        "svn+ssh://user@host:123/My Stuff/file.doc",
        "svn+ssh://user@host:123/My%20Stuff/file.doc")
    test_remove_port_80 = _makeSUCTest(
        "http://foo.com:80/bar", "http://foo.com/bar")
    test_dont_remove_port_80 = _makeSUCTest(
        "https://foo.com:80/bar", "https://foo.com:80/bar")  # not http
    test_remove_port_443 = _makeSUCTest(
        "https://foo.com:443/bar", "https://foo.com/bar")
    test_dont_remove_port_443 = _makeSUCTest(
        "svn://foo.com:443/bar", "svn://foo.com:443/bar")  # not https
    test_remove_port_3690 = _makeSUCTest(
        "svn://foo.com:3690/bar", "svn://foo.com/bar")
    test_dont_remove_port_3690 = _makeSUCTest(
        "http://foo.com:3690/bar", "http://foo.com:3690/bar")  # not svn
    test_dont_remove_port_other = _makeSUCTest(
        "https://foo.com:2093/bar", "https://foo.com:2093/bar")
    test_quote_funny_chars = _makeSUCTest(
        "http://foo.com/\x10\xe6%", "http://foo.com/%10%E6%25")
    test_overquoted = _makeSUCTest(
        "http://foo.com/%68%65%6c%6c%6f%20%77%6f%72%6c%64",
        "http://foo.com/hello%20world")
