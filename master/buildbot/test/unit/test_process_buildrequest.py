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

class FakeSource:
    def __init__(self, mergeable = True):
        self.codebase = ''
        self.mergeable = mergeable
        self.changes = []

    def canBeMergedWith(self, other):
        return self.mergeable

class TestBuildRequest(unittest.TestCase):

    def test_fromBrdict(self):
        master = fakemaster.make_master()
        master.db = fakedb.FakeDBConnector(self)
        master.db.insertTestData([
            fakedb.Change(changeid=13, branch='trunk', revision='9283',
                        repository='svn://...', project='world-domination'),
            fakedb.SourceStampSet(id=234),
            fakedb.SourceStamp(id=234, sourcestampsetid=234, branch='trunk',
                        revision='9284', repository='svn://...',
                        project='world-domination'),
            fakedb.SourceStampChange(sourcestampid=234, changeid=13),
            fakedb.Buildset(id=539, reason='triggered', sourcestampsetid=234),
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
            fakedb.SourceStampSet(id=234),
            fakedb.SourceStamp(id=234, sourcestampsetid=234, branch='trunk',
                        revision='9284', repository='svn://...',
                        project='world-domination'),
            fakedb.Buildset(id=539, reason='triggered', sourcestampsetid=234),
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

    def test_fromBrdict_no_sourcestamps(self):
        master = fakemaster.make_master()
        master.db = fakedb.FakeDBConnector(self)
        master.db.insertTestData([
            fakedb.SourceStampSet(id=234),
            # Sourcestampset has no sourcestamps
            fakedb.Buildset(id=539, reason='triggered', sourcestampsetid=234),
            fakedb.BuildRequest(id=288, buildsetid=539, buildername='not important',
                        priority=0, submitted_at=None),
        ])
        # use getBuildRequest to minimize the risk from changes to the format
        # of the brdict
        d = master.db.buildrequests.getBuildRequest(288)
        d.addCallback(lambda brdict:
            buildrequest.BuildRequest.fromBrdict(master, brdict))
        return self.assertFailure(d, AssertionError)
        
    def test_fromBrdict_multiple_sourcestamps(self):
        master = fakemaster.make_master()
        master.db = fakedb.FakeDBConnector(self)
        master.db.insertTestData([
            fakedb.SourceStampSet(id=234),

            fakedb.Change(changeid=13, branch='trunk', revision='9283',
                        repository='svn://a..',  codebase='A',
                        project='world-domination'),
            fakedb.SourceStamp(id=234, sourcestampsetid=234, branch='trunk',
                        revision='9283', repository='svn://a..',
                         codebase='A', project='world-domination'),
            fakedb.SourceStampChange(sourcestampid=234, changeid=13),

            fakedb.Change(changeid=14, branch='trunk', revision='9284',
                        repository='svn://b..',  codebase='B',
                        project='world-domination'),
            fakedb.SourceStamp(id=235, sourcestampsetid=234, branch='trunk',
                        revision='9284', repository='svn://b..',
                         codebase='B', project='world-domination'),
            fakedb.SourceStampChange(sourcestampid=235, changeid=14),

            fakedb.Buildset(id=539, reason='triggered', sourcestampsetid=234),
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

            # Test the single-sourcestamp interface
            self.assertEqual(br.source.ssid, 234)

            # Test the multiple sourcestamp interface
            self.assertEqual(br.sources['A'].ssid, 234)
            self.assertEqual(br.sources['B'].ssid, 235)
            
            self.assertEqual([ ch.number for ch in br.sources['A'].changes], [13])
            self.assertEqual([ ch.number for ch in br.sources['B'].changes], [14])

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

    def test_mergeSourceStampsWith_common_codebases(self):
        """ This testcase has two buildrequests
            Request Change Codebase Revision Comment
            ----------------------------------------------------------------------
            288     13     A        9283
            289     15     A        9284
            288     14     B        9200
            289     16     B        9201
            -------------------------------- 
            After merged in Build:
            Source1 has rev 9284 and contains changes 13 and 15 from repository svn://a
            Source2 has rev 9201 and contains changes 14 and 16 from repository svn://b
        """
        brs=[] # list of buildrequests
        master = fakemaster.make_master()
        master.db = fakedb.FakeDBConnector(self)
        master.db.insertTestData([
            fakedb.SourceStampSet(id=2340),

            fakedb.Change(changeid=13, branch='trunk', revision='9283',
                        repository='svn://a..',  codebase='A',
                        project='world-domination'),
            fakedb.SourceStamp(id=234, sourcestampsetid=2340, branch='trunk',
                        revision='9283', repository='svn://a..', codebase='A',
                        project='world-domination'),
            fakedb.SourceStampChange(sourcestampid=234, changeid=13),

            fakedb.Change(changeid=14, branch='trunk', revision='9200',
                        repository='svn://b..',  codebase='A',
                        project='world-domination'),
            fakedb.SourceStamp(id=235, sourcestampsetid=2340, branch='trunk',
                        revision='9200', repository='svn://b..', codebase='B',
                        project='world-domination'),
            fakedb.SourceStampChange(sourcestampid=235, changeid=14),

            fakedb.SourceStampSet(id=2360),

            fakedb.Change(changeid=15, branch='trunk', revision='9284',
                        repository='svn://a..',  codebase='A',
                        project='world-domination'),
            fakedb.SourceStamp(id=236, sourcestampsetid=2360, branch='trunk',
                        revision='9284', repository='svn://a..', codebase='A',
                        project='world-domination'),
            fakedb.SourceStampChange(sourcestampid=236, changeid=15),

            fakedb.Change(changeid=16, branch='trunk', revision='9201',
                        repository='svn://b..',  codebase='B',
                        project='world-domination'),
            fakedb.SourceStamp(id=237, sourcestampsetid=2360, branch='trunk',
                        revision='9201', repository='svn://b..', codebase='B',
                        project='world-domination'),
            fakedb.SourceStampChange(sourcestampid=237, changeid=16),
      
            fakedb.Buildset(id=539, reason='triggered', sourcestampsetid=2340),
            fakedb.BuildRequest(id=288, buildsetid=539, buildername='bldr'),

            fakedb.Buildset(id=540, reason='triggered', sourcestampsetid=2360),
            fakedb.BuildRequest(id=289, buildsetid=540, buildername='bldr'),
        ])
        # use getBuildRequest to minimize the risk from changes to the format
        # of the brdict
        d = master.db.buildrequests.getBuildRequest(288)
        d.addCallback(lambda brdict :
                    buildrequest.BuildRequest.fromBrdict(master, brdict))
        d.addCallback(lambda br : brs.append(br))
        d.addCallback(lambda _ : 
                    master.db.buildrequests.getBuildRequest(289))
        d.addCallback(lambda brdict :
                    buildrequest.BuildRequest.fromBrdict(master, brdict))
        d.addCallback(lambda br : brs.append(br))
        def check(_):
            sources = brs[0].mergeSourceStampsWith(brs[1:])
            
            source1 = source2 = None
            for source in sources:
                if source.codebase == 'A':
                    source1 = source
                if source.codebase == 'B':
                    source2 = source

            self.assertFalse(source1 == None)
            self.assertEqual(source1.revision,'9284')
            
            self.assertFalse(source2 == None)
            self.assertEqual(source2.revision,'9201')
                      
            self.assertEqual([c.number for c in source1.changes], [13,15])
            self.assertEqual([c.number for c in source2.changes], [14,16])
            
        d.addCallback(check)
        return d

    def test_canBeMergedWith_different_codebases_raises_error(self):
        """ This testcase has two buildrequests
            Request Change Codebase   Revision Comment
            ----------------------------------------------------------------------
            288     17     C          1800     request 1 has repo not in request 2
            289     18     D          2100     request 2 has repo not in request 1
            -------------------------------- 
            Merge cannot be performd and raises error:
              Merging requests requires both requests to have the same codebases
        """
        brs=[] # list of buildrequests
        master = fakemaster.make_master()
        master.db = fakedb.FakeDBConnector(self)
        master.db.insertTestData([
            fakedb.SourceStampSet(id=2340),

            fakedb.Change(changeid=17, branch='trunk', revision='1800',
                        repository='svn://c..',  codebase='C',
                        project='world-domination'),
            fakedb.SourceStamp(id=238, sourcestampsetid=2340, branch='trunk',
                        revision='1800', repository='svn://c..',
                         codebase='C', project='world-domination'),
            fakedb.SourceStampChange(sourcestampid=238, changeid=17),

            fakedb.SourceStampSet(id=2360),

            fakedb.Change(changeid=18, branch='trunk', revision='2100',
                        repository='svn://d..',  codebase='D',
                        project='world-domination'),
            fakedb.SourceStamp(id=239, sourcestampsetid=2360, branch='trunk',
                        revision='2100', repository='svn://d..',
                         codebase='D', project='world-domination'),
            fakedb.SourceStampChange(sourcestampid=239, changeid=18),
            
            fakedb.Buildset(id=539, reason='triggered', sourcestampsetid=2340),
            fakedb.BuildRequest(id=288, buildsetid=539, buildername='bldr'),

            fakedb.Buildset(id=540, reason='triggered', sourcestampsetid=2360),
            fakedb.BuildRequest(id=289, buildsetid=540, buildername='bldr'),
        ])
        # use getBuildRequest to minimize the risk from changes to the format
        # of the brdict
        d = master.db.buildrequests.getBuildRequest(288)
        d.addCallback(lambda brdict :
                    buildrequest.BuildRequest.fromBrdict(master, brdict))
        d.addCallback(lambda br : brs.append(br))
        d.addCallback(lambda _ : 
                    master.db.buildrequests.getBuildRequest(289))
        d.addCallback(lambda brdict :
                    buildrequest.BuildRequest.fromBrdict(master, brdict))
        d.addCallback(lambda br : brs.append(br))
        def check(_):
            self.assertEqual(brs[0].canBeMergedWith(brs[1]), False)

        d.addCallback(check)
        return d

    def test_build_can_be_merged_with_mergables_same_codebases(self):
        r1 = buildrequest.BuildRequest()
        r1.sources = {"A": FakeSource()}
        r2 = buildrequest.BuildRequest()
        r2.sources = {"A": FakeSource()}
        mergeable = r1.canBeMergedWith(r2)
        self.assertTrue(mergeable, "Both request should be able to merge")
    
    def test_build_can_be_merged_with_non_mergable_same_codebases(self):
        r1 = buildrequest.BuildRequest()
        r1.sources = {"A": FakeSource(mergeable = False)}
        r2 = buildrequest.BuildRequest()
        r2.sources = {"A": FakeSource(mergeable = False)}
        mergeable = r1.canBeMergedWith(r2)
        self.assertFalse(mergeable, "Both request should not be able to merge")

    def test_build_can_be_merged_with_non_mergables_different_codebases(self):
        r1 = buildrequest.BuildRequest()
        r1.sources = {"A": FakeSource(mergeable = False)}
        r2 = buildrequest.BuildRequest()
        r2.sources = {"B": FakeSource(mergeable = False)}
        mergeable = r1.canBeMergedWith(r2)
        self.assertFalse(mergeable, "Request containing different codebases " +
                                    "should never be able to merge")


