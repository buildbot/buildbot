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

import mock
import pprint
import sqlalchemy as sa

from buildbot.changes.changes import Change
from buildbot.db import changes
from buildbot.test.fake import fakedb
from buildbot.test.util import connector_component
from buildbot.util import epoch2datetime
from twisted.internet import defer
from twisted.internet import task
from twisted.trial import unittest


class TestChangesConnectorComponent(
    connector_component.ConnectorComponentMixin,
        unittest.TestCase):

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

    # common sample data

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

    change14_dict = {
        'changeid': 14,
        'author': u'warner',
        'branch': u'warnerdb',
        'category': u'devel',
        'comments': u'fix whitespace',
        'files': [u'master/buildbot/__init__.py'],
        'is_dir': 0,
        'project': u'Buildbot',
        'properties': {},
        'repository': u'git://warner',
        'codebase': u'mainapp',
        'revision': u'0e92a098b',
        'revlink': u'http://warner/0e92a098b',
        'when_timestamp': epoch2datetime(266738404),
    }

    def change14(self):
        c = Change(**dict(
            category='devel',
            isdir=0,
            repository=u'git://warner',
            codebase=u'mainapp',
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

    def assertChangesEqual(self, ca, cb):
        ok = True
        ok = ok and ca.number == cb.number
        ok = ok and ca.who == cb.who
        ok = ok and sorted(ca.files) == sorted(cb.files)
        ok = ok and ca.comments == cb.comments
        ok = ok and bool(ca.isdir) == bool(cb.isdir)
        ok = ok and ca.revision == cb.revision
        ok = ok and ca.when == cb.when
        ok = ok and ca.branch == cb.branch
        ok = ok and ca.category == cb.category
        ok = ok and ca.revlink == cb.revlink
        ok = ok and ca.properties == cb.properties
        ok = ok and ca.repository == cb.repository
        ok = ok and ca.codebase == cb.codebase
        ok = ok and ca.project == cb.project
        if not ok:
            def printable(c):
                return pprint.pformat(c.__dict__)
            self.fail("changes do not match; expected\n%s\ngot\n%s" %
                      (printable(ca), printable(cb)))

    # tests

    def test_getChange(self):
        d = self.insertTestData(self.change14_rows)

        def get14(_):
            return self.db.changes.getChange(14)
        d.addCallback(get14)

        def check14(chdict):
            self.assertEqual(chdict, self.change14_dict)
        d.addCallback(check14)
        return d

    def test_Change_fromChdict_with_chdict(self):
        # test that the chdict getChange returns works with Change.fromChdict
        d = Change.fromChdict(mock.Mock(), self.change14_dict)

        def check(c):
            self.assertChangesEqual(c, self.change14())
        d.addCallback(check)
        return d

    def test_getChange_missing(self):
        d = defer.succeed(None)

        def get14(_):
            return self.db.changes.getChange(14)
        d.addCallback(get14)

        def check14(chdict):
            self.failUnless(chdict is None)
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
            author=u'dustin',
            files=[u'master/LICENSING.txt', u'slave/LICENSING.txt'],
            comments=u'fix spelling',
            is_dir=0,
            revision=u'2d6caa52',
            when_timestamp=epoch2datetime(266738400),
            branch=u'master',
            category=None,
            revlink=None,
            properties={u'platform': (u'linux', 'Change')},
            repository=u'',
            codebase=u'',
            project=u'')
        # check all of the columns of the four relevant tables

        def check_change(changeid):
            def thd(conn):
                self.assertEqual(changeid, 1)
                r = conn.execute(self.db.model.changes.select())
                r = r.fetchall()
                self.assertEqual(len(r), 1)
                self.assertEqual(r[0].changeid, changeid)
                self.assertEqual(r[0].author, 'dustin')
                self.assertEqual(r[0].comments, 'fix spelling')
                self.assertFalse(r[0].is_dir)
                self.assertEqual(r[0].branch, 'master')
                self.assertEqual(r[0].revision, '2d6caa52')
                self.assertEqual(r[0].when_timestamp, 266738400)
                self.assertEqual(r[0].category, None)
                self.assertEqual(r[0].repository, '')
                self.assertEqual(r[0].codebase, '')
                self.assertEqual(r[0].project, '')
            return self.db.pool.do(thd)
        d.addCallback(check_change)

        def check_change_files(_):
            def thd(conn):
                query = self.db.model.change_files.select()
                query.where(self.db.model.change_files.c.changeid == 1)
                query.order_by(self.db.model.change_files.c.filename)
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
                query.order_by(self.db.model.change_properties.c.property_name)
                r = conn.execute(query)
                r = r.fetchall()
                self.assertEqual(len(r), 1)
                self.assertEqual(r[0].property_name, 'platform')
                self.assertEqual(r[0].property_value, '["linux", "Change"]')
            return self.db.pool.do(thd)
        d.addCallback(check_change_properties)

        def check_change_users(_):
            def thd(conn):
                query = self.db.model.change_users.select()
                r = conn.execute(query)
                r = r.fetchall()
                self.assertEqual(len(r), 0)
            return self.db.pool.do(thd)
        d.addCallback(check_change_users)
        return d

    def test_addChange_when_timestamp_None(self):
        clock = task.Clock()
        clock.advance(1239898353)
        d = self.db.changes.addChange(
            author=u'dustin',
            files=[],
            comments=u'fix spelling',
            is_dir=0,
            revision=u'2d6caa52',
            when_timestamp=None,
            branch=u'master',
            category=None,
            revlink=None,
            properties={},
            repository=u'',
            codebase=u'',
            project=u'',
            _reactor=clock)
        # check all of the columns of the four relevant tables

        def check_change(changeid):
            def thd(conn):
                r = conn.execute(self.db.model.changes.select())
                r = r.fetchall()
                self.assertEqual(len(r), 1)
                self.assertEqual(r[0].changeid, changeid)
                self.assertEqual(r[0].when_timestamp, 1239898353)
            return self.db.pool.do(thd)
        d.addCallback(check_change)

        def check_change_files(_):
            def thd(conn):
                query = self.db.model.change_files.select()
                r = conn.execute(query)
                r = r.fetchall()
                self.assertEqual(len(r), 0)
            return self.db.pool.do(thd)
        d.addCallback(check_change_files)

        def check_change_properties(_):
            def thd(conn):
                query = self.db.model.change_properties.select()
                r = conn.execute(query)
                r = r.fetchall()
                self.assertEqual(len(r), 0)
            return self.db.pool.do(thd)
        d.addCallback(check_change_properties)

        def check_change_users(_):
            def thd(conn):
                query = self.db.model.change_users.select()
                r = conn.execute(query)
                r = r.fetchall()
                self.assertEqual(len(r), 0)
            return self.db.pool.do(thd)
        d.addCallback(check_change_users)
        return d

    def test_addChange_with_uid(self):
        d = self.insertTestData([
            fakedb.User(uid=1, identifier="one"),
        ])
        d.addCallback(lambda _:
                      self.db.changes.addChange(
                          author=u'dustin',
                          files=[],
                          comments=u'fix spelling',
                          is_dir=0,
                          revision=u'2d6caa52',
                          when_timestamp=epoch2datetime(1239898353),
                          branch=u'master',
                          category=None,
                          revlink=None,
                          properties={},
                          repository=u'',
                          codebase=u'',
                          project=u'',
                          uid=1))
        # check all of the columns of the five relevant tables

        def check_change(changeid):
            def thd(conn):
                r = conn.execute(self.db.model.changes.select())
                r = r.fetchall()
                self.assertEqual(len(r), 1)
                self.assertEqual(r[0].changeid, changeid)
                self.assertEqual(r[0].when_timestamp, 1239898353)
            return self.db.pool.do(thd)
        d.addCallback(check_change)

        def check_change_files(_):
            def thd(conn):
                query = self.db.model.change_files.select()
                r = conn.execute(query)
                r = r.fetchall()
                self.assertEqual(len(r), 0)
            return self.db.pool.do(thd)
        d.addCallback(check_change_files)

        def check_change_properties(_):
            def thd(conn):
                query = self.db.model.change_properties.select()
                r = conn.execute(query)
                r = r.fetchall()
                self.assertEqual(len(r), 0)
            return self.db.pool.do(thd)
        d.addCallback(check_change_properties)

        def check_change_users(_):
            def thd(conn):
                query = self.db.model.change_users.select()
                r = conn.execute(query)
                r = r.fetchall()
                self.assertEqual(len(r), 1)
                self.assertEqual(r[0].changeid, 1)
                self.assertEqual(r[0].uid, 1)
            return self.db.pool.do(thd)
        d.addCallback(check_change_users)
        return d

    def test_getChangeUids_missing(self):
        d = self.db.changes.getChangeUids(1)

        def check(res):
            self.assertEqual(res, [])
        d.addCallback(check)
        return d

    def test_getChangeUids_found(self):
        d = self.insertTestData(self.change14_rows + [
            fakedb.User(uid=1),
            fakedb.ChangeUser(changeid=14, uid=1),
        ])
        d.addCallback(lambda _: self.db.changes.getChangeUids(14))

        def check(res):
            self.assertEqual(res, [1])
        d.addCallback(check)
        return d

    def test_getChangeUids_multi(self):
        d = self.insertTestData(self.change14_rows + self.change13_rows + [
            fakedb.User(uid=1, identifier="one"),
            fakedb.User(uid=2, identifier="two"),
            fakedb.User(uid=99, identifier="nooo"),
            fakedb.ChangeUser(changeid=14, uid=1),
            fakedb.ChangeUser(changeid=14, uid=2),
            fakedb.ChangeUser(changeid=13, uid=99),  # not selected
        ])
        d.addCallback(lambda _: self.db.changes.getChangeUids(14))

        def check(res):
            self.assertEqual(sorted(res), [1, 2])
        d.addCallback(check)
        return d

    def test_pruneChanges(self):
        d = self.insertTestData(
            [
                fakedb.Object(id=29),
                fakedb.SourceStamp(id=234),

                fakedb.Change(changeid=11),

                fakedb.Change(changeid=12),
                fakedb.SchedulerChange(objectid=29, changeid=12),
                fakedb.SourceStampChange(sourcestampid=234, changeid=12),
            ] +

            self.change13_rows +
            [
                fakedb.SchedulerChange(objectid=29, changeid=13),
            ] +

            self.change14_rows +
            [
                fakedb.SchedulerChange(objectid=29, changeid=14),

                fakedb.Change(changeid=15),
                fakedb.SourceStampChange(sourcestampid=234, changeid=15),
            ]
        )

        # pruning with a horizon of 2 should delete changes 11, 12 and 13
        d.addCallback(lambda _: self.db.changes.pruneChanges(2))

        def check(_):
            def thd(conn):
                results = {}
                for tbl_name in ('scheduler_changes', 'sourcestamp_changes',
                                 'change_files', 'change_properties',
                                 'changes'):
                    tbl = self.db.model.metadata.tables[tbl_name]
                    res = conn.execute(sa.select([tbl.c.changeid]))
                    results[tbl_name] = sorted([row[0] for row in res.fetchall()])
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

        d.addCallback(lambda _: self.db.changes.pruneChanges(1))

        def check(_):
            def thd(conn):
                results = {}
                for tbl_name in ('scheduler_changes', 'sourcestamp_changes',
                                 'change_files', 'change_properties',
                                 'changes'):
                    tbl = self.db.model.metadata.tables[tbl_name]
                    res = conn.execute(sa.select([tbl.c.changeid]))
                    results[tbl_name] = len([row for row in res.fetchall()])
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

        d.addCallback(lambda _: self.db.changes.pruneChanges(None))

        def check(_):
            def thd(conn):
                tbl = self.db.model.changes
                res = conn.execute(tbl.select())
                self.assertEqual([row.changeid for row in res.fetchall()],
                                 [13])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_getRecentChanges_subset(self):
        d = self.insertTestData([
            fakedb.Change(changeid=8),
            fakedb.Change(changeid=9),
            fakedb.Change(changeid=10),
            fakedb.Change(changeid=11),
            fakedb.Change(changeid=12),
        ] + self.change13_rows + self.change14_rows)
        d.addCallback(lambda _:
                      self.db.changes.getRecentChanges(5))

        def check(changes):
            changeids = [c['changeid'] for c in changes]
            self.assertEqual(changeids, [10, 11, 12, 13, 14])
        d.addCallback(check)
        return d

    def test_getRecentChanges_empty(self):
        d = defer.succeed(None)
        d.addCallback(lambda _:
                      self.db.changes.getRecentChanges(5))

        def check(changes):
            changeids = [c['changeid'] for c in changes]
            self.assertEqual(changeids, [])
        d.addCallback(check)
        return d

    def test_getRecentChanges_missing(self):
        d = self.insertTestData(self.change13_rows + self.change14_rows)
        d.addCallback(lambda _:
                      self.db.changes.getRecentChanges(5))

        def check(changes):
            # requested 5, but only got 2
            changeids = [c['changeid'] for c in changes]
            self.assertEqual(changeids, [13, 14])
            # double-check that they have .files, etc.
            self.assertEqual(sorted(changes[0]['files']),
                             sorted(['master/README.txt', 'slave/README.txt']))
            self.assertEqual(changes[0]['properties'],
                             {'notest': ('no', 'Change')})
        d.addCallback(check)
        return d
