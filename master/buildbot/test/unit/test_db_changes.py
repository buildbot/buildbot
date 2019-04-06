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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.db import builds
from buildbot.db import changes
from buildbot.db import sourcestamps
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import connector_component
from buildbot.test.util import interfaces
from buildbot.test.util import validation
from buildbot.test.util.misc import TestReactorMixin
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
        'author': 'warner',
        'branch': 'warnerdb',
        'category': 'devel',
        'comments': 'fix whitespace',
        'files': ['master/buildbot/__init__.py'],
        'project': 'Buildbot',
        'properties': {},
        'repository': 'git://warner',
        'codebase': 'mainapp',
        'revision': '0e92a098b',
        'revlink': 'http://warner/0e92a098b',
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
        self.reactor.advance(SOMETIME)
        changeid = yield self.db.changes.addChange(
            author='dustin',
            files=[],
            comments='fix spelling',
            revision='2d6caa52',
            when_timestamp=epoch2datetime(OTHERTIME),
            branch='master',
            category=None,
            revlink=None,
            properties={},
            repository='repo://',
            codebase='cb',
            project='proj')
        chdict = yield self.db.changes.getChange(changeid)
        validation.verifyDbDict(self, 'chdict', chdict)
        chdict = chdict.copy()
        ss = yield self.db.sourcestamps.getSourceStamp(chdict['sourcestampid'])
        chdict['sourcestampid'] = ss
        self.assertEqual(chdict, {
            'author': 'dustin',
            'branch': 'master',
            'category': None,
            'changeid': changeid,
            'parent_changeids': [],
            'codebase': 'cb',
            'comments': 'fix spelling',
            'files': [],
            'project': 'proj',
            'properties': {},
            'repository': 'repo://',
            'revision': '2d6caa52',
            'revlink': None,
            'sourcestampid': {
                'branch': 'master',
                'codebase': 'cb',
                'patch_author': None,
                'patch_body': None,
                'patch_comment': None,
                'patch_level': None,
                'patch_subdir': None,
                'patchid': None,
                'project': 'proj',
                'repository': 'repo://',
                'revision': '2d6caa52',
                'created_at': epoch2datetime(SOMETIME),
                'ssid': ss['ssid'],
            },
            'when_timestamp': epoch2datetime(OTHERTIME),
        })

    @defer.inlineCallbacks
    def test_addChange_withParent(self):
        yield self.insertTestData(self.change14_rows)

        self.reactor.advance(SOMETIME)
        changeid = yield self.db.changes.addChange(
            author='delanne',
            files=[],
            comments='child of changeid14',
            revision='50adad56',
            when_timestamp=epoch2datetime(OTHERTIME),
            branch='warnerdb',
            category='devel',
            revlink=None,
            properties={},
            repository='git://warner',
            codebase='mainapp',
            project='Buildbot')
        chdict = yield self.db.changes.getChange(changeid)
        validation.verifyDbDict(self, 'chdict', chdict)
        chdict = chdict.copy()
        ss = yield self.db.sourcestamps.getSourceStamp(chdict['sourcestampid'])
        chdict['sourcestampid'] = ss
        self.assertEqual(chdict, {
            'author': 'delanne',
            'branch': 'warnerdb',
            'category': 'devel',
            'changeid': changeid,
            'parent_changeids': [14],
            'codebase': 'mainapp',
            'comments': 'child of changeid14',
            'files': [],
            'project': 'Buildbot',
            'properties': {},
            'repository': 'git://warner',
            'revision': '50adad56',
            'revlink': None,
            'sourcestampid': {
                'branch': 'warnerdb',
                'codebase': 'mainapp',
                'created_at': epoch2datetime(SOMETIME),
                'patch_author': None,
                'patch_body': None,
                'patch_comment': None,
                'patch_level': None,
                'patch_subdir': None,
                'patchid': None,
                'project': 'Buildbot',
                'repository': 'git://warner',
                'revision': '50adad56',
                'ssid': ss['ssid']
            },
            'when_timestamp': epoch2datetime(OTHERTIME),
        })

    @defer.inlineCallbacks
    def test_getChange_chdict(self):
        yield self.insertTestData(self.change14_rows)

        chdict = yield self.db.changes.getChange(14)

        validation.verifyDbDict(self, 'chdict', chdict)
        self.assertEqual(chdict, self.change14_dict)

    @defer.inlineCallbacks
    def test_getChange_missing(self):
        chdict = yield self.db.changes.getChange(14)

        self.assertTrue(chdict is None)

    def test_signature_getChangeUids(self):
        @self.assertArgSpecMatches(self.db.changes.getChangeUids)
        def getChangeUids(self, changeid):
            pass

    @defer.inlineCallbacks
    def test_getChangeUids_missing(self):
        res = yield self.db.changes.getChangeUids(1)

        self.assertEqual(res, [])

    @defer.inlineCallbacks
    def test_getChangeUids_found(self):
        yield self.insertTestData(self.change14_rows + [
            fakedb.SourceStamp(id=92),
            fakedb.User(uid=1),
            fakedb.ChangeUser(changeid=14, uid=1),
        ])
        res = yield self.db.changes.getChangeUids(14)

        self.assertEqual(res, [1])

    @defer.inlineCallbacks
    def test_getChangeUids_multi(self):
        yield self.insertTestData(self.change14_rows + self.change13_rows + [
            fakedb.User(uid=1, identifier="one"),
            fakedb.User(uid=2, identifier="two"),
            fakedb.User(uid=99, identifier="nooo"),
            fakedb.ChangeUser(changeid=14, uid=1),
            fakedb.ChangeUser(changeid=14, uid=2),
            fakedb.ChangeUser(changeid=13, uid=99),  # not selected
        ])
        res = yield self.db.changes.getChangeUids(14)

        self.assertEqual(sorted(res), [1, 2])

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

    @defer.inlineCallbacks
    def test_getRecentChanges_subset(self):
        yield self.insert7Changes()
        changes = yield self.db.changes.getRecentChanges(5)

        changeids = [c['changeid'] for c in changes]
        self.assertEqual(changeids, [10, 11, 12, 13, 14])

    @defer.inlineCallbacks
    def test_getChangesCount(self):
        yield self.insert7Changes()
        n = yield self.db.changes.getChangesCount()

        self.assertEqual(n, 7)

    @defer.inlineCallbacks
    def test_getChangesHugeCount(self):
        yield self.insertTestData([
            fakedb.SourceStamp(id=92),
        ] + [
            fakedb.Change(changeid=i) for i in range(2, 102)])
        n = yield self.db.changes.getChangesCount()

        self.assertEqual(n, 100)

    @defer.inlineCallbacks
    def test_getRecentChanges_empty(self):
        changes = yield self.db.changes.getRecentChanges(5)

        changeids = [c['changeid'] for c in changes]
        self.assertEqual(changeids, [])
        yield self.db.changes.getChanges()

        changeids = [c['changeid'] for c in changes]
        self.assertEqual(changeids, [])

    @defer.inlineCallbacks
    def test_getRecentChanges_missing(self):
        yield self.insertTestData(self.change13_rows + self.change14_rows)

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

        changes = yield self.db.changes.getRecentChanges(5)
        check(changes)

        changes = yield self.db.changes.getChanges()
        check(changes)

    def test_signature_getLatestChangeid(self):
        @self.assertArgSpecMatches(self.db.changes.getLatestChangeid)
        def getLatestChangeid(self):
            pass

    @defer.inlineCallbacks
    def test_getLatestChangeid(self):
        yield self.insertTestData(self.change13_rows)

        changeid = yield self.db.changes.getLatestChangeid()

        self.assertEqual(changeid, 13)

    @defer.inlineCallbacks
    def test_getLatestChangeid_empty(self):
        changeid = yield self.db.changes.getLatestChangeid()

        self.assertEqual(changeid, None)

    def test_signature_getParentChangeIds(self):
        @self.assertArgSpecMatches(self.db.changes.getParentChangeIds)
        def getParentChangeIds(self, branch, repository, project, codebase):
            pass

    @defer.inlineCallbacks
    def test_getParentChangeIds(self):
        yield self.insertTestData(self.change14_rows + self.change13_rows)

        changeid = yield self.db.changes.getParentChangeIds(branch='warnerdb',
                                                      repository='git://warner',
                                                      project='Buildbot',
                                                      codebase='mainapp')
        self.assertEqual(changeid, [14])


