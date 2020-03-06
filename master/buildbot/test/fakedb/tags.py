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

from twisted.internet import defer

from buildbot.test.fakedb.base import FakeDBComponent
from buildbot.test.fakedb.row import Row


class Tag(Row):
    table = "tags"

    defaults = dict(
        id=None,
        name='some:tag',
        name_hash=None,
    )

    id_column = 'id'
    hashedColumns = [('name_hash', ('name',))]


class FakeTagsComponent(FakeDBComponent):

    def setUp(self):
        self.tags = {}

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, Tag):
                self.tags[row.id] = dict(
                    id=row.id,
                    name=row.name)

    def findTagId(self, name):
        for m in self.tags.values():
            if m['name'] == name:
                return defer.succeed(m['id'])
        id = len(self.tags) + 1
        self.tags[id] = dict(
            id=id,
            name=name)
        return defer.succeed(id)
