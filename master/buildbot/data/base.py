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
from buildbot.data import exceptions

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
    pathPatterns = []
    rootLinkName = None

    def __init__(self, master):
        self.master = master

    def get(self, options, kwargs):
        raise NotImplementedError

    def control(self, action, args, kwargs):
        raise NotImplementedError

    def startConsuming(self, callback, options, kwargs):
        raise NotImplementedError

class ControlParamsCheckMixin(object):
    action_specs = {}
    def control(self, action, args, kwargs):
        if not action in self.action_specs:
            raise exceptions.InvalidActionException(
                "'%s' action is not supported. Only %s are"%(action, self.action_specs.keys()))
        self.checkParams(args,self.action_specs[action])
        return self.safeControl(action, args, kwargs)
    def safeControl(self, action, args, kwargs):
        raise NotImplementedError
    def checkParams(self, args, specs):
        """specs is a dict with check descriptions:
           type: verify the arg is of this type
           re: verify the arg matches the compiled regex
           required: verify the arg exist is args
        """
        for k, spec in specs.items():
            if "required" in spec:
                if not k in args:
                    raise exceptions.InvalidOptionException("need '%s' param"%(k))
            if not k in args:
                continue
            arg = args[k]
            if "type" in spec:
                if spec["type"] != type(arg):
                    raise exceptions.InvalidOptionException(
                        "need '%s' param to be a '%s' while its '%s'"%(k,
                                                                       str(spec["type"]),
                                                                       arg))
            if "re" in spec:
                if not spec["re"].match(arg):
                    raise exceptions.InvalidOptionException(
                        "need '%s' param to match regular expression '%s' its '%s'"%(k,
                                                                       spec["re"].pattern,
                                                                       arg))
        for k in args.keys():
            if not k in specs:
                    raise exceptions.InvalidOptionException(
                        "param '%s' is not supported by this api only %s are"%(k, specs.keys()))

class Link(object):
    "A Link points to another resource, specified by path"

    __slots__ = [ 'path' ]

    def __init__(self, path):
        assert isinstance(path, tuple)
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