class RealTests(Tests):

    # tests that only "real" implementations will pass

    @defer.inlineCallbacks
    def test_addChange(self):
        self.reactor.advance(SOMETIME)
        changeid = yield self.db.changes.addChange(
            author='dustin',
            files=['master/LICENSING.txt', 'worker/LICENSING.txt'],
            comments='fix spelling',
            revision='2d6caa52',
            when_timestamp=epoch2datetime(266738400),
            branch='master',
            category=None,
            revlink=None,
            properties={'platform': ('linux', 'Change')},
            repository='',
            codebase='cb',
            project='')
        # check all of the columns of the four relevant tables

        def thd_change(conn):
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
            self.assertEqual(r[0].codebase, 'cb')
            self.assertEqual(r[0].project, '')
            self.assertEqual(r[0].sourcestampid, 1)
        yield self.db.pool.do(thd_change)

        def thd_change_files(conn):
            query = self.db.model.change_files.select()
            query.where(self.db.model.change_files.c.changeid == 1)
            query.order_by(self.db.model.change_files.c.filename)
            r = conn.execute(query)
            r = r.fetchall()
            self.assertEqual(len(r), 2)
            self.assertEqual(r[0].filename, 'master/LICENSING.txt')
            self.assertEqual(r[1].filename, 'worker/LICENSING.txt')
        yield self.db.pool.do(thd_change_files)

        def thd_change_properties(conn):
            query = self.db.model.change_properties.select()
            query.where(self.db.model.change_properties.c.changeid == 1)
            query.order_by(self.db.model.change_properties.c.property_name)
            r = conn.execute(query)
            r = r.fetchall()
            self.assertEqual(len(r), 1)
            self.assertEqual(r[0].property_name, 'platform')
            self.assertEqual(r[0].property_value, '["linux", "Change"]')
        yield self.db.pool.do(thd_change_properties)

        def thd_change_users(conn):
            query = self.db.model.change_users.select()
            r = conn.execute(query)
            r = r.fetchall()
            self.assertEqual(len(r), 0)
        yield self.db.pool.do(thd_change_users)

        def thd_change_sourcestamps(conn):
            query = self.db.model.sourcestamps.select()
            r = conn.execute(query)
            self.assertEqual([dict(row) for row in r.fetchall()], [{
                'branch': 'master',
                'codebase': 'cb',
                'id': 1,
                'patchid': None,
                'project': '',
                'repository': '',
                'revision': '2d6caa52',
                'created_at': SOMETIME,
                'ss_hash': 'b777dbd10d1d4c76651335f6a78e278e88b010d6',
            }])
        yield self.db.pool.do(thd_change_sourcestamps)

    @defer.inlineCallbacks
    def test_addChange_when_timestamp_None(self):
        self.reactor.advance(OTHERTIME)
        changeid = yield self.db.changes.addChange(
            author='dustin',
            files=[],
            comments='fix spelling',
            revision='2d6caa52',
            when_timestamp=None,
            branch='master',
            category=None,
            revlink=None,
            properties={},
            repository='',
            codebase='',
            project='')
        # check all of the columns of the four relevant tables

        def thd(conn):
            r = conn.execute(self.db.model.changes.select())
            r = r.fetchall()
            self.assertEqual(len(r), 1)
            self.assertEqual(r[0].changeid, changeid)
            self.assertEqual(r[0].when_timestamp, OTHERTIME)
        yield self.db.pool.do(thd)

        def thd_change(conn):
            query = self.db.model.change_files.select()
            r = conn.execute(query)
            r = r.fetchall()
            self.assertEqual(len(r), 0)
        yield self.db.pool.do(thd_change)

        def thd_change_file(conn):
            query = self.db.model.change_properties.select()
            r = conn.execute(query)
            r = r.fetchall()
            self.assertEqual(len(r), 0)
        yield self.db.pool.do(thd_change_file)

        def thd_change_properties(conn):
            query = self.db.model.change_users.select()
            r = conn.execute(query)
            r = r.fetchall()
            self.assertEqual(len(r), 0)
        yield self.db.pool.do(thd_change_properties)

    @defer.inlineCallbacks
    def test_addChange_with_uid(self):
        yield self.insertTestData([
            fakedb.User(uid=1, identifier="one"),
        ])
        changeid = yield self.db.changes.addChange(
                          author='dustin',
                          files=[],
                          comments='fix spelling',
                          revision='2d6caa52',
                          when_timestamp=epoch2datetime(OTHERTIME),
                          branch='master',
                          category=None,
                          revlink=None,
                          properties={},
                          repository='',
                          codebase='',
                          project='',
                          uid=1)
        # check all of the columns of the five relevant tables

        def thd_change(conn):
            r = conn.execute(self.db.model.changes.select())
            r = r.fetchall()
            self.assertEqual(len(r), 1)
            self.assertEqual(r[0].changeid, changeid)
            self.assertEqual(r[0].when_timestamp, OTHERTIME)
        yield self.db.pool.do(thd_change)

        def thd_change_files(conn):
            query = self.db.model.change_files.select()
            r = conn.execute(query)
            r = r.fetchall()
            self.assertEqual(len(r), 0)
        yield self.db.pool.do(thd_change_files)

        def thd_change_properties(conn):
            query = self.db.model.change_properties.select()
            r = conn.execute(query)
            r = r.fetchall()
            self.assertEqual(len(r), 0)
        yield self.db.pool.do(thd_change_properties)

        def thd_change_users(conn):
            query = self.db.model.change_users.select()
            r = conn.execute(query)
            r = r.fetchall()
            self.assertEqual(len(r), 1)
            self.assertEqual(r[0].changeid, 1)
            self.assertEqual(r[0].uid, 1)
        yield self.db.pool.do(thd_change_users)

    @defer.inlineCallbacks
    def test_pruneChanges(self):
        yield self.insertTestData([
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
        yield self.db.changes.pruneChanges(2)

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
        yield self.db.pool.do(thd)

    @defer.inlineCallbacks
    def test_pruneChanges_lots(self):
        yield self.insertTestData([
            fakedb.SourceStamp(id=29),
        ] + [
            fakedb.Change(changeid=n, sourcestampid=29)
            for n in range(1, 151)
        ])

        yield self.db.changes.pruneChanges(1)

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
        yield self.db.pool.do(thd)

    @defer.inlineCallbacks
    def test_pruneChanges_None(self):
        yield self.insertTestData(self.change13_rows)

        yield self.db.changes.pruneChanges(None)

        def thd(conn):
            tbl = self.db.model.changes
            res = conn.execute(tbl.select())
            self.assertEqual([row.changeid for row in res.fetchall()],
                             [13])
        yield self.db.pool.do(thd)

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
            for cb, ss in codebase_ss.items():
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

        yield expect(1, ['2nd commit', '3rd commit', '1st commit'])
        yield expect(2, ['4th commit'])
        yield expect(3, ['6th commit'])
        yield expect(4, [])
        yield expect(5, ['8th commit', '9th commit', '7th commit'])
        yield expect(6, ['10th commit'])
        yield expect(7, ['11th commit'])


class TestFakeDB(TestReactorMixin, unittest.TestCase, Tests):

    def setUp(self):
        self.setUpTestReactor()
        self.master = fakemaster.make_master(self, wantDb=True)
        self.db = self.master.db
        self.db.checkForeignKeys = True
        self.insertTestData = self.db.insertTestData


class TestRealDB(unittest.TestCase,
                 connector_component.ConnectorComponentMixin,
                 RealTests):

    @defer.inlineCallbacks
    def setUp(self):
        yield self.setUpConnectorComponent(
            table_names=['changes', 'change_files',
                         'change_properties', 'scheduler_changes', 'schedulers',
                         'sourcestampsets', 'sourcestamps', 'patches', 'change_users',
                         'users', 'buildsets', 'workers', 'builders', 'masters',
                         'buildrequests', 'builds', 'buildset_sourcestamps',
                         'workers'])

        self.db.changes = changes.ChangesConnectorComponent(self.db)
        self.db.builds = builds.BuildsConnectorComponent(self.db)
        self.db.sourcestamps = \
            sourcestamps.SourceStampsConnectorComponent(self.db)
        self.master = self.db.master
        self.master.db = self.db

    def tearDown(self):
        return self.tearDownConnectorComponent()
