from buildbot.interfaces import IConfigured
from zope.interface import implements

class Authz(object):
    implements(IConfigured)

    def getConfigDict(self):
        return {}

    def assertUserAllowed(self, **kwargs):
        raise NotImplementedError()
