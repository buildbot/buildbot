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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.config import ConfigErrors
from buildbot.process.properties import Property
from buildbot.process.results import SUCCESS
from buildbot.steps.cmake import CMake
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import ExpectShell
from buildbot.test.steps import TestBuildStepMixin


class TestCMake(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        yield self.setup_test_build_step()

    async def expect_and_run_command(self, *params) -> None:
        command = [CMake.DEFAULT_CMAKE, *list(params)]

        self.expect_commands(ExpectShell(command=command, workdir='wkdir').exit(0))
        self.expect_outcome(result=SUCCESS)
        await self.run_step()

    def test_definitions_type(self):
        with self.assertRaises(ConfigErrors):
            CMake(definitions='hello')

    def test_options_type(self):
        with self.assertRaises(ConfigErrors):
            CMake(options='hello')

    def test_plain(self):
        self.setup_step(CMake())
        self.expect_commands(ExpectShell(command=[CMake.DEFAULT_CMAKE], workdir='wkdir').exit(0))
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_cmake(self):
        cmake_bin = 'something/else/cmake'

        self.setup_step(CMake(cmake=cmake_bin))
        self.expect_commands(ExpectShell(command=[cmake_bin], workdir='wkdir').exit(0))
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_cmake_interpolation(self):
        prop = 'CMAKE'
        value = 'Real_CMAKE'

        self.setup_step(CMake(cmake=Property(prop)))
        self.build.setProperty(prop, value, source='test')

        self.expect_commands(ExpectShell(command=[value], workdir='wkdir').exit(0))
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    async def test_definitions(self):
        definition = {'a': 'b'}
        self.setup_step(CMake(definitions=definition))
        await self.expect_and_run_command('-Da=b')

    def test_environment(self):
        command = [CMake.DEFAULT_CMAKE]
        environment = {'a': 'b'}
        self.setup_step(CMake(env=environment))
        self.expect_commands(ExpectShell(command=command, workdir='wkdir', env={'a': 'b'}).exit(0))
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    async def test_definitions_interpolation(self):
        definitions = {'a': Property('b')}

        self.setup_step(CMake(definitions=definitions))
        self.build.setProperty('b', 'real_b', source='test')
        await self.expect_and_run_command('-Da=real_b')

    async def test_definitions_renderable(self):
        definitions = Property('b')
        self.setup_step(CMake(definitions=definitions))
        self.build.setProperty('b', {'a': 'real_b'}, source='test')
        await self.expect_and_run_command('-Da=real_b')

    async def test_generator(self):
        generator = 'Ninja'

        self.setup_step(CMake(generator=generator))
        await self.expect_and_run_command('-G', generator)

    async def test_generator_interpolation(self):
        value = 'Our_GENERATOR'

        self.setup_step(CMake(generator=Property('GENERATOR')))
        self.build.setProperty('GENERATOR', value, source='test')

        await self.expect_and_run_command('-G', value)

    async def test_options(self):
        options = ('A', 'B')

        self.setup_step(CMake(options=options))
        await self.expect_and_run_command(*options)

    async def test_options_interpolation(self):
        prop = 'option'
        value = 'value'

        self.setup_step(CMake(options=(Property(prop),)))
        self.build.setProperty(prop, value, source='test')
        await self.expect_and_run_command(value)

    async def test_path(self):
        path = 'some/path'

        self.setup_step(CMake(path=path))
        await self.expect_and_run_command(path)

    async def test_path_interpolation(self):
        prop = 'path'
        value = 'some/path'

        self.setup_step(CMake(path=Property(prop)))
        self.build.setProperty(prop, value, source='test')
        await self.expect_and_run_command(value)

    async def test_options_path(self):
        self.setup_step(CMake(path='some/path', options=('A', 'B')))
        await self.expect_and_run_command('A', 'B', 'some/path')
