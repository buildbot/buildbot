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

from __future__ import annotations

import os
import re
from unittest import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.changes import gitpoller
from buildbot.test.fake.private_tempdir import MockPrivateTemporaryDirectory
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.runprocess import ExpectMasterShell
from buildbot.test.runprocess import MasterRunProcessMixin
from buildbot.test.util import changesource
from buildbot.test.util import config
from buildbot.test.util import logging
from buildbot.util import bytes2unicode
from buildbot.util import unicode2bytes
from buildbot.util.twisted import async_to_deferred

# Test that environment variables get propagated to subprocesses (See #2116)
os.environ['TEST_THAT_ENVIRONMENT_GETS_PASSED_TO_SUBPROCESSES'] = 'TRUE'


class TestGitPollerBase(
    MasterRunProcessMixin,
    changesource.ChangeSourceMixin,
    logging.LoggingMixin,
    TestReactorMixin,
    unittest.TestCase,
):
    REPOURL = 'git@example.com:~foo/baz.git'
    REPOURL_QUOTED = 'ssh/example.com/%7Efoo/baz'

    POLLER_WORKDIR = os.path.join('basedir', 'gitpoller-work')

    def createPoller(self):
        # this is overridden in TestGitPollerWithSshPrivateKey
        return gitpoller.GitPoller(self.REPOURL, branches=['master'])

    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.setup_master_run_process()
        yield self.setUpChangeSource()
        yield self.master.startService()

        self.poller = yield self.attachChangeSource(self.createPoller())

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.master.stopService()
        yield self.tearDownChangeSource()

    @async_to_deferred
    async def set_last_rev(self, state: dict[str, str]) -> None:
        await self.poller.setState('lastRev', state)
        self.poller.lastRev = state

    @async_to_deferred
    async def assert_last_rev(self, state: dict[str, str]) -> None:
        last_rev = await self.poller.getState('lastRev', None)
        self.assertEqual(last_rev, state)
        self.assertEqual(self.poller.lastRev, state)


