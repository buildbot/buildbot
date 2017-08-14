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

import fnmatch
import re

from twisted.internet import defer
from twisted.web.error import Error
from zope.interface import implementer

from buildbot.interfaces import IConfigured
from buildbot.util import unicode2bytes
from buildbot.www.authz.roles import RolesFromOwner


class Forbidden(Error):

    def __init__(self, msg):
        Error.__init__(self, 403, msg)


# fnmatch and re.match are reversed API, we cannot just rename them
def fnmatchStrMatcher(value, match):
    return fnmatch.fnmatch(value, match)


def reStrMatcher(value, match):
    return re.match(match, value)


@implementer(IConfigured)
class Authz(object):

    def getConfigDict(self):
        return {}

    def __init__(self, allowRules=None, roleMatchers=None, stringsMatcher=fnmatchStrMatcher):
        self.match = stringsMatcher
        if allowRules is None:
            allowRules = []
        if roleMatchers is None:
            roleMatchers = []
        self.allowRules = allowRules
        self.roleMatchers = [
            r for r in roleMatchers if not isinstance(r, RolesFromOwner)]
        self.ownerRoleMatchers = [
            r for r in roleMatchers if isinstance(r, RolesFromOwner)]

    def setMaster(self, master):
        self.master = master
        for r in self.roleMatchers + self.ownerRoleMatchers + self.allowRules:
            r.setAuthz(self)

    def getRolesFromUser(self, userDetails):
        roles = set()
        for roleMatcher in self.roleMatchers:
            roles.update(set(roleMatcher.getRolesFromUser(userDetails)))
        return roles

    def getOwnerRolesFromUser(self, userDetails, owner):
        roles = set()
        for roleMatcher in self.ownerRoleMatchers:
            roles.update(set(roleMatcher.getRolesFromUser(userDetails, owner)))
        return roles

    @defer.inlineCallbacks
    def assertUserAllowed(self, ep, action, options, userDetails):
        roles = self.getRolesFromUser(userDetails)
        for rule in self.allowRules:
            match = yield rule.match(ep, action, options)
            if match is not None:
                # only try to get owner if there are owner Matchers
                if self.ownerRoleMatchers:
                    owner = yield match.getOwner()
                    if owner is not None:
                        roles.update(
                            self.getOwnerRolesFromUser(userDetails, owner))
                for role in roles:
                    if self.match(role, rule.role):
                        defer.returnValue(None)

                if not rule.defaultDeny:
                    continue   # check next suitable rule if not denied
                else:
                    error_msg = unicode2bytes(
                        "you need to have role '%s'" % rule.role)
                    raise Forbidden(error_msg)
        defer.returnValue(None)
