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
from buildbot.test.fake import fakedb, fakemaster
from buildbot.process import buildrequest

class TestBuildRequest(unittest.TestCase):

    def test_fromBrdict(self):
        master = fakemaster.make_master()
        master.db = fakedb.FakeDBConnector(self)
        master.db.insertTestData([
            fakedb.Change(changeid=13, branch='trunk', revision='9283',
                        repository='svn://...', project='world-domination'),
            fakedb.SourceStamp(id=234, branch='trunk', revision='9284',
                        repository='svn://...', project='world-domination'),
            fakedb.SourceStampChange(sourcestampid=234, changeid=13),
            fakedb.Buildset(id=539, reason='triggered', sourcestampid=234),
            fakedb.BuildsetProperty(buildsetid=539, property_name='x',
                        property_value='[1, "X"]'),
            fakedb.BuildsetProperty(buildsetid=539, property_name='y',
                        property_value='[2, "Y"]'),
            fakedb.BuildRequest(id=288, buildsetid=539, buildername='bldr',
                        priority=13, submitted_at=1200000000),
        ])
        # use getBuildRequest to minimize the risk from changes to the format
        # of the brdict
        d = master.db.buildrequests.getBuildRequest(288)
        d.addCallback(lambda brdict :
                    buildrequest.BuildRequest.fromBrdict(master, brdict))
        def check(br):
            # check enough of the source stamp to verify it found the changes
            self.assertEqual(br.source.ssid, 234)
            self.assertEqual([ ch.number for ch in br.source.changes], [13])

            self.assertEqual(br.reason, 'triggered')

            self.assertEqual(br.properties.getProperty('x'), 1)
            self.assertEqual(br.properties.getProperty('y'), 2)
            self.assertEqual(br.submittedAt, 1200000000)
            self.assertEqual(br.buildername, 'bldr')
            self.assertEqual(br.priority, 13)
            self.assertEqual(br.id, 288)
            self.assertEqual(br.bsid, 539)
        d.addCallback(check)
        return d

    def test_fromBrdict_submittedAt_NULL(self):
        master = fakemaster.make_master()
        master.db = fakedb.FakeDBConnector(self)
        master.db.insertTestData([
            fakedb.SourceStamp(id=234, branch='trunk', revision='9284',
                        repository='svn://...', project='world-domination'),
            fakedb.Buildset(id=539, reason='triggered', sourcestampid=234),
            fakedb.BuildRequest(id=288, buildsetid=539, buildername='bldr',
                        priority=13, submitted_at=None),
        ])
        # use getBuildRequest to minimize the risk from changes to the format
        # of the brdict
        d = master.db.buildrequests.getBuildRequest(288)
        d.addCallback(lambda brdict :
                    buildrequest.BuildRequest.fromBrdict(master, brdict))
        def check(br):
            # remaining fields assumed to be checked in test_fromBrdict
            self.assertEqual(br.submittedAt, None)
        d.addCallback(check)
        return d
