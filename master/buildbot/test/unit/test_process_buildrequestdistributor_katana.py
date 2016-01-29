from twisted.trial import unittest
from twisted.internet import defer
from twisted.python import log
from buildbot.test.fake import fakedb, fakemaster
from buildbot.process import buildrequestdistributor
from buildbot.process.buildrequestdistributor import Slavepool
from buildbot.process import builder, factory
from buildbot import config
import mock
from buildbot.db import buildrequests
from buildbot.db.buildrequests import Queue
from buildbot.test.util import connector_component
from buildbot.status.results import RESUME


class TestKatanaBuildRequestDistributor(connector_component.ConnectorComponentMixin, unittest.TestCase):

    def addSlavesToList(self, slavelist, slavebuilders):
        if not slavebuilders:
            return
        """C{slaves} maps name : available"""
        for name, avail in slavebuilders.iteritems():
            sb = mock.Mock(spec=['isAvailable'], name=name)
            sb.name = name
            sb.isAvailable.return_value = avail
            sb.slave = mock.Mock()
            sb.slave.slave_status = mock.Mock(spec=['getName'])
            sb.slave.slave_status.getName.return_value = name
            slavelist.append(sb)

    def createBuilder(self, name, slavenames=None, startSlavenames=None):
        bldr = builder.Builder(name, _addServices=False)
        self.factory = factory.BuildFactory()

        def getSlaves(param):
            return param.keys() if list and isinstance(param, dict) else []

        config_args = dict(name=name, builddir="bdir",
                           slavebuilddir="sbdir", project='default', factory=self.factory)

        if slavenames:
            config_args['slavenames'] = getSlaves(slavenames)

        if startSlavenames:
            config_args['startSlavenames'] = getSlaves(startSlavenames)

        bldr.config = config.BuilderConfig(**config_args)
        self.botmaster.builders[name] = bldr
        self.addSlavesToList(bldr.slaves, slavenames)
        self.addSlavesToList(bldr.startSlaves, startSlavenames)

    @defer.inlineCallbacks
    def setUp(self):
        yield self.setUpConnectorComponent(
            table_names=['buildrequests', 'buildrequest_claims', 'buildsets', 'buildset_properties'])

        self.db.buildrequests = buildrequests.BuildRequestsConnectorComponent(self.db)
        self.db.master.getObjectId = lambda : defer.succeed(self.MASTER_ID)
        self.botmaster = mock.Mock(name='botmaster')
        self.botmaster.builders = {}
        self.master = self.botmaster.master = mock.Mock(name='master')
        self.master.db = self.db
        self.brd = buildrequestdistributor.KatanaBuildRequestDistributor(self.botmaster)
        self.brd.startService()
        self.MASTER_ID = 1

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.tearDownConnectorComponent()
        if self.brd.running:
            yield self.brd.stopService()

    @defer.inlineCallbacks
    def test_getNextPriorityBuilderUnclaimedQueue(self):
        breqs = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="bldr1",
                                 priority=20, submitted_at=1449578391),
                 fakedb.BuildRequest(id=2, buildsetid=2, buildername="bldr2",
                                 priority=50, submitted_at=1450171039),
                 fakedb.BuildRequest(id=3, buildsetid=3, buildername="bldr1",
                                     priority=100,submitted_at=1449578391,
                                     results=RESUME, complete=0)]

        breqsclaims = [fakedb.BuildRequestClaim(brid=3, objectid=self.MASTER_ID, claimed_at=1449578391)]

        yield self.insertTestData(breqs + breqsclaims)

        self.createBuilder(name='bldr2', slavenames={'slave-01': False}, startSlavenames={'slave-02': True})
        builder = yield self.brd._getNextPriorityBuilder(queue=Queue.unclaimed)

        self.assertEquals(builder.name, 'bldr2')

    @defer.inlineCallbacks
    def test_getNextPriorityBuilderResumeQueue(self):
        breqs = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="bldr1",
                                 priority=20, submitted_at=1449578391, results=RESUME, complete=0),
                 fakedb.BuildRequest(id=2, buildsetid=2, buildername="bldr2",
                                 priority=50, submitted_at=1450171039, results=RESUME, complete=0),
                 fakedb.BuildRequest(id=3, buildsetid=3, buildername="bldr1",
                                     priority=100,submitted_at=1449578391)]

        breqsclaims = [fakedb.BuildRequestClaim(brid=1, objectid=self.MASTER_ID, claimed_at=1449578391),
                       fakedb.BuildRequestClaim(brid=2, objectid=self.MASTER_ID, claimed_at=1450171039)]

        yield self.insertTestData(breqs + breqsclaims)

        self.createBuilder(name='bldr2', slavenames={'slave-01': True}, startSlavenames={'slave-02': False})
        builder = yield self.brd._getNextPriorityBuilder(queue=Queue.resume)

        self.assertEquals(builder.name, 'bldr2')

    @defer.inlineCallbacks
    def test_getNextPriorityBuilderUnknownBuilder(self):
        breqs = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="bldr1",priority=20, submitted_at=1449578391),
                 fakedb.BuildRequest(id=2, buildsetid=2, buildername="bldr2", priority=50, submitted_at=1450171039)]

        yield self.insertTestData(breqs)

        self.createBuilder(name='bldr1', slavenames={'slave-01': True}, startSlavenames={'slave-02': True})

        self.log = []
        self.expectedLog =["_getNextPriorityBuilder found 2 buildrequests in the 'unclaimed' Queue",
                           "Not available slaves in 'startSlavenames' list "
                           "to process buildrequest.id 2 for builder bldr2"]
        def addLog(value):
            self.log.append(value)

        self.patch(log, 'msg', addLog)

        builder = yield self.brd._getNextPriorityBuilder(queue=Queue.unclaimed)
        # builder could be removed from master after reconfiguration
        # in this case brd should pick next high priority builder and a message should be added to log
        self.assertEquals(builder.name, 'bldr1')
        self.assertEquals(self.log, self.expectedLog)

    @defer.inlineCallbacks
    def test_getNextPriorityBuilderEmptyQueue(self):
        builder = yield self.brd._getNextPriorityBuilder(queue=Queue.unclaimed)
        self.assertEquals(builder, None)
        builder = yield self.brd._getNextPriorityBuilder(queue=Queue.resume)
        self.assertEquals(builder, None)

    @defer.inlineCallbacks
    def test_getNextPriorityBuilderCheckAvailableSlavesInPool(self):
        breqs = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="bldr2", results=RESUME, complete=0,
                                     priority=20, submitted_at=1449578391, slavepool=Slavepool.slavenames),
                 fakedb.BuildRequest(id=2, buildsetid=2, buildername="bldr1",
                                     priority=50, submitted_at=1450171039, slavepool=Slavepool.startSlavenames,
                                     results=RESUME, complete=0)]

        breqsclaims = [fakedb.BuildRequestClaim(brid=1, objectid=self.MASTER_ID, claimed_at=1449578391),
                       fakedb.BuildRequestClaim(brid=2, objectid=self.MASTER_ID, claimed_at=1450171039)]

        self.createBuilder(name='bldr1', slavenames={'slave-01': True}, startSlavenames={'slave-02': False})
        self.createBuilder(name='bldr2', slavenames={'slave-01': True}, startSlavenames={'slave-02': False})

        yield self.insertTestData(breqs + breqsclaims)

        builder = yield self.brd._getNextPriorityBuilder(queue=Queue.resume)

        self.assertEquals(builder.name, "bldr2")

    @defer.inlineCallbacks
    def test_getNextPriorityBuilderNotAvailableSlavesToProcessRequests(self):
        breqs = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="bldr1",
                                 priority=20, submitted_at=1449578391),
                 fakedb.BuildRequest(id=2, buildsetid=2, buildername="bldr2",
                                 priority=50, submitted_at=1450171039),
                 fakedb.BuildRequest(id=3, buildsetid=3, buildername="bldr1",
                                     priority=100,submitted_at=1449578391,
                                     results=RESUME, complete=0)]

        breqsclaims = [fakedb.BuildRequestClaim(brid=3, objectid=self.MASTER_ID, claimed_at=1449578391)]

        self.createBuilder(name='bldr1', slavenames={'slave-01': False}, startSlavenames={'slave-02': False})
        self.createBuilder(name='bldr2', slavenames={'slave-01': False}, startSlavenames={'slave-02': False})

        yield self.insertTestData(breqs + breqsclaims)

        builder = yield self.brd._getNextPriorityBuilder(queue=Queue.unclaimed)
        self.assertEquals(builder, None)

        builder = yield self.brd._getNextPriorityBuilder(queue=Queue.resume)
        self.assertEquals(builder, None)

    @defer.inlineCallbacks
    def test_getNextPriorityBuilderSelectedSlaveUnclaimQueue(self):
        breqs = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="bldr2",
                                     priority=2, submitted_at=1450171024),
                 fakedb.BuildRequest(id=2, buildsetid=2, buildername="bldr1",
                                     priority=50, submitted_at=1450171039)]

        breqsprop = [fakedb.BuildsetProperty(buildsetid=2,
                                             property_name='selected_slave',
                                             property_value='["slave-01", "Force Build Form"]')]

        yield self.insertTestData(breqs + breqsprop)

        self.createBuilder(name='bldr1', slavenames={'slave-01': False, 'slave-02': True})
        self.createBuilder(name='bldr2', slavenames={'slave-01': True, 'slave-02': True})

        builder = yield self.brd._getNextPriorityBuilder(queue=Queue.unclaimed)
        # selected slave not available pick next builder
        self.assertEquals(builder.name, "bldr2")

        # selected slave available
        self.createBuilder(name='bldr1', slavenames={'slave-01': True, 'slave-02': True})
        builder = yield self.brd._getNextPriorityBuilder(queue=Queue.unclaimed)
        self.assertEquals(builder.name, "bldr1")

        # Unclaim Queue Ignored selected slave
        self.createBuilder(name='bldr1', slavenames={'slave-01': False, 'slave-02': True},
                           startSlavenames={'slave-03': True})
        self.createBuilder(name='bldr2', slavenames={'slave-01': True, 'slave-02': True},
                           startSlavenames={'slave-03': True})

        # selected slave not available pick next builder
        self.assertEquals(builder.name, "bldr1")


