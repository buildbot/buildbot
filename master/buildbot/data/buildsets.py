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
from future.utils import itervalues

import copy

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log

from buildbot.data import sourcestamps as sourcestampsapi
from buildbot.data import base
from buildbot.data import types
from buildbot.process.buildrequest import BuildRequestCollapser
from buildbot.process.results import SUCCESS
from buildbot.process.results import worst_status
from buildbot.util import datetime2epoch
from buildbot.util import epoch2datetime


class Db2DataMixin(object):

    @defer.inlineCallbacks
    def db2data(self, bsdict):
        if not bsdict:
            defer.returnValue(None)

        buildset = bsdict.copy()

        # gather the actual sourcestamps, in parallel
        sourcestamps = []

        @defer.inlineCallbacks
        def getSs(ssid):
            ss = yield self.master.data.get(('sourcestamps', str(ssid)))
            sourcestamps.append(ss)
        yield defer.DeferredList([getSs(id)
                                  for id in buildset['sourcestamps']],
                                 fireOnOneErrback=True, consumeErrors=True)
        buildset['sourcestamps'] = sourcestamps

        # minor modifications
        buildset['submitted_at'] = datetime2epoch(buildset['submitted_at'])
        buildset['complete_at'] = datetime2epoch(buildset['complete_at'])

        defer.returnValue(buildset)

    fieldMapping = {
        'buildsetid': 'buildsets.id',
        'external_idstring': 'buildsets.external_idstring',
        'reason': 'buildsets.reason',
        'submitted_at': 'buildsets.submitted_at',
        'complete': 'buildsets.complete',
        'complete_at': 'buildsets.complete_at',
        'results': 'buildsets.results',
        'parent_buildid': 'buildsets.parent_buildid',
        'parent_relationship': 'buildsets.parent_relationship'
    }


class BuildsetEndpoint(Db2DataMixin, base.Endpoint):

    isCollection = False
    pathPatterns = """
        /buildsets/n:bsid
    """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        res = yield self.master.db.buildsets.getBuildset(kwargs['bsid'])
        res = yield self.db2data(res)
        defer.returnValue(res)


class BuildsetsEndpoint(Db2DataMixin, base.Endpoint):

    isCollection = True
    pathPatterns = """
        /buildsets
    """
    rootLinkName = 'buildsets'

    def get(self, resultSpec, kwargs):
        complete = resultSpec.popBooleanFilter('complete')
        resultSpec.fieldMapping = self.fieldMapping
        d = self.master.db.buildsets.getBuildsets(complete=complete, resultSpec=resultSpec)

        @d.addCallback
        def db2data(buildsets):
            d = defer.DeferredList([self.db2data(bs) for bs in buildsets],
                                   fireOnOneErrback=True, consumeErrors=True)

            @d.addCallback
            def getResults(res):
                return [r[1] for r in res]
            return d
        return d


class Buildset(base.ResourceType):

    name = "buildset"
    plural = "buildsets"
    endpoints = [BuildsetEndpoint, BuildsetsEndpoint]
    keyFields = ['bsid']
    eventPathPatterns = """
        /buildsets/:bsid
    """

    class EntityType(types.Entity):
        bsid = types.Integer()
        external_idstring = types.NoneOk(types.String())
        reason = types.String()
        submitted_at = types.Integer()
        complete = types.Boolean()
        complete_at = types.NoneOk(types.Integer())
        results = types.NoneOk(types.Integer())
        sourcestamps = types.List(
            of=sourcestampsapi.SourceStamp.entityType)
        parent_buildid = types.NoneOk(types.Integer())
        parent_relationship = types.NoneOk(types.String())
    entityType = EntityType(name)

    @base.updateMethod
    @defer.inlineCallbacks
    def addBuildset(self, waited_for, scheduler=None, sourcestamps=None, reason=u'',
                    properties=None, builderids=None, external_idstring=None,
                    parent_buildid=None, parent_relationship=None,
                    _reactor=reactor):
        if sourcestamps is None:
            sourcestamps = []
        if properties is None:
            properties = {}
        if builderids is None:
            builderids = []
        submitted_at = int(_reactor.seconds())
        bsid, brids = yield self.master.db.buildsets.addBuildset(
            sourcestamps=sourcestamps, reason=reason,
            properties=properties, builderids=builderids,
            waited_for=waited_for, external_idstring=external_idstring,
            submitted_at=epoch2datetime(submitted_at),
            parent_buildid=parent_buildid, parent_relationship=parent_relationship)

        yield BuildRequestCollapser(self.master, list(itervalues(brids))).collapse()

        # get each of the sourcestamps for this buildset (sequentially)
        bsdict = yield self.master.db.buildsets.getBuildset(bsid)
        sourcestamps = []
        for ssid in bsdict['sourcestamps']:
            sourcestamps.append(
                (yield self.master.data.get(('sourcestamps', str(ssid)))).copy()
            )

        # notify about the component build requests
        brResource = self.master.data.getResourceType("buildrequest")
        brResource.generateEvent(list(itervalues(brids)), 'new')

        # and the buildset itself
        msg = dict(
            bsid=bsid,
            external_idstring=external_idstring,
            reason=reason,
            submitted_at=submitted_at,
            complete=False,
            complete_at=None,
            results=None,
            scheduler=scheduler,
            sourcestamps=sourcestamps)
        # TODO: properties=properties)
        self.produceEvent(msg, "new")

        log.msg("added buildset %d to database" % bsid)

        # if there are no builders, then this is done already, so send the
        # appropriate messages for that
        if not builderids:
            yield self.maybeBuildsetComplete(bsid, _reactor=_reactor)

        defer.returnValue((bsid, brids))

    @base.updateMethod
    @defer.inlineCallbacks
    def maybeBuildsetComplete(self, bsid, _reactor=reactor):
        brdicts = yield self.master.db.buildrequests.getBuildRequests(
            bsid=bsid, complete=False)

        # if there are incomplete buildrequests, bail out
        if brdicts:
            return

        brdicts = yield self.master.db.buildrequests.getBuildRequests(bsid=bsid)

        # figure out the overall results of the buildset:
        cumulative_results = SUCCESS
        for brdict in brdicts:
            cumulative_results = worst_status(
                cumulative_results, brdict['results'])

        # get a copy of the buildset
        bsdict = yield self.master.db.buildsets.getBuildset(bsid)

        # if it's already completed, we're late to the game, and there's
        # nothing to do.
        #
        # NOTE: there's still a strong possibility of a race condition here,
        # which would cause two buildset.$bsid.complete messages to be sent.
        # That's an acceptable risk, and a necessary consequence of this
        # denormalized representation of a buildset's state.
        if bsdict['complete']:
            return

        # mark it as completed in the database
        complete_at = epoch2datetime(int(_reactor.seconds()))
        yield self.master.db.buildsets.completeBuildset(bsid,
                                                        cumulative_results, complete_at=complete_at)

        # get the sourcestamps for the message
        # get each of the sourcestamps for this buildset (sequentially)
        bsdict = yield self.master.db.buildsets.getBuildset(bsid)
        sourcestamps = []
        for ssid in bsdict['sourcestamps']:
            sourcestamps.append(
                copy.deepcopy(
                    (yield self.master.data.get(('sourcestamps', str(ssid))))
                )
            )

        msg = dict(
            bsid=bsid,
            external_idstring=bsdict['external_idstring'],
            reason=bsdict['reason'],
            sourcestamps=sourcestamps,
            submitted_at=bsdict['submitted_at'],
            complete=True,
            complete_at=complete_at,
            results=cumulative_results)
        # TODO: properties=properties)
        self.produceEvent(msg, "complete")
