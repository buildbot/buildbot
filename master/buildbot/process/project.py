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


from buildbot import util
from buildbot.config.checks import check_markdown_support
from buildbot.config.checks import check_param_str
from buildbot.config.checks import check_param_str_none
from buildbot.config.errors import error


class Project(util.ComparableMixin):

    compare_attrs = (
        "name",
        "slug",
        "description",
        "description_format",
    )

    def __init__(self, name, slug=None, description=None, description_format=None):
        if slug is None:
            slug = name

        self.name = check_param_str(name, self.__class__, "name")
        self.slug = check_param_str(slug, self.__class__, "slug")
        self.description = check_param_str_none(description, self.__class__, "description")
        self.description_format = \
            check_param_str_none(description_format, self.__class__, "description_format")
        if self.description_format is None:
            pass
        elif self.description_format == "markdown":
            if not check_markdown_support(self.__class__):  # pragma: no cover
                self.description_format = None
        else:
            error("project description format must be None or \"markdown\"")
            self.description_format = None