class TestGitPoller(TestGitPollerBase):
    dummyRevStr = '12345abcde'

    @defer.inlineCallbacks
    def _perform_git_output_test(
        self, methodToTest, args, desiredGoodOutput, desiredGoodResult, emptyRaisesException=True
    ):
        self.expect_commands(
            ExpectMasterShell(['git'] + args).workdir(self.POLLER_WORKDIR),
        )

        # we should get an Exception with empty output from git
        try:
            yield methodToTest(self.dummyRevStr)
            if emptyRaisesException:
                self.fail("run_process should have failed on empty output")
        except Exception as e:
            if not emptyRaisesException:
                import traceback

                traceback.print_exc()
                self.fail("run_process should NOT have failed on empty output: " + repr(e))

        self.assert_all_commands_ran()

        # and the method shouldn't suppress any exceptions
        self.expect_commands(
            ExpectMasterShell(['git'] + args).workdir(self.POLLER_WORKDIR).exit(1),
        )

        try:
            yield methodToTest(self.dummyRevStr)
            self.fail("run_process should have failed on stderr output")
        except Exception:
            pass

        self.assert_all_commands_ran()

        # finally we should get what's expected from good output
        self.expect_commands(
            ExpectMasterShell(['git'] + args).workdir(self.POLLER_WORKDIR).stdout(desiredGoodOutput)
        )

        r = yield methodToTest(self.dummyRevStr)

        self.assertEqual(r, desiredGoodResult)
        # check types
        if isinstance(r, str):
            self.assertIsInstance(r, str)
        elif isinstance(r, list):
            for e in r:
                self.assertIsInstance(e, str)

        self.assert_all_commands_ran()

    def test_get_commit_author(self):
        authorStr = 'Sammy Jankis <email@example.com>'
        authorBytes = unicode2bytes(authorStr)
        return self._perform_git_output_test(
            self.poller._get_commit_author,
            ['log', '--no-walk', '--format=%aN <%aE>', self.dummyRevStr, '--'],
            authorBytes,
            authorStr,
        )

    def test_get_commit_committer(self):
        committerStr = 'Sammy Jankis <email@example.com>'
        committerBytes = unicode2bytes(committerStr)
        return self._perform_git_output_test(
            self.poller._get_commit_committer,
            ['log', '--no-walk', '--format=%cN <%cE>', self.dummyRevStr, '--'],
            committerBytes,
            committerStr,
        )

    def _test_get_commit_comments(self, commentStr):
        commentBytes = unicode2bytes(commentStr)
        return self._perform_git_output_test(
            self.poller._get_commit_comments,
            ['log', '--no-walk', '--format=%s%n%b', self.dummyRevStr, '--'],
            commentBytes,
            commentStr,
            emptyRaisesException=False,
        )

    def test_get_commit_comments(self):
        comments = ['this is a commit message\n\nthat is multiline', 'single line message', '']
        return defer.DeferredList([
            self._test_get_commit_comments(commentStr) for commentStr in comments
        ])

    def test_get_commit_files(self):
        filesBytes = b'\n\nfile1\nfile2\n"\146ile_octal"\nfile space'
        filesRes = ['file1', 'file2', 'file_octal', 'file space']
        return self._perform_git_output_test(
            self.poller._get_commit_files,
            ['log', '--name-only', '--no-walk', '--format=%n', self.dummyRevStr, '--'],
            filesBytes,
            filesRes,
            emptyRaisesException=False,
        )

    def test_get_commit_files_with_space_in_changed_files(self):
        filesBytes = b'normal_directory/file1\ndirectory with space/file2'
        filesStr = bytes2unicode(filesBytes)
        return self._perform_git_output_test(
            self.poller._get_commit_files,
            ['log', '--name-only', '--no-walk', '--format=%n', self.dummyRevStr, '--'],
            filesBytes,
            [l for l in filesStr.splitlines() if l.strip()],
            emptyRaisesException=False,
        )

    def test_get_commit_timestamp(self):
        stampBytes = b'1273258009'
        stampStr = bytes2unicode(stampBytes)
        return self._perform_git_output_test(
            self.poller._get_commit_timestamp,
            ['log', '--no-walk', '--format=%ct', self.dummyRevStr, '--'],
            stampBytes,
            float(stampStr),
        )

    def test_describe(self):
        self.assertSubstring("GitPoller", self.poller.describe())

    def test_name(self):
        self.assertEqual(bytes2unicode(self.REPOURL), bytes2unicode(self.poller.name))

        # and one with explicit name...
        other = gitpoller.GitPoller(self.REPOURL, name="MyName")
        self.assertEqual("MyName", other.name)

    @defer.inlineCallbacks
    def test_checkGitFeatures_git_not_installed(self):
        self.setUpLogging()
        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'Command not found'),
        )

        yield self.assertFailure(self.poller._checkGitFeatures(), EnvironmentError)
        self.assert_all_commands_ran()

    @defer.inlineCallbacks
    def test_checkGitFeatures_git_bad_version(self):
        self.setUpLogging()
        self.expect_commands(ExpectMasterShell(['git', '--version']).stdout(b'git '))

        with self.assertRaises(EnvironmentError):
            yield self.poller._checkGitFeatures()

        self.assert_all_commands_ran()

    @defer.inlineCallbacks
    def test_poll_initial(self):
        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 1.7.5\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]),
            ExpectMasterShell([
                'git',
                'ls-remote',
                '--refs',
                self.REPOURL,
                'refs/heads/master',
            ]).stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\trefs/heads/master\n'),
            ExpectMasterShell([
                'git',
                'fetch',
                '--progress',
                self.REPOURL,
                '+refs/heads/master:refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
                '--',
            ]).workdir(self.POLLER_WORKDIR),
            ExpectMasterShell([
                'git',
                'rev-parse',
                'refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5\n'),
        )

        self.poller.doPoll.running = True
        yield self.poller.poll()

        self.assert_all_commands_ran()
        yield self.assert_last_rev({'master': 'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5'})

    @defer.inlineCallbacks
    def test_poll_initial_poller_not_running(self):
        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 1.7.5\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]),
            ExpectMasterShell([
                'git',
                'ls-remote',
                '--refs',
                self.REPOURL,
                'refs/heads/master',
            ]).stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\trefs/heads/master\n'),
        )

        self.poller.doPoll.running = False
        yield self.poller.poll()

        self.assert_all_commands_ran()
        yield self.assert_last_rev(None)

    def test_poll_failInit(self):
        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 1.7.5\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]).exit(1),
        )

        self.poller.doPoll.running = True
        d = self.assertFailure(self.poller.poll(), EnvironmentError)

        d.addCallback(lambda _: self.assert_all_commands_ran())
        return d

    @defer.inlineCallbacks
    def test_poll_branch_do_not_exist(self):
        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 1.7.5\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]),
            ExpectMasterShell(['git', 'ls-remote', '--refs', self.REPOURL, 'refs/heads/master']),
        )

        self.poller.doPoll.running = True
        yield self.poller.poll()

        self.assert_all_commands_ran()

    @defer.inlineCallbacks
    def test_poll_failRevParse(self):
        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 1.7.5\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]),
            ExpectMasterShell([
                'git',
                'ls-remote',
                '--refs',
                self.REPOURL,
                'refs/heads/master',
            ]).stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\trefs/heads/master\n'),
            ExpectMasterShell([
                'git',
                'fetch',
                '--progress',
                self.REPOURL,
                '+refs/heads/master:refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
                '--',
            ]).workdir(self.POLLER_WORKDIR),
            ExpectMasterShell([
                'git',
                'rev-parse',
                'refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
            ])
            .workdir(self.POLLER_WORKDIR)
            .exit(1),
        )

        self.poller.doPoll.running = True
        yield self.poller.poll()

        self.assert_all_commands_ran()
        self.assertEqual(len(self.flushLoggedErrors()), 1)
        yield self.assert_last_rev({})

    @defer.inlineCallbacks
    def test_poll_failLog(self):
        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 1.7.5\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]),
            ExpectMasterShell([
                'git',
                'ls-remote',
                '--refs',
                self.REPOURL,
                'refs/heads/master',
            ]).stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\trefs/heads/master\n'),
            ExpectMasterShell([
                'git',
                'fetch',
                '--progress',
                self.REPOURL,
                '+refs/heads/master:refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
                '--',
            ]).workdir(self.POLLER_WORKDIR),
            ExpectMasterShell([
                'git',
                'rev-parse',
                'refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            ExpectMasterShell([
                'git',
                'log',
                '--ignore-missing',
                '--format=%H',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '^fa3ae8ed68e664d4db24798611b352e3c6509930',
                '--',
            ])
            .workdir(self.POLLER_WORKDIR)
            .exit(1),
        )

        # do the poll
        yield self.set_last_rev({'master': 'fa3ae8ed68e664d4db24798611b352e3c6509930'})

        self.poller.doPoll.running = True
        yield self.poller.poll()

        self.assert_all_commands_ran()
        self.assertEqual(len(self.flushLoggedErrors()), 1)
        yield self.assert_last_rev({'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241'})

    @defer.inlineCallbacks
    def test_poll_GitError(self):
        # Raised when git exits with status code 128. See issue 2468
        self.expect_commands(
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]).exit(128),
        )

        with self.assertRaises(gitpoller.GitError):
            yield self.poller._dovccmd('init', ['--bare', self.POLLER_WORKDIR])

        self.assert_all_commands_ran()

    @defer.inlineCallbacks
    def test_poll_GitError_log(self):
        self.setUpLogging()
        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 1.7.5\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]).exit(128),
        )

        self.poller.doPoll.running = True
        yield self.poller.poll()

        self.assert_all_commands_ran()
        self.assertLogged("command.*on repourl.*failed.*exit code 128.*")

    @defer.inlineCallbacks
    def test_poll_nothingNew(self):
        # Test that environment variables get propagated to subprocesses
        # (See #2116)
        self.patch(os, 'environ', {'ENVVAR': 'TRUE'})
        self.add_run_process_expect_env({'ENVVAR': 'TRUE'})

        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 1.7.5\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]),
            ExpectMasterShell([
                'git',
                'ls-remote',
                '--refs',
                self.REPOURL,
                'refs/heads/master',
            ]).stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\trefs/heads/master\n'),
            ExpectMasterShell([
                'git',
                'fetch',
                '--progress',
                self.REPOURL,
                '+refs/heads/master:refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
                '--',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'no interesting output'),
            ExpectMasterShell([
                'git',
                'rev-parse',
                'refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            ExpectMasterShell([
                'git',
                'log',
                '--ignore-missing',
                '--format=%H',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '--',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b''),
        )

        yield self.set_last_rev({'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241'})

        self.poller.doPoll.running = True
        yield self.poller.poll()

        self.assert_all_commands_ran()
        yield self.assert_last_rev({'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241'})

    @defer.inlineCallbacks
    def test_poll_multipleBranches_initial(self):
        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 1.7.5\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]),
            ExpectMasterShell([
                'git',
                'ls-remote',
                '--refs',
                self.REPOURL,
                'refs/heads/master',
                'refs/heads/release',
                'refs/heads/not_on_remote',
            ]).stdout(
                b'4423cdbcbb89c14e50dd5f4152415afd686c5241\t'
                b'refs/heads/master\n'
                b'9118f4ab71963d23d02d4bdc54876ac8bf05acf2\t'
                b'refs/heads/release\n'
            ),
            ExpectMasterShell([
                'git',
                'fetch',
                '--progress',
                self.REPOURL,
                '+refs/heads/master:refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
                '+refs/heads/release:refs/buildbot/' + self.REPOURL_QUOTED + '/heads/release',
                '--',
            ]).workdir(self.POLLER_WORKDIR),
            ExpectMasterShell([
                'git',
                'rev-parse',
                'refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            ExpectMasterShell([
                'git',
                'rev-parse',
                'refs/buildbot/' + self.REPOURL_QUOTED + '/heads/release',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'9118f4ab71963d23d02d4bdc54876ac8bf05acf2'),
        )

        # do the poll
        self.poller.branches = ['master', 'release', 'not_on_remote']
        self.poller.doPoll.running = True
        yield self.poller.poll()

        self.assert_all_commands_ran()
        yield self.assert_last_rev({
            'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241',
            'release': '9118f4ab71963d23d02d4bdc54876ac8bf05acf2',
        })

    @defer.inlineCallbacks
    def test_poll_multipleBranches(self):
        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 1.7.5\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]),
            ExpectMasterShell([
                'git',
                'ls-remote',
                '--refs',
                self.REPOURL,
                'refs/heads/master',
                'refs/heads/release',
            ]).stdout(
                b'4423cdbcbb89c14e50dd5f4152415afd686c5241\t'
                b'refs/heads/master\n'
                b'9118f4ab71963d23d02d4bdc54876ac8bf05acf2\t'
                b'refs/heads/release\n'
            ),
            ExpectMasterShell([
                'git',
                'fetch',
                '--progress',
                self.REPOURL,
                '+refs/heads/master:refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
                '+refs/heads/release:refs/buildbot/' + self.REPOURL_QUOTED + '/heads/release',
                '--',
            ]).workdir(self.POLLER_WORKDIR),
            ExpectMasterShell([
                'git',
                'rev-parse',
                'refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            ExpectMasterShell([
                'git',
                'log',
                '--ignore-missing',
                '--format=%H',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '^bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
                '^fa3ae8ed68e664d4db24798611b352e3c6509930',
                '--',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(
                b'\n'.join([
                    b'64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                    b'4423cdbcbb89c14e50dd5f4152415afd686c5241',
                ])
            ),
            ExpectMasterShell([
                'git',
                'rev-parse',
                'refs/buildbot/' + self.REPOURL_QUOTED + '/heads/release',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'9118f4ab71963d23d02d4bdc54876ac8bf05acf2'),
            ExpectMasterShell([
                'git',
                'log',
                '--ignore-missing',
                '--format=%H',
                '9118f4ab71963d23d02d4bdc54876ac8bf05acf2',
                '^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '^bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
                '--',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'\n'.join([b'9118f4ab71963d23d02d4bdc54876ac8bf05acf2'])),
        )

        # and patch out the _get_commit_foo methods which were already tested
        # above
        def timestamp(rev):
            return defer.succeed(1273258009)

        self.patch(self.poller, '_get_commit_timestamp', timestamp)

        def author(rev):
            return defer.succeed('by:' + rev[:8])

        self.patch(self.poller, '_get_commit_author', author)

        def committer(rev):
            return defer.succeed('by:' + rev[:8])

        self.patch(self.poller, '_get_commit_committer', committer)

        def files(rev):
            return defer.succeed(['/etc/' + rev[:3]])

        self.patch(self.poller, '_get_commit_files', files)

        def comments(rev):
            return defer.succeed('hello!')

        self.patch(self.poller, '_get_commit_comments', comments)

        # do the poll
        self.poller.branches = ['master', 'release']
        yield self.set_last_rev({
            'master': 'fa3ae8ed68e664d4db24798611b352e3c6509930',
            'release': 'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
        })
        self.poller.doPoll.running = True
        yield self.poller.poll()

        self.assert_all_commands_ran()
        yield self.assert_last_rev({
            'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241',
            'release': '9118f4ab71963d23d02d4bdc54876ac8bf05acf2',
        })

        self.assertEqual(
            self.master.data.updates.changesAdded,
            [
                {
                    'author': 'by:4423cdbc',
                    'committer': 'by:4423cdbc',
                    'branch': 'master',
                    'category': None,
                    'codebase': None,
                    'comments': 'hello!',
                    'files': ['/etc/442'],
                    'project': '',
                    'properties': {},
                    'repository': 'git@example.com:~foo/baz.git',
                    'revision': '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                    'revlink': '',
                    'src': 'git',
                    'when_timestamp': 1273258009,
                },
                {
                    'author': 'by:64a5dc2a',
                    'committer': 'by:64a5dc2a',
                    'branch': 'master',
                    'category': None,
                    'codebase': None,
                    'comments': 'hello!',
                    'files': ['/etc/64a'],
                    'project': '',
                    'properties': {},
                    'repository': 'git@example.com:~foo/baz.git',
                    'revision': '64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                    'revlink': '',
                    'src': 'git',
                    'when_timestamp': 1273258009,
                },
                {
                    'author': 'by:9118f4ab',
                    'committer': 'by:9118f4ab',
                    'branch': 'release',
                    'category': None,
                    'codebase': None,
                    'comments': 'hello!',
                    'files': ['/etc/911'],
                    'project': '',
                    'properties': {},
                    'repository': 'git@example.com:~foo/baz.git',
                    'revision': '9118f4ab71963d23d02d4bdc54876ac8bf05acf2',
                    'revlink': '',
                    'src': 'git',
                    'when_timestamp': 1273258009,
                },
            ],
        )

    @defer.inlineCallbacks
    def test_poll_multipleBranches_buildPushesWithNoCommits_default(self):
        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 1.7.5\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]),
            ExpectMasterShell([
                'git',
                'ls-remote',
                '--refs',
                self.REPOURL,
                'refs/heads/release',
            ]).stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\trefs/heads/release\n'),
            ExpectMasterShell([
                'git',
                'fetch',
                '--progress',
                self.REPOURL,
                '+refs/heads/release:refs/buildbot/' + self.REPOURL_QUOTED + '/heads/release',
                '--',
            ]).workdir(self.POLLER_WORKDIR),
            ExpectMasterShell([
                'git',
                'rev-parse',
                'refs/buildbot/' + self.REPOURL_QUOTED + '/heads/release',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            ExpectMasterShell([
                'git',
                'log',
                '--ignore-missing',
                '--format=%H',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '--',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b''),
        )

        # do the poll
        self.poller.branches = ['release']
        yield self.set_last_rev({
            'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241',
        })
        self.poller.doPoll.running = True
        yield self.poller.poll()

        self.assert_all_commands_ran()
        yield self.assert_last_rev({'release': '4423cdbcbb89c14e50dd5f4152415afd686c5241'})
        self.assertEqual(len(self.master.data.updates.changesAdded), 0)

    @defer.inlineCallbacks
    def test_poll_multipleBranches_buildPushesWithNoCommits_true(self):
        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 1.7.5\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]),
            ExpectMasterShell([
                'git',
                'ls-remote',
                '--refs',
                self.REPOURL,
                'refs/heads/release',
            ]).stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\trefs/heads/release\n'),
            ExpectMasterShell([
                'git',
                'fetch',
                '--progress',
                self.REPOURL,
                '+refs/heads/release:refs/buildbot/' + self.REPOURL_QUOTED + '/heads/release',
                '--',
            ]).workdir(self.POLLER_WORKDIR),
            ExpectMasterShell([
                'git',
                'rev-parse',
                'refs/buildbot/' + self.REPOURL_QUOTED + '/heads/release',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            ExpectMasterShell([
                'git',
                'log',
                '--ignore-missing',
                '--format=%H',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '--',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b''),
        )

        # and patch out the _get_commit_foo methods which were already tested
        # above
        def timestamp(rev):
            return defer.succeed(1273258009)

        self.patch(self.poller, '_get_commit_timestamp', timestamp)

        def author(rev):
            return defer.succeed('by:' + rev[:8])

        self.patch(self.poller, '_get_commit_author', author)

        def committer(rev):
            return defer.succeed('by:' + rev[:8])

        self.patch(self.poller, '_get_commit_committer', committer)

        def files(rev):
            return defer.succeed(['/etc/' + rev[:3]])

        self.patch(self.poller, '_get_commit_files', files)

        def comments(rev):
            return defer.succeed('hello!')

        self.patch(self.poller, '_get_commit_comments', comments)

        # do the poll
        self.poller.branches = ['release']
        yield self.set_last_rev({'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241'})

        self.poller.buildPushesWithNoCommits = True
        self.poller.doPoll.running = True
        yield self.poller.poll()

        self.assert_all_commands_ran()
        yield self.assert_last_rev({'release': '4423cdbcbb89c14e50dd5f4152415afd686c5241'})
        self.assertEqual(
            self.master.data.updates.changesAdded,
            [
                {
                    'author': 'by:4423cdbc',
                    'committer': 'by:4423cdbc',
                    'branch': 'release',
                    'category': None,
                    'codebase': None,
                    'comments': 'hello!',
                    'files': ['/etc/442'],
                    'project': '',
                    'properties': {},
                    'repository': 'git@example.com:~foo/baz.git',
                    'revision': '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                    'revlink': '',
                    'src': 'git',
                    'when_timestamp': 1273258009,
                }
            ],
        )

    @defer.inlineCallbacks
    def test_poll_multipleBranches_buildPushesWithNoCommits_true_fast_forward(self):
        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 1.7.5\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]),
            ExpectMasterShell([
                'git',
                'ls-remote',
                '--refs',
                self.REPOURL,
                'refs/heads/release',
            ]).stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\trefs/heads/release\n'),
            ExpectMasterShell([
                'git',
                'fetch',
                '--progress',
                self.REPOURL,
                '+refs/heads/release:refs/buildbot/' + self.REPOURL_QUOTED + '/heads/release',
                '--',
            ]).workdir(self.POLLER_WORKDIR),
            ExpectMasterShell([
                'git',
                'rev-parse',
                'refs/buildbot/' + self.REPOURL_QUOTED + '/heads/release',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            ExpectMasterShell([
                'git',
                'log',
                '--ignore-missing',
                '--format=%H',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '^0ba9d553b7217ab4bbad89ad56dc0332c7d57a8c',
                '^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '--',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b''),
        )

        # and patch out the _get_commit_foo methods which were already tested
        # above
        def timestamp(rev):
            return defer.succeed(1273258009)

        self.patch(self.poller, '_get_commit_timestamp', timestamp)

        def author(rev):
            return defer.succeed('by:' + rev[:8])

        self.patch(self.poller, '_get_commit_author', author)

        def committer(rev):
            return defer.succeed('by:' + rev[:8])

        self.patch(self.poller, '_get_commit_committer', committer)

        def files(rev):
            return defer.succeed(['/etc/' + rev[:3]])

        self.patch(self.poller, '_get_commit_files', files)

        def comments(rev):
            return defer.succeed('hello!')

        self.patch(self.poller, '_get_commit_comments', comments)

        # do the poll
        self.poller.branches = ['release']
        yield self.set_last_rev({
            'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241',
            'release': '0ba9d553b7217ab4bbad89ad56dc0332c7d57a8c',
        })

        self.poller.buildPushesWithNoCommits = True
        self.poller.doPoll.running = True
        yield self.poller.poll()

        self.assert_all_commands_ran()
        yield self.assert_last_rev({'release': '4423cdbcbb89c14e50dd5f4152415afd686c5241'})
        self.assertEqual(
            self.master.data.updates.changesAdded,
            [
                {
                    'author': 'by:4423cdbc',
                    'committer': 'by:4423cdbc',
                    'branch': 'release',
                    'category': None,
                    'codebase': None,
                    'comments': 'hello!',
                    'files': ['/etc/442'],
                    'project': '',
                    'properties': {},
                    'repository': 'git@example.com:~foo/baz.git',
                    'revision': '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                    'revlink': '',
                    'src': 'git',
                    'when_timestamp': 1273258009,
                }
            ],
        )

    @defer.inlineCallbacks
    def test_poll_multipleBranches_buildPushesWithNoCommits_true_not_tip(self):
        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 1.7.5\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]),
            ExpectMasterShell([
                'git',
                'ls-remote',
                '--refs',
                self.REPOURL,
                'refs/heads/release',
            ]).stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\trefs/heads/release\n'),
            ExpectMasterShell([
                'git',
                'fetch',
                '--progress',
                self.REPOURL,
                '+refs/heads/release:refs/buildbot/' + self.REPOURL_QUOTED + '/heads/release',
                '--',
            ]).workdir(self.POLLER_WORKDIR),
            ExpectMasterShell([
                'git',
                'rev-parse',
                'refs/buildbot/' + self.REPOURL_QUOTED + '/heads/release',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            ExpectMasterShell([
                'git',
                'log',
                '--ignore-missing',
                '--format=%H',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '^0ba9d553b7217ab4bbad89ad56dc0332c7d57a8c',
                '--',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b''),
        )

        # and patch out the _get_commit_foo methods which were already tested
        # above
        def timestamp(rev):
            return defer.succeed(1273258009)

        self.patch(self.poller, '_get_commit_timestamp', timestamp)

        def author(rev):
            return defer.succeed('by:' + rev[:8])

        self.patch(self.poller, '_get_commit_author', author)

        def committer(rev):
            return defer.succeed('by:' + rev[:8])

        self.patch(self.poller, '_get_commit_committer', committer)

        def files(rev):
            return defer.succeed(['/etc/' + rev[:3]])

        self.patch(self.poller, '_get_commit_files', files)

        def comments(rev):
            return defer.succeed('hello!')

        self.patch(self.poller, '_get_commit_comments', comments)

        # do the poll
        self.poller.branches = ['release']
        yield self.set_last_rev({'master': '0ba9d553b7217ab4bbad89ad56dc0332c7d57a8c'})

        self.poller.buildPushesWithNoCommits = True
        self.poller.doPoll.running = True
        yield self.poller.poll()

        self.assert_all_commands_ran()
        yield self.assert_last_rev({'release': '4423cdbcbb89c14e50dd5f4152415afd686c5241'})
        self.assertEqual(
            self.master.data.updates.changesAdded,
            [
                {
                    'author': 'by:4423cdbc',
                    'committer': 'by:4423cdbc',
                    'branch': 'release',
                    'category': None,
                    'codebase': None,
                    'comments': 'hello!',
                    'files': ['/etc/442'],
                    'project': '',
                    'properties': {},
                    'repository': 'git@example.com:~foo/baz.git',
                    'revision': '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                    'revlink': '',
                    'src': 'git',
                    'when_timestamp': 1273258009,
                }
            ],
        )

    @defer.inlineCallbacks
    def test_poll_allBranches_single(self):
        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 1.7.5\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]),
            ExpectMasterShell(['git', 'ls-remote', '--refs', self.REPOURL, 'refs/heads/*']).stdout(
                b'4423cdbcbb89c14e50dd5f4152415afd686c5241\trefs/heads/master\n'
            ),
            ExpectMasterShell([
                'git',
                'fetch',
                '--progress',
                self.REPOURL,
                '+refs/heads/master:refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
                '--',
            ]).workdir(self.POLLER_WORKDIR),
            ExpectMasterShell([
                'git',
                'rev-parse',
                'refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            ExpectMasterShell([
                'git',
                'log',
                '--ignore-missing',
                '--format=%H',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '^fa3ae8ed68e664d4db24798611b352e3c6509930',
                '--',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(
                b'\n'.join([
                    b'64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                    b'4423cdbcbb89c14e50dd5f4152415afd686c5241',
                ])
            ),
        )

        # and patch out the _get_commit_foo methods which were already tested
        # above
        def timestamp(rev):
            return defer.succeed(1273258009)

        self.patch(self.poller, '_get_commit_timestamp', timestamp)

        def author(rev):
            return defer.succeed('by:' + rev[:8])

        self.patch(self.poller, '_get_commit_author', author)

        def committer(rev):
            return defer.succeed('by:' + rev[:8])

        self.patch(self.poller, '_get_commit_committer', committer)

        def files(rev):
            return defer.succeed(['/etc/' + rev[:3]])

        self.patch(self.poller, '_get_commit_files', files)

        def comments(rev):
            return defer.succeed('hello!')

        self.patch(self.poller, '_get_commit_comments', comments)

        # do the poll
        self.poller.branches = True
        yield self.set_last_rev({
            'refs/heads/master': 'fa3ae8ed68e664d4db24798611b352e3c6509930',
        })
        self.poller.doPoll.running = True
        yield self.poller.poll()

        self.assert_all_commands_ran()
        yield self.assert_last_rev({
            'refs/heads/master': '4423cdbcbb89c14e50dd5f4152415afd686c5241',
        })

        added = self.master.data.updates.changesAdded
        self.assertEqual(len(added), 2)

        self.assertEqual(added[0]['author'], 'by:4423cdbc')
        self.assertEqual(added[0]['committer'], 'by:4423cdbc')
        self.assertEqual(added[0]['when_timestamp'], 1273258009)
        self.assertEqual(added[0]['comments'], 'hello!')
        self.assertEqual(added[0]['branch'], 'master')
        self.assertEqual(added[0]['files'], ['/etc/442'])
        self.assertEqual(added[0]['src'], 'git')

        self.assertEqual(added[1]['author'], 'by:64a5dc2a')
        self.assertEqual(added[1]['committer'], 'by:64a5dc2a')
        self.assertEqual(added[1]['when_timestamp'], 1273258009)
        self.assertEqual(added[1]['comments'], 'hello!')
        self.assertEqual(added[1]['files'], ['/etc/64a'])
        self.assertEqual(added[1]['src'], 'git')

    @defer.inlineCallbacks
    def test_poll_noChanges(self):
        # Test that environment variables get propagated to subprocesses
        # (See #2116)
        self.patch(os, 'environ', {'ENVVAR': 'TRUE'})
        self.add_run_process_expect_env({'ENVVAR': 'TRUE'})

        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 1.7.5\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]),
            ExpectMasterShell([
                'git',
                'ls-remote',
                '--refs',
                self.REPOURL,
                'refs/heads/master',
            ]).stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\trefs/heads/master\n'),
            ExpectMasterShell([
                'git',
                'fetch',
                '--progress',
                self.REPOURL,
                '+refs/heads/master:refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
                '--',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'no interesting output'),
            ExpectMasterShell([
                'git',
                'rev-parse',
                'refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            ExpectMasterShell([
                'git',
                'log',
                '--ignore-missing',
                '--format=%H',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '--',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b''),
        )

        yield self.set_last_rev({'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241'})
        self.poller.doPoll.running = True
        yield self.poller.poll()

        self.assert_all_commands_ran()
        yield self.assert_last_rev({'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241'})

    @defer.inlineCallbacks
    def test_poll_allBranches_multiple(self):
        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 1.7.5\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]),
            ExpectMasterShell(['git', 'ls-remote', '--refs', self.REPOURL, 'refs/heads/*']).stdout(
                b'\n'.join([
                    b'4423cdbcbb89c14e50dd5f4152415afd686c5241\trefs/heads/master',
                    b'9118f4ab71963d23d02d4bdc54876ac8bf05acf2\trefs/heads/release',
                ])
            ),
            ExpectMasterShell([
                'git',
                'fetch',
                '--progress',
                self.REPOURL,
                '+refs/heads/master:refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
                '+refs/heads/release:refs/buildbot/' + self.REPOURL_QUOTED + '/heads/release',
                '--',
            ]).workdir(self.POLLER_WORKDIR),
            ExpectMasterShell([
                'git',
                'rev-parse',
                'refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            ExpectMasterShell([
                'git',
                'log',
                '--ignore-missing',
                '--format=%H',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '^bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
                '^fa3ae8ed68e664d4db24798611b352e3c6509930',
                '--',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(
                b'\n'.join([
                    b'64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                    b'4423cdbcbb89c14e50dd5f4152415afd686c5241',
                ])
            ),
            ExpectMasterShell([
                'git',
                'rev-parse',
                'refs/buildbot/' + self.REPOURL_QUOTED + '/heads/release',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'9118f4ab71963d23d02d4bdc54876ac8bf05acf2'),
            ExpectMasterShell([
                'git',
                'log',
                '--ignore-missing',
                '--format=%H',
                '9118f4ab71963d23d02d4bdc54876ac8bf05acf2',
                '^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '^bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
                '--',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'\n'.join([b'9118f4ab71963d23d02d4bdc54876ac8bf05acf2'])),
        )

        # and patch out the _get_commit_foo methods which were already tested
        # above
        def timestamp(rev):
            return defer.succeed(1273258009)

        self.patch(self.poller, '_get_commit_timestamp', timestamp)

        def author(rev):
            return defer.succeed('by:' + rev[:8])

        self.patch(self.poller, '_get_commit_author', author)

        def committer(rev):
            return defer.succeed('by:' + rev[:8])

        self.patch(self.poller, '_get_commit_committer', committer)

        def files(rev):
            return defer.succeed(['/etc/' + rev[:3]])

        self.patch(self.poller, '_get_commit_files', files)

        def comments(rev):
            return defer.succeed('hello!')

        self.patch(self.poller, '_get_commit_comments', comments)

        # do the poll
        self.poller.branches = True
        yield self.set_last_rev({
            'refs/heads/master': 'fa3ae8ed68e664d4db24798611b352e3c6509930',
            'refs/heads/release': 'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
        })
        self.poller.doPoll.running = True
        yield self.poller.poll()

        self.assert_all_commands_ran()
        yield self.assert_last_rev({
            'refs/heads/master': '4423cdbcbb89c14e50dd5f4152415afd686c5241',
            'refs/heads/release': '9118f4ab71963d23d02d4bdc54876ac8bf05acf2',
        })

        added = self.master.data.updates.changesAdded
        self.assertEqual(len(added), 3)

        self.assertEqual(added[0]['author'], 'by:4423cdbc')
        self.assertEqual(added[0]['committer'], 'by:4423cdbc')
        self.assertEqual(added[0]['when_timestamp'], 1273258009)
        self.assertEqual(added[0]['comments'], 'hello!')
        self.assertEqual(added[0]['branch'], 'master')
        self.assertEqual(added[0]['files'], ['/etc/442'])
        self.assertEqual(added[0]['src'], 'git')

        self.assertEqual(added[1]['author'], 'by:64a5dc2a')
        self.assertEqual(added[1]['committer'], 'by:64a5dc2a')
        self.assertEqual(added[1]['when_timestamp'], 1273258009)
        self.assertEqual(added[1]['comments'], 'hello!')
        self.assertEqual(added[1]['files'], ['/etc/64a'])
        self.assertEqual(added[1]['src'], 'git')

        self.assertEqual(added[2]['author'], 'by:9118f4ab')
        self.assertEqual(added[2]['committer'], 'by:9118f4ab')
        self.assertEqual(added[2]['when_timestamp'], 1273258009)
        self.assertEqual(added[2]['comments'], 'hello!')
        self.assertEqual(added[2]['files'], ['/etc/911'])
        self.assertEqual(added[2]['src'], 'git')

    @defer.inlineCallbacks
    def test_poll_callableFilteredBranches(self):
        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 1.7.5\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]),
            ExpectMasterShell(['git', 'ls-remote', '--refs', self.REPOURL]).stdout(
                b'\n'.join([
                    b'4423cdbcbb89c14e50dd5f4152415afd686c5241\trefs/heads/master',
                    b'9118f4ab71963d23d02d4bdc54876ac8bf05acf2\trefs/heads/release',
                ])
            ),
            ExpectMasterShell([
                'git',
                'fetch',
                '--progress',
                self.REPOURL,
                '+refs/heads/master:refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
                '--',
            ]).workdir(self.POLLER_WORKDIR),
            ExpectMasterShell([
                'git',
                'rev-parse',
                'refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            ExpectMasterShell([
                'git',
                'log',
                '--ignore-missing',
                '--format=%H',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '^bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
                '^fa3ae8ed68e664d4db24798611b352e3c6509930',
                '--',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(
                b'\n'.join([
                    b'64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                    b'4423cdbcbb89c14e50dd5f4152415afd686c5241',
                ])
            ),
        )

        # and patch out the _get_commit_foo methods which were already tested
        # above
        def timestamp(rev):
            return defer.succeed(1273258009)

        self.patch(self.poller, '_get_commit_timestamp', timestamp)

        def author(rev):
            return defer.succeed('by:' + rev[:8])

        self.patch(self.poller, '_get_commit_author', author)

        def committer(rev):
            return defer.succeed('by:' + rev[:8])

        self.patch(self.poller, '_get_commit_committer', committer)

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
        yield self.set_last_rev({
            'refs/heads/master': 'fa3ae8ed68e664d4db24798611b352e3c6509930',
            'refs/heads/release': 'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
        })
        self.poller.doPoll.running = True
        yield self.poller.poll()

        self.assert_all_commands_ran()

        # The release branch id should remain unchanged,
        # because it was ignored.
        yield self.assert_last_rev({
            'refs/heads/master': '4423cdbcbb89c14e50dd5f4152415afd686c5241'
        })

        added = self.master.data.updates.changesAdded
        self.assertEqual(len(added), 2)

        self.assertEqual(added[0]['author'], 'by:4423cdbc')
        self.assertEqual(added[0]['committer'], 'by:4423cdbc')
        self.assertEqual(added[0]['when_timestamp'], 1273258009)
        self.assertEqual(added[0]['comments'], 'hello!')
        self.assertEqual(added[0]['branch'], 'master')
        self.assertEqual(added[0]['files'], ['/etc/442'])
        self.assertEqual(added[0]['src'], 'git')

        self.assertEqual(added[1]['author'], 'by:64a5dc2a')
        self.assertEqual(added[1]['committer'], 'by:64a5dc2a')
        self.assertEqual(added[1]['when_timestamp'], 1273258009)
        self.assertEqual(added[1]['comments'], 'hello!')
        self.assertEqual(added[1]['files'], ['/etc/64a'])
        self.assertEqual(added[1]['src'], 'git')

    @defer.inlineCallbacks
    def test_poll_branchFilter(self):
        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 1.7.5\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]),
            ExpectMasterShell(['git', 'ls-remote', '--refs', self.REPOURL]).stdout(
                b'\n'.join([
                    b'4423cdbcbb89c14e50dd5f4152415afd686c5241\trefs/pull/410/merge',
                    b'9118f4ab71963d23d02d4bdc54876ac8bf05acf2\trefs/pull/410/head',
                ])
            ),
            ExpectMasterShell([
                'git',
                'fetch',
                '--progress',
                self.REPOURL,
                '+refs/pull/410/head:refs/buildbot/' + self.REPOURL_QUOTED + '/pull/410/head',
                '--',
            ]).workdir(self.POLLER_WORKDIR),
            ExpectMasterShell([
                'git',
                'rev-parse',
                'refs/buildbot/' + self.REPOURL_QUOTED + '/pull/410/head',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'9118f4ab71963d23d02d4bdc54876ac8bf05acf2'),
            ExpectMasterShell([
                'git',
                'log',
                '--ignore-missing',
                '--format=%H',
                '9118f4ab71963d23d02d4bdc54876ac8bf05acf2',
                '^bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
                '^fa3ae8ed68e664d4db24798611b352e3c6509930',
                '--',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'\n'.join([b'9118f4ab71963d23d02d4bdc54876ac8bf05acf2'])),
        )

        # and patch out the _get_commit_foo methods which were already tested
        # above
        def timestamp(rev):
            return defer.succeed(1273258009)

        self.patch(self.poller, '_get_commit_timestamp', timestamp)

        def author(rev):
            return defer.succeed('by:' + rev[:8])

        self.patch(self.poller, '_get_commit_author', author)

        def committer(rev):
            return defer.succeed('by:' + rev[:8])

        self.patch(self.poller, '_get_commit_committer', committer)

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
        yield self.set_last_rev({
            'master': 'fa3ae8ed68e664d4db24798611b352e3c6509930',
            'refs/pull/410/head': 'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
        })
        self.poller.doPoll.running = True
        yield self.poller.poll()

        self.assert_all_commands_ran()
        yield self.assert_last_rev({
            'refs/pull/410/head': '9118f4ab71963d23d02d4bdc54876ac8bf05acf2'
        })

        added = self.master.data.updates.changesAdded
        self.assertEqual(len(added), 1)

        self.assertEqual(added[0]['author'], 'by:9118f4ab')
        self.assertEqual(added[0]['committer'], 'by:9118f4ab')
        self.assertEqual(added[0]['when_timestamp'], 1273258009)
        self.assertEqual(added[0]['comments'], 'hello!')
        self.assertEqual(added[0]['files'], ['/etc/911'])
        self.assertEqual(added[0]['src'], 'git')

    @defer.inlineCallbacks
    def test_poll_old(self):
        # Test that environment variables get propagated to subprocesses
        # (See #2116)
        self.patch(os, 'environ', {'ENVVAR': 'TRUE'})
        self.add_run_process_expect_env({'ENVVAR': 'TRUE'})

        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 1.7.5\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]),
            ExpectMasterShell([
                'git',
                'ls-remote',
                '--refs',
                self.REPOURL,
                'refs/heads/master',
            ]).stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\trefs/heads/master\n'),
            ExpectMasterShell([
                'git',
                'fetch',
                '--progress',
                self.REPOURL,
                '+refs/heads/master:refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
                '--',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'no interesting output'),
            ExpectMasterShell([
                'git',
                'rev-parse',
                'refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            ExpectMasterShell([
                'git',
                'log',
                '--ignore-missing',
                '--format=%H',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '^fa3ae8ed68e664d4db24798611b352e3c6509930',
                '--',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(
                b'\n'.join([
                    b'64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                    b'4423cdbcbb89c14e50dd5f4152415afd686c5241',
                ])
            ),
        )

        # and patch out the _get_commit_foo methods which were already tested
        # above
        def timestamp(rev):
            return defer.succeed(1273258009)

        self.patch(self.poller, '_get_commit_timestamp', timestamp)

        def author(rev):
            return defer.succeed('by:' + rev[:8])

        self.patch(self.poller, '_get_commit_author', author)

        def committer(rev):
            return defer.succeed('by:' + rev[:8])

        self.patch(self.poller, '_get_commit_committer', committer)

        def files(rev):
            return defer.succeed(['/etc/' + rev[:3]])

        self.patch(self.poller, '_get_commit_files', files)

        def comments(rev):
            return defer.succeed('hello!')

        self.patch(self.poller, '_get_commit_comments', comments)

        # do the poll
        yield self.set_last_rev({'master': 'fa3ae8ed68e664d4db24798611b352e3c6509930'})
        self.poller.doPoll.running = True
        yield self.poller.poll()

        # check the results
        yield self.assert_last_rev({'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241'})
        self.assertEqual(
            self.master.data.updates.changesAdded,
            [
                {
                    'author': 'by:4423cdbc',
                    'committer': 'by:4423cdbc',
                    'branch': 'master',
                    'category': None,
                    'codebase': None,
                    'comments': 'hello!',
                    'files': ['/etc/442'],
                    'project': '',
                    'properties': {},
                    'repository': 'git@example.com:~foo/baz.git',
                    'revision': '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                    'revlink': '',
                    'src': 'git',
                    'when_timestamp': 1273258009,
                },
                {
                    'author': 'by:64a5dc2a',
                    'committer': 'by:64a5dc2a',
                    'branch': 'master',
                    'category': None,
                    'codebase': None,
                    'comments': 'hello!',
                    'files': ['/etc/64a'],
                    'project': '',
                    'properties': {},
                    'repository': 'git@example.com:~foo/baz.git',
                    'revision': '64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                    'revlink': '',
                    'src': 'git',
                    'when_timestamp': 1273258009,
                },
            ],
        )
        self.assert_all_commands_ran()

    @defer.inlineCallbacks
    def test_poll_callableCategory(self):
        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 1.7.5\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]),
            ExpectMasterShell(['git', 'ls-remote', '--refs', self.REPOURL, 'refs/heads/*']).stdout(
                b'4423cdbcbb89c14e50dd5f4152415afd686c5241\trefs/heads/master\n'
            ),
            ExpectMasterShell([
                'git',
                'fetch',
                '--progress',
                self.REPOURL,
                '+refs/heads/master:refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
                '--',
            ]).workdir(self.POLLER_WORKDIR),
            ExpectMasterShell([
                'git',
                'rev-parse',
                'refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\n'),
            ExpectMasterShell([
                'git',
                'log',
                '--ignore-missing',
                '--format=%H',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '^fa3ae8ed68e664d4db24798611b352e3c6509930',
                '--',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(
                b'\n'.join([
                    b'64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                    b'4423cdbcbb89c14e50dd5f4152415afd686c5241',
                ])
            ),
        )

        # and patch out the _get_commit_foo methods which were already tested
        # above
        def timestamp(rev):
            return defer.succeed(1273258009)

        self.patch(self.poller, '_get_commit_timestamp', timestamp)

        def author(rev):
            return defer.succeed('by:' + rev[:8])

        self.patch(self.poller, '_get_commit_author', author)

        def committer(rev):
            return defer.succeed('by:' + rev[:8])

        self.patch(self.poller, '_get_commit_committer', committer)

        def files(rev):
            return defer.succeed(['/etc/' + rev[:3]])

        self.patch(self.poller, '_get_commit_files', files)

        def comments(rev):
            return defer.succeed('hello!')

        self.patch(self.poller, '_get_commit_comments', comments)

        # do the poll
        self.poller.branches = True

        def callableCategory(chdict):
            return chdict['revision'][:6]

        self.poller.category = callableCategory

        yield self.set_last_rev({
            'refs/heads/master': 'fa3ae8ed68e664d4db24798611b352e3c6509930',
        })
        self.poller.doPoll.running = True
        yield self.poller.poll()

        self.assert_all_commands_ran()
        yield self.assert_last_rev({
            'refs/heads/master': '4423cdbcbb89c14e50dd5f4152415afd686c5241',
        })

        added = self.master.data.updates.changesAdded
        self.assertEqual(len(added), 2)

        self.assertEqual(added[0]['author'], 'by:4423cdbc')
        self.assertEqual(added[0]['committer'], 'by:4423cdbc')
        self.assertEqual(added[0]['when_timestamp'], 1273258009)
        self.assertEqual(added[0]['comments'], 'hello!')
        self.assertEqual(added[0]['branch'], 'master')
        self.assertEqual(added[0]['files'], ['/etc/442'])
        self.assertEqual(added[0]['src'], 'git')
        self.assertEqual(added[0]['category'], '4423cd')

        self.assertEqual(added[1]['author'], 'by:64a5dc2a')
        self.assertEqual(added[1]['committer'], 'by:64a5dc2a')
        self.assertEqual(added[1]['when_timestamp'], 1273258009)
        self.assertEqual(added[1]['comments'], 'hello!')
        self.assertEqual(added[1]['files'], ['/etc/64a'])
        self.assertEqual(added[1]['src'], 'git')
        self.assertEqual(added[1]['category'], '64a5dc')

    @async_to_deferred
    async def test_startService(self):
        self.assertEqual(self.poller.workdir, self.POLLER_WORKDIR)
        await self.assert_last_rev(None)

    @defer.inlineCallbacks
    def test_startService_loadLastRev(self):
        yield self.poller.stopService()

        self.master.db.state.set_fake_state(
            self.poller, 'lastRev', {"master": "fa3ae8ed68e664d4db24798611b352e3c6509930"}
        )

        yield self.poller.startService()

        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 1.7.5\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]),
            ExpectMasterShell([
                'git',
                'ls-remote',
                '--refs',
                self.REPOURL,
                "refs/heads/master",
            ]).stdout(b'fa3ae8ed68e664d4db24798611b352e3c6509930\trefs/heads/master\n'),
            ExpectMasterShell([
                'git',
                'fetch',
                '--progress',
                self.REPOURL,
                f'+refs/heads/master:refs/buildbot/{self.REPOURL_QUOTED}/heads/master',
                '--',
            ]).workdir(self.POLLER_WORKDIR),
            ExpectMasterShell([
                'git',
                'rev-parse',
                f'refs/buildbot/{self.REPOURL_QUOTED}/heads/master',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'fa3ae8ed68e664d4db24798611b352e3c6509930\n'),
            ExpectMasterShell([
                'git',
                'log',
                '--ignore-missing',
                '--format=%H',
                'fa3ae8ed68e664d4db24798611b352e3c6509930',
                '^fa3ae8ed68e664d4db24798611b352e3c6509930',
                '--',
            ]).workdir(self.POLLER_WORKDIR),
        )

        yield self.poller.poll()

        self.assert_all_commands_ran()

        yield self.assert_last_rev({"master": "fa3ae8ed68e664d4db24798611b352e3c6509930"})