class KatanaBuildChooserTestCase(unittest.TestCase):

    def setUp(self):
        self.botmaster = mock.Mock(name='botmaster')
        self.botmaster.builders = {}
        self.master = self.botmaster.master = mock.Mock(name='master')
        self.master.db = fakedb.FakeDBConnector(self)
        class getCache(object):
            def get_cache(self):
                return self
            def get(self, name):
                return
        self.master.caches = fakemaster.FakeCaches()
        self.brd = buildrequestdistributor.KatanaBuildRequestDistributor(self.botmaster)
        self.brd.startService()

        self.startedBuilds = []

        # TODO: this is a terrible way to detect the "end" of the test -
        # it regularly completes too early after a simple modification of
        # a test.  Is there a better way?
        self.quiet_deferred = defer.Deferred()
        def _quiet():
            if self.quiet_deferred:
                d, self.quiet_deferred = self.quiet_deferred, None
                d.callback(None)
            else:
                self.fail("loop has already gone quiet once")
        self.brd._quiet = _quiet

        self.bldr = self.createBuilder('A')

        self.base_rows = [fakedb.SourceStampSet(id=1),
                          fakedb.SourceStamp(id=1, sourcestampsetid=1, codebase='c',
                                             branch="az", repository="xz", revision="ww"),
                          fakedb.Buildset(id=1, reason='because', sourcestampsetid=1,
                                          submitted_at=1300305712, results=-1),
                          fakedb.BuildRequest(id=1, buildsetid=1, buildername="A", priority=15,
                                              submitted_at=130000)]

        self.pending_requests = [fakedb.SourceStampSet(id=1),
                                 fakedb.SourceStamp(id=1, sourcestampsetid=1, branch='az',
                                                    revision='az', codebase='c', repository='z'),
                                 fakedb.SourceStamp(id=2, sourcestampsetid=1, branch='bw',
                                                    revision='bz', codebase='f', repository='w'),
                                 fakedb.SourceStampSet(id=2),
                                 fakedb.SourceStamp(id=3, sourcestampsetid=2, branch='az',
                                                    revision='az', codebase='c', repository='z'),
                                 fakedb.SourceStamp(id=4, sourcestampsetid=2, branch='bw',
                                                    revision='bz', codebase='f', repository='w'),
                                 fakedb.Buildset(id=1, sourcestampsetid=1, reason='foo',
                                                 submitted_at=1300305712, results=-1),
                                 fakedb.Buildset(id=2, sourcestampsetid=2, reason='foo',
                                                 submitted_at=1300305712, results=-1),
                                 fakedb.BuildRequest(id=1, buildsetid=1, buildername='A',
                                                     priority=13, submitted_at=1300305712, results=-1),
                                 fakedb.BuildRequest(id=2, buildsetid=2, buildername='A',
                                                     priority=13, submitted_at=1300305712, results=-1)]

    def tearDown(self):
        if self.brd.running:
            return self.brd.stopService()

    def createBuilder(self, name):

        bldr = builder.Builder(name, _addServices=False)

        self.botmaster.builders[name] = bldr
        bldr.building = []

        def maybeStartBuild(slave, builds):
            self.startedBuilds.append((slave.name, builds))
            self.bldr.building = [ mock.Mock()]
            self.bldr.building[0].requests = []
            self.bldr.building[0].requests.extend(builds)
            return defer.succeed(True)

        bldr.maybeStartBuild = maybeStartBuild
        bldr.canStartWithSlavebuilder = lambda _: True
        bldr.maybeUpdateMergedBuilds = lambda brid, buildnumber, brids: True

        bldr.slaves = []
        self.factory = factory.BuildFactory()

        config_args = dict(name=name, slavename="slave-01", builddir="bdir",
                     slavebuilddir="sbdir", project='default', factory=self.factory)

        bldr.config = config.BuilderConfig(**config_args)

        def canStartBuild(*args):
            can = bldr.config.canStartBuild
            return not can or can(*args)
        bldr.canStartBuild = canStartBuild

        return bldr

    def addSlaves(self, slavebuilders):
        """C{slaves} maps name : available"""
        for name, avail in slavebuilders.iteritems():
            sb = mock.Mock(spec=['isAvailable'], name=name)
            sb.name = name
            sb.isAvailable.return_value = avail
            sb.slave = mock.Mock()
            sb.slave.slave_status = mock.Mock(spec=['getName'])
            sb.slave.slave_status.getName.return_value = name
            self.bldr.slaves.append(sb)

    def assertBuildsStarted(self, exp):
        # munge builds_started into (slave, [brids])
        builds_started = [
                (slave, [br.id for br in breqs])
                for (slave, breqs) in self.startedBuilds ]
        self.assertEqual(sorted(builds_started), sorted(exp))

    def assertBuildingRequets(self, exp):
        builds_started = [br.id for br in self.bldr.building[0].requests]
        self.assertEqual(sorted(builds_started), sorted(exp))

    @defer.inlineCallbacks
    def do_test_maybeStartBuildsOnBuilder(self, rows=[], exp_claims=[], exp_brids=None, exp_builds=[]):
        yield self.master.db.insertTestData(rows)

        yield self.brd._maybeStartBuildsOnBuilder(self.bldr)

        self.master.db.buildrequests.assertMyClaims(exp_claims)

        if exp_brids:
                self.assertBuildingRequets(exp_brids)
        if exp_builds:
            self.assertBuildsStarted(exp_builds)

    @defer.inlineCallbacks
    def test_maybeStartBuildByPriority(self):

        self.addSlaves({'slave-01': 1})

        rows = self.base_rows + [fakedb.SourceStamp(id=2, sourcestampsetid=1,
                                                    branch='bw', revision='bz',
                                                    codebase='f', repository='w'),
                                 fakedb.SourceStampSet(id=2),
                                 fakedb.SourceStamp(id=3, sourcestampsetid=2,
                                                    branch='a', revision='az', codebase='c', repository='z'),
                                 fakedb.SourceStamp(id=4, sourcestampsetid=2, branch='bw',
                                                    revision='wz', codebase='f', repository='w'),
                                 fakedb.Buildset(id=2, sourcestampsetid=2, reason='foo',
                                                 submitted_at=1300305712, results=-1),
                                 fakedb.BuildRequest(id=2, buildsetid=2, buildername='A',
                                                     submitted_at=1300305712, priority=75, results=-1)]

        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows,
                exp_claims=[2], exp_builds=[('slave-01', [2])])

    @defer.inlineCallbacks
    def test_maybeStartBuild_mergeBuilding(self):
        self.addSlaves({'slave-01':1})

        yield self.do_test_maybeStartBuildsOnBuilder(rows=self.base_rows, exp_claims=[1], exp_brids=[1])

        self.master.db.sourcestampsets.insertTestData([fakedb.SourceStampSet(id=2)])
        self.master.db.sourcestamps.insertTestData([fakedb.SourceStamp(id=2, sourcestampsetid=2, codebase='c',
                                                                       branch="az", repository="xz", revision="ww")])
        self.master.db.buildsets.insertTestData([fakedb.Buildset(id=2, reason='because', sourcestampsetid=2)])
        self.master.db.buildrequests.insertTestData([fakedb.BuildRequest(id=2, buildsetid=2, buildername="A",
                                                                  submitted_at=130000)])

        yield self.do_test_maybeStartBuildsOnBuilder(exp_claims=[1, 2], exp_brids=[1, 2])

    @defer.inlineCallbacks
    def test_maybeStartBuild_mergeBuildingCouldNotMerge(self):
        self.addSlaves({'slave-01':1})

        yield self.do_test_maybeStartBuildsOnBuilder(rows=self.base_rows, exp_claims=[1], exp_brids=[1])

        self.master.db.sourcestampsets.insertTestData([fakedb.SourceStampSet(id=2)])
        self.master.db.sourcestamps.insertTestData([fakedb.SourceStamp(id=2, sourcestampsetid=2, codebase='c',
                                                                       branch="az", repository="xz", revision="bb")])
        self.master.db.buildsets.insertTestData([fakedb.Buildset(id=2, reason='because', sourcestampsetid=2)])
        self.master.db.buildrequests.insertTestData([fakedb.BuildRequest(id=2, buildsetid=2, buildername="A",
                                                                  submitted_at=130000)])

        yield self.do_test_maybeStartBuildsOnBuilder(exp_claims=[1, 2], exp_brids=[2])

    @defer.inlineCallbacks
    def test_maybeStartBuild_selectedSlave(self):
        self.addSlaves({'slave-01': 1, 'slave-02': 1, 'slave-03': 1, 'slave-04': 1})

        rows = self.base_rows + [fakedb.BuildsetProperty(buildsetid=1, property_name='selected_slave',
                                        property_value='["slave-03", "Force Build Form"]')]

        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows,
                exp_claims=[1], exp_builds=[('slave-03', [1])])

    @defer.inlineCallbacks
    def test_mergePending_CodebasesMatchSelectedSlave(self):
        self.addSlaves({'slave-01': 1, 'slave-02': 1})

        rows = self.pending_requests + [fakedb.BuildsetProperty(buildsetid=1,
                                                                property_name='selected_slave',
                                                                property_value='["slave-02", "Force Build Form"]')]

        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows,
                exp_claims=[1], exp_builds=[('slave-02', [1])])

    @defer.inlineCallbacks
    def test_mergePending_CodebasesMatchForceRebuild(self):
        self.addSlaves({'slave-01': 1})

        rows = self.pending_requests + [fakedb.BuildsetProperty(buildsetid=1,
                                                                property_name='force_rebuild',
                                                                property_value='[true, "Force Build Form"]')]

        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows,
                exp_claims=[1], exp_builds=[('slave-01', [1])])


    @defer.inlineCallbacks
    def test_mergePending_CodebasesMatchForceChainRebuild(self):
        self.addSlaves({'slave-01': 1})

        rows = self.pending_requests + [fakedb.BuildsetProperty(buildsetid=1,
                                                                property_name='force_chain_rebuild',
                                                                property_value='[true, "Force Build Form"]')]

        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows,
                exp_claims=[1], exp_builds=[('slave-01', [1])])

    @defer.inlineCallbacks
    def test_mergePending_CodebasesMatchBuildLatestRev(self):
        self.addSlaves({'slave-01': 1})

        rows = self.pending_requests + [fakedb.BuildsetProperty(buildsetid=1, property_name='buildLatestRev',
                                        property_value='[true, "Force Build Form"]')]

        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows,
                exp_claims=[1, 2], exp_builds=[('slave-01', [1, 2])])

    @defer.inlineCallbacks
    def test_mergePending_CodebaseDoesNotMatch(self):
        self.addSlaves({'slave-01': 1})

        rows = [fakedb.SourceStampSet(id=1),
                fakedb.SourceStamp(id=1, sourcestampsetid=1, branch='az', revision='az', codebase='c', repository='z'),
                fakedb.SourceStamp(id=2, sourcestampsetid=1, branch='bw', revision='bz', codebase='f', repository='w'),
                fakedb.SourceStampSet(id=2),
                fakedb.SourceStamp(id=3, sourcestampsetid=2, branch='a', revision='az', codebase='c', repository='z'),
                fakedb.SourceStamp(id=4, sourcestampsetid=2, branch='bw', revision='wz', codebase='f', repository='w'),
                fakedb.Buildset(id=1, sourcestampsetid=1, reason='foo',
                    submitted_at=1300305712, results=-1),
                fakedb.Buildset(id=2, sourcestampsetid=2, reason='foo',
                    submitted_at=1300305712, results=-1),
                fakedb.BuildRequest(id=1, buildsetid=1, buildername='A',
                    priority=13, submitted_at=1300305712, results=-1),
                fakedb.BuildRequest(id=2, buildsetid=2, buildername='A',
                    priority=13, submitted_at=1300305712, results=-1)]

        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows,
                exp_claims=[1], exp_builds=[('slave-01', [1])])
