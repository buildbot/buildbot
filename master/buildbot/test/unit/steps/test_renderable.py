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

if TYPE_CHECKING:
    from twisted.internet import defer

from buildbot.process.buildstep import BuildStep
from buildbot.process.properties import Interpolate
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import TestBuildStepMixin
from buildbot.test.util import config as configmixin


class TestBuildStep(BuildStep):
    def run(self) -> defer.Deferred[int]:
        self.setProperty('name', self.name)
        return 0  # type: ignore[return-value]


class TestBuildStepNameIsRenderable(
    TestBuildStepMixin, TestReactorMixin, configmixin.ConfigErrorsMixin, unittest.TestCase
):
    def setUp(self) -> defer.Deferred[None]:  # type: ignore[override]
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def test_name_is_renderable(self) -> defer.Deferred[None]:
        step = TestBuildStep(name=Interpolate('%(kw:foo)s', foo='bar'))
        self.setup_step(step)
        self.expect_property('name', 'bar')
        self.expect_outcome(0)
        return self.run_step()
