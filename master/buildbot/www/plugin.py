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

import importlib.resources

from twisted.web import static

from buildbot.util import bytes2unicode


class Application:
    def __init__(self, package_name: str, description: str, ui: bool = True) -> None:
        self.description = description
        # type ignore on `importlib.resources.files` since mypy conf target 3.8
        # where master is 3.9+, so mypy think it does not exists as it was introduced in 3.9.
        version_file = importlib.resources.files(package_name).joinpath("VERSION")  # type: ignore[attr-defined]
        self.version = bytes2unicode(version_file.read_bytes())
        self.static_dir = importlib.resources.files(package_name) / "static"  # type: ignore[attr-defined]
        self.resource = static.File(self.static_dir)
        self.ui = ui

    def setMaster(self, master: object) -> None:
        self.master = master

    def setConfiguration(self, config: object) -> None:
        self.config = config

    def __repr__(self) -> str:
        return (
            "www.plugin.Application(version={version}, "
            "description={description}, "
            "static_dir={static_dir})"
        ).format(**self.__dict__)
