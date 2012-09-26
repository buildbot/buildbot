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

from zope.interface import implements
from twisted.trial import unittest
from twisted.internet import task, defer
from buildbot import interfaces
from buildbot.data import buildsets
from buildbot.test.util import types, endpoint
from buildbot.test.fake import fakedb, fakemaster
from buildbot.status.results import SUCCESS, FAILURE

A_TIMESTAMP = 1341700729
EARLIER = 1248529376

class Buildset(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = buildsets.BuildsetEndpoint

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.SourceStampSet(id=92),
            fakedb.Buildset(id=13, sourcestampsetid=92,
                reason='because I said so'),
        ])


    def tearDown(self):
        self.tearDownEndpoint()


    def test_get_existing(self):
        d = self.callGet(dict(), dict(bsid=13))
        @d.addCallback
        def check(buildset):
            types.verifyData(self, 'buildset', {}, buildset)
            self.assertEqual(buildset['reason'], 'because I said so')
        return d


    def test_get_missing(self):
        d = self.callGet(dict(), dict(bsid=99))
        @d.addCallback
        def check(buildset):
            self.assertEqual(buildset, None)
        return d

    def test_startConsuming(self):
        self.callStartConsuming({}, {'bsid' : 13},
                expected_filter=('buildset', '13', 'complete'))


class Buildsets(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = buildsets.BuildsetsEndpoint

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.SourceStampSet(id=92),
            fakedb.Buildset(id=13, complete=True, sourcestampsetid=92),
            fakedb.Buildset(id=14, complete=False, sourcestampsetid=92),
        ])


    def tearDown(self):
        self.tearDownEndpoint()

    def test_get(self):
        d = self.callGet(dict(), dict())
        @d.addCallback
        def check(buildsets):
            types.verifyData(self, 'buildset', {}, buildsets[0])
            self.assertEqual(buildsets[0]['bsid'], 13)
            types.verifyData(self, 'buildset', {}, buildsets[1])
            self.assertEqual(buildsets[1]['bsid'], 14)
        return d

    def test_get_complete(self):
        d = self.callGet(dict(complete=True), dict())
        @d.addCallback
        def check(buildsets):
            self.assertEqual(len(buildsets), 1)
            types.verifyData(self, 'buildset', {}, buildsets[0])
            self.assertEqual(buildsets[0]['bsid'], 13)
        return d

    def test_get_incomplete(self):
        d = self.callGet(dict(complete=False), dict())
        @d.addCallback
        def check(buildsets):
            self.assertEqual(len(buildsets), 1)
            types.verifyData(self, 'buildset', {}, buildsets[0])
            self.assertEqual(buildsets[0]['bsid'], 14)
        return d

    def test_startConsuming(self):
        self.callStartConsuming({}, {},
                expected_filter=('buildset', None, 'new'))



