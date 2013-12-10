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

from buildbot import pbutil
from twisted.application import service
from twisted.internet import defer
from twisted.python import log


class UsersBase(service.MultiService):

    """
    Base class for services that manage users manually. This takes care
    of the service.MultiService work needed by all the services that
    subclass it.
    """

    def __init__(self):
        service.MultiService.__init__(self)
        self.master = None

    def startService(self):
        service.MultiService.startService(self)

    def stopService(self):
        return service.MultiService.stopService(self)


class CommandlineUserManagerPerspective(pbutil.NewCredPerspective):

    """
    Perspective registered in buildbot.pbmanager and contains the real
    workings of `buildbot user` by working with the database when
    perspective_commandline is called.
    """

    def __init__(self, master):
        self.master = master

    def formatResults(self, op, results):
        """
        This formats the results of the database operations for printing
        back to the caller

        @param op: operation to perform (add, remove, update, get)
        @type op: string

        @param results: results from db queries in perspective_commandline
        @type results: list

        @returns: string containing formatted results
        """
        formatted_results = ""

        if op == 'add':
            # list, alternating ident, uid
            formatted_results += "user(s) added:\n"
            for user in results:
                if isinstance(user, basestring):
                    formatted_results += "identifier: %s\n" % user
                else:
                    formatted_results += "uid: %d\n\n" % user
        elif op == 'remove':
            # list of dictionaries
            formatted_results += "user(s) removed:\n"
            for user in results:
                if user:
                    formatted_results += "identifier: %s\n" % (user)
        elif op == 'update':
            # list, alternating ident, None
            formatted_results += "user(s) updated:\n"
            for user in results:
                if user:
                    formatted_results += "identifier: %s\n" % (user)
        elif op == 'get':
            # list of dictionaries
            formatted_results += "user(s) found:\n"
            for user in results:
                if user:
                    for key in user:
                        if key != 'bb_password':
                            formatted_results += "%s: %s\n" % (key, user[key])
                    formatted_results += "\n"
                else:
                    formatted_results += "no match found\n"
        return formatted_results

    @defer.inlineCallbacks
    def perspective_commandline(self, op, bb_username, bb_password, ids, info):
        """
        This performs the requested operations from the `buildbot user`
        call by calling the proper buildbot.db.users methods based on
        the operation. It yields a deferred instance with the results
        from the database methods.

        @param op: operation to perform (add, remove, update, get)
        @type op: string

        @param bb_username: username portion of auth credentials
        @type bb_username: string

        @param bb_password: hashed password portion of auth credentials
        @type bb_password: hashed string

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
                # get identifier, guaranteed to be in user from checks
                # done in C{scripts.runner}
                uid = yield self.master.db.users.identifierToUid(
                    identifier=user)

                result = None
                if op == 'remove':
                    if uid:
                        yield self.master.db.users.removeUser(uid)
                        result = user
                    else:
                        log.msg("Unable to find uid for identifier %s" % user)
                elif op == 'get':
                    if uid:
                        result = yield self.master.db.users.getUser(uid)
                    else:
                        log.msg("Unable to find uid for identifier %s" % user)

                results.append(result)
        else:
            for user in info:
                # get identifier, guaranteed to be in user from checks
                # done in C{scripts.runner}
                ident = user.pop('identifier')
                uid = yield self.master.db.users.identifierToUid(
                    identifier=ident)

                # if only an identifier was in user, we're updating only
                # the bb_username and bb_password.
                if not user:
                    if uid:
                        result = yield self.master.db.users.updateUser(
                            uid=uid,
                            identifier=ident,
                            bb_username=bb_username,
                            bb_password=bb_password)
                        results.append(ident)
                    else:
                        log.msg("Unable to find uid for identifier %s"
                                % user)
                else:
                    # when adding, we update the user after the first attr
                    once_through = False
                    for attr in user:
                        result = None
                        if op == 'update' or once_through:
                            if uid:
                                result = yield self.master.db.users.updateUser(
                                    uid=uid,
                                    identifier=ident,
                                    bb_username=bb_username,
                                    bb_password=bb_password,
                                    attr_type=attr,
                                    attr_data=user[attr])
                            else:
                                log.msg("Unable to find uid for identifier %s"
                                        % user)
                        elif op == 'add':
                            result = yield self.master.db.users.findUserByAttr(
                                identifier=ident,
                                attr_type=attr,
                                attr_data=user[attr])
                            once_through = True
                        results.append(ident)

                        # result is None from updateUser calls
                        if result:
                            results.append(result)
                            uid = result
        results = self.formatResults(op, results)
        defer.returnValue(results)


class CommandlineUserManager(UsersBase):

    """
    Service that runs to set up and register CommandlineUserManagerPerspective
    so `buildbot user` calls get to perspective_commandline.
    """

    def __init__(self, username=None, passwd=None, port=None):
        UsersBase.__init__(self)
        assert username and passwd, ("A username and password pair must be given "
                                     "to connect and use `buildbot user`")
        self.username = username
        self.passwd = passwd

        assert port, "A port must be specified for a PB connection"
        self.port = port
        self.registration = None

    def startService(self):
        UsersBase.startService(self)
        # set up factory and register with buildbot.pbmanager

        def factory(mind, username):
            return CommandlineUserManagerPerspective(self.master)
        self.registration = self.master.pbmanager.register(self.port,
                                                           self.username,
                                                           self.passwd,
                                                           factory)

    def stopService(self):
        d = defer.maybeDeferred(UsersBase.stopService, self)

        def unreg(_):
            if self.registration:
                return self.registration.unregister()
        d.addCallback(unreg)
        return d
