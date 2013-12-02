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

import datetime
import mock

from buildbot.data import buildrequests
from buildbot.data import resultspec
from buildbot.data.base import Link
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import endpoint
from buildbot.test.util import interfaces
from buildbot.util import UTC

from twisted.internet import defer
from twisted.internet import reactor
from twisted.trial import unittest


class TestBuildRequestEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = buildrequests.BuildRequestEndpoint
    resourceTypeClass = buildrequests.BuildRequest

    CLAIMED_AT = datetime.datetime(1978, 6, 15, 12, 31, 15, tzinfo=UTC)
    CLAIMED_AT_EPOCH = 266761875
    SUBMITTED_AT = datetime.datetime(1979, 6, 15, 12, 31, 15, tzinfo=UTC)
    SUBMITTED_AT_EPOCH = 298297875
    COMPLETE_AT = datetime.datetime(1980, 6, 15, 12, 31, 15, tzinfo=UTC)
    COMPLETE_AT_EPOCH = 329920275

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.Builder(id=77, name='bbb'),
            fakedb.Master(id=fakedb.FakeBuildRequestsComponent.MASTER_ID),
            fakedb.Buildslave(id=13, name='sl'),
            fakedb.Buildset(id=8822),
            fakedb.BuildRequest(id=44, buildsetid=8822, buildername='bbb',
                                priority=7, submitted_at=self.SUBMITTED_AT_EPOCH,
                                waited_for=1),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    @defer.inlineCallbacks
    def testGetExisting(self):
        self.db.buildrequests.claimBuildRequests([44], claimed_at=self.CLAIMED_AT)
        self.db.buildrequests.completeBuildRequests([44], 75, complete_at=self.COMPLETE_AT)
        buildrequest = yield self.callGet(('buildrequest', 44))
        self.validateData(buildrequest)
        # check data formatting:
        self.assertEqual(buildrequest['buildrequestid'], 44)
        self.assertEqual(buildrequest['complete'], True)
        self.assertEqual(buildrequest['builderid'], 77)
        self.assertEqual(buildrequest['waited_for'], True)
        self.assertEqual(buildrequest['claimed_at'], self.CLAIMED_AT_EPOCH)
        self.assertEqual(buildrequest['results'], 75)
        self.assertEqual(buildrequest['claimed_by_masterid'],
                         fakedb.FakeBuildRequestsComponent.MASTER_ID)
        self.assertEqual(buildrequest['link'].__repr__(),
                         Link(('buildrequest', '44'), []).__repr__())
        self.assertEqual(buildrequest['claimed'], True)
        self.assertEqual(buildrequest['submitted_at'], self.SUBMITTED_AT_EPOCH)
        self.assertEqual(buildrequest['complete_at'], self.COMPLETE_AT_EPOCH)
        self.assertEqual(buildrequest['buildsetid'], 8822)
        self.assertEqual(buildrequest['priority'], 7)
        self.assertEqual(buildrequest['buildset_link'].__repr__(),
                         Link(('buildset', '8822'), []).__repr__())

    @defer.inlineCallbacks
    def testGetMissing(self):
        buildrequest = yield self.callGet(('buildrequest', 9999))
        self.assertEqual(buildrequest, None)


class TestBuildRequestsEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = buildrequests.BuildRequestsEndpoint
    resourceTypeClass = buildrequests.BuildRequest

    CLAIMED_AT = datetime.datetime(1978, 6, 15, 12, 31, 15, tzinfo=UTC)
    CLAIMED_AT_EPOCH = 266761875
    SUBMITTED_AT = datetime.datetime(1979, 6, 15, 12, 31, 15, tzinfo=UTC)
    SUBMITTED_AT_EPOCH = 298297875
    COMPLETE_AT = datetime.datetime(1980, 6, 15, 12, 31, 15, tzinfo=UTC)
    COMPLETE_AT_EPOCH = 329920275

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.Builder(id=77, name='bbb'),
            fakedb.Builder(id=78, name='ccc'),
            fakedb.Master(id=fakedb.FakeBuildRequestsComponent.MASTER_ID),
            fakedb.Buildslave(id=13, name='sl'),
            fakedb.Buildset(id=8822),
            fakedb.BuildRequest(id=44, buildsetid=8822, buildername='bbb',
                                priority=7, submitted_at=self.SUBMITTED_AT_EPOCH,
                                waited_for=1),
            fakedb.BuildRequest(id=45, buildsetid=8822, buildername='bbb'),
            fakedb.BuildRequest(id=46, buildsetid=8822, buildername='ccc'),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    @defer.inlineCallbacks
    def testGetAll(self):
        buildrequests = yield self.callGet(('buildrequest',))
        [self.validateData(br) for br in buildrequests]
        self.assertEqual(sorted([br['buildrequestid'] for br in buildrequests]),
                         [44, 45, 46])

    @defer.inlineCallbacks
    def testGetBuildername(self):
        buildrequests = yield self.callGet(('builder', 'ccc', 'buildrequest'))
        [self.validateData(br) for br in buildrequests]
        self.assertEqual(sorted([br['buildrequestid'] for br in buildrequests]), [46])

    @defer.inlineCallbacks
    def testGetNoBuildRequest(self):
        buildrequests = yield self.callGet(('builder', 'ddd', 'buildrequest'))
        self.assertEqual(buildrequests, [])

    @defer.inlineCallbacks
    def testGetBuilderid(self):
        buildrequests = yield self.callGet(('builder', 78, 'buildrequest'))
        [self.validateData(br) for br in buildrequests]
        self.assertEqual(sorted([br['buildrequestid'] for br in buildrequests]), [46])

    @defer.inlineCallbacks
    def testGetUnknownBuilderid(self):
        buildrequests = yield self.callGet(('builder', 79, 'buildrequest'))
        self.assertEqual(buildrequests, [])

    @defer.inlineCallbacks
    def testGetNoFilters(self):
        getBuildRequestsMock = mock.Mock(return_value={})
        self.patch(self.master.db.buildrequests, 'getBuildRequests', getBuildRequestsMock)
        yield self.callGet(('buildrequest',))
        getBuildRequestsMock.assert_called_with(
            buildername=None,
            complete=None,
            claimed=None,
            bsid=None,
            branch=None,
            repository=None)

    @defer.inlineCallbacks
    def testGetFilters(self):
        getBuildRequestsMock = mock.Mock(return_value={})
        self.patch(self.master.db.buildrequests, 'getBuildRequests', getBuildRequestsMock)
        f1 = resultspec.Filter('complete', 'eq', [False])
        f2 = resultspec.Filter('claimed', 'eq', [True])
        f3 = resultspec.Filter('bsid', 'eq', [55])
        f4 = resultspec.Filter('branch', 'eq', ['mybranch'])
        f5 = resultspec.Filter('repository', 'eq', ['myrepo'])
        yield self.callGet(
            ('buildrequest',),
            resultSpec=resultspec.ResultSpec(filters=[f1, f2, f3, f4, f5]))
        getBuildRequestsMock.assert_called_with(
            buildername=None,
            complete=False,
            claimed=True,
            bsid=55,
            branch='mybranch',
            repository='myrepo')

    @defer.inlineCallbacks
    def testGetClaimedByMasterIdFilters(self):
        getBuildRequestsMock = mock.Mock(return_value={})
        self.patch(self.master.db.buildrequests, 'getBuildRequests', getBuildRequestsMock)
        f1 = resultspec.Filter('claimed', 'eq', [True])
        f2 = resultspec.Filter('claimed_by_masterid', 'eq',
                               [fakedb.FakeBuildRequestsComponent.MASTER_ID])
        yield self.callGet(
            ('buildrequest',),
            resultSpec=resultspec.ResultSpec(filters=[f1, f2]))
        getBuildRequestsMock.assert_called_with(
            buildername=None,
            complete=None,
            claimed=fakedb.FakeBuildRequestsComponent.MASTER_ID,
            bsid=None,
            branch=None,
            repository=None)


