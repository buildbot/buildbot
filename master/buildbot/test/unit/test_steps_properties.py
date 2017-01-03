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

from buildbot.process.properties import Interpolate
from buildbot.process.properties import renderer
from buildbot.process.results import SUCCESS
from buildbot.steps import properties
from buildbot.test.util import steps


class Tests(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def doOneTest(self, **kwargs):
        # all three tests should create a 'a' property with 'b' value, all with different
        # more or less dynamic methods
        self.setupStep(
            properties.SetProperties(name="my-step", **kwargs))
        self.expectProperty('a', 'b', 'my-step')
        self.expectOutcome(result=SUCCESS, state_string='finished')
        return self.runStep()

    def test_basic(self):
        return self.doOneTest(properties={'a': 'b'})

    def test_renderable(self):
        return self.doOneTest(properties={'a': Interpolate("b")})

    def test_renderer(self):
        @renderer
        def manipulate(props):
            # the renderer returns renderable!
            return {'a': Interpolate('b')}
        return self.doOneTest(properties=manipulate)
