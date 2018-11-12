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

from buildbot.changes import gitpoller
from buildbot.test.util import changesource
from buildbot.test.util import config
from buildbot.test.util import gpo
from buildbot.test.util import logging
from buildbot.util import bytes2unicode
from buildbot.util import unicode2bytes

# Test that environment variables get propagated to subprocesses (See #2116)
os.environ['TEST_THAT_ENVIRONMENT_GETS_PASSED_TO_SUBPROCESSES'] = 'TRUE'


class GitOutputParsing(gpo.GetProcessOutputMixin, unittest.TestCase):

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
        self.expectCommands(
            gpo.Expect('git', *args)
            .path('gitpoller-work'),
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
            gpo.Expect('git', *args)
            .path('gitpoller-work')
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
            gpo.Expect('git', *args)
            .path('gitpoller-work')
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
        authorBytes = unicode2bytes(authorStr)
        return self._perform_git_output_test(self.poller._get_commit_author,
                                             ['log', '--no-walk', '--format=%aN <%aE>',
                                                 self.dummyRevStr, '--'],
                                             authorBytes, authorStr)

    def _test_get_commit_comments(self, commentStr):
        commentBytes = unicode2bytes(commentStr)
        return self._perform_git_output_test(self.poller._get_commit_comments,
                                             ['log', '--no-walk', '--format=%s%n%b',
                                                 self.dummyRevStr, '--'],
                                             commentBytes, commentStr, emptyRaisesException=False)

    def test_get_commit_comments(self):
        comments = [u'this is a commit message\n\nthat is multiline',
                    u'single line message', u'']
        return defer.DeferredList([self._test_get_commit_comments(commentStr) for commentStr in comments])

    def test_get_commit_files(self):
        filesBytes = b'\n\nfile1\nfile2\n"\146ile_octal"\nfile space'
        filesRes = [u'file1', u'file2', u'file_octal', u'file space']
        return self._perform_git_output_test(self.poller._get_commit_files,
                                             ['log', '--name-only', '--no-walk',
                                              '--format=%n', self.dummyRevStr, '--'],
                                             filesBytes, filesRes, emptyRaisesException=False)

    def test_get_commit_files_with_space_in_changed_files(self):
        filesBytes = b'normal_directory/file1\ndirectory with space/file2'
        filesStr = bytes2unicode(filesBytes)
        return self._perform_git_output_test(
            self.poller._get_commit_files,
            ['log', '--name-only', '--no-walk',
             '--format=%n', self.dummyRevStr, '--'],
            filesBytes,
            [l for l in filesStr.splitlines() if l.strip()],
            emptyRaisesException=False,
        )

    def test_get_commit_timestamp(self):
        stampBytes = b'1273258009'
        stampStr = bytes2unicode(stampBytes)
        return self._perform_git_output_test(self.poller._get_commit_timestamp,
                                             ['log', '--no-walk', '--format=%ct',
                                                 self.dummyRevStr, '--'],
                                             stampBytes, float(stampStr))

    # _get_changes is tested in TestGitPoller, below


class TestGitPollerBase(gpo.GetProcessOutputMixin,
                        changesource.ChangeSourceMixin,
                        logging.LoggingMixin,
                        unittest.TestCase):

    REPOURL = 'git@example.com:foo/baz.git'
    REPOURL_QUOTED = 'git%40example.com%3Afoo%2Fbaz.git'

    def createPoller(self):
        # this is overridden in TestGitPollerWithSshPrivateKey
        return gitpoller.GitPoller(self.REPOURL)

    @defer.inlineCallbacks
    def setUp(self):
        self.setUpGetProcessOutput()
        yield self.setUpChangeSource()

        self.poller = self.createPoller()
        self.poller.setServiceParent(self.master)

    def tearDown(self):
        return self.tearDownChangeSource()


class TestGitPoller(TestGitPollerBase):

    def test_describe(self):
        self.assertSubstring("GitPoller", self.poller.describe())

    def test_name(self):
        self.assertEqual(bytes2unicode(self.REPOURL),
                         bytes2unicode(self.poller.name))

        # and one with explicit name...
        other = gitpoller.GitPoller(self.REPOURL, name="MyName")
        self.assertEqual("MyName", other.name)

    @defer.inlineCallbacks
    def test_checkGitFeatures_git_not_installed(self):
        self.setUpLogging()
        self.expectCommands(
            gpo.Expect('git', '--version')
            .stdout(b'Command not found'),
        )

        yield self.assertFailure(self.poller._checkGitFeatures(),
                                 EnvironmentError)
        self.assertAllCommandsRan()

    @defer.inlineCallbacks
    def test_checkGitFeatures_git_bad_version(self):
        self.setUpLogging()
        self.expectCommands(
            gpo.Expect('git', '--version')
            .stdout(b'git ')
        )

        yield self.assertFailure(self.poller._checkGitFeatures(),
                                 EnvironmentError)

        self.assertAllCommandsRan()

    @defer.inlineCallbacks
    def test_poll_initial(self):
        self.expectCommands(
            gpo.Expect('git', '--version')
            .stdout(b'git version 1.7.5\n'),
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'fetch', self.REPOURL,
                       '+master:refs/buildbot/' + self.REPOURL_QUOTED + '/master')
            .path('gitpoller-work'),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/' + self.REPOURL_QUOTED + '/master')
            .path('gitpoller-work')
            .stdout(b'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5\n'),
        )

        yield self.poller.poll()

        self.assertAllCommandsRan()
        self.assertEqual(self.poller.lastRev, {
            'master': 'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5'
        })
        self.master.db.state.assertStateByClass(
            name=bytes2unicode(self.REPOURL), class_name='GitPoller',
            lastRev={
                'master': 'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5'
            })

    def test_poll_failInit(self):
        self.expectCommands(
            gpo.Expect('git', '--version')
            .stdout(b'git version 1.7.5\n'),
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work')
            .exit(1),
        )

        d = self.assertFailure(self.poller.poll(), EnvironmentError)

        d.addCallback(lambda _: self.assertAllCommandsRan())
        return d

    def test_poll_failFetch(self):
        self.expectCommands(
            gpo.Expect('git', '--version')
            .stdout(b'git version 1.7.5\n'),
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'fetch', self.REPOURL,
                       '+master:refs/buildbot/' + self.REPOURL_QUOTED + '/master')
            .path('gitpoller-work')
            .exit(1),
        )

        d = self.assertFailure(self.poller.poll(), EnvironmentError)
        d.addCallback(lambda _: self.assertAllCommandsRan())
        return d

    @defer.inlineCallbacks
    def test_poll_failRevParse(self):
        self.expectCommands(
            gpo.Expect('git', '--version')
            .stdout(b'git version 1.7.5\n'),
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'fetch', self.REPOURL,
                       '+master:refs/buildbot/' + self.REPOURL_QUOTED + '/master')
            .path('gitpoller-work'),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/' + self.REPOURL_QUOTED + '/master')
            .path('gitpoller-work')
            .exit(1),
        )

        yield self.poller.poll()

        self.assertAllCommandsRan()
        self.assertEqual(len(self.flushLoggedErrors()), 1)
        self.assertEqual(self.poller.lastRev, {})

    @defer.inlineCallbacks
    def test_poll_failLog(self):
        self.expectCommands(
            gpo.Expect('git', '--version')
            .stdout(b'git version 1.7.5\n'),
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'fetch', self.REPOURL,
                       '+master:refs/buildbot/' + self.REPOURL_QUOTED + '/master')
            .path('gitpoller-work'),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/' + self.REPOURL_QUOTED + '/master')
            .path('gitpoller-work')
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect('git', 'log',
                       '--format=%H',
                       '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       '^fa3ae8ed68e664d4db24798611b352e3c6509930',
                       '--')
            .path('gitpoller-work')
            .exit(1),
        )

        # do the poll
        self.poller.lastRev = {
            'master': 'fa3ae8ed68e664d4db24798611b352e3c6509930'
        }
        yield self.poller.poll()

        self.assertAllCommandsRan()
        self.assertEqual(len(self.flushLoggedErrors()), 1)
        self.assertEqual(self.poller.lastRev, {
            'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241'
        })

    def test_poll_GitError(self):
        # Raised when git exits with status code 128. See issue 2468
        self.expectCommands(
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work')
            .exit(128),
        )

        d = self.assertFailure(self.poller._dovccmd('init', ['--bare',
                                                             'gitpoller-work']), gitpoller.GitError)

        d.addCallback(lambda _: self.assertAllCommandsRan())
        return d

    def test_poll_GitError_log(self):
        self.setUpLogging()
        self.expectCommands(
            gpo.Expect('git', '--version')
            .stdout(b'git version 1.7.5\n'),
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work')
            .exit(128),
        )

        d = self.poller.poll()
        d.addCallback(lambda _: self.assertAllCommandsRan())
        self.assertLogged("command.*on repourl.*failed.*exit code 128.*")
        return d

    @defer.inlineCallbacks
    def test_poll_nothingNew(self):
        # Test that environment variables get propagated to subprocesses
        # (See #2116)
        self.patch(os, 'environ', {'ENVVAR': 'TRUE'})
        self.addGetProcessOutputExpectEnv({'ENVVAR': 'TRUE'})

        self.expectCommands(
            gpo.Expect('git', '--version')
            .stdout(b'git version 1.7.5\n'),
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'fetch', self.REPOURL,
                       '+master:refs/buildbot/' + self.REPOURL_QUOTED + '/master')
            .path('gitpoller-work')
            .stdout(b'no interesting output'),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/' + self.REPOURL_QUOTED + '/master')
            .path('gitpoller-work')
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect('git', 'log',
                       '--format=%H',
                       '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       '^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       '--')
            .path('gitpoller-work')
            .stdout(b''),
        )

        self.poller.lastRev = {
            'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241'
        }
        yield self.poller.poll()

        self.assertAllCommandsRan()
        self.master.db.state.assertStateByClass(
            name=bytes2unicode(self.REPOURL), class_name='GitPoller',
            lastRev={
                'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241'
            })

    @defer.inlineCallbacks
    def test_poll_multipleBranches_initial(self):
        self.expectCommands(
            gpo.Expect('git', '--version')
            .stdout(b'git version 1.7.5\n'),
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'fetch', self.REPOURL,
                       '+master:refs/buildbot/' + self.REPOURL_QUOTED + '/master',
                       '+release:refs/buildbot/' + self.REPOURL_QUOTED + '/release')
            .path('gitpoller-work'),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/' + self.REPOURL_QUOTED + '/master')
            .path('gitpoller-work')
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/' + self.REPOURL_QUOTED + '/release')
            .path('gitpoller-work')
            .stdout(b'9118f4ab71963d23d02d4bdc54876ac8bf05acf2'),
        )

        # do the poll
        self.poller.branches = ['master', 'release']
        yield self.poller.poll()

        self.assertAllCommandsRan()
        self.assertEqual(self.poller.lastRev, {
            'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241',
            'release': '9118f4ab71963d23d02d4bdc54876ac8bf05acf2'
        })

    @defer.inlineCallbacks
    def test_poll_multipleBranches(self):
        self.expectCommands(
            gpo.Expect('git', '--version')
            .stdout(b'git version 1.7.5\n'),
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'fetch', self.REPOURL,
                       '+master:refs/buildbot/' + self.REPOURL_QUOTED + '/master',
                       '+release:refs/buildbot/' + self.REPOURL_QUOTED + '/release')
            .path('gitpoller-work'),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/' + self.REPOURL_QUOTED + '/master')
            .path('gitpoller-work')
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect('git', 'log',
                       '--format=%H',
                       '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       '^bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
                       '^fa3ae8ed68e664d4db24798611b352e3c6509930',
                       '--')
            .path('gitpoller-work')
            .stdout(b'\n'.join([
                b'64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                b'4423cdbcbb89c14e50dd5f4152415afd686c5241'])),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/' + self.REPOURL_QUOTED + '/release')
            .path('gitpoller-work')
            .stdout(b'9118f4ab71963d23d02d4bdc54876ac8bf05acf2'),
            gpo.Expect('git', 'log',
                       '--format=%H',
                       '9118f4ab71963d23d02d4bdc54876ac8bf05acf2',
                       '^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       '^bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
                       '--')
            .path('gitpoller-work')
            .stdout(b'\n'.join([
                b'9118f4ab71963d23d02d4bdc54876ac8bf05acf2'
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
        yield self.poller.poll()

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

    @defer.inlineCallbacks
    def test_poll_multipleBranches_buildPushesWithNoCommits_default(self):
        self.expectCommands(
            gpo.Expect('git', '--version')
            .stdout(b'git version 1.7.5\n'),
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'fetch', self.REPOURL,
                       '+release:refs/buildbot/' + self.REPOURL_QUOTED + '/release')
            .path('gitpoller-work'),

            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/' + self.REPOURL_QUOTED + '/release')
            .path('gitpoller-work')
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect('git', 'log',
                       '--format=%H',
                       '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       '^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       '--')
            .path('gitpoller-work')
            .stdout(b''),
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
            gpo.Expect('git', '--version')
            .stdout(b'git version 1.7.5\n'),
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'fetch', self.REPOURL,
                       '+release:refs/buildbot/' + self.REPOURL_QUOTED + '/release')
            .path('gitpoller-work'),

            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/' + self.REPOURL_QUOTED + '/release')
            .path('gitpoller-work')
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect('git', 'log',
                       '--format=%H',
                       '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       '^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       '--')
            .path('gitpoller-work')
            .stdout(b''),
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
            gpo.Expect('git', '--version')
            .stdout(b'git version 1.7.5\n'),
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'fetch', self.REPOURL,
                       '+release:refs/buildbot/' + self.REPOURL_QUOTED + '/release')
            .path('gitpoller-work'),

            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/' + self.REPOURL_QUOTED + '/release')
            .path('gitpoller-work')
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect('git', 'log',
                       '--format=%H',
                       '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       '^0ba9d553b7217ab4bbad89ad56dc0332c7d57a8c',
                       '^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       '--')
            .path('gitpoller-work')
            .stdout(b''),
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

    @defer.inlineCallbacks
    def test_poll_allBranches_single(self):
        self.expectCommands(
            gpo.Expect('git', '--version')
            .stdout(b'git version 1.7.5\n'),
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'ls-remote', '--refs', self.REPOURL)
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\t'
                    b'refs/heads/master\n'),
            gpo.Expect('git', 'fetch', self.REPOURL,
                       '+master:refs/buildbot/' + self.REPOURL_QUOTED + '/master')
            .path('gitpoller-work'),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/' + self.REPOURL_QUOTED + '/master')
            .path('gitpoller-work')
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect(
                'git', 'log', '--format=%H',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '^fa3ae8ed68e664d4db24798611b352e3c6509930',
                '--')
            .path('gitpoller-work')
            .stdout(b'\n'.join([
                b'64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                b'4423cdbcbb89c14e50dd5f4152415afd686c5241'])),
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
        yield self.poller.poll()

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

    @defer.inlineCallbacks
    def test_poll_noChanges(self):
        # Test that environment variables get propagated to subprocesses
        # (See #2116)
        self.patch(os, 'environ', {'ENVVAR': 'TRUE'})
        self.addGetProcessOutputExpectEnv({'ENVVAR': 'TRUE'})

        self.expectCommands(
            gpo.Expect('git', '--version')
            .stdout(b'git version 1.7.5\n'),
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'fetch', self.REPOURL,
                       '+master:refs/buildbot/' + self.REPOURL_QUOTED + '/master')
            .path('gitpoller-work')
            .stdout(b'no interesting output'),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/' + self.REPOURL_QUOTED + '/master')
            .path('gitpoller-work')
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect('git', 'log',
                       '--format=%H',
                       '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       '^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       '--')
            .path('gitpoller-work')
            .stdout(b''),
        )

        self.poller.lastRev = {
            'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241'
        }
        yield self.poller.poll()

        self.assertAllCommandsRan()
        self.assertEqual(self.poller.lastRev, {
            'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241'
        })

    @defer.inlineCallbacks
    def test_poll_allBranches_multiple(self):
        self.expectCommands(
            gpo.Expect('git', '--version')
            .stdout(b'git version 1.7.5\n'),
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'ls-remote', '--refs', self.REPOURL)
            .stdout(b'\n'.join([
                b'4423cdbcbb89c14e50dd5f4152415afd686c5241\trefs/heads/master',
                b'9118f4ab71963d23d02d4bdc54876ac8bf05acf2\trefs/heads/release',
            ])),
            gpo.Expect(
                'git', 'fetch', self.REPOURL,
                '+master:refs/buildbot/' + self.REPOURL_QUOTED + '/master',
                '+release:refs/buildbot/' + self.REPOURL_QUOTED + '/release')
            .path('gitpoller-work'),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/' + self.REPOURL_QUOTED + '/master')
            .path('gitpoller-work')
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect(
                'git', 'log', '--format=%H',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '^bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
                '^fa3ae8ed68e664d4db24798611b352e3c6509930',
                '--')
            .path('gitpoller-work')
            .stdout(b'\n'.join([
                b'64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                b'4423cdbcbb89c14e50dd5f4152415afd686c5241'])),
            gpo.Expect(
                'git', 'rev-parse', 'refs/buildbot/' + self.REPOURL_QUOTED + '/release')
            .path('gitpoller-work')
            .stdout(b'9118f4ab71963d23d02d4bdc54876ac8bf05acf2'),
            gpo.Expect(
                'git', 'log', '--format=%H',
                '9118f4ab71963d23d02d4bdc54876ac8bf05acf2',
                '^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '^bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
                '--')
            .path('gitpoller-work')
            .stdout(b'\n'.join([b'9118f4ab71963d23d02d4bdc54876ac8bf05acf2'])),
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
        yield self.poller.poll()

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

    @defer.inlineCallbacks
    def test_poll_callableFilteredBranches(self):
        self.expectCommands(
            gpo.Expect('git', '--version')
            .stdout(b'git version 1.7.5\n'),
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'ls-remote', '--refs', self.REPOURL)
            .stdout(b'\n'.join([
                b'4423cdbcbb89c14e50dd5f4152415afd686c5241\trefs/heads/master',
                b'9118f4ab71963d23d02d4bdc54876ac8bf05acf2\trefs/heads/release',
            ])),
            gpo.Expect(
                'git', 'fetch', self.REPOURL,
                '+master:refs/buildbot/' + self.REPOURL_QUOTED + '/master')
            .path('gitpoller-work'),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/' + self.REPOURL_QUOTED + '/master')
            .path('gitpoller-work')
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect(
                'git', 'log', '--format=%H',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '^bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
                '^fa3ae8ed68e664d4db24798611b352e3c6509930',
                '--')
            .path('gitpoller-work')
            .stdout(b'\n'.join([
                b'64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                b'4423cdbcbb89c14e50dd5f4152415afd686c5241']))
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
        yield self.poller.poll()

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

    @defer.inlineCallbacks
    def test_poll_branchFilter(self):
        self.expectCommands(
            gpo.Expect('git', '--version')
            .stdout(b'git version 1.7.5\n'),
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'ls-remote', '--refs', self.REPOURL)
            .stdout(b'\n'.join([
                b'4423cdbcbb89c14e50dd5f4152415afd686c5241\t'
                b'refs/pull/410/merge',
                b'9118f4ab71963d23d02d4bdc54876ac8bf05acf2\t'
                b'refs/pull/410/head',
            ])),
            gpo.Expect(
                'git', 'fetch', self.REPOURL,
                '+refs/pull/410/head:refs/buildbot/' + self.REPOURL_QUOTED + '/refs/pull/410/head')
            .path('gitpoller-work'),
            gpo.Expect(
                'git', 'rev-parse',
                'refs/buildbot/' + self.REPOURL_QUOTED + '/refs/pull/410/head')
            .path('gitpoller-work')
            .stdout(b'9118f4ab71963d23d02d4bdc54876ac8bf05acf2'),
            gpo.Expect(
                'git', 'log', '--format=%H',
                '9118f4ab71963d23d02d4bdc54876ac8bf05acf2',
                '^bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
                '^fa3ae8ed68e664d4db24798611b352e3c6509930',
                '--')
            .path('gitpoller-work')
            .stdout(b'\n'.join([b'9118f4ab71963d23d02d4bdc54876ac8bf05acf2'])),
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
        yield self.poller.poll()

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

    @defer.inlineCallbacks
    def test_poll_old(self):
        # Test that environment variables get propagated to subprocesses
        # (See #2116)
        self.patch(os, 'environ', {'ENVVAR': 'TRUE'})
        self.addGetProcessOutputExpectEnv({'ENVVAR': 'TRUE'})

        # patch out getProcessOutput and getProcessOutputAndValue for the
        # benefit of the _get_changes method
        self.expectCommands(
            gpo.Expect('git', '--version')
            .stdout(b'git version 1.7.5\n'),
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'fetch', self.REPOURL,
                       '+master:refs/buildbot/' + self.REPOURL_QUOTED + '/master')
            .path('gitpoller-work')
            .stdout(b'no interesting output'),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/' + self.REPOURL_QUOTED + '/master')
            .path('gitpoller-work')
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect('git', 'log',
                       '--format=%H',
                       '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       '^fa3ae8ed68e664d4db24798611b352e3c6509930',
                       '--')
            .path('gitpoller-work')
            .stdout(b'\n'.join([
                b'64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                b'4423cdbcbb89c14e50dd5f4152415afd686c5241'
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
        yield self.poller.poll()

        # check the results
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
            name=bytes2unicode(self.REPOURL), class_name='GitPoller',
            lastRev={
                'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241'
            })

    @defer.inlineCallbacks
    def test_poll_callableCategory(self):
        self.expectCommands(
            gpo.Expect('git', '--version')
            .stdout(b'git version 1.7.5\n'),
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'ls-remote', '--refs', self.REPOURL)
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\t'
                    b'refs/heads/master\n'),
            gpo.Expect('git', 'fetch', self.REPOURL,
                       '+master:refs/buildbot/' + self.REPOURL_QUOTED + '/master')
            .path('gitpoller-work'),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/' + self.REPOURL_QUOTED + '/master')
            .path('gitpoller-work')
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect(
                'git', 'log', '--format=%H',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '^fa3ae8ed68e664d4db24798611b352e3c6509930',
                '--')
            .path('gitpoller-work')
            .stdout(b'\n'.join([
                b'64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                b'4423cdbcbb89c14e50dd5f4152415afd686c5241'])),
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
        yield self.poller.poll()

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

    @defer.inlineCallbacks
    def test_startService(self):
        yield self.poller.startService()

        self.assertEqual(
            self.poller.workdir, os.path.join('basedir', 'gitpoller-work'))
        self.assertEqual(self.poller.lastRev, {})

        yield self.poller.stopService()

    @defer.inlineCallbacks
    def test_startService_loadLastRev(self):
        self.master.db.state.fakeState(
            name=bytes2unicode(self.REPOURL), class_name='GitPoller',
            lastRev={"master": "fa3ae8ed68e664d4db24798611b352e3c6509930"},
        )

        yield self.poller.startService()

        self.assertEqual(self.poller.lastRev, {
            "master": "fa3ae8ed68e664d4db24798611b352e3c6509930"
        })

        yield self.poller.stopService()


class TestGitPollerWithSshPrivateKey(TestGitPollerBase):

    def createPoller(self):
        return gitpoller.GitPoller(self.REPOURL, sshPrivateKey='ssh-key')

    @mock.patch('buildbot.util.private_tempdir.PrivateTemporaryDirectory._create_dir')
    @mock.patch('buildbot.util.private_tempdir.PrivateTemporaryDirectory.cleanup')
    @mock.patch('buildbot.changes.gitpoller.GitPoller._writeLocalFile')
    @defer.inlineCallbacks
    def test_check_git_features_ssh_1_7(self, write_local_file_mock,
                                        cleanup_dir_mock, create_dir_mock):
        self.expectCommands(
            gpo.Expect('git', '--version')
            .stdout(b'git version 1.7.5\n'),
        )

        yield self.assertFailure(self.poller._checkGitFeatures(), EnvironmentError)

        self.assertAllCommandsRan()

        create_dir_mock.assert_not_called()
        cleanup_dir_mock.assert_not_called()
        write_local_file_mock.assert_not_called()

    @mock.patch('buildbot.util.private_tempdir.PrivateTemporaryDirectory._create_dir')
    @mock.patch('buildbot.util.private_tempdir.PrivateTemporaryDirectory.cleanup')
    @mock.patch('buildbot.changes.gitpoller.GitPoller._writeLocalFile')
    @defer.inlineCallbacks
    def test_poll_initial_2_10(self, write_local_file_mock, cleanup_dir_mock,
                               create_dir_mock):
        key_path = os.path.join('gitpoller-work', '.buildbot-ssh', 'ssh-key')

        self.expectCommands(
            gpo.Expect('git', '--version')
            .stdout(b'git version 2.10.0\n'),
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git',
                       '-c', 'core.sshCommand=ssh -i "{0}"'.format(key_path),
                       'fetch', self.REPOURL,
                       '+master:refs/buildbot/' + self.REPOURL_QUOTED + '/master')
            .path('gitpoller-work'),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/' + self.REPOURL_QUOTED + '/master')
            .path('gitpoller-work')
            .stdout(b'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5\n'),
        )

        yield self.poller.poll()

        self.assertAllCommandsRan()
        self.assertEqual(self.poller.lastRev, {
            'master': 'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5'
        })
        self.master.db.state.assertStateByClass(
            name=bytes2unicode(self.REPOURL), class_name='GitPoller',
            lastRev={
                'master': 'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5'
            })

        create_dir_mock.assert_called_with(
                os.path.join('gitpoller-work', '.buildbot-ssh'), 0o700)
        cleanup_dir_mock.assert_called()
        write_local_file_mock.assert_called_with(key_path, 'ssh-key',
                                                 mode=0o400)

    @mock.patch('buildbot.util.private_tempdir.PrivateTemporaryDirectory._create_dir')
    @mock.patch('buildbot.util.private_tempdir.PrivateTemporaryDirectory.cleanup')
    @mock.patch('buildbot.changes.gitpoller.GitPoller._writeLocalFile')
    @defer.inlineCallbacks
    def test_poll_initial_2_3(self, write_local_file_mock, cleanup_dir_mock,
                              create_dir_mock):
        key_path = os.path.join('gitpoller-work', '.buildbot-ssh', 'ssh-key')

        self.expectCommands(
            gpo.Expect('git', '--version')
            .stdout(b'git version 2.3.0\n'),
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'fetch', self.REPOURL,
                       '+master:refs/buildbot/' + self.REPOURL_QUOTED + '/master')
            .path('gitpoller-work')
            .env({'GIT_SSH_COMMAND': 'ssh -i "{0}"'.format(key_path)}),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/' + self.REPOURL_QUOTED + '/master')
            .path('gitpoller-work')
            .stdout(b'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5\n'),
        )

        yield self.poller.poll()

        self.assertAllCommandsRan()
        self.assertEqual(self.poller.lastRev, {
            'master': 'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5'
        })
        self.master.db.state.assertStateByClass(
            name=bytes2unicode(self.REPOURL), class_name='GitPoller',
            lastRev={
                'master': 'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5'
            })

        create_dir_mock.assert_called_with(
                os.path.join('gitpoller-work', '.buildbot-ssh'), 0o700)
        cleanup_dir_mock.assert_called()
        write_local_file_mock.assert_called_with(key_path, 'ssh-key',
                                                 mode=0o400)

    @mock.patch('buildbot.util.private_tempdir.PrivateTemporaryDirectory._create_dir')
    @mock.patch('buildbot.util.private_tempdir.PrivateTemporaryDirectory.cleanup')
    @mock.patch('buildbot.changes.gitpoller.GitPoller._writeLocalFile')
    @defer.inlineCallbacks
    def test_poll_failFetch_git_2_10(self, write_local_file_mock,
                                     cleanup_dir_mock, create_dir_mock):
        key_path = os.path.join('gitpoller-work', '.buildbot-ssh', 'ssh-key')

        # make sure we cleanup the private key when fetch fails
        self.expectCommands(
            gpo.Expect('git', '--version')
            .stdout(b'git version 2.10.0\n'),
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git',
                       '-c', 'core.sshCommand=ssh -i "{0}"'.format(key_path),
                       'fetch', self.REPOURL,
                       '+master:refs/buildbot/' + self.REPOURL_QUOTED + '/master')
            .path('gitpoller-work')
            .exit(1),
        )

        yield self.assertFailure(self.poller.poll(), EnvironmentError)

        self.assertAllCommandsRan()

        create_dir_mock.assert_called_with(
                os.path.join('gitpoller-work', '.buildbot-ssh'), 0o700)
        cleanup_dir_mock.assert_called()
        write_local_file_mock.assert_called_with(key_path, 'ssh-key',
                                                 mode=0o400)


class TestGitPollerWithSshHostKey(TestGitPollerBase):

    def createPoller(self):
        return gitpoller.GitPoller(self.REPOURL, sshPrivateKey='ssh-key',
                                   sshHostKey='ssh-host-key')

    @mock.patch('buildbot.util.private_tempdir.PrivateTemporaryDirectory._create_dir')
    @mock.patch('buildbot.util.private_tempdir.PrivateTemporaryDirectory.cleanup')
    @mock.patch('buildbot.changes.gitpoller.GitPoller._writeLocalFile')
    @defer.inlineCallbacks
    def test_poll_initial_2_10(self, write_local_file_mock, cleanup_dir_mock,
                               create_dir_mock):

        key_path = os.path.join('gitpoller-work', '.buildbot-ssh', 'ssh-key')
        known_hosts_path = \
            os.path.join('gitpoller-work', '.buildbot-ssh', 'ssh-known-hosts')

        self.expectCommands(
            gpo.Expect('git', '--version')
            .stdout(b'git version 2.10.0\n'),
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git',
                       '-c',
                       'core.sshCommand=ssh -i "{0}" '
                       '-o "UserKnownHostsFile={1}"'.format(
                               key_path, known_hosts_path),
                       'fetch', self.REPOURL,
                       '+master:refs/buildbot/' + self.REPOURL_QUOTED + '/master')
            .path('gitpoller-work'),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/' + self.REPOURL_QUOTED + '/master')
            .path('gitpoller-work')
            .stdout(b'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5\n'),
        )

        yield self.poller.poll()

        self.assertAllCommandsRan()
        self.assertEqual(self.poller.lastRev, {
            'master': 'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5'
        })
        self.master.db.state.assertStateByClass(
            name=bytes2unicode(self.REPOURL), class_name='GitPoller',
            lastRev={
                'master': 'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5'
            })

        create_dir_mock.assert_called_with(
                os.path.join('gitpoller-work', '.buildbot-ssh'), 0o700)
        cleanup_dir_mock.assert_called()

        expected_file_writes = [
            mock.call(key_path, 'ssh-key', mode=0o400),
            mock.call(known_hosts_path, '* ssh-host-key'),
        ]

        self.assertEqual(expected_file_writes,
                         write_local_file_mock.call_args_list)


class TestGitPollerConstructor(unittest.TestCase, config.ConfigErrorsMixin):

    def test_deprecatedFetchRefspec(self):
        with self.assertRaisesConfigError(
                "fetch_refspec is no longer supported"):
            gitpoller.GitPoller("/tmp/git.git", fetch_refspec='not-supported')

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
        with self.assertRaisesConfigError(
                "can't specify both branch and branches"):
            gitpoller.GitPoller("/tmp/git.git", branch='bad',
                                branches=['listy'])

    def test_branches_and_only_tags(self):
        with self.assertRaisesConfigError(
                "can't specify only_tags and branch/branches"):
            gitpoller.GitPoller("/tmp/git.git", only_tags=True,
                                branches=['listy'])

    def test_branch_and_only_tags(self):
        with self.assertRaisesConfigError(
                "can't specify only_tags and branch/branches"):
            gitpoller.GitPoller("/tmp/git.git", only_tags=True, branch='bad')

    def test_gitbin_default(self):
        poller = gitpoller.GitPoller("/tmp/git.git")
        self.assertEqual(poller.gitbin, "git")
