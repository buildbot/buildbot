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

from twisted.python import log
from twisted.internet import defer, reactor
from buildbot.util import datetime2epoch, epoch2datetime
from buildbot.status.results import SUCCESS, WARNINGS, FAILURE
from buildbot.data import base

class BuildsetEndpoint(base.Endpoint):

    pathPattern = ( 'buildset', 'i:bsid' )

    def get(self, options, kwargs):
        d = self.master.db.buildsets.getBuildset(kwargs['bsid'])
        d.addCallback(_addLink)
        return d

    def startConsuming(self, callback, options, kwargs):
        return self.master.mq.startConsuming(callback,
                ('buildset', str(kwargs['bsid']), 'complete'))


class BuildsetsEndpoint(base.Endpoint):

    pathPattern = ( 'buildset', )

    def get(self, options, kwargs):
        complete = None
        if 'complete' in options:
            complete = bool(options['complete']) # TODO: booleans from strings?
        d = self.master.db.buildsets.getBuildsets(complete=complete)
        @d.addCallback
        def addLinks(list):
            return [ _addLink(bs) for bs in list ]
        return d

    def startConsuming(self, callback, options, kwargs):
        return self.master.mq.startConsuming(callback,
                ('buildset', None, 'new'))



class BuildsetResourceType(base.ResourceType):

    type = "buildset"
    endpoints = [ BuildsetEndpoint, BuildsetsEndpoint ]
    keyFields = [ 'bsid' ]

    @base.updateMethod
    @defer.inlineCallbacks
    def addBuildset(self, scheduler=None, sourcestampsetid=None, reason=u'',
            properties={}, builderNames=[], external_idstring=None,
            _reactor=reactor):
        submitted_at = int(_reactor.seconds())
        bsid, brids = yield self.master.db.buildsets.addBuildset(
                sourcestampsetid=sourcestampsetid, reason=reason,
                properties=properties, builderNames=builderNames,
                external_idstring=external_idstring,
                submitted_at=epoch2datetime(submitted_at))

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
            sourcestampsetid=sourcestampsetid,
            submitted_at=submitted_at,
            complete=False,
            complete_at=None,
            results=None,
            scheduler=scheduler)
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

        msg = dict(
            bsid=bsid,
            external_idstring=bsdict['external_idstring'],
            reason=bsdict['reason'],
            sourcestampsetid=bsdict['sourcestampsetid'],
            submitted_at=datetime2epoch(bsdict['submitted_at']),
            complete=True,
            complete_at=complete_at_epoch,
            results=cumulative_results)
            # TODO: properties=properties)
        self.master.mq.produce(('buildset', str(bsid), 'complete'), msg)


def _addLink(bsdict):
    if bsdict:
        bsdict = bsdict.copy()
        bsdict['submitted_at'] = datetime2epoch(bsdict['submitted_at'])
        bsdict['complete_at'] = datetime2epoch(bsdict['complete_at'])
        bsdict['link'] = base.Link(('buildset', str(bsdict['bsid'])))
    return bsdict
