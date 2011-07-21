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

# this class is known to contain cruft and will be looked at later, so
# no current implementation utilizes it aside from scripts.runner.

from twisted.python import log
from twisted.internet import defer
from twisted.application import service
from buildbot import pbutil

class UsersBase(service.MultiService):
    """
    Base class for services that manage users manually. This takes care
    of the service.MultiService work needed by all the services that
    subclass it.
    """

    def __init__(self):
        service.MultiService.__init__(self)
        self.master = None

    def _setUpManualUsers(self, master):
        # called from UserManager.setUpManualUsers
        self.master = master

    def startService(self):
        service.MultiService.startService(self)

    def stopService(self):
        return service.MultiService.stopService(self)

class Commandline_Users_Perspective(pbutil.NewCredPerspective):
    """
    Perspective registered in buildbot.pbmanager and contains the real
    workings of `buildbot user` by working with the database when
    perspective_commandline is called.
    """

    def __init__(self, master):
        self.master = master

    def formatResults(self, op, info, results):
        """
        This formats the results of the database operations for printing
        back to the caller

        @param op: operation to perform (add, remove, update, show)
        @type op: string

        @param info: type/value pairs for each user that will be added
                     or updated in the database
        @type info: list of dictionaries or None

        @param results: results from database queries in perspective_commandline
        @type results: list

        @returns: string containing formatted results
        """
        formatted_results = ""

        if op == 'add':
            # list, alternating ident, uid
            formatted_results += "user(s) added:\n\n"
            for user in results:
                if isinstance(user, basestring):
                    formatted_results += "identifier: %s\n" % user
                else:
                    formatted_results += "uid: %d\n\n" % user
        elif op == 'remove':
            # list of dictionaries
            formatted_results += "user(s) removed:\n\n"
            for user in results:
                if user:
                    for key in user:
                        formatted_results += "%s: %s\n" % (key, user[key])
                    formatted_results += "\n"
                else:
                    formatted_results += "no match found\n\n"
        elif op == 'update':
            # list, alternating ident, None
            formatted_results += "user(s) updated:\n\n"
            for user in results:
                if user:
                    formatted_results += "identifier: %s\n" % user
                    for usinfo in info:
                        for key in usinfo:
                            if key != 'identifier':
                                formatted_results += "%s: %s\n" % (key,
                                                                   usinfo[key])
                    formatted_results += "\n"
        elif op == 'show':
            # list of dictionaries
            formatted_results += "user(s) to show:\n\n"
            for user in results:
                if user:
                    for key in user:
                        formatted_results += "%s: %s\n" % (key, user[key])
                    formatted_results += "\n"
                else:
                    formatted_results += "no match found\n\n"
        return formatted_results

    @defer.deferredGenerator
    def perspective_commandline(self, op, ids, info):
        """
        This performs the requested operations from the `buildbot user`
        call by calling the proper buildbot.db.users methods based on
        the operation. It yields a deferred instance with the results
        from the database methods.

        @param op: operation to perform (add, remove, update, show)
        @type op: string

        @param ids: user identifiers used to find existing users
        @type ids: list of strings or None

        @param info: type/value pairs for each user that will be added
                     or updated in the database
        @type info: list of dictionaries or None

        @returns: results from db.users methods via deferred
        """
        log.msg("perspective_commandline called")
        results = []

        if ids:
            for user in ids:
                if op == 'remove':
                    d = self.master.db.users.removeUser(identifier=user)
                elif op == 'show':
                    d = self.master.db.users.getUser(key=user)
                wfd = defer.waitForDeferred(d)
                yield wfd
                results.append(wfd.getResult())
        else:
            for user in info:
                # get identifier
                ident = user.pop('identifier')
                if op == 'add':
                    d = self.master.db.users.addUser(identifier=ident,
                                                     auth_dict=user)
                elif op == 'update':
                    d = self.master.db.users.updateUser(identifier=ident,
                                                        auth_dict=user)
                wfd = defer.waitForDeferred(d)
                yield wfd
                results.append(ident)
                results.append(wfd.getResult())
        results = self.formatResults(op, info, results)
        yield results

class Commandline_Users(UsersBase):
    """
    Service that runs to set up and register Commandline_Users_Perspective
    so `buildbot user` calls get to perspective_commandline.
    """

    def __init__(self, username="user", passwd="userpw"):
        UsersBase.__init__(self)
        self.username = username
        self.passwd = passwd
        self.registration = None

    def startService(self):
        UsersBase.startService(self)

        # set up factory and register with buildbot.pbmanager
        def factory(mind, username):
            return Commandline_Users_Perspective(self.master)
        port = self.master.slavePortnum
        self.registration = self.master.pbmanager.register(port, self.username,
                                                           self.passwd, factory)

    def stopService(self):
        d = defer.maybeDeferred(UsersBase.stopService, self)
        def unreg(_):
            if self.registration:
                return self.registration.unregister()
        d.addCallback(unreg)
        return d
