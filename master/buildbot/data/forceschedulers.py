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

from buildbot.data import base, types
from buildbot.schedulers import forcesched


def forceScheduler2Data(sched):
    ret = dict(all_fields = [],
               name = sched.name,
               builder_names = sched.builderNames)
    for field in sched.all_fields:
            ret["all_fields"].append(field.toJsonDict())
    return ret

class ForceSchedulerEndpoint(base.Endpoint):

    isCollection = False
    pathPatterns = """
        /forceschedulers/i:schedulername
    """

    def get(self, resultSpec, kwargs):
        for sched in self.master.allSchedulers():
            if sched.name == kwargs['schedulername'] and isinstance(sched, forcesched.ForceScheduler):
                return forceScheduler2Data(sched)


class ForceSchedulersEndpoint(base.Endpoint):

    isCollection = True
    pathPatterns = """
        /forceschedulers
    """
    rootLinkName = 'schedulers'

    def get(self, resultSpec, kwargs):
        l = []
        for sched in self.master.allSchedulers():
            print sched, isinstance(sched, forcesched.ForceScheduler)
            if isinstance(sched, forcesched.ForceScheduler):
                l.append(forceScheduler2Data(sched))
        return l


class ForceScheduler(base.ResourceType):

    name = "forcescheduler"
    plural = "forceschedulers"
    endpoints = [ ForceSchedulerEndpoint, ForceSchedulersEndpoint ]
    keyFields = [ ]

    class EntityType(types.Entity):
        name = types.String()
        builder_names = types.List(of=types.Identifier())
        all_fields = types.List(of=types.JsonObject())
    entityType = EntityType(name)

