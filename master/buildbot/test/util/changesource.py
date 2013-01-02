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

from twisted.internet import defer
from buildbot.test.fake import fakemaster

class ChangeSourceMixin(object):
    """
    This class is used for testing change sources, and handles a few things:

     - starting and stopping a ChangeSource service
     - a fake master with a data API implementation
    """

    changesource = None
    started = False

    def setUpChangeSource(self):
        "Set up the mixin - returns a deferred."
        self.master = fakemaster.make_master(wantDb=True, wantData=True,
                                             testcase=self)
        assert not hasattr(self.master, 'addChange') # just checking..
        return defer.succeed(None)

    def tearDownChangeSource(self):
        "Tear down the mixin - returns a deferred."
        if not self.started:
            return defer.succeed(None)
        if self.changesource.running:
            return defer.maybeDeferred(self.changesource.stopService)
        return defer.succeed(None)

    def attachChangeSource(self, cs):
        "Set up a change source for testing; sets its .master attribute"
        self.changesource = cs
        self.changesource.master = self.master

    def startChangeSource(self):
        "start the change source as a service"
        self.started = True
        self.changesource.startService()

    def stopChangeSource(self):
        "stop the change source again; returns a deferred"
        d = self.changesource.stopService()
        def mark_stopped(_):
            self.started = False
        d.addCallback(mark_stopped)
        return d
