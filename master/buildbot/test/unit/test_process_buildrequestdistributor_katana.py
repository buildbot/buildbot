from twisted.trial import unittest
from twisted.internet import defer
from twisted.python import log
from buildbot.test.fake import fakedb, fakemaster
from buildbot.process import buildrequestdistributor
from buildbot.process.buildrequestdistributor import Slavepool
from buildbot.process import builder, factory
from buildbot import config
import mock
from buildbot.db.buildrequests import Queue
from buildbot.status.results import RESUME
from buildbot.test.util.katanabuildrequestdistributor import KatanaBuildRequestDistributorTestSetup


class TestKatanaBuildRequestDistributor(unittest.TestCase,
                                        KatanaBuildRequestDistributorTestSetup):

    @defer.inlineCallbacks
    def setUp(self):
        yield self.setUpComponents()
        self.brd = buildrequestdistributor.KatanaBuildRequestDistributor(self.botmaster)
        self.brd.startService()

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.tearDownComponents()
        if self.brd.running:
            yield self.brd.stopService()

    # _getNextPriorityBuilder Tests

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

        self.setupBuilderInMaster(name='bldr2', slavenames={'slave-01': False}, startSlavenames={'slave-02': True})
        builder, brid, slavepool = yield self.brd._getNextPriorityBuilder(queue=Queue.unclaimed)

        self.assertEquals((builder.name, brid, slavepool[0].name) , ('bldr2', 2,'slave-02'))

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

        self.setupBuilderInMaster(name='bldr2', slavenames={'slave-01': True}, startSlavenames={'slave-02': False})
        builder, brid, slavepool = yield self.brd._getNextPriorityBuilder(queue=Queue.resume)

        self.assertEquals((builder.name, brid, slavepool[0].name) , ('bldr2', 2,'slave-01'))

    @defer.inlineCallbacks
    def test_getNextPriorityBuilderUnknownBuilder(self):
        breqs = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="bldr1", priority=20, submitted_at=1449578391),
                 fakedb.BuildRequest(id=2, buildsetid=2, buildername="bldr2", priority=50, submitted_at=1450171039)]

        yield self.insertTestData(breqs)

        self.setupBuilderInMaster(name='bldr1', slavenames={'slave-01': True}, startSlavenames={'slave-02': True})

        self.log = []
        self.expectedLog =["_getNextPriorityBuilder found 2 buildrequests in the 'unclaimed' Queue",
                           "Not available slaves in 'startSlavenames' list "
                           "to process buildrequest.id 2 for builder bldr2"]
        def addLog(value):
            self.log.append(value)

        self.patch(log, 'msg', addLog)

        builder, brid, slavepool = yield self.brd._getNextPriorityBuilder(queue=Queue.unclaimed)
        # builder could be removed from master after reconfiguration
        # in this case brd should pick next high priority builder and a message should be added to log
        self.assertEquals((builder.name, brid, slavepool[0].name) , ('bldr1', 1, 'slave-02'))
        self.assertEquals(self.log, self.expectedLog)

    @defer.inlineCallbacks
    def test_getNextPriorityBuilderEmptyQueue(self):
        builder, brid, slavepool = yield self.brd._getNextPriorityBuilder(queue=Queue.unclaimed)
        self.assertEquals(builder, None)
        builder, brid, slavepool = yield self.brd._getNextPriorityBuilder(queue=Queue.resume)
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

        self.setupBuilderInMaster(name='bldr1', slavenames={'slave-01': True}, startSlavenames={'slave-02': False})
        self.setupBuilderInMaster(name='bldr2', slavenames={'slave-01': True}, startSlavenames={'slave-02': False})

        yield self.insertTestData(breqs + breqsclaims)

        builder, brid, slavepool = yield self.brd._getNextPriorityBuilder(queue=Queue.resume)

        self.assertEquals((builder.name, brid, slavepool[0].name) , ('bldr2', 1, 'slave-01'))

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

        self.setupBuilderInMaster(name='bldr1', slavenames={'slave-01': False}, startSlavenames={'slave-02': False})
        self.setupBuilderInMaster(name='bldr2', slavenames={'slave-01': False}, startSlavenames={'slave-02': False})

        yield self.insertTestData(breqs + breqsclaims)

        builder, brid, slavepool = yield self.brd._getNextPriorityBuilder(queue=Queue.unclaimed)
        self.assertEquals(builder, None)

        builder, brid, slavepool = yield self.brd._getNextPriorityBuilder(queue=Queue.resume)
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

        self.setupBuilderInMaster(name='bldr1', slavenames={'slave-01': False, 'slave-02': True})
        self.setupBuilderInMaster(name='bldr2', slavenames={'slave-01': True, 'slave-02': True})

        builder, brid, slavepool = yield self.brd._getNextPriorityBuilder(queue=Queue.unclaimed)
        # selected slave not available pick next builder
        self.assertEquals((builder.name, brid, slavepool[0].name), ("bldr2", 1, 'slave-02'))

        # selected slave available
        self.slaves['slave-01'].isAvailable.return_value = True
        builder, brid, slavepool = yield self.brd._getNextPriorityBuilder(queue=Queue.unclaimed)
        self.assertEquals((builder.name, brid, slavepool[0].name), ("bldr1", 2, 'slave-02'))

        # Unclaim queue should ignored selected slave
        self.setupBuilderInMaster(name='bldr1', slavenames={'slave-01': False, 'slave-02': True},
                           startSlavenames={'slave-03': True})
        self.setupBuilderInMaster(name='bldr2', slavenames={'slave-01': True, 'slave-02': True},
                           startSlavenames={'slave-03': True})

        builder, brid, slavepool = yield self.brd._getNextPriorityBuilder(queue=Queue.unclaimed)
        self.assertEquals((builder.name, brid, slavepool[0].name), ("bldr1", 2, 'slave-03'))

    @defer.inlineCallbacks
    def test_getNextPriorityBuilderSelectedSlaveResumeQueue(self):
        breqs = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="bldr2", results=RESUME, complete=0,
                                     priority=20, submitted_at=1449578391),
                 fakedb.BuildRequest(id=2, buildsetid=2, buildername="bldr1",
                                     priority=50, submitted_at=1450171039,
                                     results=RESUME, complete=0)]

        breqsclaims = [fakedb.BuildRequestClaim(brid=1, objectid=self.MASTER_ID, claimed_at=1449578391),
                       fakedb.BuildRequestClaim(brid=2, objectid=self.MASTER_ID, claimed_at=1450171039)]

        breqsprop = [fakedb.BuildsetProperty(buildsetid=2,
                                             property_name='selected_slave',
                                             property_value='["slave-01", "Force Build Form"]')]

        yield self.insertTestData(breqs + breqsclaims + breqsprop)
        self.setupBuilderInMaster(name='bldr1', slavenames={'slave-01': False, 'slave-02': True},
                           startSlavenames={'slave-03': True})
        self.setupBuilderInMaster(name='bldr2', slavenames={'slave-01': False, 'slave-02': True},
                           startSlavenames={'slave-03': True})

        builder, brid, slavepool = yield self.brd._getNextPriorityBuilder(queue=Queue.resume)
        # selected slave not available pick next builder
        self.assertEquals((builder.name, brid, slavepool[0].name), ("bldr2", 1, 'slave-02'))
        # selected slave is available
        self.slaves['slave-01'].isAvailable.return_value = True
        builder, brid, slavepool = yield self.brd._getNextPriorityBuilder(queue=Queue.resume)
        self.assertEquals((builder.name, brid, slavepool[0].name), ("bldr1", 2, 'slave-02'))

    @defer.inlineCallbacks
    def test_getNextPriorityBuilderIgnoreSelectedSlaveResumeQueue(self):
        breqs = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="bldr2", results=RESUME, complete=0,
                                     priority=20, submitted_at=1449578391),
                 fakedb.BuildRequest(id=2, buildsetid=2, buildername="bldr1",
                                     priority=50, submitted_at=1450171039,
                                     results=RESUME, complete=0, slavepool=Slavepool.startSlavenames)]

        breqsclaims = [fakedb.BuildRequestClaim(brid=1, objectid=self.MASTER_ID, claimed_at=1449578391),
                       fakedb.BuildRequestClaim(brid=2, objectid=self.MASTER_ID, claimed_at=1450171039)]

        breqsprop = [fakedb.BuildsetProperty(buildsetid=2,
                                             property_name='selected_slave',
                                             property_value='["slave-01", "Force Build Form"]')]

        yield self.insertTestData(breqs + breqsclaims + breqsprop)

        self.setupBuilderInMaster(name='bldr1', slavenames={'slave-01': False, 'slave-02': True},
                           startSlavenames={'slave-03': True})
        self.setupBuilderInMaster(name='bldr2', slavenames={'slave-01': False, 'slave-02': True},
                           startSlavenames={'slave-03': True})

        builder, brid, slavepool = yield self.brd._getNextPriorityBuilder(queue=Queue.resume)
        self.assertEquals((builder.name, brid, slavepool[0].name), ("bldr1", 2, 'slave-03'))


