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

from __future__ import absolute_import
from __future__ import print_function
from future.builtins import range
from future.utils import iteritems

import sqlalchemy as sa

from twisted.internet import defer
from twisted.internet import task
from twisted.trial import unittest

from buildbot.db import builds
from buildbot.db import changes
from buildbot.db import sourcestamps
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import connector_component
from buildbot.test.util import interfaces
from buildbot.test.util import validation
from buildbot.util import epoch2datetime

SOMETIME = 20398573
OTHERTIME = 937239287


class Tests(interfaces.InterfaceTests):

    # common sample data

    change13_rows = [
        fakedb.SourceStamp(id=92, branch="thirteen"),
        fakedb.Change(changeid=13, author="dustin", comments="fix spelling",
                      branch="master", revision="deadbeef",
                      when_timestamp=266738400, revlink=None, category=None,
                      repository='', codebase='', project='', sourcestampid=92),

        fakedb.ChangeFile(changeid=13, filename='master/README.txt'),
        fakedb.ChangeFile(changeid=13, filename='worker/README.txt'),

        fakedb.ChangeProperty(changeid=13, property_name='notest',
                              property_value='["no","Change"]'),
    ]

    change14_rows = [
        fakedb.SourceStamp(id=233, branch="fourteen"),
        fakedb.Change(changeid=14, author="warner", comments="fix whitespace",
                      branch="warnerdb", revision="0e92a098b",
                      when_timestamp=266738404, revlink='http://warner/0e92a098b',
                      category='devel', repository='git://warner', codebase='mainapp',
                      project='Buildbot', sourcestampid=233),

        fakedb.ChangeFile(changeid=14, filename='master/buildbot/__init__.py'),
    ]

    change14_dict = {
        'changeid': 14,
        'parent_changeids': [],
        'author': u'warner',
        'branch': u'warnerdb',
        'category': u'devel',
        'comments': u'fix whitespace',
        'files': [u'master/buildbot/__init__.py'],
        'project': u'Buildbot',
        'properties': {},
        'repository': u'git://warner',
        'codebase': u'mainapp',
        'revision': u'0e92a098b',
        'revlink': u'http://warner/0e92a098b',
        'when_timestamp': epoch2datetime(266738404),
        'sourcestampid': 233,
    }

    # tests

    def test_signature_addChange(self):
        @self.assertArgSpecMatches(self.db.changes.addChange)
        def addChange(self, author=None, files=None, comments=None, is_dir=None,
                      revision=None, when_timestamp=None, branch=None, category=None,
                      revlink='', properties=None, repository='', codebase='',
                      project='', uid=None):
            pass

    def test_signature_getChange(self):
        @self.assertArgSpecMatches(self.db.changes.getChange)
        def getChange(self, key, no_cache=False):
            pass

    @defer.inlineCallbacks
    def test_addChange_getChange(self):
        clock = task.Clock()
        clock.advance(SOMETIME)
        changeid = yield self.db.changes.addChange(
            author=u'dustin',
            files=[],
            comments=u'fix spelling',
            revision=u'2d6caa52',
            when_timestamp=epoch2datetime(OTHERTIME),
            branch=u'master',
            category=None,
            revlink=None,
            properties={},
            repository=u'repo://',
            codebase=u'cb',
            project=u'proj',
            _reactor=clock)
        chdict = yield self.db.changes.getChange(changeid)
        validation.verifyDbDict(self, 'chdict', chdict)
        chdict = chdict.copy()
        ss = yield self.db.sourcestamps.getSourceStamp(chdict['sourcestampid'])
        chdict['sourcestampid'] = ss
        self.assertEqual(chdict, {
            'author': u'dustin',
            'branch': u'master',
            'category': None,
            'changeid': changeid,
            'parent_changeids': [],
            'codebase': u'cb',
            'comments': u'fix spelling',
            'files': [],
            'project': u'proj',
            'properties': {},
            'repository': u'repo://',
            'revision': u'2d6caa52',
            'revlink': None,
            'sourcestampid': {
                'branch': u'master',
                'codebase': u'cb',
                'patch_author': None,
                'patch_body': None,
                'patch_comment': None,
                'patch_level': None,
                'patch_subdir': None,
                'patchid': None,
                'project': u'proj',
                'repository': u'repo://',
                'revision': u'2d6caa52',
                'created_at': epoch2datetime(SOMETIME),
                'ssid': ss['ssid'],
            },
            'when_timestamp': epoch2datetime(OTHERTIME),
        })

    @defer.inlineCallbacks
    def test_addChange_withParent(self):
        yield self.insertTestData(self.change14_rows)

        clock = task.Clock()
        clock.advance(SOMETIME)
        changeid = yield self.db.changes.addChange(
            author=u'delanne',
            files=[],
            comments=u'child of changeid14',
            revision=u'50adad56',
            when_timestamp=epoch2datetime(OTHERTIME),
            branch=u'warnerdb',
            category=u'devel',
            revlink=None,
            properties={},
            repository=u'git://warner',
            codebase=u'mainapp',
            project=u'Buildbot',
            _reactor=clock)
        chdict = yield self.db.changes.getChange(changeid)
        validation.verifyDbDict(self, 'chdict', chdict)
        chdict = chdict.copy()
        ss = yield self.db.sourcestamps.getSourceStamp(chdict['sourcestampid'])
        chdict['sourcestampid'] = ss
        self.assertEqual(chdict, {
            'author': u'delanne',
            'branch': u'warnerdb',
            'category': u'devel',
            'changeid': changeid,
            'parent_changeids': [14],
            'codebase': u'mainapp',
            'comments': u'child of changeid14',
            'files': [],
            'project': u'Buildbot',
            'properties': {},
            'repository': u'git://warner',
            'revision': u'50adad56',
            'revlink': None,
            'sourcestampid': {
                'branch': u'warnerdb',
                'codebase': u'mainapp',
                'created_at': epoch2datetime(SOMETIME),
                'patch_author': None,
                'patch_body': None,
                'patch_comment': None,
                'patch_level': None,
                'patch_subdir': None,
                'patchid': None,
                'project': u'Buildbot',
                'repository': u'git://warner',
                'revision': u'50adad56',
                'ssid': ss['ssid']
            },
            'when_timestamp': epoch2datetime(OTHERTIME),
        })

    def test_getChange_chdict(self):
        d = self.insertTestData(self.change14_rows)

        def get14(_):
            return self.db.changes.getChange(14)
        d.addCallback(get14)

        def check14(chdict):
            validation.verifyDbDict(self, 'chdict', chdict)
            self.assertEqual(chdict, self.change14_dict)
        d.addCallback(check14)
        return d

    def test_getChange_missing(self):
        d = defer.succeed(None)

        def get14(_):
            return self.db.changes.getChange(14)
        d.addCallback(get14)

        def check14(chdict):
            self.assertTrue(chdict is None)
        d.addCallback(check14)
        return d

    def test_signature_getChangeUids(self):
        @self.assertArgSpecMatches(self.db.changes.getChangeUids)
        def getChangeUids(self, changeid):
            pass

    def test_getChangeUids_missing(self):
        d = self.db.changes.getChangeUids(1)

        def check(res):
            self.assertEqual(res, [])
        d.addCallback(check)
        return d

    def test_getChangeUids_found(self):
        d = self.insertTestData(self.change14_rows + [
            fakedb.SourceStamp(id=92),
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

    def test_signature_getRecentChanges(self):
        @self.assertArgSpecMatches(self.db.changes.getRecentChanges)
        def getRecentChanges(self, count):
            pass

    def test_signature_getChanges(self):
        @self.assertArgSpecMatches(self.db.changes.getChanges)
        def getChanges(self):
            pass

    def insert7Changes(self):
        return self.insertTestData([
            fakedb.SourceStamp(id=922),
            fakedb.Change(changeid=8, sourcestampid=922),
            fakedb.Change(changeid=9, sourcestampid=922),
            fakedb.Change(changeid=10, sourcestampid=922),
            fakedb.Change(changeid=11, sourcestampid=922),
            fakedb.Change(changeid=12, sourcestampid=922),
        ] + self.change13_rows + self.change14_rows)

    def test_getRecentChanges_subset(self):
        d = self.insert7Changes()
        d.addCallback(lambda _:
                      self.db.changes.getRecentChanges(5))

        def check(changes):
            changeids = [c['changeid'] for c in changes]
            self.assertEqual(changeids, [10, 11, 12, 13, 14])
        d.addCallback(check)
        return d

    def test_getChangesCount(self):
        d = self.insert7Changes()
        d.addCallback(lambda _:
                      self.db.changes.getChangesCount())

        def check(n):
            self.assertEqual(n, 7)
        d.addCallback(check)
        return d

    def test_getChangesHugeCount(self):
        d = self.insertTestData([
            fakedb.SourceStamp(id=92),
        ] + [
            fakedb.Change(changeid=i) for i in range(2, 102)])
        d.addCallback(lambda _:
                      self.db.changes.getChangesCount())

        def check(n):
            self.assertEqual(n, 100)
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
        d.addCallback(lambda _:
                      self.db.changes.getChanges())
        d.addCallback(check)
        return d

    def test_getRecentChanges_missing(self):
        d = self.insertTestData(self.change13_rows + self.change14_rows)
        d.addCallback(lambda _:
                      self.db.changes.getRecentChanges(5))

        def check(changes):
            # requested all, but only got 2
            # sort by changeid, since we assert on change 13 at index 0
            changes.sort(key=lambda c: c['changeid'])
            changeids = [c['changeid'] for c in changes]
            self.assertEqual(changeids, [13, 14])
            # double-check that they have .files, etc.
            self.assertEqual(sorted(changes[0]['files']),
                             sorted(['master/README.txt', 'worker/README.txt']))
            self.assertEqual(changes[0]['properties'],
                             {'notest': ('no', 'Change')})
        d.addCallback(check)
        d.addCallback(lambda _:
                      self.db.changes.getChanges())
        d.addCallback(check)
        return d

    def test_signature_getLatestChangeid(self):
        @self.assertArgSpecMatches(self.db.changes.getLatestChangeid)
        def getLatestChangeid(self):
            pass

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

    def test_signature_getParentChangeIds(self):
        @self.assertArgSpecMatches(self.db.changes.getParentChangeIds)
        def getParentChangeIds(self, branch, repository, project, codebase):
            pass

    def test_getParentChangeIds(self):
        d = self.insertTestData(self.change14_rows + self.change13_rows)

        def getParent(_):
            return self.db.changes.getParentChangeIds(branch='warnerdb',
                                                      repository='git://warner',
                                                      project='Buildbot',
                                                      codebase='mainapp')
        d.addCallback(getParent)

        def check(changeid):
            self.assertEqual(changeid, [14])
        d.addCallback(check)
        return d


class RealTests(Tests):

    # tests that only "real" implementations will pass

    def test_addChange(self):
        clock = task.Clock()
        clock.advance(SOMETIME)
        d = self.db.changes.addChange(
            author=u'dustin',
            files=[u'master/LICENSING.txt', u'worker/LICENSING.txt'],
            comments=u'fix spelling',
            revision=u'2d6caa52',
            when_timestamp=epoch2datetime(266738400),
            branch=u'master',
            category=None,
            revlink=None,
            properties={u'platform': (u'linux', 'Change')},
            repository=u'',
            codebase=u'cb',
            project=u'',
            _reactor=clock)
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
                self.assertEqual(r[0].branch, 'master')
                self.assertEqual(r[0].revision, '2d6caa52')
                self.assertEqual(r[0].when_timestamp, 266738400)
                self.assertEqual(r[0].category, None)
                self.assertEqual(r[0].repository, '')
                self.assertEqual(r[0].codebase, u'cb')
                self.assertEqual(r[0].project, '')
                self.assertEqual(r[0].sourcestampid, 1)
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
                self.assertEqual(r[1].filename, 'worker/LICENSING.txt')
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

        def check_change_sourcestamps(_):
            def thd(conn):
                query = self.db.model.sourcestamps.select()
                r = conn.execute(query)
                self.assertEqual([dict(row) for row in r.fetchall()], [{
                    'branch': u'master',
                    'codebase': u'cb',
                    'id': 1,
                    'patchid': None,
                    'project': u'',
                    'repository': u'',
                    'revision': u'2d6caa52',
                    'created_at': SOMETIME,
                    'ss_hash': 'b777dbd10d1d4c76651335f6a78e278e88b010d6',
                }])
            return self.db.pool.do(thd)
        d.addCallback(check_change_sourcestamps)
        return d

    def test_addChange_when_timestamp_None(self):
        clock = task.Clock()
        clock.advance(OTHERTIME)
        d = self.db.changes.addChange(
            author=u'dustin',
            files=[],
            comments=u'fix spelling',
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
                self.assertEqual(r[0].when_timestamp, OTHERTIME)
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
                          revision=u'2d6caa52',
                          when_timestamp=epoch2datetime(OTHERTIME),
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
                self.assertEqual(r[0].when_timestamp, OTHERTIME)
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

    def test_pruneChanges(self):
        d = self.insertTestData([
            fakedb.Scheduler(id=29),
            fakedb.SourceStamp(id=234, branch='aa'),
            fakedb.SourceStamp(id=235, branch='bb'),
            fakedb.Change(changeid=11),
            fakedb.Change(changeid=12, sourcestampid=234),
            fakedb.SchedulerChange(schedulerid=29, changeid=12),
        ] + self.change13_rows + [
            fakedb.SchedulerChange(schedulerid=29, changeid=13),
        ] + self.change14_rows + [
            fakedb.SchedulerChange(schedulerid=29, changeid=14),
            fakedb.Change(changeid=15, sourcestampid=235),
        ]
        )

        # pruning with a horizon of 2 should delete changes 11, 12 and 13
        d.addCallback(lambda _: self.db.changes.pruneChanges(2))

        def check(_):
            def thd(conn):
                results = {}
                for tbl_name in ('scheduler_changes', 'change_files',
                                 'change_properties', 'changes'):
                    tbl = self.db.model.metadata.tables[tbl_name]
                    res = conn.execute(sa.select([tbl.c.changeid]))
                    results[tbl_name] = sorted(
                        [row[0] for row in res.fetchall()])
                self.assertEqual(results, {
                    'scheduler_changes': [14],
                    'change_files': [14],
                    'change_properties': [],
                    'changes': [14, 15],
                })
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_pruneChanges_lots(self):
        d = self.insertTestData([
            fakedb.SourceStamp(id=29),
        ] + [
            fakedb.Change(changeid=n, sourcestampid=29)
            for n in range(1, 151)
        ])

        d.addCallback(lambda _: self.db.changes.pruneChanges(1))

        def check(_):
            def thd(conn):
                results = {}
                for tbl_name in ('scheduler_changes', 'change_files',
                                 'change_properties', 'changes'):
                    tbl = self.db.model.metadata.tables[tbl_name]
                    res = conn.execute(sa.select([tbl.c.changeid]))
                    results[tbl_name] = len([row for row in res.fetchall()])
                self.assertEqual(results, {
                    'scheduler_changes': 0,
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

    @defer.inlineCallbacks
    def test_getChangesForBuild(self):
        rows = [fakedb.Master(id=88, name="bar"),
                fakedb.Worker(id=13, name='one'),
                fakedb.Builder(id=77, name='A')]
        lastID = {"changeid": 0,
                  "sourcestampid": 0,
                  "buildsetid": 0,
                  "buildsetSourceStampid": 0,
                  "buildrequestid": 0,
                  "buildid": 0}

        codebase_ss = {}  # shared state between addChange and addBuild

        def addChange(codebase, revision, author, comments, branch='master', category='cat', project='proj', repository='repo'):
            lastID["sourcestampid"] += 1
            lastID["changeid"] += 1
            parent_changeids = codebase_ss.get(codebase, None)

            codebase_ss[codebase] = lastID["sourcestampid"]

            changeRows = [fakedb.SourceStamp(id=lastID["sourcestampid"],
                                             codebase=codebase,
                                             revision=revision),
                          fakedb.Change(changeid=lastID["changeid"],
                                        author=author,
                                        comments=comments,
                                        revision=revision,
                                        sourcestampid=lastID["sourcestampid"],
                                        parent_changeids=parent_changeids,
                                        when_timestamp=SOMETIME +
                                        lastID["changeid"],
                                        branch=branch,
                                        category=category,
                                        project=project,
                                        repository=repository)]
            return changeRows

        def addBuild(codebase_ss, results=0):

            lastID["buildid"] += 1
            lastID["buildsetid"] += 1
            lastID["buildrequestid"] += 1

            buildRows = [fakedb.Buildset(id=lastID["buildsetid"],
                                         reason='foo',
                                         submitted_at=1300305012, results=-1)]
            for cb, ss in iteritems(codebase_ss):
                lastID["buildsetSourceStampid"] += 1
                buildRows.append(
                    fakedb.BuildsetSourceStamp(id=lastID["buildsetSourceStampid"],
                                               sourcestampid=ss,
                                               buildsetid=lastID["buildsetid"]))
            codebase_ss.clear()
            buildRows.extend([
                fakedb.BuildRequest(id=lastID["buildrequestid"],
                                    buildsetid=lastID["buildsetid"],
                                    builderid=77,
                                    priority=13, submitted_at=1300305712, results=-1),
                fakedb.Build(id=lastID["buildid"],
                             buildrequestid=lastID["buildrequestid"],
                             number=lastID["buildid"],
                             masterid=88,
                             builderid=77,
                             state_string="test",
                             workerid=13,
                             started_at=SOMETIME + lastID["buildid"],
                             complete_at=SOMETIME + 2 * lastID["buildid"],
                             results=results)])
            return buildRows

        # Build1 has 1 change per code base
        rows.extend(addChange('A', 1, 'franck', '1st commit'))
        rows.extend(addChange('B', 1, 'alice', '2nd commit'))
        rows.extend(addChange('C', 1, 'bob', '3rd commit'))
        rows.extend(addBuild(codebase_ss))
        # Build 2 has only one change for codebase A
        rows.extend(addChange('A', 2, 'delanne', '4th commit'))
        rows.extend(addBuild(codebase_ss))
        # Build 3 has only one change for codebase B
        rows.extend(addChange('B', 2, 'bob', '6th commit'))
        rows.extend(addBuild(codebase_ss))
        # Build 4 has no change
        rows.extend(addBuild(codebase_ss))
        # Build 5 has 2 changes for codebase A and 1 change for codebase C
        rows.extend(addChange('A', 3, 'franck', '7th commit'))
        rows.extend(addChange('A', 4, 'alice', '8th commit'))
        rows.extend(addChange('B', 3, 'bob', '9th commit'))
        rows.extend(addBuild(codebase_ss))
        # Build 6 has only one change for codebase C
        rows.extend(addChange('C', 2, 'bob', '10th commit'))
        rows.extend(addBuild(codebase_ss, 2))
        # Build 7 has only one change for codebase C
        rows.extend(addChange('C', 3, 'bob', '11th commit'))
        rows.extend(addBuild(codebase_ss, 2))
        yield self.insertTestData(rows)

        @defer.inlineCallbacks
        def expect(buildid, commits):
            got = yield self.db.changes.getChangesForBuild(buildid)
            got_commits = [c['comments'] for c in got]
            self.assertEqual(sorted(got_commits), sorted(commits))

        yield expect(1, [u'2nd commit', u'3rd commit', u'1st commit'])
        yield expect(2, [u'4th commit'])
        yield expect(3, [u'6th commit'])
        yield expect(4, [])
        yield expect(5, [u'8th commit', u'9th commit', u'7th commit'])
        yield expect(6, [u'10th commit'])
        yield expect(7, [u'11th commit'])


class TestFakeDB(unittest.TestCase, Tests):

    def setUp(self):
        self.master = fakemaster.make_master(wantDb=True, testcase=self)
        self.db = self.master.db
        self.db.checkForeignKeys = True
        self.insertTestData = self.db.insertTestData


class TestRealDB(unittest.TestCase,
                 connector_component.ConnectorComponentMixin,
                 RealTests):

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['changes', 'change_files',
                         'change_properties', 'scheduler_changes', 'schedulers',
                         'sourcestampsets', 'sourcestamps', 'patches', 'change_users',
                         'users', 'buildsets', 'workers', 'builders', 'masters',
                         'buildrequests', 'builds', 'buildset_sourcestamps',
                         'workers'])

        @d.addCallback
        def finish_setup(_):
            self.db.changes = changes.ChangesConnectorComponent(self.db)
            self.db.builds = builds.BuildsConnectorComponent(self.db)
            self.db.sourcestamps = \
                sourcestamps.SourceStampsConnectorComponent(self.db)
            self.master = self.db.master
            self.master.db = self.db

        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()