class TestGitPollerDefaultBranch(TestGitPollerBase):
    def createPoller(self):
        return gitpoller.GitPoller(self.REPOURL, branches=None)

    @async_to_deferred
    async def test_resolve_head_ref_with_symref(self):
        self.patch(self.poller, 'supports_lsremote_symref', True)

        self.expect_commands(
            ExpectMasterShell(['git', 'ls-remote', '--symref', self.REPOURL, 'HEAD'])
            .exit(0)
            .stdout(
                b'ref: refs/heads/default_branch	HEAD\n'
                b'737b94eca1ddde3dd4a0040b25c8a25fe973fe09	HEAD\n'
            ),
        )

        result = await self.poller._resolve_head_ref()

        self.assert_all_commands_ran()
        self.assertEqual(result, 'refs/heads/default_branch')

    @async_to_deferred
    async def test_resolve_head_ref_without_symref(self):
        self.patch(self.poller, 'supports_lsremote_symref', False)

        self.expect_commands(
            ExpectMasterShell(['git', 'ls-remote', self.REPOURL, 'HEAD', 'refs/heads/*'])
            .exit(0)
            .stdout(
                b'737b94eca1ddde3dd4a0040b25c8a25fe973fe09	HEAD\n'
                b'274ec17f8bfb56adc0035b12735785097df488fc	refs/heads/3.10.x\n'
                b'972a389242fd15a59f2d2840d1be4c0fc7b97109	refs/heads/3.11.x\n'
                b'737b94eca1ddde3dd4a0040b25c8a25fe973fe09	refs/heads/master\n'
            ),
        )

        result = await self.poller._resolve_head_ref()

        self.assert_all_commands_ran()
        self.assertEqual(result, 'refs/heads/master')

    @async_to_deferred
    async def test_resolve_head_ref_without_symref_multiple_head_candidates(self):
        self.patch(self.poller, 'supports_lsremote_symref', False)

        self.expect_commands(
            ExpectMasterShell(['git', 'ls-remote', self.REPOURL, 'HEAD', 'refs/heads/*'])
            .exit(0)
            .stdout(
                b'737b94eca1ddde3dd4a0040b25c8a25fe973fe09	HEAD\n'
                b'274ec17f8bfb56adc0035b12735785097df488fc	refs/heads/3.10.x\n'
                b'737b94eca1ddde3dd4a0040b25c8a25fe973fe09	refs/heads/3.11.x\n'
                b'737b94eca1ddde3dd4a0040b25c8a25fe973fe09	refs/heads/master\n'
            ),
        )

        result = await self.poller._resolve_head_ref()

        self.assert_all_commands_ran()
        self.assertEqual(result, None)

    @async_to_deferred
    async def test_poll_found_head(self):
        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 2.10.0\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]),
            ExpectMasterShell([
                'git',
                'ls-remote',
                '--symref',
                self.REPOURL,
                'HEAD',
            ]).stdout(
                b'ref: refs/heads/default_branch	HEAD\n'
                b'737b94eca1ddde3dd4a0040b25c8a25fe973fe09	HEAD\n'
            ),
            ExpectMasterShell([
                'git',
                'fetch',
                '--progress',
                self.REPOURL,
                f'+refs/heads/default_branch:refs/buildbot/{self.REPOURL_QUOTED}/heads/default_branch',
                '--',
            ]).workdir(self.POLLER_WORKDIR),
            ExpectMasterShell([
                'git',
                'rev-parse',
                f'refs/buildbot/{self.REPOURL_QUOTED}/heads/default_branch',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'737b94eca1ddde3dd4a0040b25c8a25fe973fe09\n'),
            ExpectMasterShell([
                'git',
                'log',
                '--ignore-missing',
                '--format=%H',
                '737b94eca1ddde3dd4a0040b25c8a25fe973fe09',
                '^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '--',
            ]).workdir(self.POLLER_WORKDIR),
        )

        await self.set_last_rev({
            'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241',
        })
        self.poller.doPoll.running = True
        await self.poller.poll()

        self.assert_all_commands_ran()
        await self.assert_last_rev({
            'refs/heads/default_branch': '737b94eca1ddde3dd4a0040b25c8a25fe973fe09'
        })
        self.assertEqual(len(self.master.data.updates.changesAdded), 0)

    @async_to_deferred
    async def test_poll_found_head_not_found(self):
        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 2.10.0\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]),
            ExpectMasterShell([
                'git',
                'ls-remote',
                '--symref',
                self.REPOURL,
                'HEAD',
            ]).stdout(b'malformed output'),
            ExpectMasterShell([
                'git',
                'fetch',
                '--progress',
                self.REPOURL,
                f'+HEAD:refs/buildbot/raw/{self.REPOURL_QUOTED}/HEAD',
                '--',
            ]).workdir(self.POLLER_WORKDIR),
            ExpectMasterShell([
                'git',
                'rev-parse',
                f'refs/buildbot/raw/{self.REPOURL_QUOTED}/HEAD',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'737b94eca1ddde3dd4a0040b25c8a25fe973fe09\n'),
            ExpectMasterShell([
                'git',
                'log',
                '--ignore-missing',
                '--format=%H',
                '737b94eca1ddde3dd4a0040b25c8a25fe973fe09',
                '^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '--',
            ]).workdir(self.POLLER_WORKDIR),
        )

        await self.set_last_rev({
            'master': '4423cdbcbb89c14e50dd5f4152415afd686c5241',
        })
        self.poller.doPoll.running = True
        await self.poller.poll()

        self.assert_all_commands_ran()
        await self.assert_last_rev({'HEAD': '737b94eca1ddde3dd4a0040b25c8a25fe973fe09'})
        self.assertEqual(len(self.master.data.updates.changesAdded), 0)


