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
from future.builtins import range

from random import choice
from string import ascii_uppercase

from twisted.trial import unittest

from buildbot.process.buildstep import BuildStep
from buildbot.process.buildstep import _BuildStepFactory
from buildbot.process.factory import BuildFactory
from buildbot.process.factory import GNUAutoconf
from buildbot.process.factory import s
from buildbot.steps.shell import Configure


class TestBuildFactory(unittest.TestCase):

    def setUp(self):
        self.factory = BuildFactory()

    def test_init(self):
        step = BuildStep()
        self.factory = BuildFactory([step])
        self.assertEqual(self.factory.steps, [_BuildStepFactory(BuildStep)])

    def test_addStep(self):
        # create a string random string that will probably not collide
        # with what is already in the factory
        string = ''.join(choice(ascii_uppercase) for x in range(6))
        length = len(self.factory.steps)

        step = BuildStep(name=string)
        self.factory.addStep(step)

        # check if the number of nodes grew by one
        self.assertTrue(length + 1, len(self.factory.steps))
        # check if the 'right' node added in the factory
        self.assertEqual(self.factory.steps[-1],
                         _BuildStepFactory(BuildStep, name=string))

    def test_addStep_deprecated_withArguments(self):
        """
        Passing keyword arguments to L{BuildFactory.addStep} is deprecated,
        but pass the arguments to the first argument, to construct a step.
        """
        self.factory.addStep(BuildStep, name='test')

        self.assertEqual(self.factory.steps[-1],
                         _BuildStepFactory(BuildStep, name='test'))

        warnings = self.flushWarnings(
            [self.test_addStep_deprecated_withArguments])
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]['category'], DeprecationWarning)

    def test_addStep_deprecated(self):
        """
        Passing keyword arguments to L{BuildFactory.addStep} is deprecated,
        but pass the arguments to the first argument, to construct a step.
        """
        self.factory.addStep(BuildStep)

        self.assertEqual(self.factory.steps[-1],
                         _BuildStepFactory(BuildStep))

        warnings = self.flushWarnings([self.test_addStep_deprecated])
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]['category'], DeprecationWarning)

    def test_s(self):
        """
        L{s} is deprecated, but pass keyword arguments to the first argument,
        to construct a step.
        """
        stepFactory = s(BuildStep, name='test')
        self.assertEqual(
            stepFactory, _BuildStepFactory(BuildStep, name='test'))
        warnings = self.flushWarnings([self.test_s])
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]['category'], DeprecationWarning)

    def test_addStep_notAStep(self):
        # This fails because object isn't adaptable to IBuildStepFactory
        self.assertRaises(TypeError, self.factory.addStep, object())

    def test_addStep_ArgumentsInTheWrongPlace(self):
        self.assertRaises(
            TypeError, self.factory.addStep, BuildStep(), name="name")
        # this also raises a deprecation error, which we don't care about (see
        # test_s)
        self.flushWarnings()

    def test_addSteps(self):
        self.factory.addSteps([BuildStep(), BuildStep()])
        self.assertEqual(self.factory.steps[-2:],
                         [_BuildStepFactory(BuildStep),
                          _BuildStepFactory(BuildStep)])


class TestGNUAutoconf(TestBuildFactory):

    def setUp(self):
        self.factory = GNUAutoconf(source=BuildStep())

    def test_init(self):
        # actual initialization is already done by setUp
        configurePresent = False
        compilePresent = False
        checkPresent = False
        distcheckPresent = False
        for step in self.factory.steps:
            if isinstance(step.buildStep(), Configure):
                configurePresent = True
            # the following checks are rather hairy and should be
            # rewritten less implementation dependent.
            try:
                if step.buildStep().command == ['make', 'all']:
                    compilePresent = True
                if step.buildStep().command == ['make', 'check']:
                    checkPresent = True
                if step.buildStep().command == ['make', 'distcheck']:
                    distcheckPresent = True
            except(AttributeError, KeyError):
                pass

        self.assertTrue(configurePresent)
        self.assertTrue(compilePresent)
        self.assertTrue(checkPresent)
        self.assertTrue(distcheckPresent)

    def test_init_none(self):
        """Default steps can be uninitialized by setting None"""

        self.factory = GNUAutoconf(source=BuildStep(), compile=None, test=None,
                                   distcheck=None)
        for step in self.factory.steps:
            try:
                cmd = step.buildStep().command
                self.assertNotIn(cmd, [['make', 'all'], ['make', 'check'],
                                 ['make', 'distcheck']],
                                 "Build step %s should not be present." % cmd)
            except(AttributeError, KeyError):
                pass

    def test_init_reconf(self):
        # test reconf = True
        self.factory = GNUAutoconf(source=BuildStep(), reconf=True)
        self.test_init()
        reconfPresent = False
        selfreconfPresent = False

        for step in self.factory.steps:
            try:
                if step.buildStep().command[0] == 'autoreconf':
                    reconfPresent = True
            except(AttributeError, KeyError):
                pass
        self.assertTrue(reconfPresent)

        # test setting your own reconfiguration step
        self.factory = GNUAutoconf(source=BuildStep(),
                                   reconf=['notsoautoreconf'])
        self.test_init()
        for step in self.factory.steps:
            try:
                if step.buildStep().command == ['notsoautoreconf']:
                    selfreconfPresent = True
            except(AttributeError, KeyError):
                pass
        self.assertTrue(selfreconfPresent)
