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
from twisted.internet import defer
from buildbot.db import sourcestamps
from buildbot.test.util import connector_component
from buildbot.test.fake import fakedb

class TestSourceStampsConnectorComponent(
            connector_component.ConnectorComponentMixin,
            unittest.TestCase):

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['changes', 'change_links', 'change_files', 'patches',
                'sourcestamp_changes', 'sourcestamps' ])

        def finish_setup(_):
            self.db.sourcestamps = \
                    sourcestamps.SourceStampsConnectorComponent(self.db)
        d.addCallback(finish_setup)

        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()

    # tests

    def test_addSourceStamp_simple(self):
        d = defer.succeed(None)
        d.addCallback(lambda _ :
            self.db.sourcestamps.addSourceStamp('production', 'abdef',
                'test://repo', 'stamper'))
        def check(ssid):
            def thd(conn):
                # should see one sourcestamp row
                ss_tbl = self.db.model.sourcestamps
                r = conn.execute(ss_tbl.select())
                rows = [ (row.id, row.branch, row.revision,
                          row.patchid, row.repository, row.project)
                         for row in r.fetchall() ]
                self.assertEqual(rows,
                    [ ( ssid, 'production', 'abdef', None, 'test://repo', 'stamper') ])

                # .. and no sourcestamp_changes
                ssc_tbl = self.db.model.sourcestamp_changes
                r = conn.execute(ssc_tbl.select())
                rows = [ 1 for row in r.fetchall() ]
                self.assertEqual(rows, [])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_addSourceStamp_changes(self):
        # add some sample changes for referential integrity
        d = self.insertTestData([
              fakedb.Change(changeid=3),
              fakedb.Change(changeid=4),
            ])

        d.addCallback(lambda _ :
            self.db.sourcestamps.addSourceStamp('production', 'abdef',
                'test://repo', 'stamper', changeids=[3,4]))
        def check(ssid):
            def thd(conn):
                # should see one sourcestamp row
                ss_tbl = self.db.model.sourcestamps
                r = conn.execute(ss_tbl.select())
                rows = [ (row.id, row.branch, row.revision,
                          row.patchid, row.repository, row.project)
                         for row in r.fetchall() ]
                self.assertEqual(rows,
                    [ ( ssid, 'production', 'abdef', None, 'test://repo', 'stamper') ])

                # .. and two sourcestamp_changes
                ssc_tbl = self.db.model.sourcestamp_changes
                r = conn.execute(ssc_tbl.select())
                rows = [ (row.sourcestampid, row.changeid) for row in r.fetchall() ]
                self.assertEqual(sorted(rows), [ (ssid, 3), (ssid, 4) ])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_addSourceStamp_patch(self):
        d = defer.succeed(None)
        d.addCallback(lambda _ :
            self.db.sourcestamps.addSourceStamp('production', 'abdef',
                'test://repo', 'stamper', patch_body='my patch', patch_level=3,
                patch_subdir='master/'))
        def check(ssid):
            def thd(conn):
                # should see one sourcestamp row
                ss_tbl = self.db.model.sourcestamps
                r = conn.execute(ss_tbl.select())
                rows = [ (row.id, row.branch, row.revision,
                          row.patchid, row.repository, row.project)
                         for row in r.fetchall() ]
                patchid = row.patchid
                self.assertNotEqual(patchid, None)
                self.assertEqual(rows,
                    [ ( ssid, 'production', 'abdef', patchid, 'test://repo', 'stamper') ])

                # .. and a single patch
                patches_tbl = self.db.model.patches
                r = conn.execute(patches_tbl.select())
                rows = [ (row.id, row.patchlevel, row.patch_base64, row.subdir)
                         for row in r.fetchall() ]
                self.assertEqual(rows, [(patchid, 3, 'bXkgcGF0Y2g=', 'master/')])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_getSourceStamp_simple(self):
        d = self.insertTestData([
            fakedb.SourceStamp(id=234, branch='br', revision='rv',
                repository='rep', project='prj'),
        ])
        d.addCallback(lambda _ :
                self.db.sourcestamps.getSourceStamp(234))
        def check(ssdict):
            self.assertEqual(ssdict, dict(ssid=234, branch='br', revision='rv',
                repository='rep', project='prj', patch_body=None,
                patch_level=None, patch_subdir=None, changeids=set([])))
        d.addCallback(check)
        return d

    def test_getSourceStamp_simple_None(self):
        "check that NULL branch and revision are handled correctly"
        d = self.insertTestData([
            fakedb.SourceStamp(id=234, branch=None, revision=None,
                repository='rep', project='prj'),
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
            fakedb.SourceStamp(id=234),
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
                subdir='/foo', patchlevel=3),
            fakedb.SourceStamp(id=234, patchid=99),
        ])
        d.addCallback(lambda _ :
                self.db.sourcestamps.getSourceStamp(234))
        def check(ssdict):
            self.assertEqual(dict((k,v) for k,v in ssdict.iteritems()
                                  if k.startswith('patch_')),
                             dict(patch_body='hello, world',
                                  patch_level=3,
                                  patch_subdir='/foo'))
        d.addCallback(check)
        return d

    def test_getSourceStamp_nosuch(self):
        d = self.db.sourcestamps.getSourceStamp(234)
        def check(ssdict):
            self.assertEqual(ssdict, None)
        d.addCallback(check)
        return d