class TestKatanaBuildChooser(KatanaBuildRequestDistributorTestSetup, unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        yield self.setUpComponents()
        self.brd = buildrequestdistributor.KatanaBuildRequestDistributor(self.botmaster)
        self.brd.startService()

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.tearDownComponents()
        if self.brd.running:
            yield self.brd.stopService()

    @defer.inlineCallbacks
    def instertTestDataPopNextBuild(self, slavepool):
        breqs = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="bldr1", results=RESUME, complete=0,
                                     priority=20, submitted_at=1449578391),
                 fakedb.BuildRequest(id=2, buildsetid=2, buildername="bldr1",
                                     priority=50, submitted_at=1450171039,
                                     results=RESUME, complete=0, slavepool=slavepool)]

        breqsclaims = [fakedb.BuildRequestClaim(brid=1, objectid=self.MASTER_ID, claimed_at=1449578391),
                       fakedb.BuildRequestClaim(brid=2, objectid=self.MASTER_ID, claimed_at=1450171039)]

        breqsprop = [fakedb.BuildsetProperty(buildsetid=2,
                                             property_name='selected_slave',
                                             property_value='["slave-01", "Force Build Form"]')]

        bset = [fakedb.Buildset(id=1, sourcestampsetid=1),
                fakedb.Buildset(id=2, sourcestampsetid=2)]

        sstamp = [fakedb.SourceStamp(sourcestampsetid=1, branch='branch_A'),
                  fakedb.SourceStamp(sourcestampsetid=2, branch='branch_B')]

        yield self.insertTestData(breqs + bset + breqsprop + sstamp + breqsclaims)

    @defer.inlineCallbacks
    def insertTestDataUnclaimedBreqs(self):
        breqs = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="bldr1",
                                     priority=20, submitted_at=1450171024),
                 fakedb.BuildRequest(id=2, buildsetid=2, buildername="bldr1",
                                     priority=50, submitted_at=1449668061),
                fakedb.BuildRequest(id=3, buildsetid=3, buildername="bldr1",
                                    priority=100, submitted_at=1450171039)]

        bset = [fakedb.Buildset(id=1, sourcestampsetid=1),
                fakedb.Buildset(id=2, sourcestampsetid=2),
                fakedb.Buildset(id=3, sourcestampsetid=3)]

        sstamp = [fakedb.SourceStamp(sourcestampsetid=1, branch='branch_A'),
                  fakedb.SourceStamp(sourcestampsetid=2, branch='branch_B'),
                  fakedb.SourceStamp(sourcestampsetid=3, branch='branch_C')]

        yield self.insertTestData(breqs + bset + sstamp)


    @defer.inlineCallbacks
    def test_popNextBuild(self):
        self.bldr = self.setupBuilderInMaster(name='bldr1',
                                              slavenames={'slave-01': False},
                                              startSlavenames={'slave-02': True})

        yield self.insertTestDataUnclaimedBreqs()

        builder, brid, slavepool = yield self.brd._getNextPriorityBuilder(queue=Queue.unclaimed)
        self.buildChooser = buildrequestdistributor.KatanaBuildChooser(builder, brid, slavepool, self.master)

        slave, breq = yield self.buildChooser.popNextBuild()

        self.assertEquals((slave.name, breq.id), ('slave-02', 3))

    @defer.inlineCallbacks
    def test_popNextBuildToResumeShouldSkipSelectedSlave(self):
        self.bldr = self.setupBuilderInMaster(name='bldr1',
                                              slavenames={'slave-01': False, 'slave-02': True},
                                              startSlavenames={'slave-03': True})

        yield self.instertTestDataPopNextBuild(slavepool=Slavepool.startSlavenames)
        builder, brid, slavepool = yield self.brd._getNextPriorityBuilder(queue=Queue.resume)
        self.buildChooser = buildrequestdistributor.KatanaBuildChooser(self.bldr, brid, slavepool, self.master)

        slave, breq = yield self.buildChooser.popNextBuildToResume()

        self.assertEquals((slave.name, breq.id), ('slave-03', 2))

    @defer.inlineCallbacks
    def test_popNextBuildToResumeShouldCheckSelectedSlave(self):
        self.bldr = self.setupBuilderInMaster(name='bldr1',
                                              slavenames={'slave-01': False, 'slave-02': True},
                                              startSlavenames={'slave-03': True})

        yield self.instertTestDataPopNextBuild(slavepool=Slavepool.slavenames)

        builder, brid, slavepool = yield self.brd._getNextPriorityBuilder(queue=Queue.resume)
        self.buildChooser = buildrequestdistributor.KatanaBuildChooser(builder, brid, slavepool, self.master)

        slave, breq = yield self.buildChooser.popNextBuildToResume()

        self.assertEquals((slave.name, breq.id), ('slave-02', 1))

    @defer.inlineCallbacks
    def test_fetchResumeBrdictsSortedByPriority(self):
        self.bldr = self.setupBuilderInMaster(name='bldr1',
                                              slavenames={'slave-01': True},
                                              startSlavenames={'slave-02': False})

        breqs = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="bldr1",
                                    priority=100, submitted_at=1450171039),
                 fakedb.BuildRequest(id=2, buildsetid=2, buildername="bldr1",
                                     priority=20,submitted_at=1449579016,
                                     results=RESUME, complete=0),
                 fakedb.BuildRequest(id=3, buildsetid=3, buildername="bldr1",
                                     priority=75, submitted_at=1450451019,
                                     results=RESUME, complete=0),
                 fakedb.BuildRequest(id=4, buildsetid=4, buildername="bldr3",
                                     priority=100, submitted_at=1446632022,
                                     results=RESUME, complete=0)]

        breqsclaims = [fakedb.BuildRequestClaim(brid=2, objectid=self.MASTER_ID, claimed_at=1300103810),
                       fakedb.BuildRequestClaim(brid=3, objectid=self.MASTER_ID, claimed_at=1300103810),
                       fakedb.BuildRequestClaim(brid=4, objectid=self.MASTER_ID, claimed_at=1300103810)]

        yield self.insertTestData(breqs + breqsclaims)

        builder, brid, slavepool = yield self.brd._getNextPriorityBuilder(queue=Queue.resume)
        self.buildChooser = buildrequestdistributor.KatanaBuildChooser(builder, brid, slavepool, self.master)

        breqs = yield self.buildChooser._fetchResumeBrdicts()

        self.assertEquals([br['brid'] for br in breqs], [3])

    @defer.inlineCallbacks
    def test_fetchUnclaimedBrdictsSortedByPriority(self):
        self.bldr = self.setupBuilderInMaster(name='bldr1',
                                              slavenames={'slave-01': False},
                                              startSlavenames={'slave-02': True})

        yield self.insertTestDataUnclaimedBreqs()

        builder, brid, slavepool = yield self.brd._getNextPriorityBuilder(queue=Queue.unclaimed)
        self.buildChooser = buildrequestdistributor.KatanaBuildChooser(builder, brid, slavepool, self.master)

        breqs = yield self.buildChooser._fetchUnclaimedBrdicts()

        self.assertEquals([br['brid'] for br in breqs], [3])