class TestBuildRequest(interfaces.InterfaceTests, unittest.TestCase):

    CLAIMED_AT = datetime.datetime(1978, 6, 15, 12, 31, 15, tzinfo=UTC)
    COMPLETE_AT = datetime.datetime(1980, 6, 15, 12, 31, 15, tzinfo=UTC)

    class dBLayerException(Exception):
        pass

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self,
                                             wantMq=True, wantDb=True, wantData=True)
        self.rtype = buildrequests.BuildRequest(self.master)

    @defer.inlineCallbacks
    def doTestCallthrough(self, dbMethodName, dbMockedMethod, method,
                          methodargs=None, methodkwargs=None,
                          expectedRes=None, expectedException=None,
                          expectedDbApiCalled=True):
        self.patch(self.master.db.buildrequests, dbMethodName, dbMockedMethod)
        if expectedException is not None:
            try:
                yield method(*methodargs, **methodkwargs)
            except expectedException:
                pass
            except Exception as e:
                self.fail('%s exception should be raised, but got %r' % (expectedException, e))
            else:
                self.fail('%s exception should be raised' % (expectedException,))
        else:
            res = yield method(*methodargs, **methodkwargs)
            self.assertEqual(res, expectedRes)
        if expectedDbApiCalled:
            dbMockedMethod.assert_called_with(*methodargs, **methodkwargs)

    def testSignatureClaimBuildRequests(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.claimBuildRequests,  # fake
            self.rtype.claimBuildRequests)  # real
        def claimBuildRequests(self, brids, claimed_at=None, _reactor=reactor):
            pass

    @defer.inlineCallbacks
    def testFakeDataClaimBuildRequests(self):
        res = yield self.master.data.updates.claimBuildRequests(
            [44, 55],
            claimed_at=self.CLAIMED_AT,
            _reactor=reactor)
        self.assertTrue(res)

    @defer.inlineCallbacks
    def testFakeDataClaimBuildRequestsNoneArgs(self):
        res = yield self.master.data.updates.claimBuildRequests([])
        self.assertTrue(res)

    @defer.inlineCallbacks
    def testClaimBuildRequests(self):
        claimBuildRequestsMock = mock.Mock(return_value=defer.succeed(None))
        yield self.doTestCallthrough('claimBuildRequests', claimBuildRequestsMock,
                                     self.rtype.claimBuildRequests,
                                     methodargs=[[44]],
                                     methodkwargs=dict(claimed_at=self.CLAIMED_AT,
                                                       _reactor=reactor),
                                     expectedRes=True,
                                     expectedException=None)

    @defer.inlineCallbacks
    def testClaimBuildRequestsNoBrids(self):
        claimBuildRequestsMock = mock.Mock(return_value=defer.succeed(None))
        yield self.doTestCallthrough('claimBuildRequests', claimBuildRequestsMock,
                                     self.rtype.claimBuildRequests,
                                     methodargs=[[]],
                                     methodkwargs=dict(),
                                     expectedRes=True,
                                     expectedException=None,
                                     expectedDbApiCalled=False)

    @defer.inlineCallbacks
    def testClaimBuildRequestsAlreadyClaimed(self):
        claimBuildRequestsMock = mock.Mock(
            side_effect=buildrequests.AlreadyClaimedError('oups ! buildrequest already claimed'))
        yield self.doTestCallthrough('claimBuildRequests', claimBuildRequestsMock,
                                     self.rtype.claimBuildRequests,
                                     methodargs=[[44]],
                                     methodkwargs=dict(claimed_at=self.CLAIMED_AT,
                                                       _reactor=reactor),
                                     expectedRes=False,
                                     expectedException=None)

    @defer.inlineCallbacks
    def testClaimBuildRequestsUnknownException(self):
        claimBuildRequestsMock = mock.Mock(
            side_effect=self.dBLayerException('oups ! unknown error'))
        yield self.doTestCallthrough('claimBuildRequests', claimBuildRequestsMock,
                                     self.rtype.claimBuildRequests,
                                     methodargs=[[44]],
                                     methodkwargs=dict(claimed_at=self.CLAIMED_AT,
                                                       _reactor=reactor),
                                     expectedRes=None,
                                     expectedException=self.dBLayerException)

    def testSignatureReclaimBuildRequests(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.reclaimBuildRequests,  # fake
            self.rtype.reclaimBuildRequests)  # real
        def reclaimBuildRequests(self, brids, _reactor=reactor):
            pass

    @defer.inlineCallbacks
    def testFakeDataReclaimBuildRequests(self):
        res = yield self.master.data.updates.reclaimBuildRequests(
            [44, 55],
            _reactor=reactor)
        self.assertTrue(res)

    @defer.inlineCallbacks
    def testFakeDataReclaimBuildRequestsNoneArgs(self):
        res = yield self.master.data.updates.reclaimBuildRequests([])
        self.assertTrue(res)

    @defer.inlineCallbacks
    def testReclaimBuildRequests(self):
        reclaimBuildRequestsMock = mock.Mock(return_value=defer.succeed(None))
        yield self.doTestCallthrough('reclaimBuildRequests',
                                     reclaimBuildRequestsMock,
                                     self.rtype.reclaimBuildRequests,
                                     methodargs=[[44]],
                                     methodkwargs=dict(_reactor=reactor),
                                     expectedRes=True,
                                     expectedException=None)

    @defer.inlineCallbacks
    def testReclaimBuildRequestsNoBrids(self):
        reclaimBuildRequestsMock = mock.Mock(return_value=defer.succeed(None))
        yield self.doTestCallthrough('reclaimBuildRequests',
                                     reclaimBuildRequestsMock,
                                     self.rtype.reclaimBuildRequests,
                                     methodargs=[[]],
                                     methodkwargs=dict(),
                                     expectedRes=True,
                                     expectedException=None,
                                     expectedDbApiCalled=False)

    @defer.inlineCallbacks
    def testReclaimBuildRequestsAlreadyClaimed(self):
        reclaimBuildRequestsMock = mock.Mock(
            side_effect=buildrequests.AlreadyClaimedError('oups ! buildrequest already claimed'))
        yield self.doTestCallthrough('reclaimBuildRequests',
                                     reclaimBuildRequestsMock,
                                     self.rtype.reclaimBuildRequests,
                                     methodargs=[[44]],
                                     methodkwargs=dict(_reactor=reactor),
                                     expectedRes=False,
                                     expectedException=None)

    @defer.inlineCallbacks
    def testReclaimBuildRequestsUnknownException(self):
        reclaimBuildRequestsMock = mock.Mock(
            side_effect=self.dBLayerException('oups ! unknown error'))
        yield self.doTestCallthrough('reclaimBuildRequests',
                                     reclaimBuildRequestsMock,
                                     self.rtype.reclaimBuildRequests,
                                     methodargs=[[44]],
                                     methodkwargs=dict(_reactor=reactor),
                                     expectedRes=True,
                                     expectedException=self.dBLayerException)

    def testSignatureUnclaimBuildRequests(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.unclaimBuildRequests,  # fake
            self.rtype.unclaimBuildRequests)  # real
        def unclaimBuildRequests(self, brids):
            pass

    @defer.inlineCallbacks
    def testFakeDataUnclaimBuildRequests(self):
        res = yield self.master.data.updates.unclaimBuildRequests([44, 55])
        self.assertEqual(res, None)

    @defer.inlineCallbacks
    def testFakeDataUnclaimBuildRequestsNoneArgs(self):
        res = yield self.master.data.updates.unclaimBuildRequests([])
        self.assertEqual(res, None)

    @defer.inlineCallbacks
    def testUnclaimBuildRequests(self):
        unclaimBuildRequestsMock = mock.Mock(return_value=defer.succeed(None))
        yield self.doTestCallthrough('unclaimBuildRequests',
                                     unclaimBuildRequestsMock,
                                     self.rtype.unclaimBuildRequests,
                                     methodargs=[[46]],
                                     methodkwargs=dict(),
                                     expectedRes=None,
                                     expectedException=None)

    @defer.inlineCallbacks
    def testUnclaimBuildRequestsNoBrids(self):
        unclaimBuildRequestsMock = mock.Mock(return_value=defer.succeed(None))
        yield self.doTestCallthrough('unclaimBuildRequests',
                                     unclaimBuildRequestsMock,
                                     self.rtype.unclaimBuildRequests,
                                     methodargs=[[]],
                                     methodkwargs=dict(),
                                     expectedRes=None,
                                     expectedException=None,
                                     expectedDbApiCalled=False)

    def testSignatureCompleteBuildRequests(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.completeBuildRequests,  # fake
            self.rtype.completeBuildRequests)  # real
        def completeBuildRequests(self, brids, results, complete_at=None,
                                  _reactor=reactor):
            pass

    @defer.inlineCallbacks
    def testFakeDataCompleteBuildRequests(self):
        res = yield self.master.data.updates.completeBuildRequests(
            [44, 55],
            12,
            complete_at=self.COMPLETE_AT,
            _reactor=reactor)
        self.assertTrue(res)

    @defer.inlineCallbacks
    def testFakeDataCompleteBuildRequestsNoneArgs(self):
        res = yield self.master.data.updates.completeBuildRequests([], 0)
        self.assertTrue(res)

    @defer.inlineCallbacks
    def testCompleteBuildRequests(self):
        completeBuildRequestsMock = mock.Mock(return_value=defer.succeed(None))
        yield self.doTestCallthrough('completeBuildRequests',
                                     completeBuildRequestsMock,
                                     self.rtype.completeBuildRequests,
                                     methodargs=[[46], 12],
                                     methodkwargs=dict(complete_at=self.COMPLETE_AT,
                                                       _reactor=reactor),
                                     expectedRes=True,
                                     expectedException=None)

    @defer.inlineCallbacks
    def testCompleteBuildRequestsNoBrids(self):
        completeBuildRequestsMock = mock.Mock(return_value=defer.succeed(None))
        yield self.doTestCallthrough('completeBuildRequests',
                                     completeBuildRequestsMock,
                                     self.rtype.completeBuildRequests,
                                     methodargs=[[], 0],
                                     methodkwargs=dict(),
                                     expectedRes=True,
                                     expectedException=None,
                                     expectedDbApiCalled=False)

    @defer.inlineCallbacks
    def testCompleteBuildRequestsNotClaimed(self):
        completeBuildRequestsMock = mock.Mock(
            side_effect=buildrequests.NotClaimedError('oups ! buildrequest not claimed'))
        yield self.doTestCallthrough('completeBuildRequests',
                                     completeBuildRequestsMock,
                                     self.rtype.completeBuildRequests,
                                     methodargs=[[46], 12],
                                     methodkwargs=dict(complete_at=self.COMPLETE_AT,
                                                       _reactor=reactor),
                                     expectedRes=False,
                                     expectedException=None)

    @defer.inlineCallbacks
    def testCompleteBuildRequestsUnknownException(self):
        completeBuildRequestsMock = mock.Mock(
            side_effect=self.dBLayerException('oups ! unknown error'))
        yield self.doTestCallthrough('completeBuildRequests',
                                     completeBuildRequestsMock,
                                     self.rtype.completeBuildRequests,
                                     methodargs=[[46], 12],
                                     methodkwargs=dict(complete_at=self.COMPLETE_AT,
                                                       _reactor=reactor),
                                     expectedRes=None,
                                     expectedException=self.dBLayerException)

    def testSignatureUnclaimExpireddRequests(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.unclaimExpiredRequests,  # fake
            self.rtype.unclaimExpiredRequests)  # real
        def unclaimExpiredRequests(self, old, _reactor=reactor):
            pass

    @defer.inlineCallbacks
    def testFakeDataUnclaimExpiredBuildRequests(self):
        res = yield self.master.data.updates.unclaimExpiredRequests(
            600,
            _reactor=reactor)
        self.assertEqual(res, None)

    @defer.inlineCallbacks
    def testFakeDataUnclaimExpiredRequestsNoneArgs(self):
        res = yield self.master.data.updates.unclaimExpiredRequests(0)
        self.assertEqual(res, None)

    @defer.inlineCallbacks
    def testUnclaimExpiredRequests(self):
        unclaimExpiredRequestsMock = mock.Mock(return_value=defer.succeed(None))
        yield self.doTestCallthrough('unclaimExpiredRequests',
                                     unclaimExpiredRequestsMock,
                                     self.rtype.unclaimExpiredRequests,
                                     methodargs=[600],
                                     methodkwargs=dict(_reactor=reactor),
                                     expectedRes=None,
                                     expectedException=None)
