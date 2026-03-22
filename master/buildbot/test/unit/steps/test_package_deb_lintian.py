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

from twisted.trial import unittest

from buildbot import config
from buildbot.process.results import SUCCESS
from buildbot.steps.package.deb import lintian
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import ExpectShell
from buildbot.test.steps import TestBuildStepMixin

if TYPE_CHECKING:
    from twisted.internet import defer


class TestDebLintian(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):
    def setUp(self) -> defer.Deferred[None]:  # type: ignore[override]
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def test_no_fileloc(self) -> None:
        with self.assertRaises(config.ConfigErrors):
            lintian.DebLintian()

    def test_success(self) -> defer.Deferred[None]:
        self.setup_step(lintian.DebLintian('foo_0.23_i386.changes'))
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['lintian', '-v', 'foo_0.23_i386.changes']).exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="Lintian")
        return self.run_step()

    def test_success_suppressTags(self) -> defer.Deferred[None]:
        self.setup_step(
            lintian.DebLintian(
                'foo_0.23_i386.changes', suppressTags=['bad-distribution-in-changes-file']
            )
        )
        self.expect_commands(
            ExpectShell(
                workdir='wkdir',
                command=[
                    'lintian',
                    '-v',
                    'foo_0.23_i386.changes',
                    '--suppress-tags',
                    'bad-distribution-in-changes-file',
                ],
            ).exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()
