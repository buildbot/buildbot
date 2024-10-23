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

from abc import abstractmethod
from typing import TYPE_CHECKING
from typing import Protocol

if TYPE_CHECKING:
    from typing import ClassVar


class CompressObjInterface(Protocol):
    def __init__(self) -> None:
        pass

    @abstractmethod
    def compress(self, data: bytes) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def flush(self) -> bytes:
        raise NotImplementedError


class CompressorInterface(Protocol):
    name: ClassVar[str]
    available: ClassVar[bool] = True

    CompressObj: ClassVar[type[CompressObjInterface]]

    @staticmethod
    @abstractmethod
    def dumps(data: bytes) -> bytes:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def read(data: bytes) -> bytes:
        raise NotImplementedError
