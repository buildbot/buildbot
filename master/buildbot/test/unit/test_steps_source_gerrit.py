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

from twisted.trial import unittest

from buildbot.process.results import SUCCESS
from buildbot.steps.source import gerrit
from buildbot.test.fake.remotecommand import Expect
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.util import config
from buildbot.test.util import sourcesteps


class TestGerrit(sourcesteps.SourceStepMixin, config.ConfigErrorsMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpSourceStep()

    def tearDown(self):
        return self.tearDownSourceStep()

    def test_mode_full_clean(self):
        self.setupStep(
            gerrit.Gerrit(repourl='http://github.com/buildbot/buildbot.git',
                          mode='full', method='clean'))
        self.build.setProperty("event.patchSet.ref", "gerrit_branch")

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
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'gerrit_branch'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'branch', '-M', 'gerrit_branch'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', 'Gerrit')
        return self.runStep()

    def test_mode_full_clean_force_build(self):
        self.setupStep(
            gerrit.Gerrit(repourl='http://github.com/buildbot/buildbot.git',
                          mode='full', method='clean'))
        self.build.setProperty("gerrit_change", "1234/567")

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
            ExpectShell(workdir='wkdir',
                        command=['git', 'fetch', '-t',
                                 'http://github.com/buildbot/buildbot.git',
                                 'refs/changes/34/1234/567'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'reset', '--hard', 'FETCH_HEAD', '--'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'branch', '-M', 'refs/changes/34/1234/567'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['git', 'rev-parse', 'HEAD'])
            + ExpectShell.log('stdio',
                              stdout='f6ad368298bd941e934a41f3babc827b2aa95a1d')
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty(
            'got_revision', 'f6ad368298bd941e934a41f3babc827b2aa95a1d', 'Gerrit')
        return self.runStep()
