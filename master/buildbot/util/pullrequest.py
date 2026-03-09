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

from fnmatch import fnmatch
from typing import Any


class PullRequestMixin:
    external_property_whitelist: list[str] = []
    external_property_denylist: list[str] = []
    property_basename: str

    def extractProperties(self, payload: dict[str, Any]) -> dict[str, Any]:
        def flatten(properties: dict[str, Any], base: str, info_dict: dict[str, Any]) -> None:
            for k, v in info_dict.items():
                name = ".".join([base, k])
                if name in self.external_property_denylist:
                    continue
                if isinstance(v, dict):
                    flatten(properties, name, v)
                elif any(fnmatch(name, expr) for expr in self.external_property_whitelist):
                    properties[name] = v

        properties: dict[str, Any] = {}
        flatten(properties, self.property_basename, payload)
        return properties
