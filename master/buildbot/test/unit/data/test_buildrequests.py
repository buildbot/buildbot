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
from unittest import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.data import buildrequests
from buildbot.data import resultspec
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import endpoint
from buildbot.test.util import interfaces
from buildbot.util import UTC
from buildbot.util import epoch2datetime


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
        self.db.insert_test_data([
            fakedb.Builder(id=77, name='bbb'),
            fakedb.Master(id=fakedb.FakeBuildRequestsComponent.MASTER_ID),
            fakedb.Worker(id=13, name='wrk'),
            fakedb.Buildset(id=8822),
            fakedb.BuildRequest(
                id=44,
                buildsetid=8822,
                builderid=77,
                priority=7,
                submitted_at=self.SUBMITTED_AT_EPOCH,
                waited_for=1,
            ),
            fakedb.BuildsetProperty(
                buildsetid=8822, property_name='prop1', property_value='["one", "fake1"]'
            ),
            fakedb.BuildsetProperty(
                buildsetid=8822, property_name='prop2', property_value='["two", "fake2"]'
            ),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    async def testGetExisting(self):
        self.db.buildrequests.claimBuildRequests([44], claimed_at=self.CLAIMED_AT)
        self.db.buildrequests.completeBuildRequests([44], 75, complete_at=self.COMPLETE_AT)
        buildrequest = await self.callGet(('buildrequests', 44))
        self.validateData(buildrequest)
        # check data formatting:
        self.assertEqual(buildrequest['buildrequestid'], 44)
        self.assertEqual(buildrequest['complete'], True)
        self.assertEqual(buildrequest['builderid'], 77)
        self.assertEqual(buildrequest['waited_for'], True)
        self.assertEqual(buildrequest['claimed_at'], self.CLAIMED_AT)
        self.assertEqual(buildrequest['results'], 75)
        self.assertEqual(
            buildrequest['claimed_by_masterid'], fakedb.FakeBuildRequestsComponent.MASTER_ID
        )
        self.assertEqual(buildrequest['claimed'], True)
        self.assertEqual(buildrequest['submitted_at'], self.SUBMITTED_AT)
        self.assertEqual(buildrequest['complete_at'], self.COMPLETE_AT)
        self.assertEqual(buildrequest['buildsetid'], 8822)
        self.assertEqual(buildrequest['priority'], 7)
        self.assertEqual(buildrequest['properties'], None)

    async def testGetMissing(self):
        buildrequest = await self.callGet(('buildrequests', 9999))
        self.assertEqual(buildrequest, None)

    async def testGetProperty(self):
        prop = resultspec.Property(b'property', 'eq', ['prop1'])
        buildrequest = await self.callGet(
            ('buildrequests', 44), resultSpec=resultspec.ResultSpec(properties=[prop])
        )
        self.assertEqual(buildrequest['buildrequestid'], 44)
        self.assertEqual(buildrequest['properties'], {'prop1': ('one', 'fake1')})

    async def testGetProperties(self):
        prop = resultspec.Property(b'property', 'eq', ['*'])
        buildrequest = await self.callGet(
            ('buildrequests', 44), resultSpec=resultspec.ResultSpec(properties=[prop])
        )
        self.assertEqual(buildrequest['buildrequestid'], 44)
        self.assertEqual(
            buildrequest['properties'], {'prop1': ('one', 'fake1'), 'prop2': ('two', 'fake2')}
        )


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
        self.db.insert_test_data([
            fakedb.Builder(id=77, name='bbb'),
            fakedb.Builder(id=78, name='ccc'),
            fakedb.Builder(id=79, name='ddd'),
            fakedb.Master(id=fakedb.FakeBuildRequestsComponent.MASTER_ID),
            fakedb.Worker(id=13, name='wrk'),
            fakedb.Buildset(id=8822),
            fakedb.BuildRequest(
                id=44,
                buildsetid=8822,
                builderid=77,
                priority=7,
                submitted_at=self.SUBMITTED_AT_EPOCH,
                waited_for=1,
            ),
            fakedb.BuildRequest(id=45, buildsetid=8822, builderid=77),
            fakedb.BuildRequest(id=46, buildsetid=8822, builderid=78),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    async def testGetAll(self):
        buildrequests = await self.callGet(('buildrequests',))

        for br in buildrequests:
            self.validateData(br)

        self.assertEqual(sorted([br['buildrequestid'] for br in buildrequests]), [44, 45, 46])

    async def testGetNoBuildRequest(self):
        buildrequests = await self.callGet(('builders', 79, 'buildrequests'))
        self.assertEqual(buildrequests, [])

    async def testGetBuilderid(self):
        buildrequests = await self.callGet(('builders', 78, 'buildrequests'))

        for br in buildrequests:
            self.validateData(br)

        self.assertEqual(sorted([br['buildrequestid'] for br in buildrequests]), [46])

    async def testGetUnknownBuilderid(self):
        buildrequests = await self.callGet(('builders', 79, 'buildrequests'))
        self.assertEqual(buildrequests, [])

    async def testGetProperties(self):
        self.master.db.insert_test_data([
            fakedb.BuildsetProperty(
                buildsetid=8822, property_name='prop1', property_value='["one", "fake1"]'
            ),
            fakedb.BuildsetProperty(
                buildsetid=8822, property_name='prop2', property_value='["two", "fake2"]'
            ),
        ])
        prop = resultspec.Property(b'property', 'eq', ['*'])
        buildrequests = await self.callGet(
            ('builders', 78, 'buildrequests'), resultSpec=resultspec.ResultSpec(properties=[prop])
        )
        self.assertEqual(len(buildrequests), 1)
        self.assertEqual(buildrequests[0]['buildrequestid'], 46)
        self.assertEqual(
            buildrequests[0]['properties'], {'prop1': ('one', 'fake1'), 'prop2': ('two', 'fake2')}
        )

    async def testGetNoFilters(self):
        getBuildRequestsMock = mock.Mock(return_value={})
        self.patch(self.master.db.buildrequests, 'getBuildRequests', getBuildRequestsMock)
        await self.callGet(('buildrequests',))
        getBuildRequestsMock.assert_called_with(
            builderid=None,
            bsid=None,
            complete=None,
            claimed=None,
            resultSpec=resultspec.ResultSpec(),
        )

    async def testGetFilters(self):
        getBuildRequestsMock = mock.Mock(return_value={})
        self.patch(self.master.db.buildrequests, 'getBuildRequests', getBuildRequestsMock)
        f1 = resultspec.Filter('complete', 'eq', [False])
        f2 = resultspec.Filter('claimed', 'eq', [True])
        f3 = resultspec.Filter('buildsetid', 'eq', [55])
        f4 = resultspec.Filter('branch', 'eq', ['mybranch'])
        f5 = resultspec.Filter('repository', 'eq', ['myrepo'])
        await self.callGet(
            ('buildrequests',), resultSpec=resultspec.ResultSpec(filters=[f1, f2, f3, f4, f5])
        )
        getBuildRequestsMock.assert_called_with(
            builderid=None,
            bsid=55,
            complete=False,
            claimed=True,
            resultSpec=resultspec.ResultSpec(filters=[f4, f5]),
        )

    async def testGetClaimedByMasterIdFilters(self):
        getBuildRequestsMock = mock.Mock(return_value={})
        self.patch(self.master.db.buildrequests, 'getBuildRequests', getBuildRequestsMock)
        f1 = resultspec.Filter('claimed', 'eq', [True])
        f2 = resultspec.Filter(
            'claimed_by_masterid', 'eq', [fakedb.FakeBuildRequestsComponent.MASTER_ID]
        )
        await self.callGet(('buildrequests',), resultSpec=resultspec.ResultSpec(filters=[f1, f2]))
        getBuildRequestsMock.assert_called_with(
            builderid=None,
            bsid=None,
            complete=None,
            claimed=fakedb.FakeBuildRequestsComponent.MASTER_ID,
            resultSpec=resultspec.ResultSpec(filters=[f1]),
        )

    async def testGetSortedLimit(self):
        await self.master.db.buildrequests.completeBuildRequests([44], 1)
        res = await self.callGet(
            ('buildrequests',), resultSpec=resultspec.ResultSpec(order=['results'], limit=2)
        )
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]['results'], -1)
        res = await self.callGet(
            ('buildrequests',), resultSpec=resultspec.ResultSpec(order=['-results'], limit=2)
        )
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]['results'], 1)


