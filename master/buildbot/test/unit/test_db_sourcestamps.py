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

from twisted.trial import unittest
from buildbot.db import sourcestamps
from buildbot.test.util import connector_component
from buildbot.test.fake import fakedb

class TestSourceStampsConnectorComponent(
            connector_component.ConnectorComponentMixin,
            unittest.TestCase):

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['changes', 'change_files', 'patches',
                'sourcestamp_changes', 'sourcestamps', 'sourcestampsets',
                'buildrequests', 'buildsets', 'buildset_properties'])

        def finish_setup(_):
            self.db.sourcestamps = \
                    sourcestamps.SourceStampsConnectorComponent(self.db)
        d.addCallback(finish_setup)

        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()

    # tests

    def test_addSourceStamp_simple(self):
        # add a sourcestampset for referential integrity
        d = self.insertTestData([
              fakedb.SourceStampSet(id=1),
        ])
        d.addCallback(lambda _ :
            self.db.sourcestamps.addSourceStamp(branch = 'production', revision='abdef',
            repository='test://repo', codebase='cb', project='stamper', sourcestampsetid=1))
        def check(ssid):
            def thd(conn):
                # should see one sourcestamp row
                ss_tbl = self.db.model.sourcestamps
                r = conn.execute(ss_tbl.select())
                rows = [ (row.id, row.branch, row.revision,
                          row.patchid, row.repository, row.codebase, row.project, row.sourcestampsetid)
                         for row in r.fetchall() ]
                self.assertEqual(rows,
                    [ ( ssid, 'production', 'abdef', None, 'test://repo', 'cb', 'stamper', 1) ])

                # .. and no sourcestamp_changes
                ssc_tbl = self.db.model.sourcestamp_changes
                r = conn.execute(ssc_tbl.select())
                rows = [ 1 for row in r.fetchall() ]
                self.assertEqual(rows, [])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_addSourceStamp_changes(self):
        # add some sample changes and a sourcestampset for referential integrity
        d = self.insertTestData([
              fakedb.SourceStampSet(id=1),
              fakedb.Change(changeid=3),
              fakedb.Change(changeid=4),
            ])

        d.addCallback(lambda _ :
            self.db.sourcestamps.addSourceStamp(branch = 'production', revision='abdef',
            repository='test://repo', codebase='cb', project='stamper', sourcestampsetid=1, changeids=[3,4]))

        def check(ssid):
            def thd(conn):
                # should see one sourcestamp row
                ss_tbl = self.db.model.sourcestamps
                r = conn.execute(ss_tbl.select())
                rows = [ (row.id, row.branch, row.revision,
                          row.patchid, row.repository, row.codebase, row.project, row.sourcestampsetid)
                         for row in r.fetchall() ]
                self.assertEqual(rows,
                    [ ( ssid, 'production', 'abdef', None, 'test://repo', 'cb', 'stamper', 1) ])

                # .. and two sourcestamp_changes
                ssc_tbl = self.db.model.sourcestamp_changes
                r = conn.execute(ssc_tbl.select())
                rows = [ (row.sourcestampid, row.changeid) for row in r.fetchall() ]
                self.assertEqual(sorted(rows), [ (ssid, 3), (ssid, 4) ])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_addSourceStamp_patch(self):
        # add a sourcestampset for referential integrity
        d = self.insertTestData([
              fakedb.SourceStampSet(id=1),
        ])
        d.addCallback(lambda _ :
            self.db.sourcestamps.addSourceStamp(branch = 'production', revision='abdef',
            repository='test://repo', codebase='cb', project='stamper', sourcestampsetid=1, patch_body='my patch', patch_level=3,
            patch_subdir='master/', patch_author='me',
            patch_comment="comment"))
        def check(ssid):
            def thd(conn):
                # should see one sourcestamp row
                ss_tbl = self.db.model.sourcestamps
                r = conn.execute(ss_tbl.select())
                rows = [ (row.id, row.branch, row.revision,
                          row.patchid, row.repository, row.codebase, row.project, row.sourcestampsetid)
                         for row in r.fetchall() ]
                patchid = row.patchid
                self.assertNotEqual(patchid, None)
                self.assertEqual(rows,
                    [ ( ssid, 'production', 'abdef', patchid, 'test://repo', 'cb',
                        'stamper', 1) ])

                # .. and a single patch
                patches_tbl = self.db.model.patches
                r = conn.execute(patches_tbl.select())
                rows = [ (row.id, row.patchlevel, row.patch_base64, row.subdir,
                          row.patch_author, row.patch_comment)
                         for row in r.fetchall() ]
                self.assertEqual(rows, [(patchid, 3, 'bXkgcGF0Y2g=', 'master/',
                                         'me', 'comment')])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_getSourceStamp_simple(self):
        d = self.insertTestData([
            fakedb.SourceStampSet(id=234),
            fakedb.SourceStamp(id=234, sourcestampsetid=234, branch='br', revision='rv', repository='rep', codebase='cb', project='prj'),
        ])
        d.addCallback(lambda _ :
                self.db.sourcestamps.getSourceStamp(234))
        def check(ssdict):
            self.assertEqual(ssdict, dict(ssid=234, branch='br', revision='rv',
            sourcestampsetid=234, repository='rep', codebase = 'cb',
                project='prj', patch_body=None,
                patch_level=None, patch_subdir=None, 
                patch_author=None, patch_comment=None, changeids=set([])))
        d.addCallback(check)
        return d

    def test_getSourceStamp_simple_None(self):
        "check that NULL branch and revision are handled correctly"
        d = self.insertTestData([
            fakedb.SourceStampSet(id=234),
            fakedb.SourceStamp(id=234, sourcestampsetid=234, branch=None, revision=None,
                repository='rep', codebase='cb', project='prj'),
        ])
        d.addCallback(lambda _ :
                self.db.sourcestamps.getSourceStamp(234))
        def check(ssdict):
            self.assertEqual((ssdict['branch'], ssdict['revision']),
                             (None, None))
        d.addCallback(check)
        return d

    def test_getSourceStamp_changes(self):
        d = self.insertTestData([
            fakedb.Change(changeid=16),
            fakedb.Change(changeid=19),
            fakedb.Change(changeid=20),
            fakedb.SourceStampSet(id=234),
            fakedb.SourceStamp(id=234, sourcestampsetid=234),
            fakedb.SourceStampChange(sourcestampid=234, changeid=16),
            fakedb.SourceStampChange(sourcestampid=234, changeid=20),
        ])
        d.addCallback(lambda _ :
                self.db.sourcestamps.getSourceStamp(234))
        def check(ssdict):
            self.assertEqual(ssdict['changeids'], set([16,20]))
        d.addCallback(check)
        return d

    def test_getSourceStamp_patch(self):
        d = self.insertTestData([
            fakedb.Patch(id=99, patch_base64='aGVsbG8sIHdvcmxk',
                patch_author='bar', patch_comment='foo', subdir='/foo',
                patchlevel=3),
            fakedb.SourceStampSet(id=234),
            fakedb.SourceStamp(id=234, sourcestampsetid=234, patchid=99),
        ])
        d.addCallback(lambda _ :
                self.db.sourcestamps.getSourceStamp(234))
        def check(ssdict):
            self.assertEqual(dict((k,v) for k,v in ssdict.iteritems()
                                  if k.startswith('patch_')),
                             dict(patch_body='hello, world',
                                  patch_level=3,
                                  patch_author='bar',
                                  patch_comment='foo',
                                  patch_subdir='/foo'))
        d.addCallback(check)
        return d

    def test_getSourceStamp_nosuch(self):
        d = self.db.sourcestamps.getSourceStamp(234)
        def check(ssdict):
            self.assertEqual(ssdict, None)
        d.addCallback(check)
        return d

    def test_updateSourceStamps(self):
        d = self.insertTestData([
            fakedb.SourceStampSet(id=1),
            fakedb.SourceStamp(id=1, sourcestampsetid=1, branch='b1', revision= None,
                repository='rep', codebase='c1'),
            fakedb.SourceStamp(id=2, sourcestampsetid=1, branch='b2', revision= None,
                repository='rep2', codebase='c2'),
        ])

        d.addCallback(lambda _ :
                self.db.sourcestamps.getSourceStamp(1))

        def checkRevision(ssdict, codebase='', revision=None):
            self.assertEqual(ssdict['codebase'], codebase)
            self.assertEqual(ssdict['revision'], revision)

        d.addCallback(checkRevision, codebase='c1')

        sourcestamps = [{'b_codebase': 'c1', 'b_revision': 'r1', 'b_sourcestampsetid': 1},
                        {'b_codebase': 'c2', 'b_revision': 'r2', 'b_sourcestampsetid': 1}]

        d.addCallback(lambda _ :
                self.db.sourcestamps.updateSourceStamps(sourcestamps))

        def checkUpdate(rowsupdated):
            self.assertEqual(rowsupdated, 2)

        d.addCallback(checkUpdate)
        d.addCallback(lambda _: self.db.sourcestamps.getSourceStamp(1))
        d.addCallback(checkRevision, codebase='c1', revision='r1')
        d.addCallback(lambda _: self.db.sourcestamps.getSourceStamp(2))
        d.addCallback(checkRevision, codebase='c2', revision='r2')

        return d

    def test_findLastBuildRev(self):
        d = self.insertTestData([fakedb.SourceStampSet(id=1),
                                fakedb.SourceStampSet(id=2),
                                fakedb.SourceStampSet(id=3),
                                fakedb.SourceStamp(id=1, sourcestampsetid=1, branch='b1', revision='az',
                repository='repo', codebase='c1'),
                                fakedb.SourceStamp(id=2, sourcestampsetid=2, branch='b1', revision='bw',
                repository='repo', codebase='c1'),
                                fakedb.SourceStamp(id=3, sourcestampsetid=3, branch='b1', revision=None,
                repository='repo', codebase='c1'),
                                fakedb.Buildset(id=1, sourcestampsetid=1),
                                fakedb.BuildsetProperty(buildsetid=1,
                                                        property_name="buildLatestRev",
                                                        property_value='[true, "Force Build Form"]'),
                                fakedb.Buildset(id=2, sourcestampsetid=2),
                                fakedb.BuildsetProperty(buildsetid=2,
                                                        property_name="buildLatestRev",
                                                        property_value='["True", "Trigger"]'),
                                fakedb.Buildset(id=3, sourcestampsetid=3),
                                fakedb.BuildRequest(id=2, buildsetid=2, buildername="builder1", complete=1, results=4),
                                fakedb.BuildRequest(id=1, buildsetid=1, buildername="builder1", complete=1, results=2),
                                fakedb.BuildRequest(id=3, buildsetid=3, buildername="builder1"),
                                ])
        def check(lastrev, expectedrev):
            self.assertEqual(lastrev, expectedrev)

        d.addCallback(lambda _:
                self.db.sourcestamps.findLastBuildRev(buildername="builder1",
                                                      brid=3, codebase="c1",
                                                      repository="repo",
                                                      branch="b1"))

        d.addCallback(check, "az")
        return d
