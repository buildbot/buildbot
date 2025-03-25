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

import datetime
import os
import re
import shutil
import stat
import tempfile
from pathlib import Path
from subprocess import CalledProcessError
from unittest import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.changes import gitpoller
from buildbot.process.codebase import Codebase
from buildbot.test import fakedb
from buildbot.test.fake.private_tempdir import MockPrivateTemporaryDirectory
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.runprocess import ExpectMasterShell
from buildbot.test.runprocess import MasterRunProcessMixin
from buildbot.test.util import changesource
from buildbot.test.util import config
from buildbot.test.util import logging
from buildbot.test.util.git_repository import TestGitRepository
from buildbot.test.util.state import StateTestMixin
from buildbot.util import bytes2unicode
from buildbot.util import unicode2bytes
from buildbot.util.git_credential import GitCredentialOptions
from buildbot.util.twisted import async_to_deferred


class TestGitPollerBase(
    MasterRunProcessMixin,
    changesource.ChangeSourceMixin,
    logging.LoggingMixin,
    TestReactorMixin,
    StateTestMixin,
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
        self.addCleanup(self.master.stopService)

        project_id = yield self.master.data.updates.find_project_id(name='project1')
        yield self.master.data.updates.find_codebase_id(projectid=project_id, name='codebase1')

        self.poller = yield self.attachChangeSource(self.createPoller())

    def patch_poller_get_commit_info(self, poller, timestamp):
        # There is a separate test suite for the methods below, no need to complicate each test
        def get_timestamp(rev):
            return defer.succeed(timestamp)

        self.patch(self.poller, '_get_commit_timestamp', get_timestamp)

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
            ExpectMasterShell(['git', *args]).workdir(self.POLLER_WORKDIR),
        )

        # we should get an Exception with empty output from git
        try:
            yield methodToTest(self.dummyRevStr)
            if emptyRaisesException:
                self.fail("run_process should have failed on empty output")
        except Exception as error:
            if not emptyRaisesException:
                import traceback

                traceback.print_exc()
                self.fail("run_process should NOT have failed on empty output: " + repr(error))

        self.assert_all_commands_ran()

        # and the method shouldn't suppress any exceptions
        self.expect_commands(
            ExpectMasterShell(['git', *args]).workdir(self.POLLER_WORKDIR).exit(1),
        )

        try:
            yield methodToTest(self.dummyRevStr)
            self.fail("run_process should have failed on stderr output")
        except Exception:
            pass

        self.assert_all_commands_ran()

        # finally we should get what's expected from good output
        self.expect_commands(
            ExpectMasterShell(['git', *args]).workdir(self.POLLER_WORKDIR).stdout(desiredGoodOutput)
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
        return defer.DeferredList(
            [self._test_get_commit_comments(commentStr) for commentStr in comments],
            consumeErrors=True,
        )

    def test_get_commit_files(self):
        filesBytes = b'\n\nfile1\nfile2\n"\146ile_octal"\nfile space'
        filesRes = ['file1', 'file2', 'file_octal', 'file space']
        return self._perform_git_output_test(
            self.poller._get_commit_files,
            [
                'log',
                '--name-only',
                '--no-walk',
                '--format=%n',
                '-m',
                '--first-parent',
                self.dummyRevStr,
                '--',
            ],
            filesBytes,
            filesRes,
            emptyRaisesException=False,
        )

    def test_get_commit_files_with_space_in_changed_files(self):
        filesBytes = b'normal_directory/file1\ndirectory with space/file2'
        filesStr = bytes2unicode(filesBytes)
        return self._perform_git_output_test(
            self.poller._get_commit_files,
            [
                'log',
                '--name-only',
                '--no-walk',
                '--format=%n',
                '-m',
                '--first-parent',
                self.dummyRevStr,
                '--',
            ],
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

        with self.assertRaises(EnvironmentError):
            yield self.poller._checkGitFeatures()
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

    @defer.inlineCallbacks
    def test_poll_failInit(self):
        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 1.7.5\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]).exit(1),
        )

        self.poller.doPoll.running = True
        with self.assertRaises(EnvironmentError):
            yield self.poller.poll()

        yield self.assert_all_commands_ran()

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
                '--first-parent',
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
                '--first-parent',
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
                '--first-parent',
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
                '--first-parent',
                '--format=%H',
                '9118f4ab71963d23d02d4bdc54876ac8bf05acf2',
                '^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '^bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
                '--',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'\n'.join([b'9118f4ab71963d23d02d4bdc54876ac8bf05acf2'])),
        )

        self.patch_poller_get_commit_info(self.poller, timestamp=1273258009)

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
                    'properties': None,
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
                    'properties': None,
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
                    'properties': None,
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
                '--first-parent',
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
                '--first-parent',
                '--format=%H',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '--',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b''),
        )

        self.patch_poller_get_commit_info(self.poller, timestamp=1273258009)

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
                    'properties': None,
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
                '--first-parent',
                '--format=%H',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '^0ba9d553b7217ab4bbad89ad56dc0332c7d57a8c',
                '^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '--',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b''),
        )

        self.patch_poller_get_commit_info(self.poller, timestamp=1273258009)

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
                    'properties': None,
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
                '--first-parent',
                '--format=%H',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '^0ba9d553b7217ab4bbad89ad56dc0332c7d57a8c',
                '--',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b''),
        )

        self.patch_poller_get_commit_info(self.poller, timestamp=1273258009)

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
                    'properties': None,
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
                '--first-parent',
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

        self.patch_poller_get_commit_info(self.poller, timestamp=1273258009)

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
                '--first-parent',
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
                '--first-parent',
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
                '--first-parent',
                '--format=%H',
                '9118f4ab71963d23d02d4bdc54876ac8bf05acf2',
                '^4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '^bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
                '--',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'\n'.join([b'9118f4ab71963d23d02d4bdc54876ac8bf05acf2'])),
        )

        self.patch_poller_get_commit_info(self.poller, timestamp=1273258009)

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
                '--first-parent',
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

        self.patch_poller_get_commit_info(self.poller, timestamp=1273258009)

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
                '--first-parent',
                '--format=%H',
                '9118f4ab71963d23d02d4bdc54876ac8bf05acf2',
                '^bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5',
                '^fa3ae8ed68e664d4db24798611b352e3c6509930',
                '--',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'\n'.join([b'9118f4ab71963d23d02d4bdc54876ac8bf05acf2'])),
        )

        self.patch_poller_get_commit_info(self.poller, timestamp=1273258009)

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
                '--first-parent',
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

        self.patch_poller_get_commit_info(self.poller, timestamp=1273258009)
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
                    'properties': None,
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
                    'properties': None,
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
                '--first-parent',
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

        self.patch_poller_get_commit_info(self.poller, timestamp=1273258009)

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

        added = yield self.master.data.get(('changes',))
        added = sorted(added, key=lambda c: c['changeid'])
        self.assertEqual(len(added), 2)

        self.assertEqual(added[0]['author'], 'by:4423cdbc')
        self.assertEqual(added[0]['committer'], 'by:4423cdbc')
        self.assertEqual(added[0]['when_timestamp'], 1273258009)
        self.assertEqual(added[0]['comments'], 'hello!')
        self.assertEqual(added[0]['branch'], 'master')
        self.assertEqual(added[0]['files'], ['/etc/442'])
        self.assertEqual(added[0]['category'], '4423cd')

        self.assertEqual(added[1]['author'], 'by:64a5dc2a')
        self.assertEqual(added[1]['committer'], 'by:64a5dc2a')
        self.assertEqual(added[1]['when_timestamp'], 1273258009)
        self.assertEqual(added[1]['comments'], 'hello!')
        self.assertEqual(added[1]['files'], ['/etc/64a'])
        self.assertEqual(added[1]['category'], '64a5dc')

    @async_to_deferred
    async def test_startService(self):
        self.assertEqual(self.poller.workdir, self.POLLER_WORKDIR)
        await self.assert_last_rev(None)

    @defer.inlineCallbacks
    def test_startService_loadLastRev(self):
        yield self.poller.stopService()

        yield self.set_fake_state(
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
                '--first-parent',
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
                '--first-parent',
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
                '--first-parent',
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


class TestGitPollerWithCodebase(TestGitPollerBase):
    def createPoller(self):
        return gitpoller.GitPoller(
            self.REPOURL, branches=['master'], codebase=Codebase('codebase1', 'project1')
        )

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
                '--first-parent',
                '--format=%H',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '^fa3ae8ed68e664d4db24798611b352e3c6509930',
                '--',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(
                b'\n'.join([
                    b'64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                    b'ff2ad982e61af5e11e6147cb2ca6bdfab47a92b7',
                    b'4423cdbcbb89c14e50dd5f4152415afd686c5241',
                ])
            ),
            ExpectMasterShell([
                'git',
                'log',
                '--no-walk',
                '--format=%P',
                '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                '--',
            ])
            .workdir(self.POLLER_WORKDIR)
            .stdout(b'0659625c8a684845076a30eeb3a7b3fe12c279b1\n'),
        )

        self.patch_poller_get_commit_info(self.poller, timestamp=1273258009)

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

        self.assertEqual(len(self.master.data.updates.changesAdded), 3)
        commits = yield self.master.data.get(('codebases', 1, 'commits'))
        commits = [
            {k: v for k, v in c.items() if k in ['commitid', 'revision', 'parent_commitid']}
            for c in commits
        ]
        commits = sorted(commits, key=lambda c: c['commitid'])
        self.assertEqual(
            commits,
            [
                {
                    'commitid': 1,
                    'parent_commitid': None,
                    'revision': '4423cdbcbb89c14e50dd5f4152415afd686c5241',
                },
                {
                    'commitid': 2,
                    'parent_commitid': 1,
                    'revision': 'ff2ad982e61af5e11e6147cb2ca6bdfab47a92b7',
                },
                {
                    'commitid': 3,
                    'parent_commitid': 2,
                    'revision': '64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                },
            ],
        )


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

        with self.assertRaises(EnvironmentError):
            yield self.poller._checkGitFeatures()

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
        self.assertEqual(temp_dir_mock.dirs, [(temp_dir_path, 0o700)])
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
        self.assertEqual(temp_dir_mock.dirs, [(temp_dir_path, 0o700)])
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
        with self.assertRaises(EnvironmentError):
            yield self.poller.poll()

        self.assert_all_commands_ran()

        temp_dir_path = os.path.join('basedir', 'gitpoller-work', '.buildbot-ssh@@@')
        self.assertEqual(temp_dir_mock.dirs, [(temp_dir_path, 0o700)])
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
        self.assertEqual(temp_dir_mock.dirs, [(temp_dir_path, 0o700)])

        expected_file_writes = [
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
        self.assertEqual(temp_dir_mock.dirs, [(temp_dir_path, 0o700)])

        expected_file_writes = [
            mock.call(key_path, 'ssh-key\n', mode=0o400),
            mock.call(known_hosts_path, 'ssh-known-hosts', mode=0o400),
        ]

        self.assertEqual(expected_file_writes, write_local_file_mock.call_args_list)


class TestGitPollerWithAuthCredentials(TestGitPollerBase):
    def createPoller(self):
        return gitpoller.GitPoller(
            self.REPOURL,
            branches=['master'],
            auth_credentials=('username', 'token'),
            git_credentials=GitCredentialOptions(
                credentials=[],
            ),
        )

    @mock.patch(
        'buildbot.util.private_tempdir.PrivateTemporaryDirectory',
        new_callable=MockPrivateTemporaryDirectory,
    )
    @defer.inlineCallbacks
    def test_poll_initial_2_10(self, temp_dir_mock):
        temp_dir_path = os.path.join('basedir', 'gitpoller-work', '.buildbot-ssh@@@')
        credential_store_filepath = os.path.join(temp_dir_path, '.git-credentials')
        self.expect_commands(
            ExpectMasterShell(['git', '--version']).stdout(b'git version 2.10.0\n'),
            ExpectMasterShell(['git', 'init', '--bare', self.POLLER_WORKDIR]),
            ExpectMasterShell([
                'git',
                '-c',
                'credential.helper=',
                '-c',
                f'credential.helper=store "--file={credential_store_filepath}"',
                'credential',
                'approve',
            ]).workdir(temp_dir_path),
            ExpectMasterShell([
                'git',
                '-c',
                'credential.helper=',
                '-c',
                f'credential.helper=store "--file={credential_store_filepath}"',
                'ls-remote',
                '--refs',
                self.REPOURL,
                'refs/heads/master',
            ]).stdout(b'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5\trefs/heads/master\n'),
            ExpectMasterShell([
                'git',
                '-c',
                'credential.helper=',
                '-c',
                f'credential.helper=store "--file={credential_store_filepath}"',
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
            .stdout(b'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5\n'),
        )

        self.poller.doPoll.running = True
        yield self.poller.poll()

        self.assert_all_commands_ran()
        yield self.assert_last_rev({'master': 'bf0b01df6d00ae8d1ffa0b2e2acbe642a6cd35d5'})

        self.assertEqual(temp_dir_mock.dirs, [(temp_dir_path, 0o700)])


class TestGitPollerConstructor(
    TestReactorMixin, changesource.ChangeSourceMixin, config.ConfigErrorsMixin, unittest.TestCase
):
    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        yield self.setUpChangeSource()
        yield self.master.startService()
        self.addCleanup(self.master.stopService)

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


class TestGitPollerBareRepository(
    changesource.ChangeSourceMixin,
    logging.LoggingMixin,
    unittest.TestCase,
):
    INITIAL_SHA = "4c3f214c2637998bb2d0c63363cabd93544fef31"
    FIX_1_SHA = "867489d185291a0b4ba4f3acceffc2c02b23a0d7"
    FEATURE_1_SHA = "43775fd1159be5a96ca5972b73f60cd5018f62db"
    MERGE_FEATURE_1_SHA = "dfbfad40b6543851583912091c7e7a225db38024"

    MAIN_HEAD_SHA = MERGE_FEATURE_1_SHA

    @defer.inlineCallbacks
    def setUp(self):
        try:
            self.repo = TestGitRepository(
                repository_path=tempfile.mkdtemp(
                    prefix="TestRepository_",
                    dir=os.getcwd(),
                )
            )
        except FileNotFoundError as e:
            raise unittest.SkipTest("Can't find git binary") from e

        yield self.prepare_repository()

        yield self.setUpChangeSource(want_real_reactor=True)
        yield self.master.db.insert_test_data([
            fakedb.Project(id=7, name='fake_project7'),
            fakedb.Codebase(id=13, projectid=7, name='codebase1'),
        ])

        yield self.master.startService()
        self.addCleanup(self.master.stopService)

        self.poller_workdir = tempfile.mkdtemp(
            prefix="TestGitPollerBareRepository_",
            dir=os.getcwd(),
        )

        self.repo_url = str(self.repo.repository_path / '.git')
        self.poller = yield self.attachChangeSource(
            gitpoller.GitPoller(
                self.repo_url,
                branches=['main'],
                workdir=self.poller_workdir,
                gitbin=self.repo.git_bin,
                codebase=Codebase('codebase1', 'fake_project7'),
            )
        )

    def tearDown(self):
        def _delete_repository(repo_path: Path):
            # on Win, git will mark objects as read-only
            git_objects_path = repo_path / "objects"
            for item in git_objects_path.rglob(''):
                if not item.is_file():
                    continue

                item.chmod(item.stat().st_mode | stat.S_IWUSR)

            shutil.rmtree(repo_path, ignore_errors=True)

        _delete_repository(Path(self.poller_workdir))
        _delete_repository(self.repo.repository_path)

    @async_to_deferred
    async def prepare_repository(self):
        # create initial commit with README
        self.repo.advance_time(datetime.timedelta(minutes=1))
        self.repo.create_file_text('README.md', 'initial\n')
        self.repo.exec_git(['add', 'README.md'])

        initial_commit_hash = self.repo.commit(
            message="Initial",
            files=['README.md'],
        )
        self.assertEqual(initial_commit_hash, self.INITIAL_SHA)

        # Create fix/1 branch
        self.repo.exec_git(['checkout', '-b', 'fix/1'])
        self.repo.advance_time(datetime.timedelta(minutes=1))
        self.repo.amend_file_text('README.md', '\nfix 1\n')
        self.repo.exec_git(['add', 'README.md'])

        fix_1_hash = self.repo.commit(
            message="Fix 1",
            files=['README.md'],
        )
        self.assertEqual(fix_1_hash, self.FIX_1_SHA)

        # merge ff fix/1 into main
        self.repo.exec_git(['checkout', 'main'])
        self.repo.exec_git(['merge', '--ff', 'fix/1'])

        # create feature/1 branch
        self.repo.exec_git(['checkout', '-b', 'feature/1', initial_commit_hash])

        self.repo.advance_time(datetime.timedelta(minutes=1))
        self.repo.amend_file_text('README.md', '\nfeature 1\n')

        feature_1_hash = self.repo.commit(
            message="Feature 1",
            files=['README.md'],
        )
        self.assertEqual(feature_1_hash, self.FEATURE_1_SHA)

        # merge no-ff feature/1 into main, this will conflict
        self.repo.advance_time(datetime.timedelta(minutes=1))
        self.repo.exec_git(['checkout', 'main'])
        # use --strategy so the command don't error due to merge conflict
        try:
            self.repo.exec_git(
                ['merge', '--no-ff', '--no-commit', '--strategy=ours', 'feature/1'],
            )
        except CalledProcessError as process_error:
            # merge conflict cause git to error with 128 code
            if process_error.returncode not in (0, 128):
                raise

        self.repo.advance_time(datetime.timedelta(minutes=1))
        self.repo.amend_file_text('README.md', "initial\n\nfix 1\nfeature 1\n")
        self.repo.exec_git(['add', 'README.md'])
        merge_feature_1_hash = self.repo.commit(
            message="Merge branch 'feature/1'",
        )
        self.assertEqual(merge_feature_1_hash, self.MERGE_FEATURE_1_SHA)

        self.assertEqual(merge_feature_1_hash, self.MAIN_HEAD_SHA)

    @async_to_deferred
    async def set_last_rev(self, state: dict[str, str]) -> None:
        await self.poller.setState('lastRev', state)
        self.poller.lastRev = state

    @async_to_deferred
    async def assert_last_rev(self, state: dict[str, str]) -> None:
        last_rev = await self.poller.getState('lastRev', None)
        self.assertEqual(last_rev, state)
        self.assertEqual(self.poller.lastRev, state)

    @async_to_deferred
    async def test_poll_initial(self):
        self.poller.doPoll.running = True
        await self.poller.poll()

        await self.assert_last_rev({'main': self.MAIN_HEAD_SHA})
        self.assertEqual(
            self.master.data.updates.changesAdded,
            [],
        )

    @async_to_deferred
    async def test_poll_from_last(self):
        self.maxDiff = None
        await self.set_last_rev({'main': self.INITIAL_SHA})
        self.poller.doPoll.running = True
        await self.poller.poll()

        await self.assert_last_rev({'main': self.MAIN_HEAD_SHA})

        self.assertEqual(
            self.master.data.updates.changesAdded,
            [
                {
                    'author': 'test user <user@example.com>',
                    'branch': 'main',
                    'category': None,
                    'codebase': None,
                    'comments': 'Fix 1',
                    'committer': 'test user <user@example.com>',
                    'files': ['README.md'],
                    'project': '',
                    'properties': None,
                    'repository': self.repo_url,
                    'revision': self.FIX_1_SHA,
                    'revlink': '',
                    'src': 'git',
                    'when_timestamp': 1717855320,
                },
                {
                    'author': 'test user <user@example.com>',
                    'branch': 'main',
                    'category': None,
                    'codebase': None,
                    'comments': "Merge branch 'feature/1'",
                    'committer': 'test user <user@example.com>',
                    'files': ['README.md'],
                    'project': '',
                    'properties': None,
                    'repository': self.repo_url,
                    'revision': self.MERGE_FEATURE_1_SHA,
                    'revlink': '',
                    'src': 'git',
                    'when_timestamp': 1717855500,
                },
            ],
        )

        commits = await self.master.data.get(('codebases', 13, 'commits'))
        self.assertEqual(
            commits,
            [
                {
                    'commitid': 1,
                    'codebaseid': 13,
                    'author': 'test user <user@example.com>',
                    'committer': 'test user <user@example.com>',
                    'comments': 'Fix 1',
                    'revision': self.FIX_1_SHA,
                    'when_timestamp': 1717855320,
                    'parent_commitid': None,
                },
                {
                    'commitid': 2,
                    'codebaseid': 13,
                    'author': 'test user <user@example.com>',
                    'committer': 'test user <user@example.com>',
                    'comments': "Merge branch 'feature/1'",
                    'revision': self.MERGE_FEATURE_1_SHA,
                    'when_timestamp': 1717855500,
                    'parent_commitid': 1,
                },
            ],
        )

        branches = await self.master.data.get(('codebases', 13, 'branches'))
        for b in branches:
            del b['last_timestamp']
        self.assertEqual(
            branches, [{'branchid': 1, 'codebaseid': 13, 'name': 'main', 'commitid': 2}]
        )
