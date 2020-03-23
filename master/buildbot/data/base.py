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

import copy
import re
from collections import UserList

from twisted.internet import defer

from buildbot.data import exceptions


class ResourceType:
    name = None
    plural = None
    endpoints = []
    keyFields = []
    eventPathPatterns = ""
    entityType = None

    def __init__(self, master):
        self.master = master
        self.compileEventPathPatterns()

    def compileEventPathPatterns(self):
        # We'll run a single format, and then split the string
        # to get the final event path tuple
        pathPatterns = self.eventPathPatterns
        pathPatterns = pathPatterns.split()
        identifiers = re.compile(r':([^/]*)')
        for i, pp in enumerate(pathPatterns):
            pp = identifiers.sub(r'{\1}', pp)
            if pp.startswith("/"):
                pp = pp[1:]
            pathPatterns[i] = pp
        self.eventPaths = pathPatterns

    def getEndpoints(self):
        endpoints = self.endpoints[:]
        for i, ep in enumerate(endpoints):
            if not issubclass(ep, Endpoint):
                raise TypeError("Not an Endpoint subclass")
            endpoints[i] = ep(self, self.master)
        return endpoints

    @staticmethod
    def sanitizeMessage(msg):
        msg = copy.deepcopy(msg)
        return msg

    def produceEvent(self, msg, event):
        if msg is not None:
            msg = self.sanitizeMessage(msg)
            for path in self.eventPaths:
                path = path.format(**msg)
                routingKey = tuple(path.split("/")) + (event,)
                self.master.mq.produce(routingKey, msg)


class Endpoint:
    pathPatterns = ""
    rootLinkName = None
    isCollection = False
    isRaw = False

    def __init__(self, rtype, master):
        self.rtype = rtype
        self.master = master

    def get(self, resultSpec, kwargs):
        raise NotImplementedError

    def control(self, action, args, kwargs):
        # we convert the action into a mixedCase method name
        action_method = getattr(self, "action" + action.capitalize(), None)
        if action_method is None:
            raise exceptions.InvalidControlException("action: {} is not supported".format(action))
        return action_method(args, kwargs)

    def __repr__(self):
        return "endpoint for " + self.pathPatterns


class BuildNestingMixin:

    """
    A mixin for methods to decipher the many ways a build, step, or log can be
    specified.
    """

    @defer.inlineCallbacks
    def getBuildid(self, kwargs):
        # need to look in the context of a step, specified by build or
        # builder or whatever
        if 'buildid' in kwargs:
            return kwargs['buildid']
        else:
            builderid = yield self.getBuilderId(kwargs)
            if builderid is None:
                return None
            build = yield self.master.db.builds.getBuildByNumber(
                builderid=builderid,
                number=kwargs['build_number'])
            if not build:
                return None
            return build['id']

    @defer.inlineCallbacks
    def getStepid(self, kwargs):
        if 'stepid' in kwargs:
            return kwargs['stepid']
        else:
            buildid = yield self.getBuildid(kwargs)
            if buildid is None:
                return None

            dbdict = yield self.master.db.steps.getStep(buildid=buildid,
                                                        number=kwargs.get(
                                                            'step_number'),
                                                        name=kwargs.get('step_name'))
            if not dbdict:
                return None
            return dbdict['id']

    def getBuilderId(self, kwargs):
        if 'buildername' in kwargs:
            return self.master.db.builders.findBuilderId(kwargs['buildername'], autoCreate=False)
        return defer.succeed(kwargs['builderid'])


class ListResult(UserList):

    __slots__ = ['offset', 'total', 'limit']

    def __init__(self, values,
                 offset=None, total=None, limit=None):
        super().__init__(values)

        # if set, this is the index in the overall results of the first element of
        # this list
        self.offset = offset

        # if set, this is the total number of results
        self.total = total

        # if set, this is the limit, either from the user or the implementation
        self.limit = limit

    def __repr__(self):
        return "ListResult(%r, offset=%r, total=%r, limit=%r)" % \
            (self.data, self.offset, self.total, self.limit)

    def __eq__(self, other):
        if isinstance(other, ListResult):
            return self.data == other.data \
                and self.offset == other.offset \
                and self.total == other.total \
                and self.limit == other.limit
        return self.data == other \
            and self.offset == self.limit is None \
            and (self.total is None or self.total == len(other))

    def __ne__(self, other):
        return not (self == other)


def updateMethod(func):
    """Decorate this resourceType instance as an update method, made available
    at master.data.updates.$funcname"""
    func.isUpdateMethod = True
    return func
