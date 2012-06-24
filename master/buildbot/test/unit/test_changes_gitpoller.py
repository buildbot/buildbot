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
from exceptions import Exception
from buildbot.changes import gitpoller
from buildbot.test.util import changesource, gpo

# Test that environment variables get propagated to subprocesses (See #2116)
os.environ['TEST_THAT_ENVIRONMENT_GETS_PASSED_TO_SUBPROCESSES'] = 'TRUE'

class GitOutputParsing(gpo.GetProcessOutputMixin, unittest.TestCase):
    """Test GitPoller methods for parsing git output"""
    def setUp(self):
        self.poller = gitpoller.GitPoller('git@example.com:foo/baz.git')
        self.setUpGetProcessOutput()

    def tearDown(self):
        self.tearDownGetProcessOutput()
        
    def _perform_git_output_test(self, methodToTest,
                                 desiredGoodOutput, desiredGoodResult,
                                 emptyRaisesException=True):
        dummyRevStr = '12345abcde'

        # make this call to self.patch here so that we raise a SkipTest if it
        # is not supported
        self.addGetProcessOutputResult(self.gpoAnyPattern(), '')

        d = defer.succeed(None)
        def call_empty(_):
            # we should get an Exception with empty output from git
            return methodToTest(dummyRevStr)
        d.addCallback(call_empty)
    
        def cb_empty(_):
            if emptyRaisesException:
                self.fail("getProcessOutput should have failed on empty output")
        def eb_empty(f):
            if not emptyRaisesException:
                self.fail("getProcessOutput should NOT have failed on empty output")
        d.addCallbacks(cb_empty, eb_empty)

        # and the method shouldn't supress any exceptions
        def call_exception(_):
            # we should get an Exception with empty output from git
            self.addGetProcessOutputResult(self.gpoAnyPattern(),
                    lambda b, a, **k: defer.fail(Exception('fake')))
            return methodToTest(dummyRevStr)
        d.addCallback(call_exception)
    
        def cb_exception(_):
            self.fail("getProcessOutput should have failed on empty output")
        def eb_exception(f):
            pass
        d.addCallbacks(cb_exception, eb_exception)

        # finally we should get what's expected from good output
        def call_desired(_):
            self.addGetProcessOutputResult(self.gpoAnyPattern(),
                desiredGoodOutput)
            return methodToTest(dummyRevStr)
        d.addCallback(call_desired)
    
        def cb_desired(r):
            self.assertEquals(r, desiredGoodResult)
            # check types
            if isinstance(r, basestring):
                self.assertIsInstance(r, unicode)
            elif isinstance(r, list):
                [ self.assertIsInstance(e, unicode) for e in r ]
        d.addCallback(cb_desired)

    def test_get_commit_author(self):
        authorStr = 'Sammy Jankis <email@example.com>'
        return self._perform_git_output_test(self.poller._get_commit_author,
                authorStr, authorStr)

    def test_get_commit_comments(self):
        commentStr = 'this is a commit message\n\nthat is multiline'
        return self._perform_git_output_test(self.poller._get_commit_comments,
                commentStr, commentStr)

    def test_get_commit_files(self):
        filesStr = 'file1\nfile2'
        return self._perform_git_output_test(self.poller._get_commit_files,
                filesStr, filesStr.split(),
                emptyRaisesException=False)

    def test_get_commit_timestamp(self):
        stampStr = '1273258009'
        return self._perform_git_output_test(self.poller._get_commit_timestamp,
                stampStr, int(stampStr))

    # _get_changes is tested in TestGitPoller, below

class TestGitPoller(gpo.GetProcessOutputMixin,
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
        self.tearDownGetProcessOutput()
        return self.tearDownChangeSource()

    def test_describe(self):
        self.assertSubstring("GitPoller", self.poller.describe())

    def test_gitbin_default(self):
        self.assertEqual(self.poller.gitbin, "git")

    def test_poll(self):
        # Test that environment variables get propagated to subprocesses (See #2116)
        os.putenv('TEST_THAT_ENVIRONMENT_GETS_PASSED_TO_SUBPROCESSES', 'TRUE')
        self.addGetProcessOutputExpectEnv({'TEST_THAT_ENVIRONMENT_GETS_PASSED_TO_SUBPROCESSES': 'TRUE'})
        self.addGetProcessOutputAndValueExpectEnv({'TEST_THAT_ENVIRONMENT_GETS_PASSED_TO_SUBPROCESSES': 'TRUE'})

        # patch out getProcessOutput and getProcessOutputAndValue for the
        # benefit of the _get_changes method
        self.addGetProcessOutputResult(
                self.gpoSubcommandPattern('git', 'fetch'),
                "no interesting output")
        self.addGetProcessOutputResult(
                self.gpoSubcommandPattern('git', 'log'),
                '\n'.join([
                    '64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                    '4423cdbcbb89c14e50dd5f4152415afd686c5241']))
        self.addGetProcessOutputAndValueResult(
                self.gpoSubcommandPattern('git', 'reset'),
                ('done', '', 0))

        # and patch out the _get_commit_foo methods which were already tested
        # above
        def timestamp(rev):
            return defer.succeed(1273258009)
        self.patch(self.poller, '_get_commit_timestamp', timestamp)
        def author(rev):
            return defer.succeed(u'by:' + rev[:8])
        self.patch(self.poller, '_get_commit_author', author)
        def files(rev):
            return defer.succeed([u'/etc/' + rev[:3]])
        self.patch(self.poller, '_get_commit_files', files)
        def comments(rev):
            return defer.succeed(u'hello!')
        self.patch(self.poller, '_get_commit_comments', comments)

        # do the poll
        d = self.poller.poll()

        # check the results
        @d.addCallback
        def check_changes(_):
            self.assertEqual(self.master.data.updates.changesAdded, [ {
                'author': 'by:4423cdbc',
                'branch': 'master',
                'category': None,
                'codebase': None,
                'comments': 'hello!',
                'files': ['/etc/442'],
                'project': '',
                'properties': {},
                'repository': 'git@example.com:foo/baz.git',
                'revision': '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                'revlink': '',
                'src': 'git',
                'when_timestamp': 1273258009,
            },
            {
                'author': 'by:64a5dc2a',
                'branch': 'master',
                'category': None,
                'codebase': None,
                'comments': 'hello!',
                'files': ['/etc/64a'],
                'project': '',
                'properties': {},
                'repository': 'git@example.com:foo/baz.git',
                'revision': '64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                'revlink': '',
                'src': 'git',
                'when_timestamp': 1273258009,
            }
            ])

        return d
