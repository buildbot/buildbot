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
from future.utils import string_types
from future.utils import text_type

import os
import re

import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.changes import base
from buildbot.changes import gitpoller
from buildbot.test.util import changesource
from buildbot.test.util import config
from buildbot.test.util import gpo
from buildbot.test.util import logging
from buildbot.util import bytes2NativeString
from buildbot.util import bytes2unicode

# Test that environment variables get propagated to subprocesses (See #2116)
os.environ['TEST_THAT_ENVIRONMENT_GETS_PASSED_TO_SUBPROCESSES'] = 'TRUE'


class GitOutputParsing(gpo.GetProcessOutputMixin, unittest.TestCase):

    """Test GitPoller methods for parsing git output"""

    def setUp(self):
        self.poller = gitpoller.GitPoller('git@example.com:foo/baz.git')
        self.setUpGetProcessOutput()

    dummyRevStr = b'12345abcde'

    def _perform_git_output_test(self, methodToTest, args,
                                 desiredGoodOutput, desiredGoodResult,
                                 emptyRaisesException=True):

        # make this call to self.patch here so that we raise a SkipTest if it
        # is not supported
        self.expectCommands(
            gpo.Expect(b'git', *args)
            .path(b'gitpoller-work'),
        )

        d = defer.succeed(None)

        @d.addCallback
        def call_empty(_):
            # we should get an Exception with empty output from git
            return methodToTest(self.dummyRevStr)

        def cb_empty(_):
            if emptyRaisesException:
                self.fail(
                    "getProcessOutput should have failed on empty output")

        def eb_empty(f):
            if not emptyRaisesException:
                self.fail(
                    "getProcessOutput should NOT have failed on empty output")

        d.addCallbacks(cb_empty, eb_empty)
        d.addCallback(lambda _: self.assertAllCommandsRan())

        # and the method shouldn't suppress any exceptions
        self.expectCommands(
            gpo.Expect(b'git', *args)
            .path(b'gitpoller-work')
            .exit(1),
        )

        @d.addCallback
        def call_exception(_):
            return methodToTest(self.dummyRevStr)

        def cb_exception(_):
            self.fail("getProcessOutput should have failed on stderr output")

        def eb_exception(f):
            pass
        d.addCallbacks(cb_exception, eb_exception)
        d.addCallback(lambda _: self.assertAllCommandsRan())

        # finally we should get what's expected from good output
        self.expectCommands(
            gpo.Expect(b'git', *args)
            .path(b'gitpoller-work')
            .stdout(desiredGoodOutput)
        )

        @d.addCallback
        def call_desired(_):
            return methodToTest(self.dummyRevStr)

        @d.addCallback
        def cb_desired(r):
            self.assertEqual(r, desiredGoodResult)
            # check types
            if isinstance(r, string_types):
                self.assertIsInstance(r, text_type)
            elif isinstance(r, list):
                [self.assertIsInstance(e, text_type) for e in r]
        d.addCallback(lambda _: self.assertAllCommandsRan())
        return d

    def test_get_commit_author(self):
        authorStr = u'Sammy Jankis <email@example.com>'
        return self._perform_git_output_test(self.poller._get_commit_author,
                                             [b'log', b'--no-walk', b'--format=%aN <%aE>',
                                                 self.dummyRevStr, b'--'],
                                             authorStr, authorStr)

    def _test_get_commit_comments(self, commentStr):
        return self._perform_git_output_test(self.poller._get_commit_comments,
                                             [b'log', b'--no-walk', b'--format=%s%n%b',
                                                 self.dummyRevStr, b'--'],
                                             commentStr, commentStr, emptyRaisesException=False)

    def test_get_commit_comments(self):
        comments = [u'this is a commit message\n\nthat is multiline',
                    u'single line message', u'']
        return defer.DeferredList([self._test_get_commit_comments(commentStr) for commentStr in comments])

    def test_get_commit_files(self):
        filesStr = '\n\nfile1\nfile2\n"\146ile_octal"\nfile space'
        filesRes = ['file1', 'file2', 'file_octal', 'file space']
        return self._perform_git_output_test(self.poller._get_commit_files,
                                             [b'log', b'--name-only', b'--no-walk',
                                                 b'--format=%n', self.dummyRevStr, b'--'],
                                             filesStr, filesRes, emptyRaisesException=False)

    def test_get_commit_files_with_space_in_changed_files(self):
        filesStr = 'normal_directory/file1\ndirectory with space/file2'
        return self._perform_git_output_test(
            self.poller._get_commit_files,
            [b'log', b'--name-only', b'--no-walk',
                b'--format=%n', self.dummyRevStr, b'--'],
            filesStr,
            [l for l in filesStr.splitlines() if l.strip()],
            emptyRaisesException=False,
        )

    def test_get_commit_timestamp(self):
        stampStr = '1273258009'
        return self._perform_git_output_test(self.poller._get_commit_timestamp,
                                             [b'log', b'--no-walk', b'--format=%ct',
                                                 self.dummyRevStr, b'--'],
                                             stampStr, float(stampStr))

    # _get_changes is tested in TestGitPoller, below


