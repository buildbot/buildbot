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

from buildbot.process.results import SUCCESS
from buildbot.steps.source import github
from buildbot.test.fake.remotecommand import Expect
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.unit import test_steps_source_git


# GitHub step shall behave exactly like Git, and thus is inheriting its tests
class TestGitHub(test_steps_source_git.TestGit):
    stepClass = github.GitHub

    def test_with_merge_branch(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean'),
            dict(branch='refs/pull/1234/merge', revision='12345678'))

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
                                 'http://github.com/buildbot/buildbot.git',
                                 'refs/pull/1234/merge'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'branch', '-M', 'refs/pull/1234/merge'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', 'GitHub')
        return self.runStep()

    def test_with_head_branch(self):
        self.setupStep(
            self.stepClass(repourl='http://github.com/buildbot/buildbot.git',
                           mode='full', method='clean'),
            dict(branch='refs/pull/1234/head', revision='12345678'))

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
            # in the case of the head, we try to find if the head is already present
            # and reset to that without fetching
            ExpectShell(workdir='wkdir',
                        command=['git', 'cat-file', '-e', '12345678'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', '12345678', '--'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'branch', '-M', 'refs/pull/1234/head'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', 'GitHub')
        return self.runStep()
