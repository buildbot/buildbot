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

from __future__ import absolute_import
from __future__ import print_function

import os
import weakref

import mock

from twisted.internet import defer
from twisted.internet import reactor
from zope.interface import implementer

from buildbot import config
from buildbot import interfaces
from buildbot.status import build
from buildbot.test.fake import bworkermanager
from buildbot.test.fake import fakedata
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemq
from buildbot.test.fake import pbmanager
from buildbot.test.fake.botmaster import FakeBotMaster
from buildbot.util import service


class FakeCache(object):

    """Emulate an L{AsyncLRUCache}, but without any real caching.  This
    I{does} do the weakref part, to catch un-weakref-able objects."""

    def __init__(self, name, miss_fn):
        self.name = name
        self.miss_fn = miss_fn

    def get(self, key, **kwargs):
        d = self.miss_fn(key, **kwargs)

        @d.addCallback
        def mkref(x):
            if x is not None:
                weakref.ref(x)
            return x
        return d

    def put(self, key, val):
        pass


class FakeCaches(object):

    def get_cache(self, name, miss_fn):
        return FakeCache(name, miss_fn)


class FakeStatus(service.BuildbotService):

    name = "status"
    lastBuilderStatus = None

    def builderAdded(self, name, basedir, tags=None, description=None):
        bs = FakeBuilderStatus(self.master)
        self.lastBuilderStatus = bs
        return bs

    def getBuilderNames(self):
        return []

    def getWorkerNames(self):
        return []

    def workerConnected(self, name):
        pass

    def build_started(self, brid, buildername, build_status):
        pass

    def getURLForBuild(self, builder_name, build_number):
        return "URLForBuild/%s/%d" % (builder_name, build_number)

    def getURLForBuildrequest(self, buildrequestid):
        return "URLForBuildrequest/%d" % (buildrequestid,)

    def subscribe(self, _):
        pass

    def getTitle(self):
        return "myBuildbot"

    def getURLForThing(self, _):
        return "h://thing"

    def getBuildbotURL(self):
        return "h://bb.me"


@implementer(interfaces.IBuilderStatus)
class FakeBuilderStatus(object):

    def __init__(self, master=None, buildername="Builder"):
        if master:
            self.master = master
            self.botmaster = master.botmaster
            self.basedir = os.path.join(master.basedir, 'bldr')
        self.lastBuildStatus = None
        self._tags = None
        self.name = buildername

    def setDescription(self, description):
        self._description = description

    def getDescription(self):
        return self._description

    def getTags(self):
        return self._tags

    def setTags(self, tags):
        self._tags = tags

    def matchesAnyTag(self, tags):
        return set(self._tags) & set(tags)

    def setWorkernames(self, names):
        pass

    def setCacheSize(self, size):
        pass

    def setBigState(self, state):
        pass

    def newBuild(self):
        bld = build.BuildStatus(self, self.master, 3)
        self.lastBuildStatus = bld
        return bld

    def buildStarted(self, builderStatus):
        pass


class FakeLogRotation(object):
    rotateLength = 42
    maxRotatedFiles = 42


class FakeMaster(service.MasterService):

    """
    Create a fake Master instance: a Mock with some convenience
    implementations:

    - Non-caching implementation for C{self.caches}
    """

    def __init__(self, master_id=fakedb.FakeBuildRequestsComponent.MASTER_ID):
        service.MasterService.__init__(self)
        self._master_id = master_id
        self.reactor = reactor
        self.objectids = {}
        self.config = config.MasterConfig()
        self.caches = FakeCaches()
        self.pbmanager = pbmanager.FakePBManager()
        self.basedir = 'basedir'
        self.botmaster = FakeBotMaster()
        self.botmaster.setServiceParent(self)
        self.status = FakeStatus()
        self.status.setServiceParent(self)
        self.name = 'fake:/master'
        self.masterid = master_id
        self.workers = bworkermanager.FakeWorkerManager()
        self.workers.setServiceParent(self)
        self.log_rotation = FakeLogRotation()
        self.db = mock.Mock()
        self.next_objectid = 0

        def getObjectId(sched_name, class_name):
            k = (sched_name, class_name)
            try:
                rv = self.objectids[k]
            except KeyError:
                rv = self.objectids[k] = self.next_objectid
                self.next_objectid += 1
            return defer.succeed(rv)
        self.db.state.getObjectId = getObjectId

    def getObjectId(self):
        return defer.succeed(self._master_id)

    def subscribeToBuildRequests(self, callback):
        pass

# Leave this alias, in case we want to add more behavior later


def make_master(wantMq=False, wantDb=False, wantData=False,
                testcase=None, url=None, **kwargs):
    master = FakeMaster(**kwargs)
    if url:
        master.buildbotURL = url
    if wantData:
        wantMq = wantDb = True
    if wantMq:
        assert testcase is not None, "need testcase for wantMq"
        master.mq = fakemq.FakeMQConnector(testcase)
        master.mq.setServiceParent(master)
    if wantDb:
        assert testcase is not None, "need testcase for wantDb"
        master.db = fakedb.FakeDBConnector(testcase)
        master.db.setServiceParent(master)
    if wantData:
        master.data = fakedata.FakeDataConnector(master, testcase)
    return master
