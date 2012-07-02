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
        clock = task.Clock()
        clock.advance(1341700729)
        d = self.rtype.addBuildset(_reactor=clock, **kwargs)
        def check((bsid, brids)):
            self.assertEqual((bsid, brids), expectedReturn)
            # check the correct message was received
            self.assertEqual(sorted(self.master.mq.productions),
                    sorted(expectedMessages))
            # and that the correct data was inserted into the db
            self.master.db.buildsets.assertBuildset(200, expectedBuildset, {})
        d.addCallback(check)
        return d

    def test_addBuildset_two_builderNames(self):
        class FakeSched(object):
            implements(interfaces.IScheduler)
            name = 'fakesched'

        kwargs = dict(scheduler=FakeSched(), reason=u'because',
                    sourcestampsetid=234, external_idstring=u'extid',
                    builderNames=['a', 'b'])
        expectedReturn = (200, dict(a=1000, b=1001))
        expectedMessages = [
        (('buildrequest', '200', '-1', '1000', 'new'), {
            'brid': 1000,
            'bsid': 200,
            'builderid': -1,
            'buildername': u'a',
        }),
        (('buildrequest', '200', '-1', '1001', 'new'), {
            'brid': 1001,
            'bsid': 200,
            'builderid': -1,
            'buildername': u'b',
        }),
        (('buildset', '200', 'new'), {
            'bsid': 200,
            'complete': False,
            'complete_at': None,
            'external_idstring': u'extid',
            'reason': u'because',
            'results': None,
            'scheduler': u'fakesched',
            'sourcestampsetid': 234,
            'submitted_at': 1341700729,
        }),
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
        expectedMessages = [(('buildset', '200', 'new'), {
            'bsid': 200,
            'complete': False,
            'complete_at': None,
            'external_idstring': u'extid',
            'reason': u'because',
            'results': None,
            'scheduler': u'fakesched',
            'sourcestampsetid': 234,
            'submitted_at': 1341700729,
        }),
        (('buildset', '200', 'complete'), {
            'bsid': 200,
            'complete': True,
            'complete_at': 1341700729,
            'external_idstring': u'extid',
            'reason': u'because',
            'results': 0,
            # note, no scheduler
            'sourcestampsetid': 234,
            'submitted_at': 1341700729,
        }),
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
        clock = task.Clock()
        clock.advance(9876543)
        def mkbr(brid, bsid=72):
            return fakedb.BuildRequest(id=brid, buildsetid=bsid,
                complete=buildRequestCompletions.get(brid),
                results=buildRequestResults.get(brid, SUCCESS))
        yield self.master.db.insertTestData([
            fakedb.Buildset(id=72, sourcestampsetid=234,
                complete=buildsetComplete),
            mkbr(42), mkbr(43), mkbr(44),
            fakedb.Buildset(id=73, sourcestampsetid=234,
                complete=False),
            mkbr(45, bsid=73),
        ])

        yield self.rtype.maybeBuildsetComplete(72, _reactor=clock)

        self.master.db.buildsets.assertBuildsetCompletion(72, expectComplete)
        if expectMessage:
            self.assertEqual(self.master.mq.productions, [ (
                ('buildset', '72', 'complete'),
                dict(bsid=72,
                    complete=True,
                    complete_at=9876543,
                    external_idstring=u'extid',
                    reason=u'because',
                    results=SUCCESS if expectSuccess else FAILURE,
                    sourcestampsetid=234,
                    submitted_at=12345678))
            ])
        else:
            self.assertEqual(self.master.mq.productions, [])

    def test_maybeBuildsetComplete_not_yet(self):
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
