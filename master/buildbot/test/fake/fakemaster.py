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
from twisted.internet import defer
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakebuild
from buildbot.test.fake import pbmanager
from buildbot import config
from buildbot.process import properties
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
    builders = {}
    pass


class FakeStatus(object):

    def __init__(self):
        self.master = None

    def builderAdded(self, name, basedir, category=None, friendly_name=None):
        return FakeBuilderStatus(self.master)

    def build_started(self, brid, buildername, build_status):
        pass

class FakeBuilderStatus(object):

    def __init__(self, master=None):
        self.master = master

    def setCategory(self, category):
        pass

    def setProject(self, project):
        pass

    def setSlavenames(self, names):
        pass

    def setCacheSize(self, size):
        pass

    def setBigState(self, state):
        pass

    def setFriendlyName(self, name):
        pass

    def setTags(self, tags):
        pass

    def newBuild(self):
        bs = fakebuild.FakeBuildStatus(self, self.master, 1)
        bs.number = 1
        bs.properties = properties.Properties()
        return bs


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

    def getStatus(self):
        return self.status

    def getObjectId(self):
        return defer.succeed(self._master_id)

    def subscribeToBuildRequests(self, callback):
        pass

    # work around http://code.google.com/p/mock/issues/detail?id=105
    def _get_child_mock(self, **kw):
        return mock.Mock(**kw)

    def maybeBuildsetComplete(self, bsid):
        pass

    def buildRequestRemoved(self, bsid, brid, buildername):
        pass

# Leave this alias, in case we want to add more behavior later
def make_master(wantDb=False, testcase=None, **kwargs):
    master = FakeMaster(**kwargs)
    if wantDb:
        assert testcase is not None, "need testcase for wantDb"
        master.db = fakedb.FakeDBConnector(testcase)
    return master
