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
from mock import Mock

from buildbot.process.factory import BuildFactory, ArgumentsInTheWrongPlace, s
from buildbot.process.buildstep import BuildStep

class TestBuildFactory(unittest.TestCase):

    def test_init(self):
        step = BuildStep()
        factory = BuildFactory([step])
        self.assertEqual(factory.steps, [(BuildStep, {})])

    def test_init_deprecated(self):
        factory = BuildFactory([s(BuildStep)])
        self.assertEqual(factory.steps, [(BuildStep, {})])

    def test_addStep(self):
        step = BuildStep()
        factory = BuildFactory()
        factory.addStep(step)
        self.assertEqual(factory.steps, [(BuildStep, {})])

    def test_addStep_deprecated(self):
        factory = BuildFactory()
        factory.addStep(BuildStep)
        self.assertEqual(factory.steps, [(BuildStep, {})])

    def test_addStep_notAStep(self):
        factory = BuildFactory()
        self.assertRaises(ValueError, factory.addStep, Mock())

    def test_addStep_ArgumentsInTheWrongPlace(self):
        factory = BuildFactory()
        self.assertRaises(ArgumentsInTheWrongPlace, factory.addStep, BuildStep(), name="name")

    def test_addSteps(self):
        factory = BuildFactory()
        factory.addSteps([BuildStep(), BuildStep()])
        self.assertEqual(factory.steps, [(BuildStep, {}), (BuildStep, {})])