class TestBuildRequest(interfaces.InterfaceTests, TestReactorMixin, unittest.TestCase):
    CLAIMED_AT = datetime.datetime(1978, 6, 15, 12, 31, 15, tzinfo=UTC)
    COMPLETE_AT = datetime.datetime(1980, 6, 15, 12, 31, 15, tzinfo=UTC)

    class dBLayerException(Exception):
        pass

    def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self, wantMq=True, wantDb=True, wantData=True)
        self.rtype = buildrequests.BuildRequest(self.master)

    async def doTestCallthrough(
        self,
        dbMethodName,
        dbMockedMethod,
        method,
        methodargs=None,
        methodkwargs=None,
        expectedRes=None,
        expectedException=None,
        expectedDbApiCalled=True,
    ):
        self.patch(self.master.db.buildrequests, dbMethodName, dbMockedMethod)
        if expectedException is not None:
            try:
                await method(*methodargs, **methodkwargs)
            except expectedException:
                pass
            except Exception as e:
                self.fail(f'{expectedException} exception should be raised, but got {e!r}')
            else:
                self.fail(f'{expectedException} exception should be raised')
        else:
            res = await method(*methodargs, **methodkwargs)
            self.assertEqual(res, expectedRes)
        if expectedDbApiCalled:
            dbMockedMethod.assert_called_with(*methodargs, **methodkwargs)

    def testSignatureClaimBuildRequests(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.claimBuildRequests,  # fake
            self.rtype.claimBuildRequests,
        )  # real
        def claimBuildRequests(self, brids, claimed_at=None):
            pass

    async def testFakeDataClaimBuildRequests(self):
        self.master.db.insert_test_data([
            fakedb.BuildRequest(id=44, buildsetid=8822),
            fakedb.BuildRequest(id=55, buildsetid=8822),
        ])
        res = await self.master.data.updates.claimBuildRequests(
            [44, 55], claimed_at=self.CLAIMED_AT
        )
        self.assertTrue(res)

    async def testFakeDataClaimBuildRequestsNoneArgs(self):
        res = await self.master.data.updates.claimBuildRequests([])
        self.assertTrue(res)

    async def testClaimBuildRequests(self):
        self.master.db.insert_test_data([
            fakedb.Builder(id=123),
            fakedb.BuildRequest(id=44, buildsetid=8822, builderid=123),
            fakedb.BuildRequest(id=55, buildsetid=8822, builderid=123),
        ])
        claimBuildRequestsMock = mock.Mock(return_value=defer.succeed(None))
        await self.doTestCallthrough(
            'claimBuildRequests',
            claimBuildRequestsMock,
            self.rtype.claimBuildRequests,
            methodargs=[[44]],
            methodkwargs={"claimed_at": self.CLAIMED_AT},
            expectedRes=True,
            expectedException=None,
        )
        msg = {
            'buildrequestid': 44,
            'complete_at': None,
            'complete': False,
            'builderid': 123,
            'waited_for': False,
            'claimed_at': None,
            'results': -1,
            'priority': 0,
            'submitted_at': datetime.datetime(1970, 5, 23, 21, 21, 18, tzinfo=UTC),
            'claimed': False,
            'claimed_by_masterid': None,
            'buildsetid': 8822,
            'properties': None,
        }
        self.assertEqual(
            sorted(self.master.mq.productions),
            sorted([
                (('buildrequests', '44', 'claimed'), msg),
                (('builders', '123', 'buildrequests', '44', 'claimed'), msg),
                (('buildsets', '8822', 'builders', '123', 'buildrequests', '44', 'claimed'), msg),
            ]),
        )

    async def testClaimBuildRequestsNoBrids(self):
        claimBuildRequestsMock = mock.Mock(return_value=defer.succeed(None))
        await self.doTestCallthrough(
            'claimBuildRequests',
            claimBuildRequestsMock,
            self.rtype.claimBuildRequests,
            methodargs=[[]],
            methodkwargs={},
            expectedRes=True,
            expectedException=None,
            expectedDbApiCalled=False,
        )
        self.assertEqual(self.master.mq.productions, [])

    async def testClaimBuildRequestsAlreadyClaimed(self):
        claimBuildRequestsMock = mock.Mock(
            side_effect=buildrequests.AlreadyClaimedError('oups ! buildrequest already claimed')
        )
        await self.doTestCallthrough(
            'claimBuildRequests',
            claimBuildRequestsMock,
            self.rtype.claimBuildRequests,
            methodargs=[[44]],
            methodkwargs={"claimed_at": self.CLAIMED_AT},
            expectedRes=False,
            expectedException=None,
        )
        self.assertEqual(self.master.mq.productions, [])

    async def testClaimBuildRequestsUnknownException(self):
        claimBuildRequestsMock = mock.Mock(
            side_effect=self.dBLayerException('oups ! unknown error')
        )
        await self.doTestCallthrough(
            'claimBuildRequests',
            claimBuildRequestsMock,
            self.rtype.claimBuildRequests,
            methodargs=[[44]],
            methodkwargs={"claimed_at": self.CLAIMED_AT},
            expectedRes=None,
            expectedException=self.dBLayerException,
        )
        self.assertEqual(self.master.mq.productions, [])

    def testSignatureUnclaimBuildRequests(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.unclaimBuildRequests,  # fake
            self.rtype.unclaimBuildRequests,
        )  # real
        def unclaimBuildRequests(self, brids):
            pass

    async def testFakeDataUnclaimBuildRequests(self):
        res = await self.master.data.updates.unclaimBuildRequests([44, 55])
        self.assertEqual(res, None)

    async def testFakeDataUnclaimBuildRequestsNoneArgs(self):
        res = await self.master.data.updates.unclaimBuildRequests([])
        self.assertEqual(res, None)

    async def testUnclaimBuildRequests(self):
        self.master.db.insert_test_data([
            fakedb.Builder(id=123),
            fakedb.BuildRequest(id=44, buildsetid=8822, builderid=123),
        ])
        unclaimBuildRequestsMock = mock.Mock(return_value=defer.succeed(None))
        await self.doTestCallthrough(
            'unclaimBuildRequests',
            unclaimBuildRequestsMock,
            self.rtype.unclaimBuildRequests,
            methodargs=[[44]],
            methodkwargs={},
            expectedRes=None,
            expectedException=None,
        )
        msg = {
            'buildrequestid': 44,
            'complete_at': None,
            'complete': False,
            'builderid': 123,
            'waited_for': False,
            'claimed_at': None,
            'results': -1,
            'priority': 0,
            'submitted_at': datetime.datetime(1970, 5, 23, 21, 21, 18, tzinfo=UTC),
            'claimed': False,
            'claimed_by_masterid': None,
            'buildsetid': 8822,
            'properties': None,
        }
        self.assertEqual(
            sorted(self.master.mq.productions),
            sorted([
                (('buildrequests', '44', 'unclaimed'), msg),
                (('builders', '123', 'buildrequests', '44', 'unclaimed'), msg),
                (('buildsets', '8822', 'builders', '123', 'buildrequests', '44', 'unclaimed'), msg),
            ]),
        )

    async def testUnclaimBuildRequestsNoBrids(self):
        unclaimBuildRequestsMock = mock.Mock(return_value=defer.succeed(None))
        await self.doTestCallthrough(
            'unclaimBuildRequests',
            unclaimBuildRequestsMock,
            self.rtype.unclaimBuildRequests,
            methodargs=[[]],
            methodkwargs={},
            expectedRes=None,
            expectedException=None,
            expectedDbApiCalled=False,
        )

    def testSignatureCompleteBuildRequests(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.completeBuildRequests,  # fake
            self.rtype.completeBuildRequests,
        )  # real
        def completeBuildRequests(self, brids, results, complete_at=None):
            pass

    async def testFakeDataCompleteBuildRequests(self):
        res = await self.master.data.updates.completeBuildRequests(
            [44, 55], 12, complete_at=self.COMPLETE_AT
        )
        self.assertTrue(res)

    async def testFakeDataCompleteBuildRequestsNoneArgs(self):
        res = await self.master.data.updates.completeBuildRequests([], 0)
        self.assertTrue(res)

    async def testCompleteBuildRequests(self):
        completeBuildRequestsMock = mock.Mock(return_value=defer.succeed(None))
        await self.doTestCallthrough(
            'completeBuildRequests',
            completeBuildRequestsMock,
            self.rtype.completeBuildRequests,
            methodargs=[[46], 12],
            methodkwargs={"complete_at": self.COMPLETE_AT},
            expectedRes=True,
            expectedException=None,
        )

    async def testCompleteBuildRequestsNoBrids(self):
        completeBuildRequestsMock = mock.Mock(return_value=defer.succeed(None))
        await self.doTestCallthrough(
            'completeBuildRequests',
            completeBuildRequestsMock,
            self.rtype.completeBuildRequests,
            methodargs=[[], 0],
            methodkwargs={},
            expectedRes=True,
            expectedException=None,
            expectedDbApiCalled=False,
        )

    async def testCompleteBuildRequestsNotClaimed(self):
        completeBuildRequestsMock = mock.Mock(
            side_effect=buildrequests.NotClaimedError('oups ! buildrequest not claimed')
        )
        await self.doTestCallthrough(
            'completeBuildRequests',
            completeBuildRequestsMock,
            self.rtype.completeBuildRequests,
            methodargs=[[46], 12],
            methodkwargs={"complete_at": self.COMPLETE_AT},
            expectedRes=False,
            expectedException=None,
        )

    async def testCompleteBuildRequestsUnknownException(self):
        completeBuildRequestsMock = mock.Mock(
            side_effect=self.dBLayerException('oups ! unknown error')
        )
        await self.doTestCallthrough(
            'completeBuildRequests',
            completeBuildRequestsMock,
            self.rtype.completeBuildRequests,
            methodargs=[[46], 12],
            methodkwargs={"complete_at": self.COMPLETE_AT},
            expectedRes=None,
            expectedException=self.dBLayerException,
        )

    async def testRebuildBuildrequest(self):
        self.master.db.insert_test_data([
            fakedb.Builder(id=77, name='builder'),
            fakedb.Master(id=88),
            fakedb.Worker(id=13, name='wrk'),
            fakedb.Buildset(id=8822),
            fakedb.SourceStamp(id=234),
            fakedb.BuildsetSourceStamp(buildsetid=8822, sourcestampid=234),
            fakedb.BuildRequest(id=82, buildsetid=8822, builderid=77),
            fakedb.BuildsetProperty(
                buildsetid=8822, property_name='prop1', property_value='["one", "fake1"]'
            ),
            fakedb.BuildsetProperty(
                buildsetid=8822, property_name='prop2', property_value='["two", "fake2"]'
            ),
        ])
        buildrequest = await self.master.data.get(('buildrequests', 82))
        new_bsid, brid_dict = await self.rtype.rebuildBuildrequest(buildrequest)

        self.assertEqual(list(brid_dict.keys()), [77])
        buildrequest = await self.master.data.get(('buildrequests', brid_dict[77]))
        # submitted_at is the time of the test, so better not depend on it
        self.assertEqual(
            buildrequest,
            {
                'buildrequestid': 1001,
                'complete': False,
                'waited_for': False,
                'claimed_at': None,
                'results': -1,
                'claimed': False,
                'buildsetid': 200,
                'complete_at': None,
                'submitted_at': epoch2datetime(0),
                'builderid': 77,
                'claimed_by_masterid': None,
                'priority': 0,
                'properties': None,
            },
        )
        buildset = await self.master.data.get(('buildsets', new_bsid))
        oldbuildset = await self.master.data.get(('buildsets', 8822))

        # assert same sourcestamp
        self.assertEqual(buildset['sourcestamps'], oldbuildset['sourcestamps'])
        buildset['sourcestamps'] = None
        self.assertEqual(
            buildset,
            {
                'bsid': 200,
                'complete_at': None,
                'submitted_at': 0,
                'sourcestamps': None,
                'parent_buildid': None,
                'results': -1,
                'parent_relationship': None,
                'reason': 'rebuild',
                'rebuilt_buildid': None,
                'external_idstring': 'extid',
                'complete': False,
            },
        )

        properties = await self.master.data.get(('buildsets', new_bsid, 'properties'))
        self.assertEqual(properties, {'prop1': ('one', 'fake1'), 'prop2': ('two', 'fake2')})

    async def test_rebuild_buildrequest_rebuilt_build(self):
        self.master.db.insert_test_data([
            fakedb.Builder(id=77, name="builder"),
            fakedb.Master(id=88),
            fakedb.Worker(id=13, name="wrk"),
            fakedb.Buildset(id=8822),
            fakedb.SourceStamp(id=234),
            fakedb.BuildsetSourceStamp(buildsetid=8822, sourcestampid=234),
            fakedb.BuildRequest(id=82, buildsetid=8822, builderid=77),
            fakedb.Build(id=123, buildrequestid=82),
        ])
        buildrequest = await self.master.data.get(("buildrequests", 82))
        new_bsid, brid_dict = await self.rtype.rebuildBuildrequest(buildrequest)

        self.assertEqual(list(brid_dict.keys()), [77])
        buildrequest = await self.master.data.get(("buildrequests", brid_dict[77]))
        # submitted_at is the time of the test, so better not depend on it
        self.assertEqual(
            buildrequest,
            {
                "buildrequestid": 1001,
                "complete": False,
                "waited_for": False,
                "claimed_at": None,
                "results": -1,
                "claimed": False,
                "buildsetid": 200,
                "complete_at": None,
                "submitted_at": epoch2datetime(0),
                "builderid": 77,
                "claimed_by_masterid": None,
                "priority": 0,
                "properties": None,
            },
        )
        buildset = await self.master.data.get(("buildsets", new_bsid))
        oldbuildset = await self.master.data.get(("buildsets", 8822))

        # assert same sourcestamp
        self.assertEqual(buildset["sourcestamps"], oldbuildset["sourcestamps"])
        buildset["sourcestamps"] = None
        self.assertEqual(
            buildset,
            {
                "bsid": 200,
                "complete_at": None,
                "submitted_at": 0,
                "sourcestamps": None,
                "parent_buildid": None,
                "results": -1,
                "parent_relationship": None,
                "reason": "rebuild",
                "rebuilt_buildid": 123,
                "external_idstring": "extid",
                "complete": False,
            },
        )

    async def test_rebuild_buildrequest_repeated_rebuilt_build(self):
        self.master.db.insert_test_data([
            fakedb.Builder(id=77, name="builder"),
            fakedb.Master(id=88),
            fakedb.Worker(id=13, name="wrk"),
            fakedb.Buildset(id=8821),
            # build already has been rebuilt from build_id = 122
            fakedb.Buildset(id=8822, rebuilt_buildid=122),
            fakedb.SourceStamp(id=234),
            fakedb.BuildsetSourceStamp(buildsetid=8822, sourcestampid=234),
            fakedb.BuildRequest(id=81, buildsetid=8821, builderid=77),
            fakedb.BuildRequest(id=82, buildsetid=8822, builderid=77),
            fakedb.Build(id=122, buildrequestid=81),
            fakedb.Build(id=123, buildrequestid=82),
        ])
        buildrequest = await self.master.data.get(("buildrequests", 82))
        new_bsid, brid_dict = await self.rtype.rebuildBuildrequest(buildrequest)

        self.assertEqual(list(brid_dict.keys()), [77])
        buildrequest = await self.master.data.get(("buildrequests", brid_dict[77]))
        # submitted_at is the time of the test, so better not depend on it
        self.assertEqual(
            buildrequest,
            {
                "buildrequestid": 1001,
                "complete": False,
                "waited_for": False,
                "claimed_at": None,
                "results": -1,
                "claimed": False,
                "buildsetid": 200,
                "complete_at": None,
                "submitted_at": epoch2datetime(0),
                "builderid": 77,
                "claimed_by_masterid": None,
                "priority": 0,
                "properties": None,
            },
        )
        buildset = await self.master.data.get(("buildsets", new_bsid))
        oldbuildset = await self.master.data.get(("buildsets", 8822))

        # assert same sourcestamp
        self.assertEqual(buildset["sourcestamps"], oldbuildset["sourcestamps"])
        buildset["sourcestamps"] = None
        self.assertEqual(
            buildset,
            {
                "bsid": 200,
                "complete_at": None,
                "submitted_at": 0,
                "sourcestamps": None,
                "parent_buildid": None,
                "results": -1,
                "parent_relationship": None,
                "reason": "rebuild",
                "rebuilt_buildid": 122,
                "external_idstring": "extid",
                "complete": False,
            },
        )
