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


def patch():
    """
    Patch startService and stopService so that they check the previous state
    first.

    (used for debugging only)
    """
    from twisted.application.service import Service
    old_startService = Service.startService
    old_stopService = Service.stopService

    def startService(self):
        assert not self.running, "%r already running" % (self,)
        return old_startService(self)

    def stopService(self):
        assert self.running, "%r already stopped" % (self,)
        return old_stopService(self)
    Service.startService = startService
    Service.stopService = stopService
