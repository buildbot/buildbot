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


class Builder(Row):
    table = "builders"

    id_column = 'id'
    hashedColumns = [('name_hash', ('name',))]

    def __init__(
        self,
        id=None,
        name='some:builder',
        name_hash=None,
        projectid=None,
        description=None,
        description_format=None,
        description_html=None
    ):
        super().__init__(
            id=id,
            name=name,
            name_hash=name_hash,
            projectid=projectid,
            description=description,
            description_format=description_format,
            description_html=description_html,
        )


class BuilderMaster(Row):
    table = "builder_masters"

    id_column = 'id'
    required_columns = ('builderid', 'masterid')

    def __init__(self, id=None, builderid=None, masterid=None):
        super().__init__(id=id, builderid=builderid, masterid=masterid)


class BuildersTags(Row):
    table = "builders_tags"

    foreignKeys = ('builderid', 'tagid')
    required_columns = ('builderid', 'tagid', )
    id_column = 'id'

    def __init__(self, id=None, builderid=None, tagid=None):
        super().__init__(id=id, builderid=builderid, tagid=tagid)


class FakeBuildersComponent(FakeDBComponent):

    def setUp(self):
        self.builders = {}
        self.builder_masters = {}
        self.builders_tags = {}

    def insert_test_data(self, rows):
        for row in rows:
            if isinstance(row, Builder):
                self.builders[row.id] = {
                    "id": row.id,
                    "name": row.name,
                    "projectid": row.projectid,
                    "description": row.description,
                    "description_format": row.description_format,
                    "description_html": row.description_html,
                }
            if isinstance(row, BuilderMaster):
                self.builder_masters[row.id] = \
                    (row.builderid, row.masterid)
            if isinstance(row, BuildersTags):
                assert row.builderid in self.builders
                self.builders_tags.setdefault(row.builderid,
                                              []).append(row.tagid)

    def findBuilderId(self, name, autoCreate=True):
        for m in self.builders.values():
            if m['name'] == name:
                return defer.succeed(m['id'])
        if not autoCreate:
            return defer.succeed(None)
        id = len(self.builders) + 1
        self.builders[id] = {
            "id": id,
            "name": name,
            "description": None,
            "description_format": None,
            "description_html": None,
            "projectid": None,
            "tags": []
        }
        return defer.succeed(id)

    def addBuilderMaster(self, builderid=None, masterid=None):
        if (builderid, masterid) not in list(self.builder_masters.values()):
            self.insert_test_data([
                BuilderMaster(builderid=builderid, masterid=masterid),
            ])
        return defer.succeed(None)

    def removeBuilderMaster(self, builderid=None, masterid=None):
        for id, tup in self.builder_masters.items():
            if tup == (builderid, masterid):
                del self.builder_masters[id]  # noqa pylint: disable=unnecessary-dict-index-lookup
                break
        return defer.succeed(None)

    def getBuilder(self, builderid):
        if builderid in self.builders:
            masterids = [bm[1] for bm in self.builder_masters.values()
                         if bm[0] == builderid]
            bldr = self.builders[builderid].copy()
            bldr['masterids'] = sorted(masterids)
            return defer.succeed(self._row2dict(bldr))
        return defer.succeed(None)

    def getBuilders(self, masterid=None, projectid=None):
        rv = []
        for builderid, bldr in self.builders.items():
            masterids = [bm[1] for bm in self.builder_masters.values()
                         if bm[0] == builderid]
            bldr = bldr.copy()
            bldr['masterids'] = sorted(masterids)
            rv.append(self._row2dict(bldr))
        if masterid is not None:
            rv = [bd for bd in rv
                  if masterid in bd['masterids']]
        if projectid is not None:
            rv = [bd for bd in rv if bd['projectid'] == projectid]
        return defer.succeed(rv)

    def addTestBuilder(self, builderid, name=None):
        if name is None:
            name = f"SomeBuilder-{builderid}"
        self.db.insert_test_data([
            Builder(id=builderid, name=name),
        ])

    @defer.inlineCallbacks
    def updateBuilderInfo(self, builderid, description, description_format, description_html,
                          projectid, tags):
        if builderid in self.builders:
            tags = tags if tags else []
            self.builders[builderid]['description'] = description
            self.builders[builderid]['description_format'] = description_format
            self.builders[builderid]['description_html'] = description_html
            self.builders[builderid]['projectid'] = projectid

            # add tags
            tagids = []
            for tag in tags:
                if not isinstance(tag, type(1)):
                    tag = yield self.db.tags.findTagId(tag)
                tagids.append(tag)
            self.builders_tags[builderid] = tagids

    def _row2dict(self, row):
        row = row.copy()
        row['tags'] = [self.db.tags.tags[tagid]['name']
                       for tagid in self.builders_tags.get(row['id'], [])]
        return row