class BuildsetResourceType(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(wantMq=True, wantDb=True,
                                                testcase=self)
        self.rtype = buildsets.BuildsetResourceType(self.master)
        return self.master.db.insertTestData([
            fakedb.SourceStampSet(id=234),
        ])

    def do_test_addBuildset(self, kwargs, expectedReturn,
            expectedMessages, expectedBuildset):
        """Run a test of addBuildset.

        @param kwargs: kwargs to addBuildset
        @param expectedReturn: expected return value - tuple of (bsid, brids)
        @param expectedMessages: expected mq messages transmitted
        @param expectedBuildset: expected buildset inserted into the db

        The buildset is added at time A_TIMESTAMP.
        Note that addBuildset does not add sourcestamps, so this method assumes
        there are none in the db.
        """
        clock = task.Clock()
        clock.advance(A_TIMESTAMP)
        d = self.rtype.addBuildset(_reactor=clock, **kwargs)
        def check((bsid, brids)):
            self.assertEqual((bsid, brids), expectedReturn)
            # check the correct message was received
            self.assertEqual(
                sorted(self.master.mq.productions),
                sorted(expectedMessages))
            # and that the correct data was inserted into the db
            self.master.db.buildsets.assertBuildset(bsid, expectedBuildset, {})
        d.addCallback(check)
        return d

    def _buildRequestMessage(self, brid, bsid, builderid, buildername):
        return (
            ('buildrequest', str(bsid), str(builderid), str(brid), 'new'),
            dict(brid=brid, bsid=bsid, builderid=builderid,
                 buildername=buildername))

    def _buildsetMessage(self, bsid, external_idstring=u'extid',
            reason=u'because', scheduler=u'fakesched', sourcestampsetid=234,
            submitted_at=A_TIMESTAMP):
        return (
            ('buildset', str(bsid), 'new'),
            dict(bsid=bsid, complete=False, complete_at=None,
                 external_idstring=external_idstring, reason=reason,
                 results=None, scheduler=scheduler,
                 sourcestampsetid=sourcestampsetid,
                 submitted_at=submitted_at))

    def _buildsetCompleteMessage(self, bsid, complete_at=A_TIMESTAMP,
            submitted_at=A_TIMESTAMP, external_idstring=u'extid',
            reason=u'because', results=0, sourcestampsetid=234):
        return (
            ('buildset', str(bsid), 'complete'),
            dict(bsid=bsid, complete=True, complete_at=complete_at,
                 external_idstring=external_idstring, reason=reason,
                 results=results, sourcestampsetid=sourcestampsetid,
                 submitted_at=submitted_at))


    def test_addBuildset_two_builderNames(self):
        class FakeSched(object):
            implements(interfaces.IScheduler)
            name = 'fakesched'

        kwargs = dict(scheduler=FakeSched(), reason=u'because',
                    sourcestampsetid=234, external_idstring=u'extid',
                    builderNames=['a', 'b'])
        expectedReturn = (200, dict(a=1000, b=1001))
        expectedMessages = [
            self._buildRequestMessage(1000, 200, -1, u'a'),
            self._buildRequestMessage(1001, 200, -1, u'b'),
            self._buildsetMessage(200),
        ]
        expectedBuildset = dict(reason=u'because',
                properties={},
                external_idstring=u'extid',
                sourcestampsetid=234)
        return self.do_test_addBuildset(kwargs,
                expectedReturn, expectedMessages, expectedBuildset)

    def test_addBuildset_no_builderNames(self):
        class FakeSched(object):
            implements(interfaces.IScheduler)
            name = 'fakesched'

        kwargs = dict(scheduler=FakeSched(), reason=u'because',
                            sourcestampsetid=234, external_idstring=u'extid')
        expectedReturn = (200, {})
        expectedMessages = [
            self._buildsetMessage(200),
            # with no builderNames, this is done already
            self._buildsetCompleteMessage(200),
        ]
        expectedBuildset = dict(reason=u'because',
                properties={},
                external_idstring=u'extid',
                sourcestampsetid=234)
        return self.do_test_addBuildset(kwargs,
                expectedReturn, expectedMessages, expectedBuildset)

    @defer.inlineCallbacks
    def do_test_maybeBuildsetComplete(self,
            buildRequestCompletions={},
            buildRequestResults={},
            buildsetComplete=False,
            expectComplete=False,
            expectMessage=False,
            expectSuccess=True):
        """Test maybeBuildsetComplete.

        @param buildRequestCompletions: dict mapping brid to True if complete,
            else False (and defaulting to False)
        @param buildRequestResults: dict mapping brid to result (defaulting
            to SUCCESS)
        @param buildsetComplete: true if the buildset is already complete
        @param expectComplete: true if the buildset should be complete at exit
        @param expectMessage: true if a buildset completion message is expected
        @param expectSuccess: if expectComplete, whether to expect the buildset
            to be complete

        This first adds two buildsets to the database - 72 and 73.  Buildset 72
        is already complete if buildsetComplete is true; 73 is not complete.
        It adds four buildrequests - 42, 43, and 44 for buildset 72, and 45 for
        buildset 73.  The completion and results are based on
        buidlRequestCompletions and buildRequestResults.

        Then, maybeBuildsetComplete is called for buildset 72, and the
        expectations are checked.
        """

        clock = task.Clock()
        clock.advance(A_TIMESTAMP)
        def mkbr(brid, bsid=72):
            return fakedb.BuildRequest(id=brid, buildsetid=bsid,
                complete=buildRequestCompletions.get(brid),
                results=buildRequestResults.get(brid, SUCCESS))
        yield self.master.db.insertTestData([
            fakedb.Buildset(id=72, sourcestampsetid=234,
                submitted_at=EARLIER,
                complete=buildsetComplete,
                complete_at=A_TIMESTAMP if buildsetComplete else None),
            mkbr(42), mkbr(43), mkbr(44),
            fakedb.Buildset(id=73, sourcestampsetid=234,
                complete=False),
            mkbr(45, bsid=73),
        ])

        yield self.rtype.maybeBuildsetComplete(72, _reactor=clock)

        self.master.db.buildsets.assertBuildsetCompletion(72, expectComplete)
        if expectMessage:
            self.assertEqual(self.master.mq.productions, [
                self._buildsetCompleteMessage(72,
                    results=SUCCESS if expectSuccess else FAILURE,
                    submitted_at=EARLIER),
            ])
        else:
            self.assertEqual(self.master.mq.productions, [])

    def test_maybeBuildsetComplete_not_yet(self):
        # only brid 42 is complete, so the buildset is not complete
        return self.do_test_maybeBuildsetComplete(
                buildRequestCompletions={42:True})

    def test_maybeBuildsetComplete_complete(self):
        return self.do_test_maybeBuildsetComplete(
                buildRequestCompletions={42:True, 43:True, 44:True},
                expectComplete=True,
                expectMessage=True)

    def test_maybeBuildsetComplete_complete_failure(self):
        return self.do_test_maybeBuildsetComplete(
                buildRequestCompletions={42:True, 43:True, 44:True},
                buildRequestResults={43:FAILURE},
                expectComplete=True,
                expectMessage=True,
                expectSuccess=False)

    def test_maybeBuildsetComplete_already_complete(self):
        return self.do_test_maybeBuildsetComplete(
                buildRequestCompletions={42:True, 43:True, 44:True},
                buildsetComplete=True,
                expectComplete=True,
                expectMessage=False)
