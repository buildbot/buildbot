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
from buildbot.test.util import db, connector_component

class TestChangesConnectorComponent(
            connector_component.ConnectorComponentMixin,
            db.RealDatabaseMixin,
            unittest.TestCase):
    """
    Tests of C{master.db.changes}
    """

    def setUp(self):
        self.setUpRealDatabase()
        self.setUpConnectorComponent(self.db_url)

        # add the .changes attribute
        self.db.changes = changes.ChangesConnectorComponent(self.db)

        # set up the tables we'll need, following links where ForeignKey
        # constraints are in place.
        def thd(engine):
            self.db.model.changes.create(bind=engine)
            self.db.model.change_files.create(bind=engine)
            self.db.model.change_links.create(bind=engine)
            self.db.model.change_properties.create(bind=engine)
            self.db.model.schedulers.create(bind=engine)
            self.db.model.scheduler_changes.create(bind=engine)
            self.db.model.patches.create(bind=engine)
            self.db.model.sourcestamps.create(bind=engine)
            self.db.model.sourcestamp_changes.create(bind=engine)
        return self.db.pool.do_with_engine(thd)

    def tearDown(self):
        self.tearDownConnectorComponent()
        self.tearDownRealDatabase()

    # add stuff to the database; these are all meant to be used
    # as callbacks on a deferred

    def addChanges(self, _, *rows):
        def thd(conn):
            stmt = self.db.model.changes.insert()
            conn.execute(stmt, rows)
        return self.db.pool.do(thd)

    def addLink(self, _, *rows):
        def thd(conn):
            stmt = self.db.model.change_links.insert()
            conn.execute(stmt, rows)
        return self.db.pool.do(thd)

    def addFile(self, _, *rows):
        def thd(conn):
            stmt = self.db.model.change_files.insert()
            conn.execute(stmt, rows)
        return self.db.pool.do(thd)

    def addProperty(self, _, *rows):
        def thd(conn):
            stmt = self.db.model.change_properties.insert()
            conn.execute(stmt, rows)
        return self.db.pool.do(thd)

    # common sample data

    def addChange13(self, _):
        d = defer.succeed(None)
        d.addCallback(self.addChanges,
          dict(changeid=13, author="dustin", comments="fix spelling", is_dir=0,
               branch="master", revision="deadbeef", when_timestamp=266738400,
               category=None, repository='', project=''),
          )
        d.addCallback(self.addLink,
          dict(changeid=13, link='http://buildbot.net'))
        d.addCallback(self.addLink,
          dict(changeid=13, link='http://sf.net/projects/buildbot'))
        d.addCallback(self.addFile,
          dict(changeid=13, filename='master/README.txt'))
        d.addCallback(self.addFile,
          dict(changeid=13, filename='slave/README.txt'))
        d.addCallback(self.addProperty,
          dict(changeid=13, property_name='notest', property_value='"no"'))
        return d

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

    def addChange14(self, _):
        d = defer.succeed(None)
        d.addCallback(self.addChanges,
          dict(changeid=14, author="warner", comments="fix whitespace", is_dir=0,
               branch="warnerdb", revision="0e92a098b", when_timestamp=266738404,
               revlink='http://warner/0e92a098b',
               category='devel', repository='git://warner', project='Buildbot'),
          )
        d.addCallback(self.addFile,
          dict(changeid=14, filename='master/buildbot/__init__.py'))
        return d

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

    def test_changeEventGenerator(self):
        d = defer.succeed(None)
        d.addCallback(self.addChange13)
        d.addCallback(self.addChange14)
        # this demonstrates that we can leave the generator running between
        # deferred operations.  Note that we expect change 14 first, because it
        # is higher-numbered
        def check14(_):
            gen = self.db.changes.changeEventGenerator()
            ch14 = gen.next()
            self.assertChangesEqual([ ch14 ], [ self.change14() ])
            return gen
        d.addCallback(check14)
        def check13(gen):
            ch13 = gen.next()
            self.assertChangesEqual([ ch13 ], [ self.change13() ])
        d.addCallback(check13)
        return d

    def test_changeEventGenerator_params(self):
        d = defer.succeed(None)
        d.addCallback(self.addChange13)
        d.addCallback(self.addChange14)
        def check(_):
            gen = self.db.changes.changeEventGenerator(
                    branches=['master', 'warnerdb'],
                    committers=['dustin', 'warner'],
                    categories=['devel'], # only matches change14
                    minTime=1)
            changes = list(gen)
            self.assertChangesEqual(changes, [ self.change14() ])
            return gen
        d.addCallback(check)
        return d

    def test_changeEventGenerator_cancel(self):
        d = defer.succeed(None)
        d.addCallback(self.addChange13)
        d.addCallback(self.addChange14)
        # leave the generator hanging -- this should cancel the thread, although we
        # have no way to verify that.  If it doesn't, then the next test will hang
        # when testing against SQLite in-memory.
        def check(_):
            gen = self.db.changes.changeEventGenerator()
            gen.next()
        d.addCallback(check)
        return d

    def test_getChangeInstance(self):
        d = defer.succeed(None)
        d.addCallback(self.addChange14)
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
        d = defer.succeed(None)
        d.addCallback(self.addChange13)
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

    def test_prune_changes(self):
        self.db.changes.changeHorizon = 1
        d = defer.succeed(None)
        d.addCallback(self.addChange13)
        d.addCallback(self.addChange14)
        d.addCallback(lambda _ : self.db.changes._prune_changes(14))
        def check(_):
            def thd(conn):
                changes_tbl = self.db.model.changes
                r = conn.execute(sa.select([changes_tbl.c.changeid]))
                self.assertEqual([ r.changeid for r in r.fetchall() ], [ 14 ])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d
