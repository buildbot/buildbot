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

from typing import TYPE_CHECKING
from typing import Any

from twisted.internet import defer

from buildbot.process.results import SUCCESS
from buildbot.steps.source import github
from buildbot.test.steps import ExpectListdir
from buildbot.test.steps import ExpectShell
from buildbot.test.steps import ExpectStat
from buildbot.test.unit.steps import test_source_git

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


# GitHub step shall behave exactly like Git, and thus is inheriting its tests
class TestGitHub(test_source_git.TestGit):
    stepClass = github.GitHub

    @defer.inlineCallbacks
    def test_merge_branch_shared_cache_fetches_merge_ref(
        self,
    ) -> InlineCallbacksType[None]:
        step = self.setup_step(
            self.stepClass(
                repourl='http://github.com/buildbot/buildbot.git',
                shared_cache=True,
                progress=False,
            )
        )

        def fake_run_vc(
            source_step: github.GitHub,
            branch: str | None,
            revision: str | None,
            patch: Any,
        ) -> defer.Deferred[int]:
            source_step.branch = branch or 'HEAD'
            source_step.revision = revision
            return defer.succeed(SUCCESS)

        self.patch(test_source_git.git.Git, 'run_vc', fake_run_vc)

        yield step.run_vc('refs/pull/1234/merge', '12345678', None)
        self.assertIsNone(step.revision)

        commands: list[list[str]] = []

        def fake_cache_command(
            cache_path: str, command: list[str], **kwargs: Any
        ) -> defer.Deferred[int]:
            commands.append(command)
            return defer.succeed(SUCCESS)

        self.patch(step, '_dovccache', fake_cache_command)

        self.assertTrue((yield step._updateSharedCache('/cache/repo.git')))
        self.assertEqual(
            commands,
            [
                [
                    'fetch',
                    '--prune',
                    '--no-tags',
                    'http://github.com/buildbot/buildbot.git',
                    '+refs/heads/*:refs/heads/*',
                    'refs/pull/1234/merge',
                ],
                [
                    'config',
                    '--local',
                    'buildbot.sharedCacheIdentity',
                    'http://github.com/buildbot/buildbot.git',
                ],
            ],
        )

    def test_with_merge_branch(self) -> defer.Deferred[None]:
        self.setup_step(
            self.stepClass(
                repourl='http://github.com/buildbot/buildbot.git', mode='full', method='clean'
            ),
            {"branch": 'refs/pull/1234/merge', "revision": '12345678'},
        )

        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True).exit(1),
            ExpectListdir(dir='wkdir').files(['.git']).exit(0),
            ExpectShell(workdir='wkdir', command=['git', 'clean', '-f', '-f', '-d']).exit(0),
            # here we always ignore revision, and fetch the merge branch
            ExpectShell(
                workdir='wkdir',
                command=[
                    'git',
                    'fetch',
                    '-f',
                    '--progress',
                    'http://github.com/buildbot/buildbot.git',
                    'refs/pull/1234/merge',
                ],
            ).exit(0),
            ExpectShell(workdir='wkdir', command=['git', 'checkout', '-f', 'FETCH_HEAD']).exit(0),
            ExpectShell(
                workdir='wkdir', command=['git', 'checkout', '-B', 'refs/pull/1234/merge']
            ).exit(0),
            ExpectShell(workdir='wkdir', command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0),
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', 'GitHub')
        return self.run_step()

    def test_with_head_branch(self) -> defer.Deferred[None]:
        self.setup_step(
            self.stepClass(
                repourl='http://github.com/buildbot/buildbot.git', mode='full', method='clean'
            ),
            {"branch": 'refs/pull/1234/head', "revision": '12345678'},
        )

        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True).exit(1),
            ExpectListdir(dir='wkdir').files(['.git']).exit(0),
            ExpectShell(workdir='wkdir', command=['git', 'clean', '-f', '-f', '-d']).exit(0),
            # in the case of the head, we try to find if the head is already present
            # and reset to that without fetching
            ExpectShell(workdir='wkdir', command=['git', 'cat-file', '-e', '12345678']).exit(0),
            ExpectShell(workdir='wkdir', command=['git', 'checkout', '-f', '12345678']).exit(0),
            ExpectShell(
                workdir='wkdir', command=['git', 'checkout', '-B', 'refs/pull/1234/head']
            ).exit(0),
            ExpectShell(workdir='wkdir', command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0),
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', 'GitHub')
        return self.run_step()
