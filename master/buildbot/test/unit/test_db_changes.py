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

import sqlalchemy as sa
from twisted.trial import unittest
from buildbot.db import changes
from buildbot.test.util import connector_component
from buildbot.test.fake import fakedb

class TestChangesConnectorComponent(
            connector_component.ConnectorComponentMixin,
            unittest.TestCase):

    change13_rows = [
        fakedb.Change(changeid=13, author="dustin", comments="fix spelling",
            is_dir=0, branch="master", revision="deadbeef",
            when_timestamp=266738400, revlink=None, category=None,
            repository='', codebase='', project=''),

        fakedb.ChangeFile(changeid=13, filename='master/README.txt'),
        fakedb.ChangeFile(changeid=13, filename='slave/README.txt'),

        fakedb.ChangeProperty(changeid=13, property_name='notest',
            property_value='["no","Change"]'),
    ]

    change14_rows = [
        fakedb.Change(changeid=14, author="warner", comments="fix whitespace",
            is_dir=0, branch="warnerdb", revision="0e92a098b",
            when_timestamp=266738404, revlink='http://warner/0e92a098b',
            category='devel', repository='git://warner', codebase='mainapp', 
            project='Buildbot'),

        fakedb.ChangeFile(changeid=14, filename='master/buildbot/__init__.py'),
    ]

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['changes', 'change_files',
                'change_properties', 'scheduler_changes', 'objects',
                'sourcestampsets', 'sourcestamps', 'sourcestamp_changes',
                'patches', 'change_users', 'users'])

        def finish_setup(_):
            self.db.changes = changes.ChangesConnectorComponent(self.db)
        d.addCallback(finish_setup)

        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()

    def test_pruneChanges(self):
        d = self.insertTestData([
            fakedb.Object(id=29),
            fakedb.SourceStamp(id=234),

            fakedb.Change(changeid=11),

            fakedb.Change(changeid=12),
            fakedb.SchedulerChange(objectid=29, changeid=12),
            fakedb.SourceStampChange(sourcestampid=234, changeid=12),
            ] +

            self.change13_rows + [
            fakedb.SchedulerChange(objectid=29, changeid=13),
            ] +

            self.change14_rows + [
            fakedb.SchedulerChange(objectid=29, changeid=14),

            fakedb.Change(changeid=15),
            fakedb.SourceStampChange(sourcestampid=234, changeid=15),
            ]
        )

        # pruning with a horizon of 2 should delete changes 11, 12 and 13
        d.addCallback(lambda _ : self.db.changes.pruneChanges(2))
        def check(_):
            def thd(conn):
                results = {}
                for tbl_name in ('scheduler_changes', 'sourcestamp_changes',
                                 'change_files', 'change_properties',
                                 'changes'):
                    tbl = self.db.model.metadata.tables[tbl_name]
                    r = conn.execute(sa.select([tbl.c.changeid]))
                    results[tbl_name] = sorted([ r[0] for r in r.fetchall() ])
                self.assertEqual(results, {
                    'scheduler_changes': [14],
                    'sourcestamp_changes': [15],
                    'change_files': [14],
                    'change_properties': [],
                    'changes': [14, 15],
                })
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_pruneChanges_lots(self):
        d = self.insertTestData([
            fakedb.Change(changeid=n)
            for n in xrange(1, 151)
        ])

        d.addCallback(lambda _ : self.db.changes.pruneChanges(1))
        def check(_):
            def thd(conn):
                results = {}
                for tbl_name in ('scheduler_changes', 'sourcestamp_changes',
                                 'change_files', 'change_properties',
                                 'changes'):
                    tbl = self.db.model.metadata.tables[tbl_name]
                    r = conn.execute(sa.select([tbl.c.changeid]))
                    results[tbl_name] = len([ r for r in r.fetchall() ])
                self.assertEqual(results, {
                    'scheduler_changes': 0,
                    'sourcestamp_changes': 0,
                    'change_files': 0,
                    'change_properties': 0,
                    'changes': 1,
                })
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_pruneChanges_None(self):
        d = self.insertTestData(self.change13_rows)

        d.addCallback(lambda _ : self.db.changes.pruneChanges(None))
        def check(_):
            def thd(conn):
                tbl = self.db.model.changes
                r = conn.execute(tbl.select())
                self.assertEqual([ row.changeid for row in r.fetchall() ],
                                 [ 13 ])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