class TestGitPollerWithSshPrivateKey(TestGitPollerBase):
    def createPoller(self):
        return gitpoller.GitPoller(self.REPOURL, branches=['master'], sshPrivateKey='ssh-key')

    @mock.patch(
        'buildbot.util.private_tempdir.PrivateTemporaryDirectory',
        new_callable=MockPrivateTemporaryDirectory,
    )
    @mock.patch('buildbot.util.git.writeLocalFile')
    @defer.inlineCallbacks
    def test_check_git_features_ssh_1_7(self, write_local_file_mock, temp_dir_mock):
        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 1.7.5\n'),
        )

        yield self.assertFailure(self.poller._checkGitFeatures(), EnvironmentError)

        self.assert_all_commands_ran()

        self.assertEqual(len(temp_dir_mock.dirs), 0)
        write_local_file_mock.assert_not_called()

    @mock.patch(
        'buildbot.util.private_tempdir.PrivateTemporaryDirectory',
        new_callable=MockPrivateTemporaryDirectory,
    )
    @mock.patch('buildbot.util.git.writeLocalFile')
    @defer.inlineCallbacks
    def test_poll_initial_2_10(self, write_local_file_mock, temp_dir_mock):
        key_path = os.path.join('basedir', 'gitpoller-work', '.buildbot-ssh@@@', 'ssh-key')

        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 2.10.0\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]),
            ExpectMasterShell([
                'git',
                '-c',
                f'core.sshCommand=ssh -o "BatchMode=yes" -i "{key_path}"',
                'ls-remote',
                '--refs',
                self.REPOURL,
                "refs/heads/master",
            ]).stdout(b'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5\trefs/heads/master\n'),
            ExpectMasterShell([
                'git',
                '-c',
                f'core.sshCommand=ssh -o "BatchMode=yes" -i "{key_path}"',
                'fetch',
                '--progress',
                self.REPOURL,
                '+refs/heads/master:refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
                '--',
            ]).workdir(self.POLLER_WORKDIR),
            ExpectMasterShell([
                'git',
                'rev-parse',
                'refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5\n'),
        )

        self.poller.doPoll.running = True
        yield self.poller.poll()

        self.assert_all_commands_ran()
        yield self.assert_last_rev({'master': 'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5'})

        temp_dir_path = os.path.join('basedir', 'gitpoller-work', '.buildbot-ssh@@@')
        self.assertEqual(temp_dir_mock.dirs, [(temp_dir_path, 0o700), (temp_dir_path, 0o700)])
        write_local_file_mock.assert_called_with(key_path, 'ssh-key\n', mode=0o400)

    @mock.patch(
        'buildbot.util.private_tempdir.PrivateTemporaryDirectory',
        new_callable=MockPrivateTemporaryDirectory,
    )
    @mock.patch('buildbot.util.git.writeLocalFile')
    @defer.inlineCallbacks
    def test_poll_initial_2_3(self, write_local_file_mock, temp_dir_mock):
        key_path = os.path.join('basedir', 'gitpoller-work', '.buildbot-ssh@@@', 'ssh-key')

        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 2.3.0\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]),
            ExpectMasterShell([
                'git',
                'ls-remote',
                '--refs',
                self.REPOURL,
                "refs/heads/master",
            ]).stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\trefs/heads/master\n'),
            ExpectMasterShell([
                'git',
                'fetch',
                '--progress',
                self.REPOURL,
                '+refs/heads/master:refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
                '--',
            ])
            .workdir(self.POLLER_WORKDIR)
            .env({'GIT_SSH_COMMAND': f'ssh -o "BatchMode=yes" -i "{key_path}"'}),
            ExpectMasterShell([
                'git',
                'rev-parse',
                'refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5\n'),
        )

        self.poller.doPoll.running = True
        yield self.poller.poll()

        self.assert_all_commands_ran()
        yield self.assert_last_rev({'master': 'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5'})

        temp_dir_path = os.path.join('basedir', 'gitpoller-work', '.buildbot-ssh@@@')
        self.assertEqual(temp_dir_mock.dirs, [(temp_dir_path, 0o700), (temp_dir_path, 0o700)])
        write_local_file_mock.assert_called_with(key_path, 'ssh-key\n', mode=0o400)

    @mock.patch(
        'buildbot.util.private_tempdir.PrivateTemporaryDirectory',
        new_callable=MockPrivateTemporaryDirectory,
    )
    @mock.patch('buildbot.util.git.writeLocalFile')
    @defer.inlineCallbacks
    def test_poll_failFetch_git_2_10(self, write_local_file_mock, temp_dir_mock):
        key_path = os.path.join('basedir', 'gitpoller-work', '.buildbot-ssh@@@', 'ssh-key')

        # make sure we cleanup the private key when fetch fails
        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 2.10.0\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]),
            ExpectMasterShell([
                'git',
                '-c',
                f'core.sshCommand=ssh -o "BatchMode=yes" -i "{key_path}"',
                'ls-remote',
                '--refs',
                self.REPOURL,
                "refs/heads/master",
            ]).stdout(b'4423cdbcbb89c14e50dd5f4152415afd686c5241\trefs/heads/master\n'),
            ExpectMasterShell([
                'git',
                '-c',
                f'core.sshCommand=ssh -o "BatchMode=yes" -i "{key_path}"',
                'fetch',
                '--progress',
                self.REPOURL,
                '+refs/heads/master:refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
                '--',
            ])
            .workdir(self.POLLER_WORKDIR)
            .exit(1),
        )

        self.poller.doPoll.running = True
        yield self.assertFailure(self.poller.poll(), EnvironmentError)

        self.assert_all_commands_ran()

        temp_dir_path = os.path.join('basedir', 'gitpoller-work', '.buildbot-ssh@@@')
        self.assertEqual(temp_dir_mock.dirs, [(temp_dir_path, 0o700), (temp_dir_path, 0o700)])
        write_local_file_mock.assert_called_with(key_path, 'ssh-key\n', mode=0o400)


