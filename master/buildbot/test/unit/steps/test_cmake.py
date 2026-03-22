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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.config import ConfigErrors
from buildbot.process.properties import Property
from buildbot.process.results import SUCCESS
from buildbot.steps.cmake import CMake
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import ExpectShell
from buildbot.test.steps import TestBuildStepMixin

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class TestCMake(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        yield self.setup_test_build_step()

    def expect_and_run_command(self, *params: str) -> defer.Deferred[None]:
        command = [CMake.DEFAULT_CMAKE, *list(params)]

        self.expect_commands(ExpectShell(command=command, workdir='wkdir').exit(0))
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_definitions_type(self) -> None:
        with self.assertRaises(ConfigErrors):
            CMake(definitions='hello')  # type: ignore[arg-type]

    def test_options_type(self) -> None:
        with self.assertRaises(ConfigErrors):
            CMake(options='hello')  # type: ignore[arg-type]

    def test_plain(self) -> defer.Deferred[None]:
        self.setup_step(CMake())
        self.expect_commands(ExpectShell(command=[CMake.DEFAULT_CMAKE], workdir='wkdir').exit(0))
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_cmake(self) -> defer.Deferred[None]:
        cmake_bin = 'something/else/cmake'

        self.setup_step(CMake(cmake=cmake_bin))
        self.expect_commands(ExpectShell(command=[cmake_bin], workdir='wkdir').exit(0))
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_cmake_interpolation(self) -> defer.Deferred[None]:
        prop = 'CMAKE'
        value = 'Real_CMAKE'

        self.setup_step(CMake(cmake=Property(prop)))
        self.build.setProperty(prop, value, source='test')

        self.expect_commands(ExpectShell(command=[value], workdir='wkdir').exit(0))
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_definitions(self) -> None:
        definition = {'a': 'b'}
        self.setup_step(CMake(definitions=definition))
        self.expect_and_run_command('-Da=b')

    def test_environment(self) -> defer.Deferred[None]:
        command = [CMake.DEFAULT_CMAKE]
        environment = {'a': 'b'}
        self.setup_step(CMake(env=environment))
        self.expect_commands(ExpectShell(command=command, workdir='wkdir', env={'a': 'b'}).exit(0))
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_definitions_interpolation(self) -> None:
        definitions = {'a': Property('b')}

        self.setup_step(CMake(definitions=definitions))
        self.build.setProperty('b', 'real_b', source='test')
        self.expect_and_run_command('-Da=real_b')

    def test_definitions_renderable(self) -> None:
        definitions = Property('b')
        self.setup_step(CMake(definitions=definitions))
        self.build.setProperty('b', {'a': 'real_b'}, source='test')
        self.expect_and_run_command('-Da=real_b')

    def test_generator(self) -> None:
        generator = 'Ninja'

        self.setup_step(CMake(generator=generator))
        self.expect_and_run_command('-G', generator)

    def test_generator_interpolation(self) -> None:
        value = 'Our_GENERATOR'

        self.setup_step(CMake(generator=Property('GENERATOR')))
        self.build.setProperty('GENERATOR', value, source='test')

        self.expect_and_run_command('-G', value)

    def test_options(self) -> None:
        options = ('A', 'B')

        self.setup_step(CMake(options=options))
        self.expect_and_run_command(*options)

    def test_options_interpolation(self) -> None:
        prop = 'option'
        value = 'value'

        self.setup_step(CMake(options=(Property(prop),)))
        self.build.setProperty(prop, value, source='test')
        self.expect_and_run_command(value)

    def test_path(self) -> None:
        path = 'some/path'

        self.setup_step(CMake(path=path))
        self.expect_and_run_command(path)

    def test_path_interpolation(self) -> None:
        prop = 'path'
        value = 'some/path'

        self.setup_step(CMake(path=Property(prop)))
        self.build.setProperty(prop, value, source='test')
        self.expect_and_run_command(value)

    def test_options_path(self) -> None:
        self.setup_step(CMake(path='some/path', options=('A', 'B')))
        self.expect_and_run_command('A', 'B', 'some/path')
