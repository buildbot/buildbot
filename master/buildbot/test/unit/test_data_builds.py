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

import mock

from twisted.internet import defer
from twisted.internet import reactor
from twisted.trial import unittest

from buildbot.data import builds
from buildbot.data import resultspec
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import endpoint
from buildbot.test.util import interfaces
from buildbot.util import epoch2datetime


# override resultSpec implementation to be noop
class MockedResultSpec(resultspec.ResultSpec):

    def apply(self, data):
        return data


class BuildEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = builds.BuildEndpoint
    resourceTypeClass = builds.Build

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.Builder(id=77),
            fakedb.Master(id=88),
            fakedb.Worker(id=13, name='wrk'),
            fakedb.Buildset(id=8822),
            fakedb.BuildRequest(id=82, buildsetid=8822, builderid=77),
            fakedb.Build(id=13, builderid=77, masterid=88, workerid=13,
                         buildrequestid=82, number=3),
            fakedb.Build(id=14, builderid=77, masterid=88, workerid=13,
                         buildrequestid=82, number=4),
            fakedb.Build(id=15, builderid=77, masterid=88, workerid=13,
                         buildrequestid=82, number=5),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    @defer.inlineCallbacks
    def test_get_existing(self):
        build = yield self.callGet(('builds', 14))
        self.validateData(build)
        self.assertEqual(build['number'], 4)

    @defer.inlineCallbacks
    def test_get_missing(self):
        build = yield self.callGet(('builds', 9999))
        self.assertEqual(build, None)

    @defer.inlineCallbacks
    def test_get_missing_builder_number(self):
        build = yield self.callGet(('builders', 999, 'builds', 4))
        self.assertEqual(build, None)

    @defer.inlineCallbacks
    def test_get_builder_missing_number(self):
        build = yield self.callGet(('builders', 77, 'builds', 44))
        self.assertEqual(build, None)

    @defer.inlineCallbacks
    def test_get_builder_number(self):
        build = yield self.callGet(('builders', 77, 'builds', 5))
        self.validateData(build)
        self.assertEqual(build['buildid'], 15)

    @defer.inlineCallbacks
    def test_properties_injection(self):
        resultSpec = MockedResultSpec(
            filters=[resultspec.Filter('property', 'eq', [False])])
        build = yield self.callGet(('builders', 77, 'builds', 5), resultSpec=resultSpec)
        self.validateData(build)
        self.assertIn('properties', build)

    @defer.inlineCallbacks
    def test_action_stop(self):
        yield self.callControl("stop", {}, ('builders', 77, 'builds', 5))
        self.master.mq.assertProductions(
            [(('control', 'builds', '15', 'stop'), {'reason': 'no reason'})])

    @defer.inlineCallbacks
    def test_action_stop_reason(self):
        yield self.callControl("stop", {'reason': 'because'}, ('builders', 77, 'builds', 5))
        self.master.mq.assertProductions(
            [(('control', 'builds', '15', 'stop'), {'reason': 'because'})])

    @defer.inlineCallbacks
    def test_action_rebuild(self):
        self.patch(self.master.data.updates, "rebuildBuildrequest",
                   mock.Mock(spec=self.master.data.updates.rebuildBuildrequest, return_value=(1, [2])))
        r = yield self.callControl("rebuild", {}, ('builders', 77, 'builds', 5))
        self.assertEqual(r, (1, [2]))

        buildrequest = yield self.master.data.get(('buildrequests', 82))
        self.master.data.updates.rebuildBuildrequest.assert_called_with(
            buildrequest)


class BuildsEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = builds.BuildsEndpoint
    resourceTypeClass = builds.Build

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.Builder(id=77),
            fakedb.Master(id=88),
            fakedb.Worker(id=13, name='wrk'),
            fakedb.Buildset(id=8822),
            fakedb.BuildRequest(id=82, buildsetid=8822),
            fakedb.Build(id=13, builderid=77, masterid=88, workerid=13,
                         buildrequestid=82, number=3),
            fakedb.Build(id=14, builderid=77, masterid=88, workerid=13,
                         buildrequestid=82, number=4),
            fakedb.Build(id=15, builderid=78, masterid=88, workerid=12,
                         buildrequestid=83, number=5, complete_at=1),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    @defer.inlineCallbacks
    def test_get_all(self):
        builds = yield self.callGet(('builds',))
        [self.validateData(build) for build in builds]
        self.assertEqual(sorted([b['number'] for b in builds]),
                         [3, 4, 5])

    @defer.inlineCallbacks
    def test_get_builder(self):
        builds = yield self.callGet(('builders', 78, 'builds'))
        [self.validateData(build) for build in builds]
        self.assertEqual(sorted([b['number'] for b in builds]), [5])

    @defer.inlineCallbacks
    def test_get_buildrequest(self):
        builds = yield self.callGet(('buildrequests', 82, 'builds'))
        [self.validateData(build) for build in builds]
        self.assertEqual(sorted([b['number'] for b in builds]), [3, 4])

    @defer.inlineCallbacks
    def test_get_buildrequest_via_filter(self):
        resultSpec = MockedResultSpec(
            filters=[resultspec.Filter('buildrequestid', 'eq', [82])])
        builds = yield self.callGet(('builds',), resultSpec=resultSpec)
        [self.validateData(build) for build in builds]
        self.assertEqual(sorted([b['number'] for b in builds]), [3, 4])

    @defer.inlineCallbacks
    def test_get_buildrequest_via_filter_with_string(self):
        resultSpec = MockedResultSpec(
            filters=[resultspec.Filter('buildrequestid', 'eq', ['82'])])
        builds = yield self.callGet(('builds',), resultSpec=resultSpec)
        [self.validateData(build) for build in builds]
        self.assertEqual(sorted([b['number'] for b in builds]), [3, 4])

    @defer.inlineCallbacks
    def test_get_worker(self):
        builds = yield self.callGet(('workers', 13, 'builds'))
        [self.validateData(build) for build in builds]
        self.assertEqual(sorted([b['number'] for b in builds]), [3, 4])

    @defer.inlineCallbacks
    def test_get_complete(self):
        resultSpec = MockedResultSpec(
            filters=[resultspec.Filter('complete', 'eq', [False])])
        builds = yield self.callGet(('builds',), resultSpec=resultSpec)
        [self.validateData(build) for build in builds]
        self.assertEqual(sorted([b['number'] for b in builds]), [3, 4])

    @defer.inlineCallbacks
    def test_get_complete_at(self):
        resultSpec = MockedResultSpec(
            filters=[resultspec.Filter('complete_at', 'eq', [None])])
        builds = yield self.callGet(('builds',), resultSpec=resultSpec)
        [self.validateData(build) for build in builds]
        self.assertEqual(sorted([b['number'] for b in builds]), [3, 4])

    @defer.inlineCallbacks
    def test_properties_injection(self):
        resultSpec = MockedResultSpec(
            filters=[resultspec.Filter('property', 'eq', [False])])
        builds = yield self.callGet(('builds',), resultSpec=resultSpec)
        for b in builds:
            self.validateData(b)
            self.assertIn('properties', b)


class Build(interfaces.InterfaceTests, unittest.TestCase):
    new_build_event = {'builderid': 10,
                       'buildid': 100,
                       'buildrequestid': 13,
                       'workerid': 20,
                       'complete': False,
                       'complete_at': None,
                       'masterid': 824,
                       'number': 1,
                       'results': None,
                       'started_at': epoch2datetime(1),
                       'state_string': u'created',
                       'properties': {}}

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self,
                                             wantMq=True, wantDb=True, wantData=True)
        self.rtype = builds.Build(self.master)

    @defer.inlineCallbacks
    def do_test_callthrough(self, dbMethodName, method, exp_args=None,
                            exp_kwargs=None, *args, **kwargs):
        rv = (1, 2)
        m = mock.Mock(return_value=defer.succeed(rv))
        setattr(self.master.db.builds, dbMethodName, m)
        res = yield method(*args, **kwargs)
        self.assertIdentical(res, rv)
        m.assert_called_with(*(exp_args or args), **(exp_kwargs or kwargs))

    @defer.inlineCallbacks
    def do_test_event(self, method, exp_events=[],
                      *args, **kwargs):
        self.patch(reactor, "seconds", lambda: 1)
        yield method(*args, **kwargs)
        self.master.mq.assertProductions(exp_events)

    def test_signature_newBuild(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.addBuild,  # fake
            self.rtype.addBuild)  # real
        def newBuild(self, builderid, buildrequestid, workerid):
            pass

    def test_newBuild(self):
        return self.do_test_callthrough('addBuild', self.rtype.addBuild,
                                        builderid=10, buildrequestid=13, workerid=20,
                                        exp_kwargs=dict(builderid=10, buildrequestid=13,
                                                        workerid=20, masterid=self.master.masterid,
                                                        state_string=u'created'))

    def test_newBuildEvent(self):

        @defer.inlineCallbacks
        def addBuild(*args, **kwargs):
            buildid, _ = yield self.rtype.addBuild(*args, **kwargs)
            yield self.rtype.generateNewBuildEvent(buildid)
            defer.returnValue(None)

        return self.do_test_event(addBuild,
                                  builderid=10, buildrequestid=13, workerid=20,
                                  exp_events=[(('builders', '10', 'builds', '1', 'new'), self.new_build_event),
                                              (('builds', '100', 'new'),
                                               self.new_build_event),
                                              (('workers', '20', 'builds', '100', 'new'), self.new_build_event)])

    def test_signature_setBuildStateString(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.setBuildStateString,  # fake
            self.rtype.setBuildStateString)  # real
        def setBuildStateString(self, buildid, state_string):
            pass

    def test_setBuildStateString(self):
        return self.do_test_callthrough('setBuildStateString',
                                        self.rtype.setBuildStateString,
                                        buildid=10, state_string=u'a b')

    def test_signature_finishBuild(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.finishBuild,  # fake
            self.rtype.finishBuild)  # real
        def finishBuild(self, buildid, results):
            pass

    def test_finishBuild(self):
        return self.do_test_callthrough('finishBuild', self.rtype.finishBuild,
                                        buildid=15, results=3)
