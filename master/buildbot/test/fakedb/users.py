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


class User(Row):
    table = "users"

    id_column = 'uid'

    def __init__(self, uid=None, identifier='soap', bb_username=None, bb_password=None):
        super().__init__(
            uid=uid, identifier=identifier, bb_username=bb_username, bb_password=bb_password
        )


class UserInfo(Row):
    table = "users_info"

    def __init__(self, uid=None, attr_type='git', attr_data='Tyler Durden <tyler@mayhem.net>'):
        super().__init__(uid=uid, attr_type=attr_type, attr_data=attr_data)
