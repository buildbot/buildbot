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
from future.utils import iteritems


class RolesFromBase(object):

    def __init__(self):
        pass

    def getRolesFromUser(self, userDetails):
        return []

    def setAuthz(self, authz):
        self.authz = authz
        self.master = authz.master


class RolesFromGroups(RolesFromBase):

    def __init__(self, groupPrefix=""):
        RolesFromBase.__init__(self)
        self.groupPrefix = groupPrefix

    def getRolesFromUser(self, userDetails):
        roles = []
        if 'groups' in userDetails:
            for group in userDetails['groups']:
                if group.startswith(self.groupPrefix):
                    roles.append(group[len(self.groupPrefix):])
        return roles


class RolesFromEmails(RolesFromBase):

    def __init__(self, **kwargs):
        RolesFromBase.__init__(self)
        self.roles = {}
        for role, emails in iteritems(kwargs):
            for email in emails:
                self.roles.setdefault(email, []).append(role)

    def getRolesFromUser(self, userDetails):
        if 'email' in userDetails:
            return self.roles.get(userDetails['email'], [])
        return []


class RolesFromOwner(RolesFromBase):

    def __init__(self, role):
        RolesFromBase.__init__(self)
        self.role = role

    def getRolesFromUser(self, userDetails, owner):
        if 'email' in userDetails:
            if userDetails['email'] == owner and owner is not None:
                return [self.role]
        return []


class RolesFromUsername(RolesFromBase):
    def __init__(self, roles, usernames):
        self.roles = roles
        if None in usernames:
            from buildbot import config
            config.error('Usernames cannot be None')
        self.usernames = usernames

    def getRolesFromUser(self, userDetails):
        if userDetails.get('username') in self.usernames:
            return self.roles
        return []
