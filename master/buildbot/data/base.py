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

from __future__ import absolute_import
from __future__ import print_function
from future.builtins import range
from future.moves.collections import UserList

import copy
import re

from twisted.internet import defer

from buildbot.data import exceptions


class ResourceType(object):
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
        for i in range(len(endpoints)):
            ep = endpoints[i]
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


class Endpoint(object):
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
        raise exceptions.InvalidControlException

    def __repr__(self):
        return "endpoint for " + self.pathPatterns


class BuildNestingMixin(object):

    """
    A mixin for methods to decipher the many ways a build, step, or log can be
    specified.
    """

    @defer.inlineCallbacks
    def getBuildid(self, kwargs):
        # need to look in the context of a step, specified by build or
        # builder or whatever
        if 'buildid' in kwargs:
            defer.returnValue(kwargs['buildid'])
        else:
            build = yield self.master.db.builds.getBuildByNumber(
                builderid=kwargs['builderid'],
                number=kwargs['build_number'])
            if not build:
                return
            defer.returnValue(build['id'])

    @defer.inlineCallbacks
    def getStepid(self, kwargs):
        if 'stepid' in kwargs:
            defer.returnValue(kwargs['stepid'])
        else:
            buildid = yield self.getBuildid(kwargs)
            if buildid is None:
                return

            dbdict = yield self.master.db.steps.getStep(buildid=buildid,
                                                        number=kwargs.get(
                                                            'step_number'),
                                                        name=kwargs.get('step_name'))
            if not dbdict:
                return
            defer.returnValue(dbdict['id'])


class ListResult(UserList):

    __slots__ = ['offset', 'total', 'limit']

    def __init__(self, values,
                 offset=None, total=None, limit=None):
        UserList.__init__(self, values)

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
