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

from typing import TYPE_CHECKING

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test import fakedb
from buildbot.test.fake import fakemaster

if TYPE_CHECKING:
    from twisted.trial import unittest

    _ChangeSourceMixinBase = unittest.TestCase
else:
    _ChangeSourceMixinBase = object


class ChangeSourceMixin(_ChangeSourceMixinBase):
    """
    This class is used for testing change sources, and handles a few things:

     - starting and stopping a ChangeSource service
     - a fake master with a data API implementation
    """

    changesource = None
    started = False

    DUMMY_CHANGESOURCE_ID = 20
    OTHER_MASTER_ID = 93
    DEFAULT_NAME = "ChangeSource"

    @defer.inlineCallbacks
    def setUpChangeSource(self, want_real_reactor: bool = False):
        "Set up the mixin - returns a deferred."
        self.master = yield fakemaster.make_master(
            self, wantDb=True, wantData=True, wantRealReactor=want_real_reactor
        )

        self.master.db.insert_test_data([
            fakedb.Master(id=fakedb.FakeDBConnector.MASTER_ID),
            fakedb.Master(id=self.OTHER_MASTER_ID, active=1),
            fakedb.ChangeSource(id=self.DUMMY_CHANGESOURCE_ID, name=self.DEFAULT_NAME),
        ])

        @defer.inlineCallbacks
        def cleanup():
            if not self.started:
                return
            if self.changesource.running:
                yield self.changesource.stopService()
            yield self.changesource.disownServiceParent()

        self.addCleanup(cleanup)

    @defer.inlineCallbacks
    def attachChangeSource(self, cs):
        self.changesource = cs
        yield self.changesource.setServiceParent(self.master)
        yield self.changesource.configureService()
        return cs

    def startChangeSource(self):
        "start the change source as a service"
        self.started = True
        return self.changesource.startService()

    @defer.inlineCallbacks
    def stopChangeSource(self):
        "stop the change source again; returns a deferred"
        yield self.changesource.stopService()

        self.started = False

    @defer.inlineCallbacks
    def setChangeSourceToMaster(self, otherMaster):
        ret = yield self.master.data.updates.trySetChangeSourceMaster(
            self.DUMMY_CHANGESOURCE_ID, otherMaster
        )
        return ret
