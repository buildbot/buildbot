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

from twisted.internet import defer
from twisted.internet import task

from buildbot.test.fake import fakemaster


class ChangeSourceMixin(object):

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

    def setUpChangeSource(self):
        "Set up the mixin - returns a deferred."
        self.master = fakemaster.make_master(wantDb=True, wantData=True,
                                             testcase=self)
        assert not hasattr(self.master, 'addChange')  # just checking..
        return defer.succeed(None)

    @defer.inlineCallbacks
    def tearDownChangeSource(self):
        "Tear down the mixin - returns a deferred."
        if not self.started:
            return
        if self.changesource.running:
            yield defer.maybeDeferred(self.changesource.stopService)
        yield self.changesource.disownServiceParent()
        return

    def attachChangeSource(self, cs):
        "Set up a change source for testing; sets its .master attribute"
        self.changesource = cs
        # FIXME some changesource does not have master property yet but
        # mailchangesource has :-/
        try:
            self.changesource.master = self.master
        except AttributeError:
            self.changesource.setServiceParent(self.master)

        # also, now that changesources are ClusteredServices, setting up
        # the clock here helps in the unit tests that check that behavior
        self.changesource.clock = task.Clock()

    def startChangeSource(self):
        "start the change source as a service"
        self.started = True
        return self.changesource.startService()

    def stopChangeSource(self):
        "stop the change source again; returns a deferred"
        d = self.changesource.stopService()

        @d.addCallback
        def mark_stopped(_):
            self.started = False
        return d

    def setChangeSourceToMaster(self, otherMaster):
        # some tests build the CS late, so for those tests we will require that
        # they use the default name in order to run tests that require master
        # assignments
        if self.changesource is not None:
            name = self.changesource.name
        else:
            name = self.DEFAULT_NAME

        self.master.data.updates.changesourceIds[
            name] = self.DUMMY_CHANGESOURCE_ID
        if otherMaster:
            self.master.data.updates.changesourceMasters[
                self.DUMMY_CHANGESOURCE_ID] = otherMaster
        else:
            del self.master.data.updates.changesourceMasters[
                self.DUMMY_CHANGESOURCE_ID]
