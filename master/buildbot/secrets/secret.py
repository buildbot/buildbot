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


class SecretDetails:
    """
    A SecretDetails object has secrets attributes:
    - source: provider where the secret was retrieved
    - key: secret key identifier
    - value: secret value
    """

    def __init__(self, source: str, key: str, value: str) -> None:
        self._source = source
        self._value = value
        self._key = key

    @property
    def source(self) -> str:
        """
        source of the secret
        """
        return self._source

    @property
    def value(self) -> str:
        """
        secret value
        """
        return self._value

    @property
    def key(self) -> str:
        """
        secret value
        """
        return self._key

    def __str__(self) -> str:
        return f'{self._source} {self._key}: {self.value!r}'

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SecretDetails):
            return NotImplemented
        return self._source == other._source and self.key == other.key and self.value == other.value

    def __hash__(self) -> int:
        return hash((self._source, self.key, self.value))
