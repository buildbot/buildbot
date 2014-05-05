import fnmatch
import re


class Authz(object):

    @staticmethod
    def fnmatchMatcher(value, match):
        return fnmatch.fnmatch(value, match)

    @staticmethod
    def reMatcher(value, match):
        return re.match(match, value)

    def __init__(self, allowRules, roleMatchers, stringsMatcher=fnmatchMatcher):
        self.match = stringsMatcher
        self.allowRules = allowRules
        self.roleMatchers = roleMatchers

    def isUserAllowed(self, ep, action, userDetails):
        return True