class TestGitPollerWithSshHostKey(TestGitPollerBase):
    def createPoller(self):
        return gitpoller.GitPoller(
            self.REPOURL, branches=['master'], sshPrivateKey='ssh-key', sshHostKey='ssh-host-key'
        )

    @mock.patch(
        'buildbot.util.private_tempdir.PrivateTemporaryDirectory',
        new_callable=MockPrivateTemporaryDirectory,
    )
    @mock.patch('buildbot.util.git.writeLocalFile')
    @defer.inlineCallbacks
    def test_poll_initial_2_10(self, write_local_file_mock, temp_dir_mock):
        key_path = os.path.join('basedir', 'gitpoller-work', '.buildbot-ssh@@@', 'ssh-key')
        known_hosts_path = os.path.join(
            'basedir', 'gitpoller-work', '.buildbot-ssh@@@', 'ssh-known-hosts'
        )

        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 2.10.0\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]),
            ExpectMasterShell([
                'git',
                '-c',
                f'core.sshCommand=ssh -o "BatchMode=yes" -i "{key_path}" '
                f'-o "UserKnownHostsFile={known_hosts_path}"',
                'ls-remote',
                '--refs',
                self.REPOURL,
                "refs/heads/master",
            ]).stdout(b'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5\trefs/heads/master\n'),
            ExpectMasterShell([
                'git',
                '-c',
                f'core.sshCommand=ssh -o "BatchMode=yes" -i "{key_path}" '
                f'-o "UserKnownHostsFile={known_hosts_path}"',
                'fetch',
                '--progress',
                self.REPOURL,
                '+refs/heads/master:refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
                '--',
            ]).workdir(self.POLLER_WORKDIR),
            ExpectMasterShell([
                'git',
                'rev-parse',
                'refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5\n'),
        )

        self.poller.doPoll.running = True
        yield self.poller.poll()

        self.assert_all_commands_ran()
        yield self.assert_last_rev({'master': 'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5'})

        temp_dir_path = os.path.join('basedir', 'gitpoller-work', '.buildbot-ssh@@@')
        self.assertEqual(temp_dir_mock.dirs, [(temp_dir_path, 0o700), (temp_dir_path, 0o700)])

        expected_file_writes = [
            mock.call(key_path, 'ssh-key\n', mode=0o400),
            mock.call(known_hosts_path, '* ssh-host-key', mode=0o400),
            mock.call(key_path, 'ssh-key\n', mode=0o400),
            mock.call(known_hosts_path, '* ssh-host-key', mode=0o400),
        ]

        self.assertEqual(expected_file_writes, write_local_file_mock.call_args_list)


