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

import mock
import os
import re

from buildbot.changes import base
from buildbot.changes import gitpoller
from buildbot.test.util import changesource
from buildbot.test.util import config
from buildbot.test.util import gpo
from buildbot.util import epoch2datetime
from twisted.internet import defer
from twisted.trial import unittest

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
        self.expectCommands(
            gpo.Expect('git', *args)
            .path('gitpoller-work')
            .exit(1),
        )

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
        self.expectCommands(
            gpo.Expect('git', *args)
            .path('gitpoller-work')
            .stdout(desiredGoodOutput)
        )

        def call_desired(_):
            return methodToTest(self.dummyRevStr)
        d.addCallback(call_desired)

        def cb_desired(r):
            self.assertEquals(r, desiredGoodResult)
        d.addCallback(cb_desired)
        d.addCallback(lambda _: self.assertAllCommandsRan())
        return d

    def test_get_commit_author(self):
        authorStr = u'Sammy Jankis <email@example.com>'
        return self._perform_git_output_test(self.poller._get_commit_author,
                                             ['log', '--no-walk', '--format=%aN <%aE>', self.dummyRevStr, '--'],
                                             authorStr, authorStr)

    def _test_get_commit_comments(self, commentStr):
        return self._perform_git_output_test(self.poller._get_commit_comments,
                                             ['log', '--no-walk', '--format=%s%n%b', self.dummyRevStr, '--'],
                                             commentStr, commentStr, emptyRaisesException=False)

    def test_get_commit_comments(self):
        comments = [u'this is a commit message\n\nthat is multiline',
                    u'single line message', u'']
        return defer.DeferredList([self._test_get_commit_comments(commentStr) for commentStr in comments])

    def test_get_commit_files(self):
        filesStr = '\n\nfile1\nfile2\n"\146ile_octal"\nfile space'
        filesRes = ['file1', 'file2', 'file_octal', 'file space']
        return self._perform_git_output_test(self.poller._get_commit_files,
                                             ['log', '--name-only', '--no-walk', '--format=%n', self.dummyRevStr, '--'],
                                             filesStr, filesRes, emptyRaisesException=False)

    def test_get_commit_files_with_space_in_changed_files(self):
        filesStr = 'normal_directory/file1\ndirectory with space/file2'
        return self._perform_git_output_test(
            self.poller._get_commit_files,
            ['log', '--name-only', '--no-walk', '--format=%n', self.dummyRevStr, '--'],
            filesStr,
            filter(lambda x: x.strip(), filesStr.splitlines(), ),
            emptyRaisesException=False,
        )

    def test_get_commit_timestamp(self):
        stampStr = '1273258009'
        return self._perform_git_output_test(self.poller._get_commit_timestamp,
                                             ['log', '--no-walk', '--format=%ct', self.dummyRevStr, '--'],
                                             stampStr, float(stampStr))

    # _get_changes is tested in TestGitPoller, below


