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

from twisted.trial.unittest import TestCase

from buildbot.config import ConfigErrors
from buildbot.process.properties import Property
from buildbot.process.results import SUCCESS
from buildbot.steps.cmake import CMake
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.util.steps import BuildStepMixin


class TestCMake(BuildStepMixin, TestCase):

    def setUp(self):
        self.setUpBuildStep()

    def tearDown(self):
        self.tearDownBuildStep()

    def expect_and_run_command(self, *params):
        command = [CMake.DEFAULT_CMAKE] + list(params)

        self.expectCommands(
            ExpectShell(command=command, workdir='wkdir') + 0)
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_definitions_type(self):
        self.assertRaises(ConfigErrors, lambda: CMake(definitions='hello'))

    def test_options_type(self):
        self.assertRaises(ConfigErrors, lambda: CMake(options='hello'))

    def test_plain(self):
        self.setupStep(CMake())
        self.expectCommands(
            ExpectShell(command=[CMake.DEFAULT_CMAKE], workdir='wkdir') + 0)
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_cmake(self):
        cmake_bin = 'something/else/cmake'

        self.setupStep(CMake(cmake=cmake_bin))
        self.expectCommands(
            ExpectShell(command=[cmake_bin], workdir='wkdir') + 0)
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_cmake_interpolation(self):
        prop = 'CMAKE'
        value = 'Real_CMAKE'

        self.setupStep(CMake(cmake=Property(prop)))
        self.properties.setProperty(prop, value, source='test')

        self.expectCommands(
            ExpectShell(command=[value], workdir='wkdir') + 0)
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_definitions(self):
        definition = {
            'a': 'b'
        }
        self.setupStep(CMake(definitions=definition))
        self.expect_and_run_command('-D%s=%s' % list(definition.items())[0])

    def test_environment(self):
        command = [CMake.DEFAULT_CMAKE]
        environment = {'a': 'b'}
        self.setupStep(CMake(env=environment))
        self.expectCommands(
            ExpectShell(
                command=command, workdir='wkdir', env={'a': 'b'}) + 0)
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_definitions_interpolation(self):
        b_value = 'real_b'

        definitions = {
            'a': Property('b')
        }

        self.setupStep(CMake(definitions=definitions))
        self.properties.setProperty('b', b_value, source='test')
        self.expect_and_run_command('-D%s=%s' % ('a', b_value))

    def test_definitions_renderable(self):
        b_value = 'real_b'

        definitions = Property('b')
        self.setupStep(CMake(definitions=definitions))
        self.properties.setProperty('b', {'a': b_value}, source='test')
        self.expect_and_run_command('-D%s=%s' % ('a', b_value))

    def test_generator(self):
        generator = 'Ninja'

        self.setupStep(CMake(generator=generator))
        self.expect_and_run_command('-G', generator)

    def test_generator_interpolation(self):
        value = 'Our_GENERATOR'

        self.setupStep(CMake(generator=Property('GENERATOR')))
        self.properties.setProperty('GENERATOR', value, source='test')

        self.expect_and_run_command('-G', value)

    def test_options(self):
        options = ('A', 'B')

        self.setupStep(CMake(options=options))
        self.expect_and_run_command(*options)

    def test_options_interpolation(self):
        prop = 'option'
        value = 'value'

        self.setupStep(CMake(options=(Property(prop),)))
        self.properties.setProperty(prop, value, source='test')
        self.expect_and_run_command(value)

    def test_path(self):
        path = 'some/path'

        self.setupStep(CMake(path=path))
        self.expect_and_run_command(path)

    def test_path_interpolation(self):
        prop = 'path'
        value = 'some/path'

        self.setupStep(CMake(path=Property(prop)))
        self.properties.setProperty(prop, value, source='test')
        self.expect_and_run_command(value)
