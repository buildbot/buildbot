import fnmatch
import re


class Authz(object):

    # fnmatch and re.match are reversed API, we cannot just rename them
    @staticmethod
    def fnmatchStrMatcher(value, match):
        return fnmatch.fnmatch(value, match)

    @staticmethod
    def reStrMatcher(value, match):
        return re.match(match, value)

    def __init__(self, allowRules=None, roleMatchers=None, stringsMatcher=fnmatchStrMatcher):
        self.match = stringsMatcher
        if allowRules is None:
            allowRules = []
        if roleMatchers is None:
            roleMatchers = []
        self.allowRules = allowRules
        self.roleMatchers = roleMatchers

    def isUserAllowed(self, ep, action, userDetails):
        return True
