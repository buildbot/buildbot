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
from buildbot.test.fake.remotecommand import Expect
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.util import config
from buildbot.test.util import sourcesteps
from buildbot.test.util.misc import TestReactorMixin


class TestGitLab(sourcesteps.SourceStepMixin, config.ConfigErrorsMixin,
                 TestReactorMixin,
                 unittest.TestCase):
    stepClass = gitlab.GitLab

    def setUp(self):
        self.setUpTestReactor()
        self.sourceName = self.stepClass.__name__
        return self.setUpSourceStep()

    def setupStep(self, step, args, **kwargs):
        step = super().setupStep(step, args, **kwargs)
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
        self.setupStep(
            self.stepClass(repourl='git@gitlab.example.com:mmusterman/awesome_project.git',
                           mode='full', method='clean'),
            dict(branch='master', revision='12345678'))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['git', '--version'])
            + ExpectShell.log('stdio',
                              stdout='git version 1.7.5')
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('listdir', {'dir': 'wkdir', 'logEnviron': True,
                               'timeout': 1200})
            + Expect.update('files', ['.git'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'clean', '-f', '-f', '-d'])
            + 0,
            # here we always ignore revision, and fetch the merge branch
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'git@gitlab.example.com:build/awesome_project.git',
                                 'ms-viewport'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'checkout', '-B', 'ms-viewport'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', 'GitLab')
        return self.runStep()
