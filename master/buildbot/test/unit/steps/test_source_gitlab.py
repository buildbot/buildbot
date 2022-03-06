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

from twisted.trial import unittest

from buildbot.process.results import SUCCESS
from buildbot.steps.source import gitlab
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import ExpectListdir
from buildbot.test.steps import ExpectShell
from buildbot.test.steps import ExpectStat
from buildbot.test.util import config
from buildbot.test.util import sourcesteps


class TestGitLab(sourcesteps.SourceStepMixin, config.ConfigErrorsMixin,
                 TestReactorMixin,
                 unittest.TestCase):
    stepClass = gitlab.GitLab

    def setUp(self):
        self.setup_test_reactor()
        self.sourceName = self.stepClass.__name__
        return self.setUpSourceStep()

    def setup_step(self, step, args, **kwargs):
        step = super().setup_step(step, args, **kwargs)
        step.build.properties.setProperty("source_branch", "ms-viewport", "gitlab source branch")
        step.build.properties.setProperty("source_git_ssh_url",
            "git@gitlab.example.com:build/awesome_project.git",
            "gitlab source git ssh url")
        step.build.properties.setProperty("source_project_id", 2337, "gitlab source project ID")
        step.build.properties.setProperty("target_branch", "master", "gitlab target branch")
        step.build.properties.setProperty("target_git_ssh_url",
            "git@gitlab.example.com:mmusterman/awesome_project.git",
            "gitlab target git ssh url")
        step.build.properties.setProperty("target_project_id", 239, "gitlab target project ID")
        return step

    def tearDown(self):
        return self.tearDownSourceStep()

    def test_with_merge_branch(self):
        self.setup_step(
            self.stepClass(repourl='git@gitlab.example.com:mmusterman/awesome_project.git',
                           mode='full', method='clean'),
            dict(branch='master', revision='12345678'))

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
                                 'git@gitlab.example.com:build/awesome_project.git',
                                 'ms-viewport', '--progress'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-f', 'FETCH_HEAD'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-B', 'ms-viewport'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            .stdout('f6ad368298bd941e934a41f3babc827b2aa95a1d')
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', 'GitLab')
        return self.run_step()
