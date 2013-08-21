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

from buildbot.process.factory import BuildFactory, s
from buildbot.process.buildstep import BuildStep, _BuildStepFactory

class TestBuildFactory(unittest.TestCase):

    def test_init(self):
        step = BuildStep()
        factory = BuildFactory([step])
        self.assertEqual(factory.steps, [_BuildStepFactory(BuildStep)])

    def test_addStep(self):
        step = BuildStep()
        factory = BuildFactory()
        factory.addStep(step)
        self.assertEqual(factory.steps, [_BuildStepFactory(BuildStep)])

    def test_addStep_deprecated_withArguments(self):
        """
        Passing keyword arguments to L{BuildFactory.addStep} is deprecated,
        but pass the arguments to the first argument, to construct a step.
        """
        factory = BuildFactory()
        factory.addStep(BuildStep, name='test')
        self.assertEqual(factory.steps, [_BuildStepFactory(BuildStep, name='test')])
        warnings = self.flushWarnings([self.test_addStep_deprecated_withArguments])
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]['category'], DeprecationWarning)

    def test_addStep_deprecated(self):
        """
        Passing keyword arguments to L{BuildFactory.addStep} is deprecated,
        but pass the arguments to the first argument, to construct a step.
        """
        factory = BuildFactory()
        factory.addStep(BuildStep)
        self.assertEqual(factory.steps, [_BuildStepFactory(BuildStep)])
        warnings = self.flushWarnings([self.test_addStep_deprecated])
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]['category'], DeprecationWarning)

    def test_s(self):
        """
        L{s} is deprecated, but pass keyword arguments to the first argument,
        to construct a step.
        """
        stepFactory = s(BuildStep, name='test')
        self.assertEqual(stepFactory, _BuildStepFactory(BuildStep, name='test'))
        warnings = self.flushWarnings([self.test_s])
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]['category'], DeprecationWarning)

    def test_addStep_notAStep(self):
        factory = BuildFactory()
        # This fails because object isn't adaptable to IBuildStepFactory
        self.assertRaises(TypeError, factory.addStep, object())

    def test_addStep_ArgumentsInTheWrongPlace(self):
        factory = BuildFactory()
        self.assertRaises(TypeError, factory.addStep, BuildStep(), name="name")

    def test_addSteps(self):
        factory = BuildFactory()
        factory.addSteps([BuildStep(), BuildStep()])
        self.assertEqual(factory.steps, [_BuildStepFactory(BuildStep), _BuildStepFactory(BuildStep)])