class TestGitPoller(gpo.GetProcessOutputMixin,
                    changesource.ChangeSourceMixin,
                    unittest.TestCase):

    REPOURL = 'git@example.com:foo/baz.git'
    REPOURL_QUOTED = 'git%40example.com%3Afoo%2Fbaz.git'

    def setUp(self):
        self.setUpGetProcessOutput()
        d = self.setUpChangeSource()

        def create_poller(_):
            self.poller = gitpoller.GitPoller(self.REPOURL)
            self.poller.master = self.master
        d.addCallback(create_poller)
        return d

    def tearDown(self):
        return self.tearDownChangeSource()

    def test_describe(self):
        self.assertSubstring("GitPoller", self.poller.describe())

    def test_poll_initial(self):
        self.expectCommands(
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'fetch', self.REPOURL,
                       '+master:refs/buildbot/%s/master' % self.REPOURL_QUOTED)
            .path('gitpoller-work'),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/%s/master' % self.REPOURL_QUOTED)
            .path('gitpoller-work')
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
                name=self.REPOURL, class_name='GitPoller',
                lastRev={
                    'master': 'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5'
                })
        return d

    def test_poll_failInit(self):
        self.expectCommands(
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work')
            .exit(1),
        )

        d = self.assertFailure(self.poller.poll(), EnvironmentError)

        d.addCallback(lambda _: self.assertAllCommandsRan)
        return d

    def test_poll_failFetch(self):
        self.expectCommands(
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'fetch', self.REPOURL,
                       '+master:refs/buildbot/%s/master' % self.REPOURL_QUOTED)
            .path('gitpoller-work')
            .exit(1),
        )

        d = self.assertFailure(self.poller.poll(), EnvironmentError)
        d.addCallback(lambda _: self.assertAllCommandsRan)
        return d

    def test_poll_failRevParse(self):
        self.expectCommands(
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'fetch', self.REPOURL,
                       '+master:refs/buildbot/%s/master' % self.REPOURL_QUOTED)
            .path('gitpoller-work'),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/%s/master' % self.REPOURL_QUOTED)
            .path('gitpoller-work')
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
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'fetch', self.REPOURL,
                       '+master:refs/buildbot/%s/master' % self.REPOURL_QUOTED)
            .path('gitpoller-work'),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/%s/master' % self.REPOURL_QUOTED)
            .path('gitpoller-work')
            .stdout('4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
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
        d = self.poller.poll()

        @d.addCallback
        def cb(_):
            self.assertAllCommandsRan()
            self.assertEqual(len(self.flushLoggedErrors()), 1)
            self.assertEqual(self.poller.lastRev, {
                'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241'
            })

    def test_poll_nothingNew(self):
        # Test that environment variables get propagated to subprocesses
        # (See #2116)
        self.patch(os, 'environ', {'ENVVAR': 'TRUE'})
        self.addGetProcessOutputExpectEnv({'ENVVAR': 'TRUE'})

        self.expectCommands(
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'fetch', self.REPOURL,
                       '+master:refs/buildbot/%s/master' % self.REPOURL_QUOTED)
            .path('gitpoller-work')
            .stdout('no interesting output'),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/%s/master' % self.REPOURL_QUOTED)
            .path('gitpoller-work')
            .stdout('4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect('git', 'log',
                       '--format=%H',
                       '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       '^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       '--')
            .path('gitpoller-work')
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
                name=self.REPOURL, class_name='GitPoller',
                lastRev={
                    'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241'
                })
        return d

    def test_poll_multipleBranches_initial(self):
        self.expectCommands(
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'fetch', self.REPOURL,
                       '+master:refs/buildbot/%s/master' % self.REPOURL_QUOTED,
                       '+release:refs/buildbot/%s/release' % self.REPOURL_QUOTED)
            .path('gitpoller-work'),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/%s/master' % self.REPOURL_QUOTED)
            .path('gitpoller-work')
            .stdout('4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/%s/release' % self.REPOURL_QUOTED)
            .path('gitpoller-work')
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
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'fetch', self.REPOURL,
                       '+master:refs/buildbot/%s/master' % self.REPOURL_QUOTED,
                       '+release:refs/buildbot/%s/release' % self.REPOURL_QUOTED)
            .path('gitpoller-work'),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/%s/master' % self.REPOURL_QUOTED)
            .path('gitpoller-work')
            .stdout('4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect('git', 'log',
                       '--format=%H',
                       '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       '^bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
                       '^fa3ae8ed68e664d4db24798611b352e3c6509930',
                       '--')
            .path('gitpoller-work')
            .stdout('\n'.join([
                '64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241'])),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/%s/release' % self.REPOURL_QUOTED)
            .path('gitpoller-work')
            .stdout('9118f4ab71963d23d02d4bdc54876ac8bf05acf2'),
            gpo.Expect('git', 'log',
                       '--format=%H',
                       '9118f4ab71963d23d02d4bdc54876ac8bf05acf2',
                       '^bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
                       '^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       '--')
            .path('gitpoller-work')
            .stdout('\n'.join([
                '9118f4ab71963d23d02d4bdc54876ac8bf05acf2'
            ])),
        )

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

            self.assertEqual(len(self.changes_added), 3)

            self.assertEqual(self.changes_added[0]['author'], 'by:4423cdbc')
            self.assertEqual(self.changes_added[0]['when_timestamp'],
                             epoch2datetime(1273258009))
            self.assertEqual(self.changes_added[0]['comments'], 'hello!')
            self.assertEqual(self.changes_added[0]['branch'], 'master')
            self.assertEqual(self.changes_added[0]['files'], ['/etc/442'])
            self.assertEqual(self.changes_added[0]['src'], 'git')

            self.assertEqual(self.changes_added[1]['author'], 'by:64a5dc2a')
            self.assertEqual(self.changes_added[1]['when_timestamp'],
                             epoch2datetime(1273258009))
            self.assertEqual(self.changes_added[1]['comments'], 'hello!')
            self.assertEqual(self.changes_added[1]['files'], ['/etc/64a'])
            self.assertEqual(self.changes_added[1]['src'], 'git')

            self.assertEqual(self.changes_added[2]['author'], 'by:9118f4ab')
            self.assertEqual(self.changes_added[2]['when_timestamp'],
                             epoch2datetime(1273258009))
            self.assertEqual(self.changes_added[2]['comments'], 'hello!')
            self.assertEqual(self.changes_added[2]['files'], ['/etc/911'])
            self.assertEqual(self.changes_added[2]['src'], 'git')

        return d

    def test_poll_allBranches_single(self):
        self.expectCommands(
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'ls-remote', self.REPOURL)
            .stdout('4423cdbcbb89c14e50dd5f4152415afd686c5241\t'
                    'refs/heads/master\n'),
            gpo.Expect('git', 'fetch', self.REPOURL,
                       '+master:refs/buildbot/%s/master' % self.REPOURL_QUOTED)
            .path('gitpoller-work'),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/%s/master' % self.REPOURL_QUOTED)
            .path('gitpoller-work')
            .stdout('4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect(
                'git', 'log', '--format=%H',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '^fa3ae8ed68e664d4db24798611b352e3c6509930',
                '--')
            .path('gitpoller-work')
            .stdout('\n'.join([
                '64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241'])),
        )

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

            self.assertEqual(len(self.changes_added), 2)

            self.assertEqual(self.changes_added[0]['author'], 'by:4423cdbc')
            self.assertEqual(self.changes_added[0]['when_timestamp'],
                             epoch2datetime(1273258009))
            self.assertEqual(self.changes_added[0]['comments'], 'hello!')
            self.assertEqual(self.changes_added[0]['branch'], 'master')
            self.assertEqual(self.changes_added[0]['files'], ['/etc/442'])
            self.assertEqual(self.changes_added[0]['src'], 'git')

            self.assertEqual(self.changes_added[1]['author'], 'by:64a5dc2a')
            self.assertEqual(self.changes_added[1]['when_timestamp'],
                             epoch2datetime(1273258009))
            self.assertEqual(self.changes_added[1]['comments'], 'hello!')
            self.assertEqual(self.changes_added[1]['files'], ['/etc/64a'])
            self.assertEqual(self.changes_added[1]['src'], 'git')

        return d

    def test_poll_noChanges(self):
        # Test that environment variables get propagated to subprocesses
        # (See #2116)
        self.patch(os, 'environ', {'ENVVAR': 'TRUE'})
        self.addGetProcessOutputExpectEnv({'ENVVAR': 'TRUE'})

        self.expectCommands(
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'fetch', self.REPOURL,
                       '+master:refs/buildbot/%s/master' % self.REPOURL_QUOTED)
            .path('gitpoller-work')
            .stdout('no interesting output'),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/%s/master' % self.REPOURL_QUOTED)
            .path('gitpoller-work')
            .stdout('4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect('git', 'log',
                       '--format=%H',
                       '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       '^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       '--')
            .path('gitpoller-work')
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
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'ls-remote', self.REPOURL)
            .stdout('\n'.join([
                '4423cdbcbb89c14e50dd5f4152415afd686c5241\trefs/heads/master',
                '9118f4ab71963d23d02d4bdc54876ac8bf05acf2\trefs/heads/release',
            ])),
            gpo.Expect(
                'git', 'fetch', self.REPOURL,
                '+master:refs/buildbot/%s/master' % self.REPOURL_QUOTED,
                '+release:refs/buildbot/%s/release' % self.REPOURL_QUOTED)
            .path('gitpoller-work'),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/%s/master' % self.REPOURL_QUOTED)
            .path('gitpoller-work')
            .stdout('4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect(
                'git', 'log', '--format=%H',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '^bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
                '^fa3ae8ed68e664d4db24798611b352e3c6509930',
                '--')
            .path('gitpoller-work')
            .stdout('\n'.join([
                '64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241'])),
            gpo.Expect(
                'git', 'rev-parse', 'refs/buildbot/%s/release' %
                self.REPOURL_QUOTED)
            .path('gitpoller-work')
            .stdout('9118f4ab71963d23d02d4bdc54876ac8bf05acf2'),
            gpo.Expect(
                'git', 'log', '--format=%H',
                '9118f4ab71963d23d02d4bdc54876ac8bf05acf2',
                '^bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
                '^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '--')
            .path('gitpoller-work')
            .stdout('\n'.join(['9118f4ab71963d23d02d4bdc54876ac8bf05acf2'])),
        )

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

            self.assertEqual(len(self.changes_added), 3)

            self.assertEqual(self.changes_added[0]['author'], 'by:4423cdbc')
            self.assertEqual(self.changes_added[0]['when_timestamp'],
                             epoch2datetime(1273258009))
            self.assertEqual(self.changes_added[0]['comments'], 'hello!')
            self.assertEqual(self.changes_added[0]['branch'], 'master')
            self.assertEqual(self.changes_added[0]['files'], ['/etc/442'])
            self.assertEqual(self.changes_added[0]['src'], 'git')

            self.assertEqual(self.changes_added[1]['author'], 'by:64a5dc2a')
            self.assertEqual(self.changes_added[1]['when_timestamp'],
                             epoch2datetime(1273258009))
            self.assertEqual(self.changes_added[1]['comments'], 'hello!')
            self.assertEqual(self.changes_added[1]['files'], ['/etc/64a'])
            self.assertEqual(self.changes_added[1]['src'], 'git')

            self.assertEqual(self.changes_added[2]['author'], 'by:9118f4ab')
            self.assertEqual(self.changes_added[2]['when_timestamp'],
                             epoch2datetime(1273258009))
            self.assertEqual(self.changes_added[2]['comments'], 'hello!')
            self.assertEqual(self.changes_added[2]['files'], ['/etc/911'])
            self.assertEqual(self.changes_added[2]['src'], 'git')

        return d

    def test_poll_callableFilteredBranches(self):
        self.expectCommands(
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'ls-remote', self.REPOURL)
            .stdout('\n'.join([
                '4423cdbcbb89c14e50dd5f4152415afd686c5241\trefs/heads/master',
                '9118f4ab71963d23d02d4bdc54876ac8bf05acf2\trefs/heads/release',
            ])),
            gpo.Expect(
                'git', 'fetch', self.REPOURL,
                '+master:refs/buildbot/%s/master' % self.REPOURL_QUOTED)
            .path('gitpoller-work'),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/%s/master' % self.REPOURL_QUOTED)
            .path('gitpoller-work')
            .stdout('4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect(
                'git', 'log', '--format=%H',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '^bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
                '^fa3ae8ed68e664d4db24798611b352e3c6509930',
                '--')
            .path('gitpoller-work')
            .stdout('\n'.join([
                '64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241']))
        )

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
            # because it was ignorned.
            self.assertEqual(self.poller.lastRev, {
                'refs/heads/master':
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                'refs/heads/release':
                'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5'
            })

            self.assertEqual(len(self.changes_added), 2)

            self.assertEqual(self.changes_added[0]['author'], 'by:4423cdbc')
            self.assertEqual(self.changes_added[0]['when_timestamp'],
                             epoch2datetime(1273258009))
            self.assertEqual(self.changes_added[0]['comments'], 'hello!')
            self.assertEqual(self.changes_added[0]['branch'], 'master')
            self.assertEqual(self.changes_added[0]['files'], ['/etc/442'])
            self.assertEqual(self.changes_added[0]['src'], 'git')

            self.assertEqual(self.changes_added[1]['author'], 'by:64a5dc2a')
            self.assertEqual(self.changes_added[1]['when_timestamp'],
                             epoch2datetime(1273258009))
            self.assertEqual(self.changes_added[1]['comments'], 'hello!')
            self.assertEqual(self.changes_added[1]['files'], ['/etc/64a'])
            self.assertEqual(self.changes_added[1]['src'], 'git')

        return d

    def test_poll_branchFilter(self):
        self.expectCommands(
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'ls-remote', self.REPOURL)
            .stdout('\n'.join([
                '4423cdbcbb89c14e50dd5f4152415afd686c5241\t'
                'refs/pull/410/merge',
                '9118f4ab71963d23d02d4bdc54876ac8bf05acf2\t'
                'refs/pull/410/head',
            ])),
            gpo.Expect(
                'git', 'fetch', self.REPOURL,
                '+refs/pull/410/head:refs/buildbot/%s/refs/pull/410/head' %
                self.REPOURL_QUOTED)
            .path('gitpoller-work'),
            gpo.Expect(
                'git', 'rev-parse',
                'refs/buildbot/%s/refs/pull/410/head' % self.REPOURL_QUOTED)
            .path('gitpoller-work')
            .stdout('9118f4ab71963d23d02d4bdc54876ac8bf05acf2'),
            gpo.Expect(
                'git', 'log', '--format=%H',
                '9118f4ab71963d23d02d4bdc54876ac8bf05acf2',
                '^fa3ae8ed68e664d4db24798611b352e3c6509930',
                '^bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
                '--')
            .path('gitpoller-work')
            .stdout('\n'.join(['9118f4ab71963d23d02d4bdc54876ac8bf05acf2'])),
        )

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

            self.assertEqual(len(self.changes_added), 1)

            self.assertEqual(self.changes_added[0]['author'], 'by:9118f4ab')
            self.assertEqual(self.changes_added[0]['when_timestamp'],
                             epoch2datetime(1273258009))
            self.assertEqual(self.changes_added[0]['comments'], 'hello!')
            self.assertEqual(self.changes_added[0]['files'], ['/etc/911'])
            self.assertEqual(self.changes_added[0]['src'], 'git')

        return d

    def test_poll_old(self):
        # Test that environment variables get propagated to subprocesses
        # (See #2116)
        self.patch(os, 'environ', {'ENVVAR': 'TRUE'})
        self.addGetProcessOutputExpectEnv({'ENVVAR': 'TRUE'})

        # patch out getProcessOutput and getProcessOutputAndValue for the
        # benefit of the _get_changes method
        self.expectCommands(
            gpo.Expect('git', 'init', '--bare', 'gitpoller-work'),
            gpo.Expect('git', 'fetch', self.REPOURL,
                       '+master:refs/buildbot/%s/master' % self.REPOURL_QUOTED)
            .path('gitpoller-work')
            .stdout('no interesting output'),
            gpo.Expect('git', 'rev-parse',
                       'refs/buildbot/%s/master' % self.REPOURL_QUOTED)
            .path('gitpoller-work')
            .stdout('4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            gpo.Expect('git', 'log',
                       '--format=%H',
                       '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                       '^fa3ae8ed68e664d4db24798611b352e3c6509930',
                       '--')
            .path('gitpoller-work')
            .stdout('\n'.join([
                '64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241'
            ])),
        )

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
        self.poller.lastRev = {
            'master': 'fa3ae8ed68e664d4db24798611b352e3c6509930'
        }
        d = self.poller.poll()

        # check the results
        def check_changes(_):
            self.assertEqual(self.poller.lastRev, {
                'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241'
            })
            self.assertEqual(len(self.changes_added), 2)
            self.assertEqual(self.changes_added[0]['author'], 'by:4423cdbc')
            self.assertEqual(self.changes_added[0]['when_timestamp'],
                             epoch2datetime(1273258009))
            self.assertEqual(self.changes_added[0]['comments'], 'hello!')
            self.assertEqual(self.changes_added[0]['branch'], 'master')
            self.assertEqual(self.changes_added[0]['files'], ['/etc/442'])
            self.assertEqual(self.changes_added[0]['src'], 'git')
            self.assertEqual(self.changes_added[1]['author'], 'by:64a5dc2a')
            self.assertEqual(self.changes_added[1]['when_timestamp'],
                             epoch2datetime(1273258009))
            self.assertEqual(self.changes_added[1]['comments'], 'hello!')
            self.assertEqual(self.changes_added[1]['files'], ['/etc/64a'])
            self.assertEqual(self.changes_added[1]['src'], 'git')
            self.assertAllCommandsRan()

            self.master.db.state.assertStateByClass(
                name=self.REPOURL, class_name='GitPoller',
                lastRev={
                    'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241'
                })
        d.addCallback(check_changes)

        return d

    # We mock out base.PollingChangeSource.startService, since it calls
    # reactor.callWhenRunning, which leaves a dirty reactor if a synchronous
    # deferred is returned from a test method.
    def test_startService(self):
        startService = mock.Mock()
        self.patch(base.PollingChangeSource, "startService", startService)
        d = self.poller.startService()

        def check(_):
            self.assertEqual(self.poller.workdir, os.path.join('basedir', 'gitpoller-work'))
            self.assertEqual(self.poller.lastRev, {})
            startService.assert_called_once_with(self.poller)
        d.addCallback(check)
        return d

    def test_startService_loadLastRev(self):
        startService = mock.Mock()
        self.patch(base.PollingChangeSource, "startService", startService)
        self.master.db.state.fakeState(
            name=self.REPOURL, class_name='GitPoller',
            lastRev={"master": "fa3ae8ed68e664d4db24798611b352e3c6509930"},
        )

        d = self.poller.startService()

        def check(_):
            self.assertEqual(self.poller.lastRev, {
                "master": "fa3ae8ed68e664d4db24798611b352e3c6509930"
            })
            startService.assert_called_once_with(self.poller)
        d.addCallback(check)
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

    def test_branches_andBranch(self):
        self.assertRaisesConfigError("can't specify both branch and branches",
                                     lambda: gitpoller.GitPoller("/tmp/git.git",
                                                                 branch='bad', branches=['listy']))

    def test_gitbin_default(self):
        poller = gitpoller.GitPoller("/tmp/git.git")
        self.assertEqual(poller.gitbin, "git")
