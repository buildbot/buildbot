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

import mock
from twisted.internet import defer

class ChangeSourceMixin(object):
    """
    Set up a fake ChangeMaster (C{self.changemaster}) and handle starting and
    stopping a ChangeSource service.  All Change objects added with
    C{addChange} appear at C{self.changes_added}.
    """

    changesource = None

    def setUpChangeSource(self):
        self.changemaster = mock.Mock()

        self.changes_added = []
        def addChange(change):
            self.changes_added.append(change)
        self.changemaster.addChange = addChange

        return defer.succeed(None)

    def tearDownChangeSource(self):
        if not self.changesource:
            return defer.succeed(None)
        return defer.maybeDeferred(self.changesource.stopService)

    def startChangeSource(self, cs):
        """Call this after constructing your changeSource; returns a deferred."""
        self.changesource = cs
        cs.parent = self.changemaster
        cs.startService()
        return defer.succeed(None)
