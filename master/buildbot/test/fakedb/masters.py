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


class Master(Row):
    table = "masters"

    id_column = 'id'
    hashedColumns = [('name_hash', ('name',))]

    def __init__(self, id=None, name=None, name_hash=None, active=1, last_active=9998999):
        if name is None:
            name = f'master-{id}'
        super().__init__(
            id=id, name=name, name_hash=name_hash, active=active, last_active=last_active
        )
