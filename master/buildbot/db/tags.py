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


from buildbot.db import base


class TagsConnectorComponent(base.DBConnectorComponent):

    def findTagId(self, name):
        tbl = self.db.model.tags
        name_hash = self.hashColumns(name)
        return self.findSomethingId(
            tbl=tbl,
            whereclause=(tbl.c.name_hash == name_hash),
            insert_values=dict(
                name=name,
                name_hash=name_hash,
            ))
