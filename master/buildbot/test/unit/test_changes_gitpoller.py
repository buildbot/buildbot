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
from twisted.trial import unittest
from twisted.internet import defer
from buildbot.changes import gitpoller
from buildbot.test.util import changesource, gpo
from buildbot.util import epoch2datetime

# Test that environment variables get propagated to subprocesses (See #2116)
os.environ['TEST_THAT_ENVIRONMENT_GETS_PASSED_TO_SUBPROCESSES'] = 'TRUE'

class GitOutputParsing(gpo.GetProcessOutputMixin_v2, unittest.TestCase):
    """Test GitPoller methods for parsing git output"""
    def setUp(self):
        self.poller = gitpoller.GitPoller('git@example.com:foo/baz.git')
        self.setUpGetProcessOutput()
        
    dummyRevStr = '12345abcde'
    def _perform_git_output_test(self, methodToTest, args,
                                 desiredGoodOutput, desiredGoodResult,
                                 emptyRaisesException=True):

        # make this call to self.patch here so that we raise a SkipTest if it
        # is not supported
        self.expectCommands(gpo.Expect('git', *args))

        d = defer.succeed(None)
        def call_empty(_):
            # we should get an Exception with empty output from git
            return methodToTest(self.dummyRevStr)
        d.addCallback(call_empty)
    
        def cb_empty(_):
            if emptyRaisesException:
                self.fail("getProcessOutput should have failed on empty output")
        def eb_empty(f):
            if not emptyRaisesException:
                self.fail("getProcessOutput should NOT have failed on empty output")
        d.addCallbacks(cb_empty, eb_empty)
        d.addCallback(lambda _: self.assertAllCommandsRan())

        # and the method shouldn't supress any exceptions
        self.expectCommands(gpo.Expect('git', *args).stderr("some error"))
        def call_exception(_):
            return methodToTest(self.dummyRevStr)
        d.addCallback(call_exception)
    
        def cb_exception(_):
            self.fail("getProcessOutput should have failed on stderr output")
        def eb_exception(f):
            pass
        d.addCallbacks(cb_exception, eb_exception)
        d.addCallback(lambda _: self.assertAllCommandsRan())

        # finally we should get what's expected from good output
        self.expectCommands(gpo.Expect('git', *args).stdout(desiredGoodOutput))
        def call_desired(_):
            return methodToTest(self.dummyRevStr)
        d.addCallback(call_desired)
    
        def cb_desired(r):
            self.assertEquals(r, desiredGoodResult)
        d.addCallback(cb_desired)
        d.addCallback(lambda _: self.assertAllCommandsRan())
        
    def test_get_commit_author(self):
        authorStr = 'Sammy Jankis <email@example.com>'
        return self._perform_git_output_test(self.poller._get_commit_author,
                ['log', self.dummyRevStr, '--no-walk', '--format=%aN <%aE>'],
                authorStr, authorStr)
        
    def test_get_commit_comments(self):
        commentStr = 'this is a commit message\n\nthat is multiline'
        return self._perform_git_output_test(self.poller._get_commit_comments,
                ['log', self.dummyRevStr, '--no-walk', '--format=%s%n%b'],
                commentStr, commentStr)
        
    def test_get_commit_files(self):
        filesStr = 'file1\nfile2'
        return self._perform_git_output_test(self.poller._get_commit_files,
                ['log', self.dummyRevStr, '--name-only', '--no-walk', '--format=%n'],
                filesStr,
                                      filesStr.split(), emptyRaisesException=False)    
        
    def test_get_commit_timestamp(self):
        stampStr = '1273258009'
        return self._perform_git_output_test(self.poller._get_commit_timestamp,
                ['log', self.dummyRevStr, '--no-walk', '--format=%ct'],
                stampStr, float(stampStr))

    # _get_changes is tested in TestGitPoller, below

class TestGitPoller(gpo.GetProcessOutputMixin_v2,
                    changesource.ChangeSourceMixin,
                    unittest.TestCase):

    def setUp(self):
        self.setUpGetProcessOutput()
        d = self.setUpChangeSource()
        def create_poller(_):
            self.poller = gitpoller.GitPoller('git@example.com:foo/baz.git')
            self.poller.master = self.master
        d.addCallback(create_poller)
        return d
        
    def tearDown(self):
        return self.tearDownChangeSource()

    def test_describe(self):
        self.assertSubstring("GitPoller", self.poller.describe())

    def test_gitbin_default(self):
        self.assertEqual(self.poller.gitbin, "git")

    def test_poll(self):
        # Test that environment variables get propagated to subprocesses (See #2116)
        self.patch(os, 'environ', {'TEST_THAT_ENVIRONMENT_GETS_PASSED_TO_SUBPROCESSES': 'TRUE'})
        self.addGetProcessOutputExpectEnv({'TEST_THAT_ENVIRONMENT_GETS_PASSED_TO_SUBPROCESSES': 'TRUE'})

        # patch out getProcessOutput and getProcessOutputAndValue for the
        # benefit of the _get_changes method
        self.expectCommands(
                gpo.Expect('git', 'fetch', 'origin').stdout('no interesting output'),
                gpo.Expect('git', 'log', 'master..origin/master', '--format=%H').stdout(
                    '\n'.join([
                        '64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                        '4423cdbcbb89c14e50dd5f4152415afd686c5241'])),
                gpo.Expect('git', 'reset', '--hard', 'origin/master').stdout('done'))

        # and patch out the _get_commit_foo methods which were already tested
        # above
        def timestamp(rev):
            return defer.succeed(1273258009.0)
        self.patch(self.poller, '_get_commit_timestamp', timestamp)
        def author(rev):
            return defer.succeed('by:' + rev[:8])
        self.patch(self.poller, '_get_commit_author', author)
        def files(rev):
            return defer.succeed(['/etc/' + rev[:3]])
        self.patch(self.poller, '_get_commit_files', files)
        def comments(rev):
            return defer.succeed('hello!')
        self.patch(self.poller, '_get_commit_comments', comments)

        # do the poll
        d = self.poller.poll()

        # check the results
        def check_changes(_):
            self.assertEqual(len(self.changes_added), 2)
            self.assertEqual(self.changes_added[0]['author'], 'by:4423cdbc')
            self.assertEqual(self.changes_added[0]['when_timestamp'],
                                        epoch2datetime(1273258009))
            self.assertEqual(self.changes_added[0]['comments'], 'hello!')
            self.assertEqual(self.changes_added[0]['branch'], 'master')
            self.assertEqual(self.changes_added[0]['files'], [ '/etc/442' ])
            self.assertEqual(self.changes_added[0]['src'], 'git')
            self.assertEqual(self.changes_added[1]['author'], 'by:64a5dc2a')
            self.assertEqual(self.changes_added[1]['when_timestamp'],
                                        epoch2datetime(1273258009))
            self.assertEqual(self.changes_added[1]['comments'], 'hello!')
            self.assertEqual(self.changes_added[1]['files'], [ '/etc/64a' ])
            self.assertEqual(self.changes_added[1]['src'], 'git')
            self.assertAllCommandsRan()
        d.addCallback(check_changes)

        return d
