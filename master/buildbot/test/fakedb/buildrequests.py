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


from twisted.internet import defer

from buildbot.db import buildrequests
from buildbot.test.fakedb.base import FakeDBComponent
from buildbot.test.fakedb.row import Row
from buildbot.util import datetime2epoch


class BuildRequest(Row):
    table = "buildrequests"

    defaults = dict(
        id=None,
        buildsetid=None,
        builderid=None,
        buildername=None,
        priority=0,
        complete=0,
        results=-1,
        submitted_at=12345678,
        complete_at=None,
        waited_for=0,
    )
    foreignKeys = ('buildsetid',)

    id_column = 'id'
    required_columns = ('buildsetid',)


class BuildRequestClaim(Row):
    table = "buildrequest_claims"

    defaults = dict(
        brid=None,
        masterid=None,
        claimed_at=None
    )
    foreignKeys = ('brid', 'masterid')

    required_columns = ('brid', 'masterid', 'claimed_at')


class FakeBuildRequestsComponent(FakeDBComponent):

    # for use in determining "my" requests
    MASTER_ID = 824

    def setUp(self):
        self.reqs = {}
        self.claims = {}

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, BuildRequest):
                self.reqs[row.id] = row

            if isinstance(row, BuildRequestClaim):
                self.claims[row.brid] = row

    # component methods
    @defer.inlineCallbacks
    def getBuildRequest(self, brid):
        row = self.reqs.get(brid)
        if row:
            claim_row = self.claims.get(brid, None)
            if claim_row:
                row.claimed_at = claim_row.claimed_at
                row.claimed = True
                row.masterid = claim_row.masterid
                row.claimed_by_masterid = claim_row.masterid
            else:
                row.claimed_at = None
            builder = yield self.db.builders.getBuilder(row.builderid)
            row.buildername = builder["name"]
            return self._brdictFromRow(row)
        else:
            return None

    @defer.inlineCallbacks
    def getBuildRequests(self, builderid=None, complete=None, claimed=None,
                         bsid=None, branch=None, repository=None, resultSpec=None):
        rv = []
        for br in self.reqs.values():
            if builderid and br.builderid != builderid:
                continue
            if complete is not None:
                if complete and not br.complete:
                    continue
                if not complete and br.complete:
                    continue
            claim_row = self.claims.get(br.id)
            if claim_row:
                br.claimed_at = claim_row.claimed_at
                br.claimed = True
                br.masterid = claim_row.masterid
                br.claimed_by_masterid = claim_row.masterid
            else:
                br.claimed_at = None
            if claimed is not None:
                if isinstance(claimed, bool):
                    if claimed:
                        if not claim_row:
                            continue
                    else:
                        if br.complete or claim_row:
                            continue
                else:
                    if not claim_row or claim_row.masterid != claimed:
                        continue
            if bsid is not None:
                if br.buildsetid != bsid:
                    continue

            if branch or repository:
                buildset = yield self.db.buildsets.getBuildset(br.buildsetid)
                sourcestamps = []
                for ssid in buildset['sourcestamps']:
                    sourcestamps.append((yield self.db.sourcestamps.getSourceStamp(ssid)))

                if branch and not any(branch == s['branch'] for s in sourcestamps):
                    continue
                if repository and not any(repository == s['repository'] for s in sourcestamps):
                    continue
            builder = yield self.db.builders.getBuilder(br.builderid)
            br.buildername = builder["name"]
            rv.append(self._brdictFromRow(br))
        if resultSpec is not None:
            rv = self.applyResultSpec(rv, resultSpec)
        return rv

    def claimBuildRequests(self, brids, claimed_at=None):
        for brid in brids:
            if brid not in self.reqs or brid in self.claims:
                raise buildrequests.AlreadyClaimedError

        if claimed_at is not None:
            claimed_at = datetime2epoch(claimed_at)
        else:
            claimed_at = int(self.reactor.seconds())

        # now that we've thrown any necessary exceptions, get started
        for brid in brids:
            self.claims[brid] = BuildRequestClaim(brid=brid,
                                                  masterid=self.MASTER_ID,
                                                  claimed_at=claimed_at)
        return defer.succeed(None)

    def unclaimBuildRequests(self, brids):
        for brid in brids:
            if brid in self.claims and self.claims[brid].masterid == self.db.master.masterid:
                self.claims.pop(brid)

    def completeBuildRequests(self, brids, results, complete_at=None):
        if complete_at is not None:
            complete_at = datetime2epoch(complete_at)
        else:
            complete_at = int(self.reactor.seconds())

        for brid in brids:
            if brid not in self.reqs or self.reqs[brid].complete == 1:
                raise buildrequests.NotClaimedError

        for brid in brids:
            self.reqs[brid].complete = 1
            self.reqs[brid].results = results
            self.reqs[brid].complete_at = complete_at
        return defer.succeed(None)

    def _brdictFromRow(self, row):
        return buildrequests.BuildRequestsConnectorComponent._brdictFromRow(row, self.MASTER_ID)

    # fake methods

    def fakeClaimBuildRequest(self, brid, claimed_at=None, masterid=None):
        if masterid is None:
            masterid = self.MASTER_ID
        self.claims[brid] = BuildRequestClaim(brid=brid,
                                              masterid=masterid,
                                              claimed_at=self.reactor.seconds())

    def fakeUnclaimBuildRequest(self, brid):
        del self.claims[brid]

    # assertions

    def assertMyClaims(self, claimed_brids):
        self.t.assertEqual(
            [id for (id, brc) in self.claims.items()
             if brc.masterid == self.MASTER_ID],
            claimed_brids)
