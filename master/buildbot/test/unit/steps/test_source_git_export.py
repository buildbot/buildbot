from __future__ import annotations

from typing import TYPE_CHECKING

from twisted.trial import unittest

from buildbot.process.results import SUCCESS
from buildbot.steps.source import git
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import ExpectRmdir
from buildbot.test.steps import ExpectShell
from buildbot.test.steps import ExpectStat
from buildbot.test.util import config
from buildbot.test.util import sourcesteps

if TYPE_CHECKING:
    from twisted.internet import defer


class TestGitExport(
    sourcesteps.SourceStepMixin,
    config.ConfigErrorsMixin,
    TestReactorMixin,
    unittest.TestCase,
):
    def setUp(self) -> defer.Deferred[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.sourceName = 'GitExport'
        return self.setup_test_build_step()

    def test_export_branch_path(self) -> defer.Deferred[None]:
        self.setup_step(
            git.GitExport(
                repourl='ssh://git@example.com/project.git',
                branch='main',
                path='src/component',
            )
        )
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['git', '--version'])
            .stdout('git version 2.27.0')
            .exit(0),
            ExpectShell(
                workdir='wkdir',
                command=[
                    'git',
                    'ls-remote',
                    'ssh://git@example.com/project.git',
                    'refs/heads/main',
                    'refs/tags/main',
                ],
            )
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d\trefs/heads/main\n')
            .exit(0),
            ExpectShell(
                workdir='wkdir',
                command=[
                    'git',
                    'archive',
                    '--remote=ssh://git@example.com/project.git',
                    '--format=tar',
                    '--output=.buildbot-git-export.tar',
                    'f6ad368298bd941e934a41f3babc827b2aa95a1d',
                    '--',
                    'src/component',
                ],
            ).exit(0),
            ExpectStat(file='wkdir/src/component', log_environ=True).exit(1),
            ExpectShell(
                workdir='wkdir',
                command=['tar', '-xf', '.buildbot-git-export.tar'],
            ).exit(0),
            ExpectRmdir(dir='wkdir/.buildbot-git-export.tar', log_environ=True).exit(0),
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', self.sourceName
        )
        return self.run_step()

    def test_export_revision_skips_ls_remote(self) -> defer.Deferred[None]:
        revision = 'f6ad368298bd941e934a41f3babc827b2aa95a1d'
        self.setup_step(
            git.GitExport(
                repourl='ssh://git@example.com/project.git',
                path='src/component',
            ),
            args={'revision': revision},
        )
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['git', '--version'])
            .stdout('git version 2.27.0')
            .exit(0),
            ExpectShell(
                workdir='wkdir',
                command=[
                    'git',
                    'archive',
                    '--remote=ssh://git@example.com/project.git',
                    '--format=tar',
                    '--output=.buildbot-git-export.tar',
                    revision,
                    '--',
                    'src/component',
                ],
            ).exit(0),
            ExpectStat(file='wkdir/src/component', log_environ=True).stat_dir().exit(0),
            ExpectRmdir(dir='wkdir/src/component', log_environ=True).exit(0),
            ExpectShell(
                workdir='wkdir',
                command=['tar', '-xf', '.buildbot-git-export.tar'],
            ).exit(0),
            ExpectRmdir(dir='wkdir/.buildbot-git-export.tar', log_environ=True).exit(0),
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', revision, self.sourceName)
        return self.run_step()

    def test_path_must_be_repository_relative(self) -> None:
        for path in ('../outside', 'C:/outside'):
            with self.assertRaisesConfigError("GitExport: path must be a repository-relative"):
                git.GitExport(
                    repourl='ssh://git@example.com/project.git',
                    path=path,
                )

    def test_archive_uses_git_auth(self) -> None:
        step = git.GitExport(
            repourl='ssh://git@example.com/project.git',
            path='src/component',
            sshPrivateKey='sshkey',
        )
        self.assertTrue(step._git_auth.is_auth_needed_for_git_command('archive'))