class TestGitPoller(gpo.GetProcessOutputMixin,
                    changesource.ChangeSourceMixin,
                    logging.LoggingMixin,
                    unittest.TestCase):

    REPOURL = b'git@example.com:foo/baz.git'
    REPOURL_QUOTED = b'git%40example.com%3Afoo%2Fbaz.git'

    def setUp(self):
        self.setUpGetProcessOutput()
        d = self.setUpChangeSource()

        @d.addCallback
        def create_poller(_):
            self.poller = gitpoller.GitPoller(self.REPOURL)
            self.poller.setServiceParent(self.master)
        return d

    def tearDown(self):
        return self.tearDownChangeSource()

    def test_describe(self):
        self.assertSubstring("GitPoller", self.poller.describe())

    def test_name(self):
        self.assertEqual(bytes2unicode(self.REPOURL),
                         bytes2unicode(self.poller.name))

        # and one with explicit name...
        other = gitpoller.GitPoller(self.REPOURL, name="MyName")
        self.assertEqual("MyName", other.name)

    def test_poll_initial(self):
        self.expectCommands(
            gpo.Expect(b'git', b'init', b'--bare', b'gitpoller-work'),
            gpo.Expect(b'git', b'fetch', self.REPOURL,
                       b'+master:refs/buildbot/' + self.REPOURL_QUOTED + b'/master')
            .path(b'gitpoller-work'),
            gpo.Expect(b'git', b'rev-parse',
                       b'refs/buildbot/' + self.REPOURL_QUOTED + b'/master')
            .path(b'gitpoller-work')
            .stdout('bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5\n'),
        )

        d = self.poller.poll()

        @d.addCallback
        def cb(_):
            self.assertAllCommandsRan()
            self.assertEqual(self.poller.lastRev, {
                'master': 'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5'
            })
            self.master.db.state.assertStateByClass(
                name=bytes2NativeString(self.REPOURL), class_name='GitPoller',
                lastRev={
                    'master': 'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5'
                })
        return d

    def test_poll_failInit(self):
        self.expectCommands(
            gpo.Expect(b'git', b'init', b'--bare', b'gitpoller-work')
            .exit(1),
        )

        d = self.assertFailure(self.poller.poll(), EnvironmentError)

        d.addCallback(lambda _: self.assertAllCommandsRan())
        return d

    def test_poll_failFetch(self):
        self.expectCommands(
            gpo.Expect(b'git', b'init', b'--bare', b'gitpoller-work'),
            gpo.Expect(b'git', b'fetch', self.REPOURL,
                       b'+master:refs/buildbot/' + self.REPOURL_QUOTED + b'/master')
            .path(b'gitpoller-work')
            .exit(1),
        )

        d = self.assertFailure(self.poller.poll(), EnvironmentError)
        d.addCallback(lambda _: self.assertAllCommandsRan())
        return d

    def test_poll_failRevParse(self):
        self.expectCommands(
            gpo.Expect(b'git', b'init', b'--bare', b'gitpoller-work'),
            gpo.Expect(b'git', b'fetch', self.REPOURL,
                       b'+master:refs/buildbot/' + self.REPOURL_QUOTED + b'/master')
            .path(b'gitpoller-work'),
            gpo.Expect(b'git', b'rev-parse',
                       b'refs/buildbot/%s/master' % self.REPOURL_QUOTED)
            .path(b'gitpoller-work')
            .exit(1),
        )

        d = self.poller.poll()

        @d.addCallback
        def cb(_):
            self.assertAllCommandsRan()
            self.assertEqual(len(self.flushLoggedErrors()), 1)
            self.assertEqual(self.poller.lastRev, {})

    def test_poll_failLog(self):
        self.expectCommands(
            gpo.Expect(b'git', b'init', b'--bare', b'gitpoller-work'),
            gpo.Expect(b'git', b'fetch', self.REPOURL,
                       b'+master:refs/buildbot/%s/master' % self.REPOURL_QUOTED)
            .path(b'gitpoller-work'),
            gpo.Expect(b'git', b'rev-parse',
                       b'refs/buildbot/' + self.REPOURL_QUOTED + b'/master')
            .path(b'gitpoller-work')
            .stdout('4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect(b'git', b'log',
                       b'--format=%H',
                       b'4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       b'^fa3ae8ed68e664d4db24798611b352e3c6509930',
                       b'--')
            .path(b'gitpoller-work')
            .exit(1),
        )

        # do the poll
        self.poller.lastRev = {
            'master': 'fa3ae8ed68e664d4db24798611b352e3c6509930'
        }
        d = self.poller.poll()

        @d.addCallback
        def cb(_):
            self.assertAllCommandsRan()
            self.assertEqual(len(self.flushLoggedErrors()), 1)
            self.assertEqual(self.poller.lastRev, {
                'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241'
            })

    def test_poll_GitError(self):
        # Raised when git exits with status code 128. See issue 2468
        self.expectCommands(
            gpo.Expect(b'git', b'init', b'--bare', b'gitpoller-work')
            .exit(128),
        )

        d = self.assertFailure(self.poller._dovccmd('init', ['--bare',
                                                             'gitpoller-work']), gitpoller.GitError)

        d.addCallback(lambda _: self.assertAllCommandsRan())
        return d

    def test_poll_GitError_log(self):
        self.setUpLogging()
        self.expectCommands(
            gpo.Expect(b'git', b'init', b'--bare', b'gitpoller-work')
            .exit(128),
        )

        d = self.poller.poll()
        d.addCallback(lambda _: self.assertAllCommandsRan())
        self.assertLogged("command.*on repourl.*failed.*exit code 128.*")
        return d

    def test_poll_nothingNew(self):
        # Test that environment variables get propagated to subprocesses
        # (See #2116)
        self.patch(os, 'environ', {'ENVVAR': 'TRUE'})
        self.addGetProcessOutputExpectEnv({'ENVVAR': 'TRUE'})

        self.expectCommands(
            gpo.Expect(b'git', b'init', b'--bare', b'gitpoller-work'),
            gpo.Expect(b'git', b'fetch', self.REPOURL,
                       b'+master:refs/buildbot/' + self.REPOURL_QUOTED + b'/master')
            .path(b'gitpoller-work')
            .stdout('no interesting output'),
            gpo.Expect(b'git', b'rev-parse',
                       b'refs/buildbot/' + self.REPOURL_QUOTED + b'/master')
            .path(b'gitpoller-work')
            .stdout('4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect(b'git', b'log',
                       b'--format=%H',
                       b'4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       b'^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       b'--')
            .path(b'gitpoller-work')
            .stdout(''),
        )

        self.poller.lastRev = {
            'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241'
        }
        d = self.poller.poll()

        @d.addCallback
        def cb(_):
            self.assertAllCommandsRan()
            self.master.db.state.assertStateByClass(
                name=bytes2NativeString(self.REPOURL), class_name='GitPoller',
                lastRev={
                    'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241'
                })
        return d

    def test_poll_multipleBranches_initial(self):
        self.expectCommands(
            gpo.Expect(b'git', b'init', b'--bare', b'gitpoller-work'),
            gpo.Expect(b'git', b'fetch', self.REPOURL,
                       b'+master:refs/buildbot/' + self.REPOURL_QUOTED + b'/master',
                       b'+release:refs/buildbot/' + self.REPOURL_QUOTED + b'/release')
            .path(b'gitpoller-work'),
            gpo.Expect(b'git', b'rev-parse',
                       b'refs/buildbot/' + self.REPOURL_QUOTED + b'/master')
            .path(b'gitpoller-work')
            .stdout('4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect(b'git', b'rev-parse',
                       b'refs/buildbot/' + self.REPOURL_QUOTED + b'/release')
            .path(b'gitpoller-work')
            .stdout('9118f4ab71963d23d02d4bdc54876ac8bf05acf2'),
        )

        # do the poll
        self.poller.branches = ['master', 'release']
        d = self.poller.poll()

        @d.addCallback
        def cb(_):
            self.assertAllCommandsRan()
            self.assertEqual(self.poller.lastRev, {
                'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                'release': '9118f4ab71963d23d02d4bdc54876ac8bf05acf2'
            })

        return d

    def test_poll_multipleBranches(self):
        self.expectCommands(
            gpo.Expect(b'git', b'init', b'--bare', b'gitpoller-work'),
            gpo.Expect(b'git', b'fetch', self.REPOURL,
                       b'+master:refs/buildbot/%s/master' % self.REPOURL_QUOTED,
                       b'+release:refs/buildbot/%s/release' % self.REPOURL_QUOTED)
            .path(b'gitpoller-work'),
            gpo.Expect(b'git', b'rev-parse',
                       b'refs/buildbot/%s/master' % self.REPOURL_QUOTED)
            .path(b'gitpoller-work')
            .stdout('4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect(b'git', b'log',
                       b'--format=%H',
                       b'4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       b'^bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
                       b'^fa3ae8ed68e664d4db24798611b352e3c6509930',
                       b'--')
            .path(b'gitpoller-work')
            .stdout('\n'.join([
                '64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241'])),
            gpo.Expect(b'git', b'rev-parse',
                       b'refs/buildbot/' + self.REPOURL_QUOTED + b'/release')
            .path(b'gitpoller-work')
            .stdout('9118f4ab71963d23d02d4bdc54876ac8bf05acf2'),
            gpo.Expect(b'git', b'log',
                       b'--format=%H',
                       b'9118f4ab71963d23d02d4bdc54876ac8bf05acf2',
                       b'^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       b'^bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
                       b'--')
            .path(b'gitpoller-work')
            .stdout('\n'.join([
                '9118f4ab71963d23d02d4bdc54876ac8bf05acf2'
            ])),
        )

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
        self.poller.branches = ['master', 'release']
        self.poller.lastRev = {
            'master': 'fa3ae8ed68e664d4db24798611b352e3c6509930',
            'release': 'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5'
        }
        d = self.poller.poll()

        @d.addCallback
        def cb(_):
            self.assertAllCommandsRan()
            self.assertEqual(self.poller.lastRev, {
                'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                'release': '9118f4ab71963d23d02d4bdc54876ac8bf05acf2'
            })

            self.assertEqual(self.master.data.updates.changesAdded, [
                {
                    'author': u'by:4423cdbc',
                    'branch': u'master',
                    'category': None,
                    'codebase': None,
                    'comments': u'hello!',
                    'files': [u'/etc/442'],
                    'project': '',
                    'properties': {},
                    'repository': 'git@example.com:foo/baz.git',
                    'revision': '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                    'revlink': '',
                    'src': 'git',
                    'when_timestamp': 1273258009,
                },
                {
                    'author': u'by:64a5dc2a',
                    'branch': u'master',
                    'category': None,
                    'codebase': None,
                    'comments': u'hello!',
                    'files': [u'/etc/64a'],
                    'project': '',
                    'properties': {},
                    'repository': 'git@example.com:foo/baz.git',
                    'revision': '64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                    'revlink': '',
                    'src': 'git',
                    'when_timestamp': 1273258009,
                },
                {
                    'author': u'by:9118f4ab',
                    'branch': u'release',
                    'category': None,
                    'codebase': None,
                    'comments': u'hello!',
                    'files': [u'/etc/911'],
                    'project': '',
                    'properties': {},
                    'repository': 'git@example.com:foo/baz.git',
                    'revision': '9118f4ab71963d23d02d4bdc54876ac8bf05acf2',
                    'revlink': '',
                    'src': 'git',
                    'when_timestamp': 1273258009,
                }
            ])

        return d

    @defer.inlineCallbacks
    def test_poll_multipleBranches_buildPushesWithNoCommits_default(self):
        self.expectCommands(
            gpo.Expect(b'git', b'init', b'--bare', b'gitpoller-work'),
            gpo.Expect(b'git', b'fetch', self.REPOURL,
                       b'+release:refs/buildbot/' + self.REPOURL_QUOTED + b'/release')
            .path(b'gitpoller-work'),

            gpo.Expect(b'git', b'rev-parse',
                       b'refs/buildbot/' + self.REPOURL_QUOTED + b'/release')
            .path(b'gitpoller-work')
            .stdout('4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect(b'git', b'log',
                       b'--format=%H',
                       b'4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       b'^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       b'--')
            .path(b'gitpoller-work')
            .stdout(''),
        )

        # do the poll
        self.poller.branches = ['release']
        self.poller.lastRev = {
            'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241',

        }

        yield self.poller.poll()

        self.assertAllCommandsRan()
        self.assertEqual(self.poller.lastRev, {
            'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241',
            'release': '4423cdbcbb89c14e50dd5f4152415afd686c5241'
        })
        self.assertEqual(len(self.master.data.updates.changesAdded), 0)

    @defer.inlineCallbacks
    def test_poll_multipleBranches_buildPushesWithNoCommits_true(self):
        self.expectCommands(
            gpo.Expect(b'git', b'init', b'--bare', b'gitpoller-work'),
            gpo.Expect(b'git', b'fetch', self.REPOURL,
                       b'+release:refs/buildbot/' + self.REPOURL_QUOTED + b'/release')
            .path(b'gitpoller-work'),

            gpo.Expect(b'git', b'rev-parse',
                       b'refs/buildbot/' + self.REPOURL_QUOTED + b'/release')
            .path(b'gitpoller-work')
            .stdout('4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect(b'git', b'log',
                       b'--format=%H',
                       b'4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       b'^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       b'--')
            .path(b'gitpoller-work')
            .stdout(''),
        )

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
        self.poller.branches = ['release']
        self.poller.lastRev = {
            'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241',

        }

        self.poller.buildPushesWithNoCommits = True
        yield self.poller.poll()

        self.assertAllCommandsRan()
        self.assertEqual(self.poller.lastRev, {
            'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241',
            'release': '4423cdbcbb89c14e50dd5f4152415afd686c5241'
        })
        self.assertEqual(self.master.data.updates.changesAdded, [
            {'author': u'by:4423cdbc',
             'branch': u'release',
             'category': None,
             'codebase': None,
             'comments': u'hello!',
             'files': [u'/etc/442'],
             'project': u'',
             'properties': {},
             'repository': u'git@example.com:foo/baz.git',
             'revision': u'4423cdbcbb89c14e50dd5f4152415afd686c5241',
             'revlink': u'',
             'src': u'git',
             'when_timestamp': 1273258009}]
        )

    @defer.inlineCallbacks
    def test_poll_multipleBranches_buildPushesWithNoCommits_true_fast_forward(self):
        self.expectCommands(
            gpo.Expect(b'git', b'init', b'--bare', b'gitpoller-work'),
            gpo.Expect(b'git', b'fetch', self.REPOURL,
                       b'+release:refs/buildbot/' + self.REPOURL_QUOTED + b'/release')
            .path(b'gitpoller-work'),

            gpo.Expect(b'git', b'rev-parse',
                       b'refs/buildbot/' + self.REPOURL_QUOTED + b'/release')
            .path(b'gitpoller-work')
            .stdout('4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect(b'git', b'log',
                       b'--format=%H',
                       b'4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       b'^0ba9d553b7217ab4bbad89ad56dc0332c7d57a8c',
                       b'^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       b'--')
            .path(b'gitpoller-work')
            .stdout(''),
        )

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
        self.poller.branches = ['release']
        self.poller.lastRev = {
            'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241',
            'release': '0ba9d553b7217ab4bbad89ad56dc0332c7d57a8c'

        }

        self.poller.buildPushesWithNoCommits = True
        yield self.poller.poll()

        self.assertAllCommandsRan()
        self.assertEqual(self.poller.lastRev, {
            'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241',
            'release': '4423cdbcbb89c14e50dd5f4152415afd686c5241'
        })
        self.assertEqual(self.master.data.updates.changesAdded, [
            {'author': u'by:4423cdbc',
             'branch': u'release',
             'category': None,
             'codebase': None,
             'comments': u'hello!',
             'files': [u'/etc/442'],
             'project': u'',
             'properties': {},
             'repository': u'git@example.com:foo/baz.git',
             'revision': u'4423cdbcbb89c14e50dd5f4152415afd686c5241',
             'revlink': u'',
             'src': u'git',
             'when_timestamp': 1273258009}]
        )

    def test_poll_allBranches_single(self):
        self.expectCommands(
            gpo.Expect(b'git', b'init', b'--bare', b'gitpoller-work'),
            gpo.Expect(b'git', b'ls-remote', self.REPOURL)
            .stdout('4423cdbcbb89c14e50dd5f4152415afd686c5241\t'
                    'refs/heads/master\n'),
            gpo.Expect(b'git', b'fetch', self.REPOURL,
                       b'+master:refs/buildbot/' + self.REPOURL_QUOTED + b'/master')
            .path(b'gitpoller-work'),
            gpo.Expect(b'git', b'rev-parse',
                       b'refs/buildbot/' + self.REPOURL_QUOTED + b'/master')
            .path(b'gitpoller-work')
            .stdout('4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect(
                b'git', b'log', b'--format=%H',
                b'4423cdbcbb89c14e50dd5f4152415afd686c5241',
                b'^fa3ae8ed68e664d4db24798611b352e3c6509930',
                b'--')
            .path(b'gitpoller-work')
            .stdout('\n'.join([
                '64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241'])),
        )

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
        self.poller.branches = True
        self.poller.lastRev = {
            'refs/heads/master': 'fa3ae8ed68e664d4db24798611b352e3c6509930',
        }
        d = self.poller.poll()

        @d.addCallback
        def cb(_):
            self.assertAllCommandsRan()
            self.assertEqual(self.poller.lastRev, {
                'refs/heads/master':
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
            })

            added = self.master.data.updates.changesAdded
            self.assertEqual(len(added), 2)

            self.assertEqual(added[0]['author'], 'by:4423cdbc')
            self.assertEqual(added[0]['when_timestamp'], 1273258009)
            self.assertEqual(added[0]['comments'], 'hello!')
            self.assertEqual(added[0]['branch'], 'master')
            self.assertEqual(added[0]['files'], [u'/etc/442'])
            self.assertEqual(added[0]['src'], 'git')

            self.assertEqual(added[1]['author'], 'by:64a5dc2a')
            self.assertEqual(added[1]['when_timestamp'], 1273258009)
            self.assertEqual(added[1]['comments'], 'hello!')
            self.assertEqual(added[1]['files'], [u'/etc/64a'])
            self.assertEqual(added[1]['src'], 'git')

        return d

    def test_poll_noChanges(self):
        # Test that environment variables get propagated to subprocesses
        # (See #2116)
        self.patch(os, 'environ', {'ENVVAR': 'TRUE'})
        self.addGetProcessOutputExpectEnv({'ENVVAR': 'TRUE'})

        self.expectCommands(
            gpo.Expect(b'git', b'init', b'--bare', b'gitpoller-work'),
            gpo.Expect(b'git', b'fetch', self.REPOURL,
                       b'+master:refs/buildbot/' + self.REPOURL_QUOTED + b'/master')
            .path(b'gitpoller-work')
            .stdout('no interesting output'),
            gpo.Expect(b'git', b'rev-parse',
                       b'refs/buildbot/' + self.REPOURL_QUOTED + b'/master')
            .path(b'gitpoller-work')
            .stdout('4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect(b'git', b'log',
                       b'--format=%H',
                       b'4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       b'^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       b'--')
            .path(b'gitpoller-work')
            .stdout(''),
        )

        self.poller.lastRev = {
            'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241'
        }
        d = self.poller.poll()

        @d.addCallback
        def cb(_):
            self.assertAllCommandsRan()
            self.assertEqual(self.poller.lastRev, {
                'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241'
            })
        return d

    def test_poll_allBranches_multiple(self):
        self.expectCommands(
            gpo.Expect(b'git', b'init', b'--bare', b'gitpoller-work'),
            gpo.Expect(b'git', b'ls-remote', self.REPOURL)
            .stdout('\n'.join([
                '4423cdbcbb89c14e50dd5f4152415afd686c5241\trefs/heads/master',
                '9118f4ab71963d23d02d4bdc54876ac8bf05acf2\trefs/heads/release',
            ])),
            gpo.Expect(
                b'git', b'fetch', self.REPOURL,
                b'+master:refs/buildbot/' + self.REPOURL_QUOTED + b'/master',
                b'+release:refs/buildbot/' + self.REPOURL_QUOTED + b'/release')
            .path(b'gitpoller-work'),
            gpo.Expect(b'git', b'rev-parse',
                       b'refs/buildbot/' + self.REPOURL_QUOTED + b'/master')
            .path(b'gitpoller-work')
            .stdout('4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect(
                b'git', b'log', b'--format=%H',
                b'4423cdbcbb89c14e50dd5f4152415afd686c5241',
                b'^bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
                b'^fa3ae8ed68e664d4db24798611b352e3c6509930',
                b'--')
            .path(b'gitpoller-work')
            .stdout('\n'.join([
                '64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241'])),
            gpo.Expect(
                b'git', b'rev-parse', b'refs/buildbot/%s/release' %
                self.REPOURL_QUOTED)
            .path(b'gitpoller-work')
            .stdout('9118f4ab71963d23d02d4bdc54876ac8bf05acf2'),
            gpo.Expect(
                b'git', b'log', b'--format=%H',
                b'9118f4ab71963d23d02d4bdc54876ac8bf05acf2',
                b'^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                b'^bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
                b'--')
            .path(b'gitpoller-work')
            .stdout('\n'.join(['9118f4ab71963d23d02d4bdc54876ac8bf05acf2'])),
        )

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
        self.poller.branches = True
        self.poller.lastRev = {
            'refs/heads/master': 'fa3ae8ed68e664d4db24798611b352e3c6509930',
            'refs/heads/release': 'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5'
        }
        d = self.poller.poll()

        @d.addCallback
        def cb(_):
            self.assertAllCommandsRan()
            self.assertEqual(self.poller.lastRev, {
                'refs/heads/master':
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                'refs/heads/release':
                '9118f4ab71963d23d02d4bdc54876ac8bf05acf2'
            })

            added = self.master.data.updates.changesAdded
            self.assertEqual(len(added), 3)

            self.assertEqual(added[0]['author'], 'by:4423cdbc')
            self.assertEqual(added[0]['when_timestamp'], 1273258009)
            self.assertEqual(added[0]['comments'], 'hello!')
            self.assertEqual(added[0]['branch'], 'master')
            self.assertEqual(added[0]['files'], ['/etc/442'])
            self.assertEqual(added[0]['src'], 'git')

            self.assertEqual(added[1]['author'], 'by:64a5dc2a')
            self.assertEqual(added[1]['when_timestamp'], 1273258009)
            self.assertEqual(added[1]['comments'], 'hello!')
            self.assertEqual(added[1]['files'], ['/etc/64a'])
            self.assertEqual(added[1]['src'], 'git')

            self.assertEqual(added[2]['author'], 'by:9118f4ab')
            self.assertEqual(added[2]['when_timestamp'], 1273258009)
            self.assertEqual(added[2]['comments'], 'hello!')
            self.assertEqual(added[2]['files'], ['/etc/911'])
            self.assertEqual(added[2]['src'], 'git')

        return d

    def test_poll_callableFilteredBranches(self):
        self.expectCommands(
            gpo.Expect(b'git', b'init', b'--bare', b'gitpoller-work'),
            gpo.Expect(b'git', b'ls-remote', self.REPOURL)
            .stdout('\n'.join([
                '4423cdbcbb89c14e50dd5f4152415afd686c5241\trefs/heads/master',
                '9118f4ab71963d23d02d4bdc54876ac8bf05acf2\trefs/heads/release',
            ])),
            gpo.Expect(
                b'git', b'fetch', self.REPOURL,
                b'+master:refs/buildbot/' + self.REPOURL_QUOTED + b'/master')
            .path(b'gitpoller-work'),
            gpo.Expect(b'git', b'rev-parse',
                       b'refs/buildbot/' + self.REPOURL_QUOTED + b'/master')
            .path(b'gitpoller-work')
            .stdout('4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect(
                b'git', b'log', b'--format=%H',
                b'4423cdbcbb89c14e50dd5f4152415afd686c5241',
                b'^bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
                b'^fa3ae8ed68e664d4db24798611b352e3c6509930',
                b'--')
            .path(b'gitpoller-work')
            .stdout('\n'.join([
                '64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241']))
        )

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
        class TestCallable:

            def __call__(self, branch):
                return branch == "refs/heads/master"

        self.poller.branches = TestCallable()
        self.poller.lastRev = {
            'refs/heads/master': 'fa3ae8ed68e664d4db24798611b352e3c6509930',
            'refs/heads/release': 'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5'
        }
        d = self.poller.poll()

        @d.addCallback
        def cb(_):
            self.assertAllCommandsRan()

            # The release branch id should remain unchanged,
            # because it was ignored.
            self.assertEqual(self.poller.lastRev, {
                'refs/heads/master':
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                'refs/heads/release':
                'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5'
            })

            added = self.master.data.updates.changesAdded
            self.assertEqual(len(added), 2)

            self.assertEqual(added[0]['author'], 'by:4423cdbc')
            self.assertEqual(added[0]['when_timestamp'], 1273258009)
            self.assertEqual(added[0]['comments'], 'hello!')
            self.assertEqual(added[0]['branch'], 'master')
            self.assertEqual(added[0]['files'], ['/etc/442'])
            self.assertEqual(added[0]['src'], 'git')

            self.assertEqual(added[1]['author'], 'by:64a5dc2a')
            self.assertEqual(added[1]['when_timestamp'], 1273258009)
            self.assertEqual(added[1]['comments'], 'hello!')
            self.assertEqual(added[1]['files'], ['/etc/64a'])
            self.assertEqual(added[1]['src'], 'git')

        return d

    def test_poll_branchFilter(self):
        self.expectCommands(
            gpo.Expect(b'git', b'init', b'--bare', b'gitpoller-work'),
            gpo.Expect(b'git', b'ls-remote', self.REPOURL)
            .stdout('\n'.join([
                '4423cdbcbb89c14e50dd5f4152415afd686c5241\t'
                'refs/pull/410/merge',
                '9118f4ab71963d23d02d4bdc54876ac8bf05acf2\t'
                'refs/pull/410/head',
            ])),
            gpo.Expect(
                b'git', b'fetch', self.REPOURL,
                b'+refs/pull/410/head:refs/buildbot/' + self.REPOURL_QUOTED + b'/refs/pull/410/head')
            .path(b'gitpoller-work'),
            gpo.Expect(
                b'git', b'rev-parse',
                b'refs/buildbot/' + self.REPOURL_QUOTED + b'/refs/pull/410/head')
            .path(b'gitpoller-work')
            .stdout('9118f4ab71963d23d02d4bdc54876ac8bf05acf2'),
            gpo.Expect(
                b'git', b'log', b'--format=%H',
                b'9118f4ab71963d23d02d4bdc54876ac8bf05acf2',
                b'^bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
                b'^fa3ae8ed68e664d4db24798611b352e3c6509930',
                b'--')
            .path(b'gitpoller-work')
            .stdout('\n'.join(['9118f4ab71963d23d02d4bdc54876ac8bf05acf2'])),
        )

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

        def pullFilter(branch):
            """
            Note that this isn't useful in practice, because it will only
            pick up *changes* to pull requests, not the original request.
            """
            return re.match('^refs/pull/[0-9]*/head$', branch)

        # do the poll
        self.poller.branches = pullFilter
        self.poller.lastRev = {
            'master': 'fa3ae8ed68e664d4db24798611b352e3c6509930',
            'refs/pull/410/head': 'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5'
        }
        d = self.poller.poll()

        @d.addCallback
        def cb(_):
            self.assertAllCommandsRan()
            self.assertEqual(self.poller.lastRev, {
                'master': 'fa3ae8ed68e664d4db24798611b352e3c6509930',
                'refs/pull/410/head': '9118f4ab71963d23d02d4bdc54876ac8bf05acf2'
            })

            added = self.master.data.updates.changesAdded
            self.assertEqual(len(added), 1)

            self.assertEqual(added[0]['author'], 'by:9118f4ab')
            self.assertEqual(added[0]['when_timestamp'], 1273258009)
            self.assertEqual(added[0]['comments'], 'hello!')
            self.assertEqual(added[0]['files'], [u'/etc/911'])
            self.assertEqual(added[0]['src'], 'git')

        return d

    def test_poll_old(self):
        # Test that environment variables get propagated to subprocesses
        # (See #2116)
        self.patch(os, 'environ', {'ENVVAR': 'TRUE'})
        self.addGetProcessOutputExpectEnv({'ENVVAR': 'TRUE'})

        # patch out getProcessOutput and getProcessOutputAndValue for the
        # benefit of the _get_changes method
        self.expectCommands(
            gpo.Expect(b'git', b'init', b'--bare', b'gitpoller-work'),
            gpo.Expect(b'git', b'fetch', self.REPOURL,
                       b'+master:refs/buildbot/' + self.REPOURL_QUOTED + b'/master')
            .path(b'gitpoller-work')
            .stdout('no interesting output'),
            gpo.Expect(b'git', b'rev-parse',
                       b'refs/buildbot/' + self.REPOURL_QUOTED + b'/master')
            .path(b'gitpoller-work')
            .stdout('4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect(b'git', b'log',
                       b'--format=%H',
                       b'4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       b'^fa3ae8ed68e664d4db24798611b352e3c6509930',
                       b'--')
            .path(b'gitpoller-work')
            .stdout('\n'.join([
                '64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241'
            ])),
        )

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
        self.poller.lastRev = {
            'master': 'fa3ae8ed68e664d4db24798611b352e3c6509930'
        }
        d = self.poller.poll()

        # check the results
        @d.addCallback
        def check_changes(_):
            self.assertEqual(self.poller.lastRev, {
                'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241'
            })
            self.assertEqual(self.master.data.updates.changesAdded, [{
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
            }, {
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
            }])
            self.assertAllCommandsRan()

            self.master.db.state.assertStateByClass(
                name=bytes2NativeString(self.REPOURL), class_name='GitPoller',
                lastRev={
                    'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241'
                })

        return d

    def test_poll_callableCategory(self):
        self.expectCommands(
            gpo.Expect(b'git', b'init', b'--bare', b'gitpoller-work'),
            gpo.Expect(b'git', b'ls-remote', self.REPOURL)
            .stdout('4423cdbcbb89c14e50dd5f4152415afd686c5241\t'
                    'refs/heads/master\n'),
            gpo.Expect(b'git', b'fetch', self.REPOURL,
                       b'+master:refs/buildbot/' + self.REPOURL_QUOTED + b'/master')
            .path(b'gitpoller-work'),
            gpo.Expect(b'git', b'rev-parse',
                       b'refs/buildbot/' + self.REPOURL_QUOTED + b'/master')
            .path(b'gitpoller-work')
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect(
                b'git', b'log', b'--format=%H',
                b'4423cdbcbb89c14e50dd5f4152415afd686c5241',
                b'^fa3ae8ed68e664d4db24798611b352e3c6509930',
                b'--')
            .path(b'gitpoller-work')
            .stdout('\n'.join([
                '64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241'])),
        )

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
        self.poller.branches = True

        def callableCategory(chdict):
            return chdict['revision'][:6]

        self.poller.category = callableCategory

        self.poller.lastRev = {
            'refs/heads/master': 'fa3ae8ed68e664d4db24798611b352e3c6509930',
        }
        d = self.poller.poll()

        @d.addCallback
        def cb(_):
            self.assertAllCommandsRan()
            self.assertEqual(self.poller.lastRev, {
                'refs/heads/master':
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
            })

            added = self.master.data.updates.changesAdded
            self.assertEqual(len(added), 2)

            self.assertEqual(added[0]['author'], 'by:4423cdbc')
            self.assertEqual(added[0]['when_timestamp'], 1273258009)
            self.assertEqual(added[0]['comments'], 'hello!')
            self.assertEqual(added[0]['branch'], 'master')
            self.assertEqual(added[0]['files'], [u'/etc/442'])
            self.assertEqual(added[0]['src'], 'git')
            self.assertEqual(added[0]['category'], u'4423cd')

            self.assertEqual(added[1]['author'], 'by:64a5dc2a')
            self.assertEqual(added[1]['when_timestamp'], 1273258009)
            self.assertEqual(added[1]['comments'], 'hello!')
            self.assertEqual(added[1]['files'], [u'/etc/64a'])
            self.assertEqual(added[1]['src'], 'git')
            self.assertEqual(added[1]['category'], u'64a5dc')
        return d

    # We mock out base.PollingChangeSource.startService, since it calls
    # reactor.callWhenRunning, which leaves a dirty reactor if a synchronous
    # deferred is returned from a test method.
    def test_startService(self):
        startService = mock.Mock()
        self.patch(base.PollingChangeSource, "startService", startService)
        d = self.poller.startService()

        @d.addCallback
        def check(_):
            self.assertEqual(
                self.poller.workdir, os.path.join('basedir', 'gitpoller-work'))
            self.assertEqual(self.poller.lastRev, {})
            startService.assert_called_once_with(self.poller)
        return d

    def test_startService_loadLastRev(self):
        startService = mock.Mock()
        self.patch(base.PollingChangeSource, "startService", startService)
        self.master.db.state.fakeState(
            name=bytes2NativeString(self.REPOURL), class_name='GitPoller',
            lastRev={"master": "fa3ae8ed68e664d4db24798611b352e3c6509930"},
        )

        d = self.poller.startService()

        @d.addCallback
        def check(_):
            self.assertEqual(self.poller.lastRev, {
                "master": "fa3ae8ed68e664d4db24798611b352e3c6509930"
            })
            startService.assert_called_once_with(self.poller)
        return d


class TestGitPollerConstructor(unittest.TestCase, config.ConfigErrorsMixin):

    def test_deprecatedFetchRefspec(self):
        self.assertRaisesConfigError("fetch_refspec is no longer supported",
                                     lambda: gitpoller.GitPoller("/tmp/git.git",
                                                                 fetch_refspec='not-supported'))

    def test_oldPollInterval(self):
        poller = gitpoller.GitPoller("/tmp/git.git", pollinterval=10)
        self.assertEqual(poller.pollInterval, 10)

    def test_branches_default(self):
        poller = gitpoller.GitPoller("/tmp/git.git")
        self.assertEqual(poller.branches, ["master"])

    def test_branches_oldBranch(self):
        poller = gitpoller.GitPoller("/tmp/git.git", branch='magic')
        self.assertEqual(poller.branches, ["magic"])

    def test_branches(self):
        poller = gitpoller.GitPoller("/tmp/git.git",
                                     branches=['magic', 'marker'])
        self.assertEqual(poller.branches, ["magic", "marker"])

    def test_branches_True(self):
        poller = gitpoller.GitPoller("/tmp/git.git", branches=True)
        self.assertEqual(poller.branches, True)

    def test_only_tags_True(self):
        poller = gitpoller.GitPoller("/tmp/git.git", only_tags=True)
        self.assertIsNotNone(poller.branches)

    def test_branches_andBranch(self):
        self.assertRaisesConfigError("can't specify both branch and branches",
                                     lambda: gitpoller.GitPoller("/tmp/git.git",
                                                                 branch='bad', branches=['listy']))

    def test_branches_and_only_tags(self):
        self.assertRaisesConfigError("can't specify only_tags and branch/branches",
                                     lambda: gitpoller.GitPoller("/tmp/git.git",
                                                                 only_tags=True, branches=['listy']))

    def test_branch_and_only_tags(self):
        self.assertRaisesConfigError("can't specify only_tags and branch/branches",
                                     lambda: gitpoller.GitPoller("/tmp/git.git",
                                                                 only_tags=True, branch='bad'))

    def test_gitbin_default(self):
        poller = gitpoller.GitPoller("/tmp/git.git")
        self.assertEqual(poller.gitbin, "git")
