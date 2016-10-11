from future.builtins import range

import urlparse
import xmlrpclib

from model import Build
from model import Builder


class BuildBotSystem(object):

    def __init__(self, url):
        try:
            scheme, loc, _, _, _ = urlparse.urlsplit(url, scheme='http')
            url = '%s://%s/xmlrpc' % (scheme, loc)
            self.server = xmlrpclib.ServerProxy(url)
        except Exception as e:
            raise ValueError(
                'Invalid BuildBot XML-RPC server %s: %s' % (url, e))

    def getAllBuildsInInterval(self, start, stop):
        return self.server.getAllBuildsInInterval(start, stop)

    def getBuilder(self, name):
        builds = []
        for i in range(1, 5 + 1):
            try:
                builds.append(Build(self.server.getBuild(name, -i)))
            except Exception as e:
                self.env.log.debug('Cannot fetch build-info: %s' % (e))
                break
        return Builder(name, builds, [])

    def getAllBuilders(self):
        return self.server.getAllBuilders()
