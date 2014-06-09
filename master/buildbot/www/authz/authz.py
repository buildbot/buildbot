import fnmatch
import re


# fnmatch and re.match are reversed API, we cannot just rename them
def fnmatchStrMatcher(value, match):
    return fnmatch.fnmatch(value, match)


def reStrMatcher(value, match):
    return re.match(match, value)


class Authz(object):

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
