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

from typing import ClassVar
from typing import Sequence

from buildbot import util
from buildbot.config.checks import check_param_str


class Codebase(util.ComparableMixin):
    compare_attrs: ClassVar[Sequence[str]] = (
        "name",
        "slug",
        "project",
    )

    def __init__(self, name: str, project: str, slug: str | None = None) -> None:
        if slug is None:
            slug = name

        self.name = check_param_str(name, self.__class__, "name")
        self.slug = check_param_str(slug, self.__class__, "slug")
        self.project = check_param_str(project, self.__class__, "project")
