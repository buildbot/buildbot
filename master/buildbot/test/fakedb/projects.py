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

from buildbot.test.fakedb.row import Row


class Project(Row):
    table = "projects"

    id_column = 'id'
    hashedColumns = [('name_hash', ('name',))]

    def __init__(
        self,
        id=None,
        name='fake_project',
        name_hash=None,
        slug=None,
        description=None,
        description_format=None,
        description_html=None,
    ):
        if slug is None:
            slug = name
        super().__init__(
            id=id,
            name=name,
            name_hash=name_hash,
            slug=slug,
            description=description,
            description_format=description_format,
            description_html=description_html,
        )
