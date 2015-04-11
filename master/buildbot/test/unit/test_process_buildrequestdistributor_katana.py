import unittest
from twisted.internet import defer
from buildbot.test.fake import fakedb, fakemaster
from buildbot.process import buildrequestdistributor
from buildbot.process import builder, factory
from buildbot import config
import mock

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
        self.brd = buildrequestdistributor.BuildRequestDistributor(self.botmaster)
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



    '''


    def compatiblePendingBuildRequests(self):
        return [
            fakedb.SourceStampSet(id=1),
            fakedb.SourceStamp(id=1, sourcestampsetid=1, branch='az', revision='az', codebase='c', repository='z'),
            fakedb.SourceStamp(id=2, sourcestampsetid=1, branch='bw', revision='bz', codebase='f', repository='w'),
            fakedb.SourceStampSet(id=2),
            fakedb.SourceStamp(id=3, sourcestampsetid=2, branch='az', revision='az', codebase='c', repository='z'),
            fakedb.SourceStamp(id=4, sourcestampsetid=2, branch='bw', revision='bz', codebase='f', repository='w'),
            fakedb.Buildset(id=1, sourcestampsetid=1, reason='foo',
                            submitted_at=1300305712, results=-1),
            fakedb.Buildset(id=2, sourcestampsetid=2, reason='foo',
                            submitted_at=1300305712, results=-1),
            fakedb.BuildRequest(id=1, buildsetid=1, buildername='bldr',
                                priority=13, submitted_at=1300305712, results=-1),
            fakedb.BuildRequest(id=2, buildsetid=2, buildername='bldr',
                                priority=13, submitted_at=1300305712, results=-1)
        ]

    @defer.inlineCallbacks
    def test_mergePending_CodebasesMatchSelectedSlave(self):
        yield self.makeBuilder()

        yield self.db.insertTestData(self.compatiblePendingBuildRequests() +
                                     [fakedb.BuildsetProperty(buildsetid = 1, property_name='selected_slave',
                                        property_value='["build-slave-01", "Force Build Form"]')])

        brdicts = yield defer.gatherResults([
                self.db.buildrequests.getBuildRequest(id)
                for id in (1, 2)
            ])

        res = yield self.bldr._mergeRequests(brdicts[0],
                                brdicts, builder.Builder._defaultMergeRequestFn)

        self.assertEqual(res, [brdicts[0]])

    @defer.inlineCallbacks
    def test_mergePending_CodebasesMatchForceRebuild(self):
        yield self.makeBuilder()

        yield self.db.insertTestData(self.compatiblePendingBuildRequests() +
                                     [fakedb.BuildsetProperty(buildsetid = 1, property_name='force_rebuild',
                                        property_value='[true, "Force Build Form"]')])

        brdicts = yield defer.gatherResults([
                self.db.buildrequests.getBuildRequest(id)
                for id in (1, 2)
            ])

        res = yield self.bldr._mergeRequests(brdicts[0],
                                brdicts, builder.Builder._defaultMergeRequestFn)

        self.assertEqual(res, [brdicts[0]])

    @defer.inlineCallbacks
    def test_mergePending_CodebasesMatchForceChainRebuild(self):
        yield self.makeBuilder()

        yield self.db.insertTestData(self.compatiblePendingBuildRequests() +
                                     [fakedb.BuildsetProperty(buildsetid = 1, property_name='force_chain_rebuild',
                                        property_value='[true, "Force Build Form"]')])

        brdicts = yield defer.gatherResults([
                self.db.buildrequests.getBuildRequest(id)
                for id in (1, 2)
            ])

        res = yield self.bldr._mergeRequests(brdicts[0],
                                brdicts, builder.Builder._defaultMergeRequestFn)

        self.assertEqual(res, [brdicts[0]])

    @defer.inlineCallbacks
    def test_mergePending_CodebasesMatchBuildLatestRev(self):
        yield self.makeBuilder()

        yield self.db.insertTestData(self.compatiblePendingBuildRequests() +
                                     [fakedb.BuildsetProperty(buildsetid = 1, property_name='buildLatestRev',
                                        property_value='[true, "Force Build Form"]')])

        brdicts = yield defer.gatherResults([
                self.db.buildrequests.getBuildRequest(id)
                for id in (1, 2)
            ])

        res = yield self.bldr._mergeRequests(brdicts[0],
                                brdicts, builder.Builder._defaultMergeRequestFn)

        self.assertEqual(res, [brdicts[0]])

    @defer.inlineCallbacks
    def test_mergePending_CodebasesMatch(self):
        yield self.makeBuilder()

        yield self.db.insertTestData(self.compatiblePendingBuildRequests())

        brdicts = yield defer.gatherResults([
                self.db.buildrequests.getBuildRequest(id)
                for id in (1, 2)
            ])

        res = yield self.bldr._mergeRequests(brdicts[0],
                                brdicts, builder.Builder._defaultMergeRequestFn)

        self.assertEqual(res, [brdicts[0], brdicts[1]])

    @defer.inlineCallbacks
    def test_mergePending_CodebaseDoesNotMatch(self):
        yield self.makeBuilder()

        yield self.db.insertTestData([
                fakedb.SourceStampSet(id=1),
                fakedb.SourceStamp(id=1, sourcestampsetid=1, branch='az', revision='az', codebase='c', repository='z'),
                fakedb.SourceStamp(id=2, sourcestampsetid=1, branch='bw', revision='bz', codebase='f', repository='w'),
                fakedb.SourceStampSet(id=2),
                fakedb.SourceStamp(id=3, sourcestampsetid=2, branch='a', revision='az', codebase='c', repository='z'),
                fakedb.SourceStamp(id=4, sourcestampsetid=2, branch='bw', revision='wz', codebase='f', repository='w'),
                fakedb.Buildset(id=1, sourcestampsetid=1, reason='foo',
                    submitted_at=1300305712, results=-1),
                fakedb.Buildset(id=2, sourcestampsetid=2, reason='foo',
                    submitted_at=1300305712, results=-1),
                fakedb.BuildRequest(id=1, buildsetid=1, buildername='bldr',
                    priority=13, submitted_at=1300305712, results=-1),
                fakedb.BuildRequest(id=2, buildsetid=2, buildername='bldr',
                    priority=13, submitted_at=1300305712, results=-1)
            ])

        brdicts = yield defer.gatherResults([
                self.db.buildrequests.getBuildRequest(id)
                for id in (1, 2)
            ])

        res = yield self.bldr._mergeRequests(brdicts[0],
                                brdicts, builder.Builder._defaultMergeRequestFn)

        self.assertEqual(res, [brdicts[0]])
    '''
