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

from buildbot.process.buildstep import BuildStep
from buildbot.process.properties import Interpolate
from buildbot.test.util import config as configmixin
from buildbot.test.util import steps
from buildbot.test.util.misc import TestReactorMixin


class TestBuildStep(BuildStep):
    def run(self):
        self.setProperty('name', self.name)
        return 0


class TestBuildStepNameIsRenderable(steps.BuildStepMixin, unittest.TestCase,
                                    TestReactorMixin,
                                    configmixin.ConfigErrorsMixin):

    def setUp(self):
        self.setUpTestReactor()
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_name_is_renderable(self):
        step = TestBuildStep(name=Interpolate('%(kw:foo)s', foo='bar'))
        self.setupStep(step)
        self.expectProperty('name', 'bar')
        self.expectOutcome(0)
        return self.runStep()
