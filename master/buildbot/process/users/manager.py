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

from twisted.python import log
from twisted.internet import defer
from twisted.application import service
from buildbot.process.users import manual

class UserManager(service.MultiService):
    """
    This is the master-side service that allows manual user management
    via the commandline. More manual user tools, such as a web interface,
    will be added in the future by appending them to manual_users in
    initManualUsers.

    An instance of this manager is at Botmaster.user_manager, which calls
    setUpManualUsers to initial each user tool, right now just being the
    commandline tool.
    """

    name = "user_manager"

    def __init__(self):
        service.MultiService.__init__(self)
        self.master = None

    def startService(self):
        service.MultiService.startService(self)
        self.master = self.parent

    def initManualUsers(self):
        """inits the services and passes them to setUpManualUsers"""
        manual_users = []
        manual_users.append(manual.Commandline_Users())
        self.setUpManualUsers(manual_users)

    def setUpManualUsers(self, manual_users):
        """
        This sets up the Commandline_Users class to handle user management
        from `buildbot user` in buildbot.scripts.runner. It takes care of
        starting each service and setting the Botmaster link in each.

        @param manual_users: services that manage users manually
        @type manual_users: list of services

        @returns: deferred
        """
        self.manual_users = manual_users
        d = defer.succeed(None)
        def setMasterParent(_):
            d = defer.succeed(None)
            def setMaster(_):
                for mu in self.manual_users:
                    mu._setUpManualUsers(self.master)
            d.addCallback(setMaster)
            def setParent(_):
                for mu in self.manual_users:
                    mu.setServiceParent(self)
            d.addCallback(setParent)
            return d
        d.addCallback(setMasterParent)
        return d