class TestGitPollerWithSshKnownHosts(TestGitPollerBase):
    def createPoller(self):
        return gitpoller.GitPoller(
            self.REPOURL,
            branches=['master'],
            sshPrivateKey='ssh-key\n',
            sshKnownHosts='ssh-known-hosts',
        )

    @mock.patch(
        'buildbot.util.private_tempdir.PrivateTemporaryDirectory',
        new_callable=MockPrivateTemporaryDirectory,
    )
    @mock.patch('buildbot.util.git.writeLocalFile')
    @defer.inlineCallbacks
    def test_poll_initial_2_10(self, write_local_file_mock, temp_dir_mock):
        key_path = os.path.join('basedir', 'gitpoller-work', '.buildbot-ssh@@@', 'ssh-key')
        known_hosts_path = os.path.join(
            'basedir', 'gitpoller-work', '.buildbot-ssh@@@', 'ssh-known-hosts'
        )

        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 2.10.0\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]),
            ExpectMasterShell([
                'git',
                '-c',
                f'core.sshCommand=ssh -o "BatchMode=yes" -i "{key_path}" '
                f'-o "UserKnownHostsFile={known_hosts_path}"',
                'ls-remote',
                '--refs',
                self.REPOURL,
                'refs/heads/master',
            ]).stdout(b'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5\trefs/heads/master\n'),
            ExpectMasterShell([
                'git',
                '-c',
                f'core.sshCommand=ssh -o "BatchMode=yes" -i "{key_path}" '
                f'-o "UserKnownHostsFile={known_hosts_path}"',
                'fetch',
                '--progress',
                self.REPOURL,
                '+refs/heads/master:refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
                '--',
            ]).workdir(self.POLLER_WORKDIR),
            ExpectMasterShell([
                'git',
                'rev-parse',
                'refs/buildbot/' + self.REPOURL_QUOTED + '/heads/master',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5\n'),
        )

        self.poller.doPoll.running = True
        yield self.poller.poll()

        self.assert_all_commands_ran()
        yield self.assert_last_rev({'master': 'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5'})

        temp_dir_path = os.path.join('basedir', 'gitpoller-work', '.buildbot-ssh@@@')
        self.assertEqual(temp_dir_mock.dirs, [(temp_dir_path, 0o700), (temp_dir_path, 0o700)])

        expected_file_writes = [
            mock.call(key_path, 'ssh-key\n', mode=0o400),
            mock.call(known_hosts_path, 'ssh-known-hosts', mode=0o400),
            mock.call(key_path, 'ssh-key\n', mode=0o400),
            mock.call(known_hosts_path, 'ssh-known-hosts', mode=0o400),
        ]

        self.assertEqual(expected_file_writes, write_local_file_mock.call_args_list)


class TestGitPollerConstructor(
    unittest.TestCase, TestReactorMixin, changesource.ChangeSourceMixin, config.ConfigErrorsMixin
):
    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        yield self.setUpChangeSource()
        yield self.master.startService()

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.master.stopService()
        yield self.tearDownChangeSource()

    @defer.inlineCallbacks
    def test_deprecatedFetchRefspec(self):
        with self.assertRaisesConfigError("fetch_refspec is no longer supported"):
            yield self.attachChangeSource(
                gitpoller.GitPoller("/tmp/git.git", fetch_refspec='not-supported')
            )

    @defer.inlineCallbacks
    def test_branches_default(self):
        poller = yield self.attachChangeSource(gitpoller.GitPoller("/tmp/git.git"))
        self.assertEqual(poller.branches, None)

    @defer.inlineCallbacks
    def test_branches_oldBranch(self):
        poller = yield self.attachChangeSource(gitpoller.GitPoller("/tmp/git.git", branch='magic'))
        self.assertEqual(poller.branches, ["magic"])

    @defer.inlineCallbacks
    def test_branches(self):
        poller = yield self.attachChangeSource(
            gitpoller.GitPoller("/tmp/git.git", branches=['magic', 'marker'])
        )
        self.assertEqual(poller.branches, ["magic", "marker"])

    @defer.inlineCallbacks
    def test_branches_True(self):
        poller = yield self.attachChangeSource(gitpoller.GitPoller("/tmp/git.git", branches=True))
        self.assertEqual(poller.branches, True)

    @defer.inlineCallbacks
    def test_only_tags_True(self):
        poller = yield self.attachChangeSource(gitpoller.GitPoller("/tmp/git.git", only_tags=True))
        self.assertIsNotNone(poller.branches)

    @defer.inlineCallbacks
    def test_branches_andBranch(self):
        with self.assertRaisesConfigError("can't specify both branch and branches"):
            yield self.attachChangeSource(
                gitpoller.GitPoller("/tmp/git.git", branch='bad', branches=['listy'])
            )

    @defer.inlineCallbacks
    def test_branches_and_only_tags(self):
        with self.assertRaisesConfigError("can't specify only_tags and branch/branches"):
            yield self.attachChangeSource(
                gitpoller.GitPoller("/tmp/git.git", only_tags=True, branches=['listy'])
            )

    @defer.inlineCallbacks
    def test_branch_and_only_tags(self):
        with self.assertRaisesConfigError("can't specify only_tags and branch/branches"):
            yield self.attachChangeSource(
                gitpoller.GitPoller("/tmp/git.git", only_tags=True, branch='bad')
            )

    @defer.inlineCallbacks
    def test_gitbin_default(self):
        poller = yield self.attachChangeSource(gitpoller.GitPoller("/tmp/git.git"))
        self.assertEqual(poller.gitbin, "git")


class TestGitPollerUtils(unittest.TestCase):
    def test_tracker_ref_protos(self):
        for url, expected_tracker in [
            (
                "https://example.org/owner/repo.git",
                "refs/buildbot/https/example.org/owner/repo/heads/branch_name",
            ),
            ("ssh://example.org:repo.git", "refs/buildbot/ssh/example.org/repo/heads/branch_name"),
            ("git@example.org:repo.git", "refs/buildbot/ssh/example.org/repo/heads/branch_name"),
        ]:
            self.assertEqual(
                gitpoller.GitPoller._tracker_ref(url, "refs/heads/branch_name"),
                expected_tracker,
            )

    def test_tracker_ref_with_port(self):
        self.assertEqual(
            gitpoller.GitPoller._tracker_ref(
                "https://example.org:1234/owner/repo.git", "refs/heads/branch_name"
            ),
            "refs/buildbot/https/example.org%3A1234/owner/repo/heads/branch_name",
        )

    def test_tracker_ref_tag(self):
        self.assertEqual(
            gitpoller.GitPoller._tracker_ref(
                "https://example.org:1234/owner/repo.git", "refs/tags/v1"
            ),
            "refs/buildbot/https/example.org%3A1234/owner/repo/tags/v1",
        )

    def test_tracker_ref_with_credentials(self):
        self.assertEqual(
            gitpoller.GitPoller._tracker_ref(
                "https://user:password@example.org:1234/owner/repo.git", "refs/heads/branch_name"
            ),
            "refs/buildbot/https/example.org%3A1234/owner/repo/heads/branch_name",
        )

    def test_tracker_ref_sub_branch(self):
        self.assertEqual(
            gitpoller.GitPoller._tracker_ref(
                "https://user:password@example.org:1234/owner/repo.git", "refs/heads/branch_name"
            ),
            "refs/buildbot/https/example.org%3A1234/owner/repo/heads/branch_name",
        )

    def test_tracker_ref_not_ref_collision(self):
        self.assertNotEqual(
            gitpoller.GitPoller._tracker_ref("https://example.org/repo.git", "heads/branch_name"),
            gitpoller.GitPoller._tracker_ref(
                "https://example.org/repo.git", "refs/heads/branch_name"
            ),
        )

    def test_tracker_ref_HEAD(self):
        self.assertNotEqual(
            gitpoller.GitPoller._tracker_ref("https://example.org/repo.git", "HEAD"),
            gitpoller.GitPoller._tracker_ref("https://example.org/repo.git", "refs/raw/HEAD"),
        )
