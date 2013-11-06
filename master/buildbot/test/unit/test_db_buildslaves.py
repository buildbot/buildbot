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

from buildbot.db import buildslaves
from buildbot.test.fake import fakedb
from buildbot.test.util import connector_component
from twisted.python import failure
from twisted.trial import unittest


class TestBuildslavesConnectorComponent(connector_component.ConnectorComponentMixin,
                                        unittest.TestCase):

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['buildslaves'])

        def finish_setup(_):
            self.db.buildslaves = buildslaves.BuildslavesConnectorComponent(self.db)
        d.addCallback(finish_setup)
        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()

    # sample buildslave data, with id's avoiding the postgres id sequence

    BOGUS_NAME = 'bogus'

    BS1_NAME, BS1_ID, BS1_INFO = 'bs1', 100, {'a': 1}
    buildslave1_rows = [
        fakedb.Buildslave(id=BS1_ID, name=BS1_NAME, info=BS1_INFO),
    ]

    BS2_NAME, BS2_ID, BS2_INFO = 'bs2', 200, {'a': 1, 'b': 2}
    buildslave2_rows = [
        fakedb.Buildslave(id=BS2_ID, name=BS2_NAME, info=BS2_INFO),
    ]

    # tests

    def test_getBuildslaveByName_empty(self):
        d = self.insertTestData(self.buildslave1_rows)

        @d.addCallback
        def get(_):
            return self.db.buildslaves.getBuildslaveByName(self.BOGUS_NAME)

        @d.addCallback
        def check(res):
            self.assertEqual(res, None)

        return d

    def test_getBuildslaveByName_existing(self):
        d = self.insertTestData(self.buildslave1_rows)

        @d.addCallback
        def get(_):
            return self.db.buildslaves.getBuildslaveByName(self.BS1_NAME)

        @d.addCallback
        def check(res):
            self.assertEqual(res['slaveid'], self.BS1_ID)
            self.assertEqual(res['name'], self.BS1_NAME)
            self.assertEqual(res['slaveinfo'], self.BS1_INFO)

        return d

    def test_getBuildslaves_empty(self):
        d = self.db.buildslaves.getBuildslaves()

        @d.addCallback
        def check(res):
            self.assertEqual(res, [])

        return d

    def test_getBuildslaves_some(self):
        d = self.insertTestData(self.buildslave1_rows + self.buildslave2_rows)

        @d.addCallback
        def get(_):
            return self.db.buildslaves.getBuildslaves()

        @d.addCallback
        def check(res):
            self.assertEqual(len(res), 2)

            self.assertEqual(res[0]['slaveid'], self.BS1_ID)
            self.assertEqual(res[0]['name'], self.BS1_NAME)

            self.assertEqual(res[1]['slaveid'], self.BS2_ID)
            self.assertEqual(res[1]['name'], self.BS2_NAME)

        return d

    def test_updateBuildslaves_existing(self):
        d = self.insertTestData(self.buildslave1_rows)

        NEW_INFO = {'other': [1, 2, 3]}

        @d.addCallback
        def update(_):
            return self.db.buildslaves.updateBuildslave(
                name=self.BS1_NAME,
                slaveinfo=NEW_INFO
            )

        @d.addCallback
        def get(_):
            return self.db.buildslaves.getBuildslaveByName(self.BS1_NAME)

        @d.addCallback
        def check(res):
            self.assertEqual(res['slaveid'], self.BS1_ID)
            self.assertEqual(res['name'], self.BS1_NAME)
            self.assertEqual(res['slaveinfo'], NEW_INFO)

        return d

    def test_updateBuildslaves_new(self):
        # insert only #1, but not #2
        d = self.insertTestData(self.buildslave1_rows)

        @d.addCallback
        def update(_):
            return self.db.buildslaves.updateBuildslave(
                name=self.BS2_NAME,
                slaveinfo=self.BS2_INFO
            )

        @d.addCallback
        def get(_):
            return self.db.buildslaves.getBuildslaveByName(self.BS2_NAME)

        @d.addCallback
        def check(res):
            self.failIfIdentical(res['slaveid'], None)
            self.assertEqual(res['name'], self.BS2_NAME)
            self.assertEqual(res['slaveinfo'], self.BS2_INFO)

        return d

    def test_updateBuildslave_race(self):
        RACE_INFO = {'race': 'yep'}

        def race_thd(conn):
            # generate a new connection, since the passed connection will be
            # rolled back as a result of the conflicting insert
            newConn = conn.engine.connect()
            newConn.execute(self.db.model.buildslaves.insert(),
                            name=self.BS1_NAME,
                            info=RACE_INFO)

        d = self.db.buildslaves.updateBuildslave(
            name=self.BS1_NAME,
            slaveinfo=self.BS1_INFO,
            _race_hook=race_thd)

        @d.addCallback
        def get(_):
            return self.db.buildslaves.getBuildslaveByName(self.BS1_NAME)

        @d.addCallback
        def check(res):
            self.failIfIdentical(res['slaveid'], None)
            self.assertEqual(res['name'], self.BS1_NAME)
            self.assertEqual(res['slaveinfo'], RACE_INFO)  # race wins

        return d

    def test_updateBuildslave_badJson(self):
        d = self.insertTestData(self.buildslave1_rows)

        @d.addCallback
        def corrupt(_):
            BAD_JSON = {
                'key': object(),  # something json wont serialize
            }
            return self.db.buildslaves.updateBuildslave(
                name=self.BS1_NAME,
                slaveinfo=BAD_JSON)

        @d.addBoth
        def shouldThrow(res):
            self.assertIsInstance(res, failure.Failure)

        @d.addCallback
        def get(_):
            return self.db.buildslaves.getBuildslaveByName(self.BS1_NAME)

        @d.addCallback
        def checkUnchanged(res):
            # should be unchanged from the original value
            self.assertEqual(res['slaveinfo'], self.BS1_INFO)

        return d
