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

import weakref
from twisted.internet import defer, reactor
from twisted.internet.protocol import ServerFactory
from buildbot.mq import connector as mqconnector
from buildbot.data import connector as dataconnector
from buildbot.test.fake import fakedb, fakemq, fakedata
from buildbot.test.fake import pbmanager
from buildbot.www import service
from buildbot import config
import mock

class FakeCache(object):
    """Emulate an L{AsyncLRUCache}, but without any real caching.  This
    I{does} do the weakref part, to catch un-weakref-able objects."""
    def __init__(self, name, miss_fn):
        self.name = name
        self.miss_fn = miss_fn

    def get(self, key, **kwargs):
        d = self.miss_fn(key, **kwargs)
        def mkref(x):
            if x is not None:
                weakref.ref(x)
            return x
        d.addCallback(mkref)
        return d


class FakeCaches(object):

    def get_cache(self, name, miss_fn):
        return FakeCache(name, miss_fn)


class FakeBotMaster(object):

    pass


class FakeStatus(object):

    def builderAdded(self, name, basedir, category=None, description=None):
        return FakeBuilderStatus()

    def getBuilderNames(self):
        return []

    def getSlaveNames(self):
        return []

class FakeBuilderStatus(object):

    def setDescription(self, description):
        self._description = description

    def getDescription(self):
        return self._description

    def setCategory(self, category):
        self._category = category

    def getCategory(self):
        return self._category

    def setSlavenames(self, names):
        pass

    def setCacheSize(self, size):
        pass

    def setBigState(self, state):
        pass


class FakeMaster(object):
    """
    Create a fake Master instance: a Mock with some convenience
    implementations:

    - Non-caching implementation for C{self.caches}
    """

    def __init__(self, master_id=fakedb.FakeBuildRequestsComponent.MASTER_ID):
        self._master_id = master_id
        self.config = config.MasterConfig()
        self.caches = FakeCaches()
        self.pbmanager = pbmanager.FakePBManager()
        self.basedir = 'basedir'
        self.botmaster = FakeBotMaster()
        self.botmaster.parent = self
        self.status = FakeStatus()
        self.status.master = self
        self.name = 'fake:/master'
        self.masterid = master_id

    def getObjectId(self):
        return defer.succeed(self._master_id)

    def subscribeToBuildRequests(self, callback):
        pass

    # work around http://code.google.com/p/mock/issues/detail?id=105
    def _get_child_mock(self, **kw):
        return mock.Mock(**kw)


# Leave this alias, in case we want to add more behavior later
def make_master(wantMq=False, wantDb=False, wantData=False,
        testcase=None, **kwargs):
    master = FakeMaster(**kwargs)
    if wantData:
        wantMq = wantDb = True
    if wantMq:
        assert testcase is not None, "need testcase for wantMq"
        master.mq = fakemq.FakeMQConnector(master, testcase)
    if wantDb:
        assert testcase is not None, "need testcase for wantDb"
        master.db = fakedb.FakeDBConnector(testcase)
    if wantData:
        master.data = fakedata.FakeDataConnector(master, testcase)
    return master

# this config has real mq, real data, real www, but fakedb, and no build engine for ui test
@defer.inlineCallbacks
def make_master_for_uitest(port, public_html):
    tcp = reactor.listenTCP(port, ServerFactory())
    port = tcp._realPortNumber
    yield tcp.stopListening()
    url = 'http://localhost:'+str(port)+"/"
    master = FakeMaster()
    master.db = fakedb.FakeDBConnector(mock.Mock())
    master.mq = mqconnector.MQConnector(master)
    class testHookedDataConnector(dataconnector.DataConnector):
        submodules = dataconnector.DataConnector.submodules + ['buildbot.data.testhooks']

    master.data = testHookedDataConnector(master)
    master.config.www = dict(url=url, port=port, public_html=public_html)
    master.www = service.WWWService(master)
    yield master.www.startService()
    yield master.www.reconfigService(master.config)
    defer.returnValue(master)
