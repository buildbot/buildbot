from twisted.internet import defer
from buildbot.process import builder, factory
from buildbot import config
import mock
from buildbot.db import buildrequests, buildsets, sourcestamps
from buildbot.test.util import connector_component

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
