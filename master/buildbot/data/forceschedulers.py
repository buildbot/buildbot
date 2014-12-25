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

from buildbot.data import base
from buildbot.data import types
from buildbot.schedulers import forcesched
from buildbot.www.rest import BadJsonRpc2
from buildbot.www.rest import JSONRPC_CODES
from twisted.internet import defer


def forceScheduler2Data(sched):
    ret = dict(all_fields=[],
               name=unicode(sched.name),
               label=unicode(sched.label),
               builder_names=map(unicode, sched.builderNames))
    ret["all_fields"] = [field.getSpec() for field in sched.all_fields]
    return ret


class ForceSchedulerEndpoint(base.Endpoint):

    isCollection = False
    pathPatterns = """
        /forceschedulers/i:schedulername
    """

    def get(self, resultSpec, kwargs):
        for sched in self.master.allSchedulers():
            if sched.name == kwargs['schedulername'] and isinstance(sched, forcesched.ForceScheduler):
                return defer.succeed(forceScheduler2Data(sched))
        return defer.succeed(None)

    @defer.inlineCallbacks
    def control(self, action, args, kwargs):
        if action == "force":
            for sched in self.master.allSchedulers():
                if sched.name == kwargs['schedulername'] and isinstance(sched, forcesched.ForceScheduler):
                    try:
                        res = yield sched.force("user", **args)
                        defer.returnValue(res)
                    except forcesched.CollectedValidationError as e:
                        raise BadJsonRpc2(e.errors, JSONRPC_CODES["invalid_params"])
        defer.returnValue(None)


class ForceSchedulersEndpoint(base.Endpoint):

    isCollection = True
    pathPatterns = """
        /forceschedulers
        /builders/:builderid/forceschedulers
    """
    rootLinkName = 'forceschedulers'

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        l = []
        builderid = kwargs.get('builderid', None)
        if builderid is not None:
            bdict = yield self.master.db.builders.getBuilder(builderid)
        for sched in self.master.allSchedulers():
            if isinstance(sched, forcesched.ForceScheduler):
                if builderid is not None and bdict['name'] not in sched.builderNames:
                    continue
                l.append(forceScheduler2Data(sched))
        defer.returnValue(l)


class ForceScheduler(base.ResourceType):

    name = "forcescheduler"
    plural = "forceschedulers"
    endpoints = [ForceSchedulerEndpoint, ForceSchedulersEndpoint]
    keyFields = []

    class EntityType(types.Entity):
        name = types.Identifier(20)
        label = types.String()
        builder_names = types.List(of=types.Identifier(20))
        all_fields = types.List(of=types.JsonObject())
    entityType = EntityType(name)
