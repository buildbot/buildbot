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
from typing import Callable
from typing import Generic
from typing import TypeVar

_ident_re = re.compile('^[a-zA-Z_-][.a-zA-Z0-9_-]*$')

_T = TypeVar('_T')


def ident(x: str) -> str:
    if _ident_re.match(x):
        return x
    raise TypeError


class Matcher(Generic[_T]):
    def __init__(self) -> None:
        self._patterns: dict[tuple[str, ...], _T] = {}
        self._dirty: bool = True

    def __setitem__(self, path: tuple[str, ...], value: _T) -> None:
        assert path not in self._patterns, f"duplicate path {path}"
        self._patterns[path] = value
        self._dirty = True

    def __repr__(self) -> str:
        return f'<Matcher {self._patterns!r}>'

    path_elt_re = re.compile('^(.?):([a-z0-9_.]+)$')
    type_fns: dict[str, Callable[[str], Any]] = {"n": int, "i": ident, "s": str}

    def __getitem__(self, path: tuple[str, ...]) -> tuple[_T, dict[str, Any]]:
        if self._dirty:
            self._compile()

        patterns = self._by_length.get(len(path), {})
        for pattern in patterns:
            kwargs: dict[str, Any] = {}
            for pattern_elt, path_elt in zip(pattern, path):
                mo = self.path_elt_re.match(pattern_elt)
                if mo:
                    type_flag, arg_name = mo.groups()
                    if type_flag:
                        try:
                            type_fn = self.type_fns[type_flag]
                        except Exception:
                            assert type_flag in self.type_fns, f"no such type flag {type_flag}"
                        try:
                            path_elt = type_fn(path_elt)
                        except Exception:
                            break
                    kwargs[arg_name] = path_elt
                else:
                    if pattern_elt != path_elt:
                        break
            else:
                # complete match
                return patterns[pattern], kwargs
        raise KeyError(f'No match for {path!r}')

    def iterPatterns(self) -> list[tuple[tuple[str, ...], _T]]:
        return list(self._patterns.items())

    def _compile(self) -> None:
        self._by_length: dict[int, dict[tuple[str, ...], _T]] = {}
        for k, v in self.iterPatterns():
            length = len(k)
            self._by_length.setdefault(length, {})[k] = v
