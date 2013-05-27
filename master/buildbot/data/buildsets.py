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
from twisted.python import log
from twisted.internet import defer, reactor
from buildbot.util import datetime2epoch, epoch2datetime
from buildbot.status.results import SUCCESS, WARNINGS, FAILURE
from buildbot.data import base, types, sourcestamps

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
            ss = yield self.master.data.get(('sourcestamp', str(ssid)))
            sourcestamps.append(ss)
        yield defer.DeferredList([ getSs(id)
                                   for id in buildset['sourcestamps'] ],
                fireOnOneErrback=True, consumeErrors=True)
        buildset['sourcestamps'] = sourcestamps

        # minor modifications
        buildset['submitted_at'] = datetime2epoch(buildset['submitted_at'])
        buildset['complete_at'] = datetime2epoch(buildset['complete_at'])
        buildset['link'] = base.Link(('buildset', str(buildset['bsid'])))

        defer.returnValue(buildset)

class BuildsetEndpoint(Db2DataMixin, base.Endpoint):

    isCollection = False
    pathPatterns = """
        /buildset/n:bsid
    """

    def get(self, resultSpec, kwargs):
        d = self.master.db.buildsets.getBuildset(kwargs['bsid'])
        d.addCallback(self.db2data)
        return d

    def startConsuming(self, callback, options, kwargs):
        return self.master.mq.startConsuming(callback,
                ('buildset', str(kwargs['bsid']), 'complete'))


class BuildsetsEndpoint(Db2DataMixin, base.Endpoint):

    isCollection = True
    pathPatterns = """
        /buildset
    """
    rootLinkName = 'buildset'

    def get(self, resultSpec, kwargs):
        complete = resultSpec.popBooleanFilter('complete')
        d = self.master.db.buildsets.getBuildsets(complete=complete)
        @d.addCallback
        def db2data(buildsets):
            d = defer.DeferredList([ self.db2data(bs) for bs in buildsets ],
                    fireOnOneErrback=True, consumeErrors=True)
            @d.addCallback
            def getResults(res):
                return [ r[1] for r in res ]
            return d
        return d

    def startConsuming(self, callback, options, kwargs):
        return self.master.mq.startConsuming(callback,
                ('buildset', None, 'new'))


class Buildset(base.ResourceType):

    name = "buildset"
    plural = "buildsets"
    endpoints = [ BuildsetEndpoint, BuildsetsEndpoint ]
    keyFields = [ 'bsid' ]

    class EntityType(types.Entity):
        bsid = types.Integer()
        external_idstring = types.NoneOk(types.String())
        reason = types.String()
        submitted_at = types.Integer()
        complete = types.Boolean()
        complete_at = types.NoneOk(types.Integer())
        results = types.NoneOk(types.Integer())
        sourcestamps = types.List(
                of=sourcestamps.SourceStamp.entityType)
        link = types.Link()
    entityType = EntityType(name)

    @base.updateMethod
    @defer.inlineCallbacks
    def addBuildset(self, scheduler=None, sourcestamps=[], reason=u'',
            properties={}, builderNames=[], external_idstring=None,
            _reactor=reactor):
        submitted_at = int(_reactor.seconds())
        bsid, brids = yield self.master.db.buildsets.addBuildset(
                sourcestamps=sourcestamps, reason=reason,
                properties=properties, builderNames=builderNames,
                external_idstring=external_idstring,
                submitted_at=epoch2datetime(submitted_at))

        # get each of the sourcestamps for this buildset (sequentially)
        bsdict = yield self.master.db.buildsets.getBuildset(bsid)
        sourcestamps = [
            (yield self.master.data.get(('sourcestamp', str(ssid)))).copy()
            for ssid in bsdict['sourcestamps'] ]

        # strip the links from those sourcestamps
        for ss in sourcestamps:
            del ss['link']

        # notify about the component build requests
        # TODO: needs to be refactored when buildrequests are in the DB
        for bn, brid in brids.iteritems():
            builderid = -1 # TODO
            msg = dict(
                brid=brid,
                bsid=bsid,
                buildername=bn,
                builderid=builderid)
            self.master.mq.produce(('buildrequest', str(bsid), str(builderid),
                                str(brid), 'new'), msg)

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
        self.master.mq.produce(("buildset", str(bsid), "new"), msg)

        log.msg("added buildset %d to database" % bsid)

        # if there are no builderNames, then this is done already, so send the
        # appropriate messages for that
        if not builderNames:
            yield self.maybeBuildsetComplete(bsid, _reactor=_reactor)

        defer.returnValue((bsid,brids))

    @base.updateMethod
    @defer.inlineCallbacks
    def maybeBuildsetComplete(self, bsid, _reactor=reactor):
        brdicts = yield self.master.db.buildrequests.getBuildRequests(
            bsid=bsid, complete=False)

        # if there are incomplete buildrequests, bail out
        if brdicts:
            return

        brdicts = yield self.master.db.buildrequests.getBuildRequests(bsid=bsid)

        # figure out the overall results of the buildset: SUCCESS unless
        # at least one build was not SUCCESS or WARNINGS.
        cumulative_results = SUCCESS
        for brdict in brdicts:
            if brdict['results'] not in (SUCCESS, WARNINGS):
                cumulative_results = FAILURE

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
        complete_at_epoch = int(_reactor.seconds())
        complete_at = epoch2datetime(complete_at_epoch)
        yield self.master.db.buildsets.completeBuildset(bsid,
                cumulative_results, complete_at=complete_at)

        # get the sourcestamps for the message
        # get each of the sourcestamps for this buildset (sequentially)
        bsdict = yield self.master.db.buildsets.getBuildset(bsid)
        sourcestamps = [
            copy.deepcopy((yield self.master.data.get(
                                            ('sourcestamp', str(ssid)))))
            for ssid in bsdict['sourcestamps'] ]

        # strip the links from those sourcestamps
        for ss in sourcestamps:
            del ss['link']

        msg = dict(
            bsid=bsid,
            external_idstring=bsdict['external_idstring'],
            reason=bsdict['reason'],
            sourcestamps=sourcestamps,
            submitted_at=datetime2epoch(bsdict['submitted_at']),
            complete=True,
            complete_at=complete_at_epoch,
            results=cumulative_results)
            # TODO: properties=properties)
        self.master.mq.produce(('buildset', str(bsid), 'complete'), msg)


