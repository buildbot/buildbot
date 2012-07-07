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

class ResourceType(object):
    type = None
    endpoints = []
    keyFields = []

    def __init__(self, master):
        self.master = master

    def getEndpoints(self):
        endpoints = self.endpoints[:]
        for i in xrange(len(endpoints)):
            ep = endpoints[i]
            if not issubclass(ep, Endpoint):
                raise TypeError("Not an Endpoint subclass")
            endpoints[i] = ep(self.master)
        return endpoints

    def produceEvent(self, msg, event):
        routingKey = (self.type,) \
             + tuple(str(msg[k]) for k in self.keyFields) \
             + (event,)
        self.master.mq.produce(routingKey, msg)


class Endpoint(object):
    pathPattern = None
    rootLinkName = None

    def __init__(self, master):
        self.master = master

    def get(self, options, kwargs):
        raise NotImplementedError

    def control(self, action, args, kwargs):
        raise NotImplementedError

    def startConsuming(self, callback, options, kwargs):
        raise NotImplementedError


class Link(object):
    "A Link points to another resource, specified by path"

    __slots__ = [ 'path' ]

    def __init__(self, path):
        self.path = path

    def __repr__(self):
        return "Link(%r)" % (self.path,)

    def __cmp__(self, other):
        return cmp(self.__class__, other.__class__) \
                or cmp(self.path, other.path)


def updateMethod(func):
    """Decorate this resourceType instance as an update method, made available
    at master.data.updates.$funcname"""
    func.isUpdateMethod = True
    return func
