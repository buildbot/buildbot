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

from twisted.trial import unittest

from buildbot.config.checks import check_param_length
from buildbot.config.checks import check_param_str
from buildbot.config.checks import check_param_str_none
from buildbot.process.properties import Interpolate
from buildbot.test.util import config


class TestCheckParamLength(unittest.TestCase, config.ConfigErrorsMixin):
    def test_short_string(self) -> None:
        check_param_length('1234567890', 'Step name', 10)

    def test_long_string(self) -> None:
        with self.assertRaisesConfigError("exceeds maximum length of 10"):
            check_param_length('12345678901', 'Step name', 10)

    def test_short_interpolate(self) -> None:
        check_param_length(Interpolate('123456%(prop:xy)s7890'), 'Step name', 10)

    def test_short_interpolate_args(self) -> None:
        check_param_length(Interpolate('123456%s7890', 'arg'), 'Step name', 10)

    def test_short_interpolate_kwargs(self) -> None:
        check_param_length(Interpolate('123456%(prop:xy)s7890', kw='arg'), 'Step name', 10)

    def test_long_interpolate(self) -> None:
        with self.assertRaisesConfigError("exceeds maximum length of 10"):
            check_param_length(Interpolate('123456%(prop:xy)s78901'), 'Step name', 10)


class TestCheckParamType(unittest.TestCase, config.ConfigErrorsMixin):
    def test_str(self) -> None:
        check_param_str('abc', self.__class__, 'param')

    def test_str_wrong(self) -> None:
        msg = "TestCheckParamType argument param must be an instance of str"
        with self.assertRaisesConfigError(msg):
            check_param_str(1, self.__class__, 'param')

    def test_str_none(self) -> None:
        check_param_str_none('abc', self.__class__, 'param')
        check_param_str_none(None, self.__class__, 'param')

    def test_str_none_wrong(self) -> None:
        msg = "TestCheckParamType argument param must be an instance of str or None"
        with self.assertRaisesConfigError(msg):
            check_param_str_none(1, self.__class__, 'param')
