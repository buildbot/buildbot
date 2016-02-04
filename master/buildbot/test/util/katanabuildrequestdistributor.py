from twisted.internet import defer
from buildbot.process import builder, factory
from buildbot import config
import mock
from buildbot.db import buildrequests, buildsets, sourcestamps
from buildbot.test.util import connector_component
from buildbot.process import buildrequestdistributor

class KatanaBuildRequestDistributorTestSetup(connector_component.ConnectorComponentMixin, object):

    MASTER_ID = 1

    @defer.inlineCallbacks
    def setUpComponents(self):
        yield self.setUpConnectorComponent(
            table_names=['buildrequests', 'buildrequest_claims', 'buildsets', 'buildset_properties',
                         'sourcestamps', 'sourcestamp_changes'])

        self.db.buildrequests = buildrequests.BuildRequestsConnectorComponent(self.db)
        self.db.buildsets = buildsets.BuildsetsConnectorComponent(self.db)
        self.db.sourcestamps = sourcestamps.SourceStampsConnectorComponent(self.db)
        self.db.master.getObjectId = lambda : defer.succeed(self.MASTER_ID)
        self.botmaster = mock.Mock(name='botmaster')
        self.botmaster.builders = {}
        self.master = self.botmaster.master = mock.Mock(name='master')
        self.master.db = self.db

    def setUpQuietDeferred(self):
        # Detects the "end" of the test
        self.quiet_deferred = defer.Deferred()
        def _quiet():
            if self.quiet_deferred:
                d, self.quiet_deferred = self.quiet_deferred, None
                d.callback(None)
            else:
                self.fail("loop has already gone quiet once")
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
        build_factory = factory.BuildFactory()

        def getSlaves(param):
            return param.keys() if list and isinstance(param, dict) else []

        config_args = dict(name=name, builddir="bdir",
                           slavebuilddir="sbdir", project='default', factory=build_factory)

        if slavenames:
            config_args['slavenames'] = getSlaves(slavenames)

        if startSlavenames:
            config_args['startSlavenames'] = getSlaves(startSlavenames)

        bldr.config = config.BuilderConfig(**config_args)

        self.addSlavesToList(bldr.slaves, slavenames)
        self.addSlavesToList(bldr.startSlaves, startSlavenames)
        return bldr

    def setupBuilderInMaster(self, name, slavenames=None, startSlavenames=None):
        bldr = self.createBuilder(name, slavenames, startSlavenames)
        self.botmaster.builders[name] = bldr
        return bldr
