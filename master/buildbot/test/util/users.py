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

from buildbot.test.fake import fakedb
from buildbot.process.users import users

class UsersMixin(object):
    """
    This class is used for testing user components, faking out parts of
    buildbot.process.users that other tests need
    """

    stored_users = None
    next_id = 1

    def setUpUsers(self):
        self.stored_users = []

    def createUserObject(self, names, src=None):
        if src == "git":
            d = users.parseGitAuthor(names)
            d.addCallback(lambda usdict : self.checkFromGit(usdict))
            return d

    def checkFromGit(self, usdict):
        res = None
        auth_dict = {}
        identifier = usdict['full_name']

        if usdict['email']:
            auth_dict['email'] = usdict['email']
            auth_dict['full_name'] = usdict['full_name']
            for row in self.stored_users:
                if (row['auth_type'] == 'email' and
                    row['auth_data'] == usdict['email']) or \
                   (row['auth_type'] == 'full_name' and
                    row['auth_data'] == usdict['full_name']):
                   res = row
        else:
            auth_dict['full_name'] = usdict['full_name']
            for row in self.stored_users:
                if row['auth_type'] == 'full_name' and \
                   row['auth_data'] == usdict['full_name']:
                    res = row

        r_uid = None
        if not res:
            uid = None
            for auth_type in auth_dict:
                auth_data = auth_dict[auth_type]
                self.stored_users.append(dict(id=self.next_id,
                                             identifier=identifier,
                                             auth_type=auth_type,
                                             auth_data=auth_data))
                if uid is None:
                    r_uid = uid = self.next_id

                self.stored_users[-1].update(dict(uid=uid))
                self.next_id += self.next_id
        else:
            r_uid = res['uid']
        return defer.succeed(r_uid)
