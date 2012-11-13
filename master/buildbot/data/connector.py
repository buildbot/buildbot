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

import inspect
from twisted.python import reflect
from twisted.internet import defer
from twisted.application import service
from buildbot.util import pathmatch
from buildbot.data import exceptions, base

class Updates(object):
    # empty container object; see _scanModule, below
    pass

class RTypes(object):
    # empty container object; see _scanModule, below
    pass


class Root(base.Endpoint):
    pathPattern = ()

    def get(self, options, kwargs):
        return defer.succeed(self.master.data.rootLinks)


class DataConnector(service.Service):

    submodules = [
        'buildbot.data.buildsets',
        'buildbot.data.changes',
        'buildbot.data.masters',
        'buildbot.data.builders',
    ]

    def __init__(self, master):
        self.setName('data')
        self.master = master

        self.matcher = pathmatch.Matcher()
        self.rootLinks = {} # links from the root of the API
        self._setup()

    def _scanModule(self, mod, _noSetattr=False):
        for sym in dir(mod):
            obj = getattr(mod, sym)
            if inspect.isclass(obj) and issubclass(obj, base.ResourceType):
                rtype = obj(self.master)
                setattr(self.rtypes, rtype.type, rtype)

                # put its update methonds into our 'updates' attribute
                for name in dir(rtype):
                    o = getattr(rtype, name)
                    if hasattr(o, 'isUpdateMethod'):
                        setattr(self.updates, name, o)

                # load its endpoints
                for ep in rtype.getEndpoints():
                    # don't use inherited values for these parameters
                    clsdict = ep.__class__.__dict__
                    pathPattern = clsdict.get('pathPattern')
                    pathPatterns = clsdict.get('pathPatterns', [])
                    patterns = [ pathPattern ] + pathPatterns
                    rootLinkName = clsdict.get('rootLinkName')
                    for pp in patterns:
                        if pp is not None:
                            self.matcher[pp] = ep
                    if rootLinkName:
                        link = base.Link(patterns[0])
                        self.rootLinks[rootLinkName] = link

    def _setup(self):
        self.updates = Updates()
        self.rtypes = RTypes()
        self.matcher[Root.pathPattern] = Root(self.master)
        for moduleName in self.submodules:
            module = reflect.namedModule(moduleName)
            self._scanModule(module)

    def _lookup(self, path):
        try:
            return self.matcher[path]
        except KeyError:
            raise exceptions.InvalidPathError

    def get(self, options, path):
        endpoint, kwargs = self._lookup(path)
        return endpoint.get(options, kwargs)

    def startConsuming(self, callback, options, path):
        endpoint, kwargs = self._lookup(path)
        return endpoint.startConsuming(callback, options, kwargs)

    def control(self, action, args, path):
        endpoint, kwargs = self._lookup(path)
        return endpoint.control(action, args, kwargs)
