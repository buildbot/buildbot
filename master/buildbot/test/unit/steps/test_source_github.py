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

from buildbot.process.results import SUCCESS
from buildbot.steps.source import github
from buildbot.test.steps import ExpectListdir
from buildbot.test.steps import ExpectShell
from buildbot.test.steps import ExpectStat
from buildbot.test.unit.steps import test_source_git


# GitHub step shall behave exactly like Git, and thus is inheriting its tests
class TestGitHub(test_source_git.TestGit):
    stepClass = github.GitHub

    def test_with_merge_branch(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean'),
            dict(branch='refs/pull/1234/merge', revision='12345678'))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            .exit(0),
            # here we always ignore revision, and fetch the merge branch
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-f', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'refs/pull/1234/merge', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-B', 'refs/pull/1234/merge'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', 'GitHub')
        return self.run_step()

    def test_with_head_branch(self):
        self.setup_step(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean'),
            dict(branch='refs/pull/1234/head', revision='12345678'))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            .stdout('git version 1.7.5')
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectListdir(dir='wkdir')
            .files(['.git'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            .exit(0),
            # in the case of the head, we try to find if the head is already present
            # and reset to that without fetching
            ExpectShell(workdir='wkdir',
                        command=['git', 'cat-file', '-e', '12345678'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', '12345678'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-B', 'refs/pull/1234/head'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', 'GitHub')
        return self.run_step()
