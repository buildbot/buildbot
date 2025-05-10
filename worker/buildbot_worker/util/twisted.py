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

"""Copied from buildbot.util.twisted"""

from __future__ import annotations

from typing import Any
from typing import Generator
from typing import TypeVar
from typing import Union

from twisted.internet import defer
from typing_extensions import ParamSpec

_T = TypeVar('_T')
_P = ParamSpec('_P')


InlineCallbacksType = Generator[Union[Any, defer.Deferred[Any]], Any, _T]
