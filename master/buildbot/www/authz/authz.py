import fnmatch
import re

from buildbot.interfaces import IConfigured
from roles import RolesFromOwner
from twisted.internet import defer
from twisted.web.error import Error
from zope.interface import implements


class Forbidden(Error):

    def __init__(self, msg):
        Error.__init__(self, 403, msg)


# fnmatch and re.match are reversed API, we cannot just rename them
def fnmatchStrMatcher(value, match):
    return fnmatch.fnmatch(value, match)


def reStrMatcher(value, match):
    return re.match(match, value)


class Authz(object):
    implements(IConfigured)

    def getConfigDict(self):
        return {}

    def __init__(self, allowRules=None, roleMatchers=None, stringsMatcher=fnmatchStrMatcher):
        self.match = stringsMatcher
        if allowRules is None:
            allowRules = []
        if roleMatchers is None:
            roleMatchers = []
        self.allowRules = allowRules
        self.roleMatchers = [r for r in roleMatchers if not isinstance(r, RolesFromOwner)]
        self.ownerRoleMatchers = [r for r in roleMatchers if isinstance(r, RolesFromOwner)]

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
                        roles.update(self.getOwnerRolesFromUser(userDetails, owner))
                if rule.role not in roles:
                    if rule.defaultDeny:
                        raise Forbidden("you need to have role '%s'" % (rule.role,))
                elif not rule.defaultDeny:
                    defer.returnValue(None)
        defer.returnValue(None)
