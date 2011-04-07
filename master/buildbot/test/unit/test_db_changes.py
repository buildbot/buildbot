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

import pprint
import sqlalchemy as sa
from twisted.trial import unittest
from twisted.internet import defer
from buildbot.changes.changes import Change
from buildbot.db import changes
from buildbot.test.util import connector_component
from buildbot.test.fake import fakedb

class TestChangesConnectorComponent(
            connector_component.ConnectorComponentMixin,
            unittest.TestCase):

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['changes', 'change_links', 'change_files',
                'change_properties', 'scheduler_changes', 'schedulers',
                'sourcestamps', 'sourcestamp_changes', 'patches' ])

        def finish_setup(_):
            self.db.changes = changes.ChangesConnectorComponent(self.db)
        d.addCallback(finish_setup)

        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()

    # common sample data

    change13_rows = [
        fakedb.Change(changeid=13, author="dustin", comments="fix spelling",
            is_dir=0, branch="master", revision="deadbeef",
            when_timestamp=266738400, revlink=None, category=None,
            repository='', project=''),

        fakedb.ChangeLink(changeid=13, link='http://buildbot.net'),
        fakedb.ChangeLink(changeid=13, link='http://sf.net/projects/buildbot'),

        fakedb.ChangeFile(changeid=13, filename='master/README.txt'),
        fakedb.ChangeFile(changeid=13, filename='slave/README.txt'),

        fakedb.ChangeProperty(changeid=13, property_name='notest',
            property_value='"no"'),
    ]

    def change13(self):
        c = Change(**dict(
         category=None,
         isdir=0,
         repository=u'',
         links=[u'http://buildbot.net', u'http://sf.net/projects/buildbot'],
         who=u'dustin',
         when=266738400,
         comments=u'fix spelling',
         project=u'',
         branch=u'master',
         revlink=None,
         properties={u'notest': u'no'},
         files=[u'master/README.txt', u'slave/README.txt'],
         revision=u'deadbeef'))
        c.number = 13
        return c

    change14_rows = [
        fakedb.Change(changeid=14, author="warner", comments="fix whitespace",
            is_dir=0, branch="warnerdb", revision="0e92a098b",
            when_timestamp=266738404, revlink='http://warner/0e92a098b',
            category='devel', repository='git://warner', project='Buildbot'),

        fakedb.ChangeFile(changeid=14, filename='master/buildbot/__init__.py'),
    ]

    def change14(self):
        c = Change(**dict(
         category='devel',
         isdir=0,
         repository=u'git://warner',
         links=[],
         who=u'warner',
         when=266738404,
         comments=u'fix whitespace',
         project=u'Buildbot',
         branch=u'warnerdb',
         revlink=u'http://warner/0e92a098b',
         properties={},
         files=[u'master/buildbot/__init__.py'],
         revision=u'0e92a098b'))
        c.number = 14
        return c

    # assertions

    def assertChangesEqual(self, a, b):
        if len(a) != len(b):
            ok = False
        else:
            ok = True
            for i in xrange(len(a)):
                ca = a[i]
                cb = b[i]
                ok = ok and ca.number == cb.number
                ok = ok and ca.who == cb.who
                ok = ok and sorted(ca.files) == sorted(cb.files)
                ok = ok and ca.comments == cb.comments
                ok = ok and bool(ca.isdir) == bool(cb.isdir)
                ok = ok and sorted(ca.links) == sorted(cb.links)
                ok = ok and ca.revision == cb.revision
                ok = ok and ca.when == cb.when
                ok = ok and ca.branch == cb.branch
                ok = ok and ca.category == cb.category
                ok = ok and ca.revlink == cb.revlink
                ok = ok and ca.properties == cb.properties
                ok = ok and ca.repository == cb.repository
                ok = ok and ca.project == cb.project
                if not ok: break
        if not ok:
            def printable(clist):
                return pprint.pformat([ c.__dict__ for c in clist ])
            self.fail("changes do not match; expected\n%s\ngot\n%s" %
                        (printable(a), printable(b)))

    # tests

    def test_getChangeInstance(self):
        d = self.insertTestData(self.change14_rows)
        def get14(_):
            return self.db.changes.getChangeInstance(14)
        d.addCallback(get14)
        def check14(c):
            self.assertChangesEqual([ c ], [ self.change14() ])
        d.addCallback(check14)
        return d

    def test_getChangeInstance_missing(self):
        d = defer.succeed(None)
        def get14(_):
            return self.db.changes.getChangeInstance(14)
        d.addCallback(get14)
        def check14(c):
            self.failUnless(c is None)
        d.addCallback(check14)
        return d

    def test_getLatestChangeid(self):
        d = self.insertTestData(self.change13_rows)
        def get(_):
            return self.db.changes.getLatestChangeid()
        d.addCallback(get)
        def check(changeid):
            self.assertEqual(changeid, 13)
        d.addCallback(check)
        return d

    def test_getLatestChangeid_empty(self):
        d = defer.succeed(None)
        def get(_):
            return self.db.changes.getLatestChangeid()
        d.addCallback(get)
        def check(changeid):
            self.assertEqual(changeid, None)
        d.addCallback(check)
        return d

    def test_addChange(self):
        d = self.db.changes.addChange(
                 who=u'dustin',
                 files=[u'master/LICENSING.txt', u'slave/LICENSING.txt'],
                 comments=u'fix spelling',
                 isdir=0,
                 links=[u'http://slashdot.org', u'http://wired.com/g'],
                 revision=u'2d6caa52ab39fbac83cee03dcf2ccb7e41eaad86',
                 when=266738400,
                 branch=u'master',
                 category=None,
                 revlink=None,
                 properties={u'platform': u'linux'},
                 repository=u'',
                 project=u'')
        # check all of the columns of the four relevant tables
        def check_change(change):
            self.assertEqual(change.number, 1)
            self.assertEqual(change.who, 'dustin')
            self.assertEqual(sorted(change.files),
                 sorted([u'master/LICENSING.txt', u'slave/LICENSING.txt']))
            self.assertEqual(change.comments, 'fix spelling')
            self.assertFalse(change.isdir)
            self.assertEqual(sorted(change.links),
                 sorted([u'http://slashdot.org', u'http://wired.com/g']))
            self.assertEqual(change.revision, '2d6caa52ab39fbac83cee03dcf2ccb7e41eaad86')
            self.assertEqual(change.when, 266738400)
            self.assertEqual(change.category, None)
            self.assertEqual(change.revlink, None)
            self.assertEqual(change.properties.asList(),
                 [('platform', 'linux', 'Change')])
            self.assertEqual(change.repository, '')
            self.assertEqual(change.project, '')
            def thd(conn):
                r = conn.execute(self.db.model.changes.select())
                r = r.fetchall()
                self.assertEqual(len(r), 1)
                self.assertEqual(r[0].changeid, 1)
                self.assertEqual(r[0].author, 'dustin')
                self.assertEqual(r[0].comments, 'fix spelling')
                self.assertFalse(r[0].is_dir)
                self.assertEqual(r[0].branch, 'master')
                self.assertEqual(r[0].revision, '2d6caa52ab39fbac83cee03dcf2ccb7e41eaad86')
                self.assertEqual(r[0].when_timestamp, 266738400)
                self.assertEqual(r[0].category, None)
                self.assertEqual(r[0].repository, '')
                self.assertEqual(r[0].project, '')
            return self.db.pool.do(thd)
        d.addCallback(check_change)
        def check_change_links(_):
            def thd(conn):
                query = self.db.model.change_links.select()
                query.where(self.db.model.change_links.c.changeid == 1)
                query.order_by([self.db.model.change_links.c.link])
                r = conn.execute(query)
                r = r.fetchall()
                self.assertEqual(len(r), 2)
                self.assertEqual(r[0].link, 'http://slashdot.org')
                self.assertEqual(r[1].link, 'http://wired.com/g')
            return self.db.pool.do(thd)
        d.addCallback(check_change_links)
        def check_change_files(_):
            def thd(conn):
                query = self.db.model.change_files.select()
                query.where(self.db.model.change_files.c.changeid == 1)
                query.order_by([self.db.model.change_files.c.filename])
                r = conn.execute(query)
                r = r.fetchall()
                self.assertEqual(len(r), 2)
                self.assertEqual(r[0].filename, 'master/LICENSING.txt')
                self.assertEqual(r[1].filename, 'slave/LICENSING.txt')
            return self.db.pool.do(thd)
        d.addCallback(check_change_files)
        def check_change_properties(_):
            def thd(conn):
                query = self.db.model.change_properties.select()
                query.where(self.db.model.change_properties.c.changeid == 1)
                query.order_by([self.db.model.change_properties.c.property_name])
                r = conn.execute(query)
                r = r.fetchall()
                self.assertEqual(len(r), 1)
                self.assertEqual(r[0].property_name, 'platform')
                self.assertEqual(r[0].property_value, '"linux"') # JSON-encoded
            return self.db.pool.do(thd)
        d.addCallback(check_change_properties)
        return d

    def test_pruneChanges(self):
        d = self.insertTestData([
            fakedb.Scheduler(schedulerid=29),
            fakedb.SourceStamp(id=234),

            fakedb.Change(changeid=11),

            fakedb.Change(changeid=12),
            fakedb.SchedulerChange(schedulerid=29, changeid=12),
            fakedb.SourceStampChange(sourcestampid=234, changeid=12),
            ] +

            self.change13_rows + [
            fakedb.SchedulerChange(schedulerid=29, changeid=13),
            ] +

            self.change14_rows + [
            fakedb.SchedulerChange(schedulerid=29, changeid=14),

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
                                 'change_files', 'change_links',
                                 'change_properties', 'changes'):
                    tbl = self.db.model.metadata.tables[tbl_name]
                    r = conn.execute(sa.select([tbl.c.changeid]))
                    results[tbl_name] = sorted([ r[0] for r in r.fetchall() ])
                self.assertEqual(results, {
                    'scheduler_changes': [14],
                    'sourcestamp_changes': [15],
                    'change_files': [14],
                    'change_links': [],
                    'change_properties': [],
                    'changes': [14, 15],
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

    def test_getRecentChangeInstances_subset(self):
        d = self.insertTestData([
            fakedb.Change(changeid=8),
            fakedb.Change(changeid=9),
            fakedb.Change(changeid=10),
            fakedb.Change(changeid=11),
            fakedb.Change(changeid=12),
        ] + self.change13_rows + self.change14_rows)
        d.addCallback(lambda _ :
                self.db.changes.getRecentChangeInstances(5))
        def check(changes):
            changeids = [ c.number for c in changes ]
            self.assertEqual(changeids, [10, 11, 12, 13, 14])
        d.addCallback(check)
        return d

    def test_getRecentChangeInstances_empty(self):
        d = defer.succeed(None)
        d.addCallback(lambda _ :
                self.db.changes.getRecentChangeInstances(5))
        def check(changes):
            changeids = [ c.number for c in changes ]
            self.assertEqual(changeids, [])
        d.addCallback(check)
        return d

    def test_getRecentChangeInstances_missing(self):
        d = self.insertTestData(self.change13_rows + self.change14_rows)
        d.addCallback(lambda _ :
                self.db.changes.getRecentChangeInstances(5))
        def check(changes):
            # requested 5, but only got 2
            changeids = [ c.number for c in changes ]
            self.assertEqual(changeids, [13, 14])
            # double-check that they have .files, etc.
            self.assertEqual(sorted(changes[0].files),
                        sorted(['master/README.txt', 'slave/README.txt']))
            self.assertEqual(sorted(changes[0].links),
                        sorted(['http://buildbot.net',
                                'http://sf.net/projects/buildbot']))
            self.assertEqual(changes[0].properties.asList(),
                        [('notest', 'no', 'Change')])
        d.addCallback(check)
        return d
