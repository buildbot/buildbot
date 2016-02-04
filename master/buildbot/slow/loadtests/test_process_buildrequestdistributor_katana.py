from twisted.trial import unittest
from twisted.internet import defer
from buildbot.test.fake import fakedb
from buildbot.db.buildrequests import Queue
from buildbot.status.results import RESUME, BEGINNING
from buildbot.process.buildrequest import Priority
from buildbot.test.util.katanabuildrequestdistributor import KatanaBuildRequestDistributorTestSetup
import cProfile, pstats


class TestKatanaBuildRequestDistributorUnderLoad(unittest.TestCase,
                                                 KatanaBuildRequestDistributorTestSetup):

    @defer.inlineCallbacks
    def setUp(self):
        yield self.setUpComponents()
        self.setUpKatanaBuildRequestDistributor()

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.tearDownComponents()
        self.stopKatanaBuildRequestDistributor()

    @defer.inlineCallbacks
    def profileAsyncFunc(self, expected_total_tt, func, **kwargs):
        pr = cProfile.Profile()
        pr.enable()
        res = yield func(**kwargs)
        pr.disable()
        ps = pstats.Stats(pr).sort_stats('time')
        ps.print_stats()
        # TODO: we should collect the profile data and compare timing
        # expected_total_tt is a reference time
        defer.returnValue(res)

    @defer.inlineCallbacks
    def generateBuildLoad(self):
        self.lastbrid = 0
        self.lastbuilderid = 0
        self.testdata = []

        def insertBuildrequests(buildername, priority, xrange, results=BEGINNING, selected_slave=None, complete=0):
            self.testdata += [fakedb.BuildRequest(id=self.lastbrid+id, buildsetid=self.lastbrid+id, buildername=buildername,
                                            priority=priority,results=results,
                                            complete=complete, submitted_at=1449578391) for id in xrange]

            if results == RESUME:
                breqsclaim = [fakedb.BuildRequestClaim(brid=self.lastbrid+id,
                                                       objectid=self.MASTER_ID, claimed_at=1449578391) for id in xrange]
                self.testdata += breqsclaim

            if selected_slave:
                self.testdata += [fakedb.BuildsetProperty(buildsetid=self.lastbrid+id,
                                                          property_name='selected_slave',
                                                          property_value='["%s", "Force Build Form"]' % selected_slave)
                                  for id in xrange]

            self.lastbrid += len(xrange)


        def createBuildersWithLoad(priority, slavenames, startSlavenames,
                                   builders_xrange, breqs_xrange, selected_slave=None):
            for id in builders_xrange:
                buildername = 'bldr%d' % (self.lastbuilderid+id)
                self.setupBuilderInMaster(name=buildername, slavenames=slavenames, startSlavenames=startSlavenames)
                insertBuildrequests(buildername, priority, breqs_xrange, selected_slave)
                insertBuildrequests(buildername, priority, breqs_xrange, results=RESUME, selected_slave=selected_slave)

            self.lastbuilderid += len(builders_xrange)

        createBuildersWithLoad(priority=Priority.Default, slavenames={'slave-01': True},
                               startSlavenames={'slave-02': True}, builders_xrange=xrange(1, 6),
                               breqs_xrange=xrange(1, 350))


        # breqs has selected slave x slave-03
        createBuildersWithLoad(priority=Priority.VeryHigh, slavenames={'slave-03': False, 'slave-04': True},
                               startSlavenames={'slave-05': False}, builders_xrange=xrange(1, 6),
                               breqs_xrange=xrange(1, 700), selected_slave='slave-03')

        # breqs dont have available slave
        createBuildersWithLoad(priority=Priority.Emergency, slavenames={'slave-05': False},
                               startSlavenames={'slave-06': False}, builders_xrange=xrange(1, 6),
                               breqs_xrange=xrange(1, 700))


        createBuildersWithLoad(priority=Priority.High, slavenames={'slave-07': True},
                               startSlavenames={'slave-08': True}, builders_xrange=xrange(1, 701),
                               breqs_xrange=xrange(1, 2))

        yield self.insertTestData(self.testdata)

    @defer.inlineCallbacks
    def test_getNextPriorityBuilderUnclaimedQueueUnderLoad(self):
        yield self.generateBuildLoad()
        builder =  yield self.profileAsyncFunc(0.5, self.brd._getNextPriorityBuilder, queue=Queue.unclaimed)
        self.assertEqual(builder.name, 'bldr16')

    @defer.inlineCallbacks
    def test_getNextPriorityBuilderResumeQueueUnderLoad(self):
        yield self.generateBuildLoad()
        builder =  yield self.profileAsyncFunc(1, self.brd._getNextPriorityBuilder, queue=Queue.resume)
        self.assertEquals(builder.name, 'bldr16')

    def test_maybeStartBuildsOnUnderLoad(self):
        self.brd.maybeStartBuildsOn([])
        def check(_):
            self.checkBRDCleanedUp()
        self.quiet_deferred.addCallback(check)
        return self.quiet_deferred
