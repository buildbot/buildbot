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

from buildbot.data import base
from buildbot.data import types
from buildbot.db.buildrequests import AlreadyClaimedError

from buildbot.db.buildrequests import NotClaimedError
from twisted.internet import defer
from twisted.internet import reactor


class Db2DataMixin(object):

    def db2data(self, dbdict):
        data = {
            'buildrequestid': dbdict['buildrequestid'],
            'buildsetid': dbdict['buildsetid'],
            'builderid': dbdict['builderid'],
            'priority': dbdict['priority'],
            'claimed': dbdict['claimed'],
            'claimed_at': dbdict['claimed_at'],
            'claimed_by_masterid': dbdict['claimed_by_masterid'],
            'complete': dbdict['complete'],
            'results': dbdict['results'],
            'submitted_at': dbdict['submitted_at'],
            'complete_at': dbdict['complete_at'],
            'waited_for': dbdict['waited_for'],
        }
        return defer.succeed(data)


class BuildRequestEndpoint(Db2DataMixin, base.Endpoint):

    isCollection = False
    pathPatterns = """
        /buildrequests/n:buildrequestid
    """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        buildrequest = yield self.master.db.buildrequests.getBuildRequest(kwargs['buildrequestid'])

        if buildrequest:
            defer.returnValue((yield self.db2data(buildrequest)))
        defer.returnValue(None)

    def startConsuming(self, callback, options, kwargs):
        buildrequestid = kwargs.get('buildrequestid')
        return self.master.mq.startConsuming(callback,
                                             ('buildrequests', buildrequestid, None))


class BuildRequestsEndpoint(Db2DataMixin, base.Endpoint):

    isCollection = True
    pathPatterns = """
        /buildrequests
        /builders/i:buildername/buildrequests
        /builders/n:builderid/buildrequests
    """
    rootLinkName = 'buildrequests'

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        builderid = kwargs.get("builderid", None)
        complete = resultSpec.popBooleanFilter('complete')
        claimed_by_masterid = resultSpec.popBooleanFilter('claimed_by_masterid')
        if claimed_by_masterid:
            # claimed_by_masterid takes precedence over 'claimed' filter
            # (no need to check consistency with 'claimed' filter even if
            # 'claimed'=False with 'claimed_by_masterid' set, doesn't make sense)
            claimed = claimed_by_masterid
        else:
            claimed = resultSpec.popBooleanFilter('claimed')

        bsid = resultSpec.popOneFilter('buildsetid', 'eq')
        buildrequests = yield self.master.db.buildrequests.getBuildRequests(
            builderid=builderid,
            complete=complete,
            claimed=claimed,
            bsid=bsid)
        defer.returnValue(
            [(yield self.db2data(br)) for br in buildrequests])

    def startConsuming(self, callback, options, kwargs):
        return self.master.mq.startConsuming(callback,
                                             ('buildrequests', None, None, None, None))


class BuildRequest(base.ResourceType):

    name = "buildrequest"
    plural = "buildrequests"
    endpoints = [BuildRequestEndpoint, BuildRequestsEndpoint]
    keyFields = ['buildsetid', 'builderid', 'buildrequestid']
    eventPathPatterns = """
        /buildsets/:buildsetid/builders/:builderid/buildrequests/:buildrequestid
        /buildrequests/:buildrequestid
    """

    class EntityType(types.Entity):
        buildrequestid = types.Integer()
        buildsetid = types.Integer()
        builderid = types.Integer()
        priority = types.Integer()
        claimed = types.Boolean()
        claimed_at = types.NoneOk(types.DateTime())
        claimed_by_masterid = types.NoneOk(types.Integer())
        complete = types.Boolean()
        results = types.NoneOk(types.Integer())
        submitted_at = types.DateTime()
        complete_at = types.NoneOk(types.DateTime())
        waited_for = types.Boolean()
    entityType = EntityType(name)

    @defer.inlineCallbacks
    def generateEvent(self, brids, event):
        for _id in brids:
            # get the build and munge the result for the notification
            br = yield self.master.data.get(('buildrequests', str(_id)))
            br = copy.deepcopy(br)
            self.produceEvent(br, event)

    @defer.inlineCallbacks
    def callDbBuildRequests(self, brids, db_callable, event, **kw):
        if not brids:
            # empty buildrequest list. No need to call db API
            defer.returnValue(True)
        try:
            yield db_callable(brids, **kw)
        except AlreadyClaimedError:
            # the db layer returned an AlreadyClaimedError exception, usually
            # because one of the buildrequests has already been claimed by another master
            defer.returnValue(False)
        yield self.generateEvent(brids, event)
        defer.returnValue(True)

    @base.updateMethod
    def claimBuildRequests(self, brids, claimed_at=None, _reactor=reactor):
        return self.callDbBuildRequests(brids,
                                        self.master.db.buildrequests.claimBuildRequests,
                                        event="claimed",
                                        claimed_at=claimed_at,
                                        _reactor=_reactor)

    @base.updateMethod
    def reclaimBuildRequests(self, brids, _reactor=reactor):
        return self.callDbBuildRequests(brids,
                                        self.master.db.buildrequests.reclaimBuildRequests,
                                        event="update",
                                        _reactor=_reactor)

    @base.updateMethod
    @defer.inlineCallbacks
    def unclaimBuildRequests(self, brids):
        if brids:
            yield self.master.db.buildrequests.unclaimBuildRequests(brids)
            yield self.generateEvent(brids, "unclaimed")

    @base.updateMethod
    @defer.inlineCallbacks
    def completeBuildRequests(self, brids, results, complete_at=None,
                              _reactor=reactor):
        if not brids:
            # empty buildrequest list. No need to call db API
            defer.returnValue(True)
        try:
            yield self.master.db.buildrequests.completeBuildRequests(
                brids,
                results,
                complete_at=complete_at,
                _reactor=_reactor)
        except NotClaimedError:
            # the db layer returned a NotClaimedError exception, usually
            # because one of the buildrequests has been claimed by another master
            defer.returnValue(False)
        yield self.generateEvent(brids, "complete")
        defer.returnValue(True)

    @base.updateMethod
    @defer.inlineCallbacks
    def unclaimExpiredRequests(self, old, _reactor=reactor):
        yield self.master.db.buildrequests.unclaimExpiredRequests(old, _reactor=_reactor)
