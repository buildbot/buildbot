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

class UsersMixin(object):
    """
    This class is used for testing user components, faking out parts of
    buildbot.process.users that other tests need
    """

    stored_users = None
    stored_users_info = None
    next_id = 1

    def setUpUsers(self):
        self.stored_users = []
        self.stored_users_info = []

    def createUserObject(self, author, src=None):
        if src == "git":
            usdict = dict(identifier=author, attr_type='git', attr_data=author)

        return self.addUser(identifier=usdict['identifier'],
                            attr_type=usdict['attr_type'],
                            attr_data=usdict['attr_data'])

    def addUser(self, identifier=None, attr_type=None, attr_data=None):
        for user in self.stored_users_info:
            if (attr_type == user['attr_type'] and
                attr_data == user['attr_data']):
                return defer.succeed(user['uid'])

        uid = self.next_id
        self.next_id += 1
        self.stored_users.append(dict(uid=uid, identifier=identifier))
        self.stored_users_info.append(dict(uid=uid,
                                           attr_type=attr_type,
                                           attr_data=attr_data))
        return defer.succeed(uid)
