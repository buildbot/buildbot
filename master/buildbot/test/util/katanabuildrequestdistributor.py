from twisted.internet import defer
from buildbot.process import builder, factory
from buildbot import config
import mock
from buildbot.db import buildrequests, buildsets, sourcestamps, builds
from buildbot.test.util import connector_component
from buildbot.process import buildrequestdistributor
from buildbot.process import cache
from buildbot.test.fake import fakedb
from buildbot.status.results import RESUME, BEGINNING
import cProfile, pstats
from buildbot.test.util import compat


class KatanaBuildRequestDistributorTestSetup(connector_component.ConnectorComponentMixin, object):

    MASTER_ID = 1

    @defer.inlineCallbacks
    def setUpComponents(self):
        yield self.setUpConnectorComponent(
            table_names=['buildrequests', 'buildrequest_claims', 'buildsets', 'buildset_properties',
                         'sourcestamps', 'sourcestamp_changes', 'builds', 'sourcestampsets'])

        self.db.buildrequests = buildrequests.BuildRequestsConnectorComponent(self.db)
        self.db.buildsets = buildsets.BuildsetsConnectorComponent(self.db)
        self.db.sourcestamps = sourcestamps.SourceStampsConnectorComponent(self.db)
        self.db.builds = builds.BuildsConnectorComponent(self.db)
        self.db.master.getObjectId = lambda : defer.succeed(self.MASTER_ID)
        self.botmaster = mock.Mock(name='botmaster')
        self.botmaster.builders = {}
        self.master = self.botmaster.master = mock.Mock(name='master')
        self.master.db = self.db
        self.master.caches = cache.CacheManager()
        self.master.config.mergeRequests = None
        self.processedBuilds = []
        self.mergedBuilds = []
        self.addRunningBuilds = False
        self.slaves = {}

    def setUpQuietDeferred(self):
        # Detects the "end" of the test
        self.quiet_deferred = defer.Deferred()
        def _quiet():
            if self.quiet_deferred:
                d, self.quiet_deferred = self.quiet_deferred, None
                d.callback(None)
        self.brd._quiet = _quiet

    def setUpKatanaBuildRequestDistributor(self):
        self.brd = buildrequestdistributor.KatanaBuildRequestDistributor(self.botmaster)
        self.brd.startService()
        self.setUpQuietDeferred()

    def stopKatanaBuildRequestDistributor(self):
        if self.brd.running:
            yield self.brd.stopService()

    def checkBRDCleanedUp(self):
        # check that the BRD didnt end with a stuck lock or in the 'active' state (which would mean
        # it ended without unwinding correctly)
        self.assertEqual(self.brd.activity_lock.locked, False)
        self.assertEqual(self.brd.active, False)

    @defer.inlineCallbacks
    def tearDownComponents(self):
        yield self.tearDownConnectorComponent()

    @defer.inlineCallbacks
    def profileAsyncFunc(self, expected_total_tt, func, **kwargs):
        if compat.runningPypy():
            res = yield func(**kwargs)
            defer.returnValue(res)
            return
        pr = cProfile.Profile()
        pr.enable()
        res = yield func(**kwargs)
        pr.disable()
        ps = pstats.Stats(pr).sort_stats('cumtime')
        ps.print_stats()
        # TODO: we should collect the profile data and compare timing
        # expected_total_tt is a reference time
        defer.returnValue(res)

    def addSlavesToList(self, slavelist, slavebuilders):
        if not slavebuilders:
            return
        """C{slaves} maps name : available"""
        for name, avail in slavebuilders.iteritems():
            if name in self.slaves.keys():
                slavelist.append(self.slaves[name])
                continue

            sb = mock.Mock(spec=['isAvailable'], name=name)
            sb.name = name
            sb.isAvailable.return_value = avail
            sb.slave = mock.Mock()
            sb.slave.slave_status = mock.Mock(spec=['getName'])
            sb.slave.slave_status.getName.return_value = name
            slavelist.append(sb)
            self.slaves[name] = sb

    def mockRunningBuilds(self, bldr, breqs):
        build = mock.Mock()
        build.finished = False
        build.requests = breqs
        bldr.building.append(build)
        build.build_status = mock.Mock()
        build.build_status.number = len(bldr.building)

    def addProcessedBuilds(self, slavebuilder, breqs):
        bldr = self.brd.katanaBuildChooser.bldr
        if self.addRunningBuilds:
            self.mockRunningBuilds(bldr, breqs)
        self.slaves[slavebuilder.name].isAvailable.return_value = False
        self.processedBuilds.append((slavebuilder.name, [br.id for br in breqs]))
        return defer.succeed(True)

    def addMergedBuilds(self, brid, buildnumber, brids):
        self.mergedBuilds.append((brid, brids))
        return defer.succeed(True)

    def createSlaveList(self, available,  xrange):
        return {'build-slave-%d' % id: available for id in xrange}

    def createBuilder(self, name, slavenames=None, startSlavenames=None,
                      maybeStartBuild=None,
                      maybeResumeBuild=None,
                      addRunningBuilds=False):
        bldr = builder.Builder(name, _addServices=False)
        build_factory = factory.BuildFactory()

        self.addRunningBuilds = addRunningBuilds

        def getSlaves(param):
            return param.keys() if list and isinstance(param, dict) else []

        config_args = dict(name=name, builddir="bdir",
                           slavebuilddir="sbdir", project='default', factory=build_factory)

        if slavenames:
            config_args['slavenames'] = getSlaves(slavenames)

        if startSlavenames:
            config_args['startSlavenames'] = getSlaves(startSlavenames)

        bldr.config = config.BuilderConfig(**config_args)
        bldr.maybeStartBuild = maybeStartBuild if maybeStartBuild else self.addProcessedBuilds
        bldr.maybeResumeBuild = maybeResumeBuild if maybeResumeBuild \
            else lambda slavebuilder, buildnumber, breqs: self.addProcessedBuilds(slavebuilder, breqs)

        bldr.maybeUpdateMergedBuilds = self.addMergedBuilds

        self.addSlavesToList(bldr.slaves, slavenames)
        self.addSlavesToList(bldr.startSlaves, startSlavenames)
        return bldr

    def setupBuilderInMaster(self, name, slavenames=None, startSlavenames=None,
                             maybeStartBuild=None, maybeResumeBuild=None, addRunningBuilds=False):
        bldr = self.createBuilder(name, slavenames, startSlavenames,
                                  maybeStartBuild, maybeResumeBuild,
                                  addRunningBuilds)

        self.botmaster.builders[name] = bldr
        bldr.master = self.master
        return bldr

    def getBuildSetTestData(self, xrange):
        testdata = [fakedb.Buildset(id=idx,
                                          sourcestampsetid=idx) for idx in xrange]

        testdata += [fakedb.SourceStamp(sourcestampsetid=idx,
                                             branch='branch_%d' % idx)
                          for idx in xrange]
        return testdata

    def initialized(self):
        self.lastbrid = 0
        self.lastbuilderid = 0
        self.testdata = []

    def insertBuildrequests(self, buildername, priority, xrange, submitted_at=1449578391,
                            results=BEGINNING, complete=0,
                            mergebrid=None, artifactbrid=None,
                            startbrid=None, selected_slave=None,
                            sources=None):
        self.testdata += [fakedb.BuildRequest(id=self.lastbrid+idx,
                                              buildsetid=self.lastbrid+idx,
                                              buildername=buildername,
                                              priority=priority,
                                              results=results,
                                              complete=complete,
                                              mergebrid=mergebrid,
                                              artifactbrid=artifactbrid,
                                              startbrid=startbrid,
                                              submitted_at=submitted_at) for idx in xrange]

        if results == RESUME:
            breqsclaim = [fakedb.BuildRequestClaim(brid=self.lastbrid+idx,
                                                   objectid=self.MASTER_ID, claimed_at=1449578391) for idx in xrange]
            self.testdata += breqsclaim

        if selected_slave:
            self.testdata += [fakedb.BuildsetProperty(buildsetid=self.lastbrid+idx,
                                                      property_name='selected_slave',
                                                      property_value='["%s", "Force Build Form"]' % selected_slave)
                              for idx in xrange]

        self.testdata += [fakedb.Buildset(id=self.lastbrid+idx,
                                          sourcestampsetid=self.lastbrid+idx) for idx in xrange]

        if not sources:
            self.testdata += [fakedb.SourceStamp(sourcestampsetid=self.lastbrid+idx,
                                                 branch='branch_%d' % (self.lastbrid+idx))
                              for idx in xrange]

        else:
            self.testdata += [fakedb.SourceStampSet(id=self.lastbrid+idx) for idx in xrange]
            for ss in sources:
                self.testdata += [fakedb.SourceStamp(sourcestampsetid=self.lastbrid+idx,
                                                     repository=ss['repository'],
                                                     codebase=ss['codebase'],
                                                     branch=ss['branch'],
                                                     revision=ss['revision']) for idx in xrange]

        self.lastbrid += len(xrange)