class TestKatanaMaybeStartBuildsOnBuilder(KatanaBuildRequestDistributorTestSetup, unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        yield self.setUpComponents()
        self.setUpKatanaBuildRequestDistributor()
        self.startedBuilds = []

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

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.tearDownComponents()
        if self.brd.running:
            yield self.brd.stopService()

    def createBuilder(self, name):

        bldr = builder.Builder(name, _addServices=False)

        self.botmaster.builders[name] = bldr
        bldr.building = []

        def maybeStartBuild(slave, builds):
            build = mock.Mock()
            if not bldr.building:
                self.bldr.building = [build]
            else:
                self.bldr.building.append(build)

            build.build_status = mock.Mock()
            build.build_status.number = len(bldr.building)
            self.bldr.building[-1].requests = []
            self.bldr.building[-1].requests.extend(builds)
            slave.isAvailable.return_value = False

            self.startedBuilds.append((slave.name, build))

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
                (slave, [br.id for br in build.requests])
                for (slave, build) in self.startedBuilds ]
        self.assertEqual(sorted(builds_started), sorted(exp))

    def assertBuildingRequets(self, exp):
        builds_started = [br.id for br in self.bldr.building[0].requests]
        self.assertEqual(sorted(builds_started), sorted(exp))

    @defer.inlineCallbacks
    def do_test_maybeStartBuildsOnBuilder(self, rows=[], exp_brids=None, exp_builds=[]):
        yield self.insertTestData(rows)

        yield self.brd._callMaybeStartBuildsOnBuilder()

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

        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows, exp_brids=[2], exp_builds=[('slave-01', [2])])

    @defer.inlineCallbacks
    def test_maybeStartBuild_mergeBuilding(self):
        self.addSlaves({'slave-01': 1})

        yield self.do_test_maybeStartBuildsOnBuilder(rows=self.base_rows, exp_brids=[1])

        yield self.insertTestData([fakedb.SourceStampSet(id=2),
                                   fakedb.SourceStamp(id=2, sourcestampsetid=2, codebase='c',
                                                      branch="az", repository="xz", revision="ww"),
                                   fakedb.Buildset(id=2, reason='because', sourcestampsetid=2),
                                   fakedb.BuildRequest(id=2, buildsetid=2, buildername="A", submitted_at=130000)])

        yield self.do_test_maybeStartBuildsOnBuilder(exp_brids=[1, 2], exp_builds=[('slave-01', [1, 2])])

    @defer.inlineCallbacks
    def test_maybeStartBuild_mergeBuildingCouldNotMerge(self):
        self.addSlaves({'slave-01': 1})

        yield self.do_test_maybeStartBuildsOnBuilder(rows=self.base_rows, exp_brids=[1])

        yield self.insertTestData([fakedb.SourceStampSet(id=2),
                                   fakedb.SourceStamp(id=2, sourcestampsetid=2, codebase='c',
                                                      branch="az", repository="xz", revision="bb"),
                                   fakedb.Buildset(id=2, reason='because', sourcestampsetid=2),
                                   fakedb.BuildRequest(id=2, buildsetid=2, buildername="A", submitted_at=130000)])

        yield self.do_test_maybeStartBuildsOnBuilder(exp_brids=[1], exp_builds=[('slave-01', [1])])

    @defer.inlineCallbacks
    def test_maybeStartBuild_selectedSlave(self):
        self.addSlaves({'slave-01': 1, 'slave-02': 1, 'slave-03': 1, 'slave-04': 1})

        rows = self.base_rows + [fakedb.BuildsetProperty(buildsetid=1, property_name='selected_slave',
                                                         property_value='["slave-03", "Force Build Form"]')]

        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows, exp_brids=[1], exp_builds=[('slave-03', [1])])

    @defer.inlineCallbacks
    def test_mergePending_CodebasesMatchSelectedSlave(self):
        self.addSlaves({'slave-01': 1, 'slave-02': 1})

        rows = self.pending_requests + [fakedb.BuildsetProperty(buildsetid=1,
                                                                property_name='selected_slave',
                                                                property_value='["slave-02", "Force Build Form"]')]

        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows, exp_brids=[1], exp_builds=[('slave-02', [1])])

    @defer.inlineCallbacks
    def test_mergePending_CodebasesMatchForceRebuild(self):
        self.addSlaves({'slave-01': 1})

        rows = self.pending_requests + [fakedb.BuildsetProperty(buildsetid=1,
                                                                property_name='force_rebuild',
                                                                property_value='[true, "Force Build Form"]')]

        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows, exp_brids=[1], exp_builds=[('slave-01', [1])])


    @defer.inlineCallbacks
    def test_mergePending_CodebasesMatchForceChainRebuild(self):
        self.addSlaves({'slave-01': 1})

        rows = self.pending_requests + [fakedb.BuildsetProperty(buildsetid=1,
                                                                property_name='force_chain_rebuild',
                                                                property_value='[true, "Force Build Form"]')]

        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows, exp_brids=[1], exp_builds=[('slave-01', [1])])

    @defer.inlineCallbacks
    def test_mergePending_CodebasesMatchBuildLatestRev(self):
        self.addSlaves({'slave-01': 1})

        rows = self.pending_requests + [fakedb.BuildsetProperty(buildsetid=1, property_name='buildLatestRev',
                                        property_value='[true, "Force Build Form"]')]

        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows, exp_brids=[1, 2], exp_builds=[('slave-01', [1, 2])])

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

        yield self.do_test_maybeStartBuildsOnBuilder(rows=rows, exp_brids=[1], exp_builds=[('slave-01', [1])])
