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

import re
from typing import Any

from twisted.cred.checkers import FilePasswordDB
from twisted.python.components import registerAdapter
from zope.interface import implementer

from buildbot.interfaces import IConfigured


@implementer(IConfigured)
class _DefaultConfigured:
    def __init__(self, value: Any) -> None:
        self.value = value

    def getConfigDict(self) -> Any:
        return self.value


registerAdapter(_DefaultConfigured, object, IConfigured)


@implementer(IConfigured)
class _ListConfigured:
    def __init__(self, value: list[Any]) -> None:
        self.value = value

    def getConfigDict(self) -> list[Any]:  # type: ignore[override]
        return [IConfigured(e).getConfigDict() for e in self.value]


registerAdapter(_ListConfigured, list, IConfigured)


@implementer(IConfigured)
class _DictConfigured:
    def __init__(self, value: dict[str, Any]) -> None:
        self.value = value

    def getConfigDict(self) -> dict[str, Any]:
        return {k: IConfigured(v).getConfigDict() for k, v in self.value.items()}


registerAdapter(_DictConfigured, dict, IConfigured)


@implementer(IConfigured)
class _SREPatternConfigured:
    def __init__(self, value: re.Pattern[str]) -> None:
        self.value = value

    def getConfigDict(self) -> dict[str, str]:
        return {"name": 're', "pattern": self.value.pattern}


registerAdapter(_SREPatternConfigured, type(re.compile("")), IConfigured)


@implementer(IConfigured)
class ConfiguredMixin:
    def getConfigDict(self) -> dict[str, Any]:
        return {'name': self.name}  # type: ignore[attr-defined]


@implementer(IConfigured)
class _FilePasswordDBConfigured:
    def __init__(self, value: FilePasswordDB) -> None:
        pass

    def getConfigDict(self) -> dict[str, str]:
        return {'type': 'file'}


registerAdapter(_FilePasswordDBConfigured, FilePasswordDB, IConfigured)
