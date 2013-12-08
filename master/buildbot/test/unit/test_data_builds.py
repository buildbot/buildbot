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

import mock

from buildbot.data import builds
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import endpoint
from buildbot.test.util import interfaces
from twisted.internet import defer
from twisted.internet import reactor
from twisted.trial import unittest


class BuildEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = builds.BuildEndpoint
    resourceTypeClass = builds.Build

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.Builder(id=77),
            fakedb.Master(id=88),
            fakedb.Buildslave(id=13, name='sl'),
            fakedb.Buildset(id=8822),
            fakedb.BuildRequest(id=82, buildsetid=8822),
            fakedb.Build(id=13, builderid=77, masterid=88, buildslaveid=13,
                         buildrequestid=82, number=3),
            fakedb.Build(id=14, builderid=77, masterid=88, buildslaveid=13,
                         buildrequestid=82, number=4),
            fakedb.Build(id=15, builderid=77, masterid=88, buildslaveid=13,
                         buildrequestid=82, number=5),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    @defer.inlineCallbacks
    def test_get_existing(self):
        build = yield self.callGet(('build', 14))
        self.validateData(build)
        self.assertEqual(build['number'], 4)

    @defer.inlineCallbacks
    def test_get_missing(self):
        build = yield self.callGet(('build', 9999))
        self.assertEqual(build, None)

    @defer.inlineCallbacks
    def test_get_missing_builder_number(self):
        build = yield self.callGet(('builder', 999, 'build', 4))
        self.assertEqual(build, None)

    @defer.inlineCallbacks
    def test_get_builder_missing_number(self):
        build = yield self.callGet(('builder', 77, 'build', 44))
        self.assertEqual(build, None)

    @defer.inlineCallbacks
    def test_get_builder_number(self):
        build = yield self.callGet(('builder', 77, 'build', 5))
        self.validateData(build)
        self.assertEqual(build['buildid'], 15)


class BuildsEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = builds.BuildsEndpoint
    resourceTypeClass = builds.Build

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.Builder(id=77),
            fakedb.Master(id=88),
            fakedb.Buildslave(id=13, name='sl'),
            fakedb.Buildset(id=8822),
            fakedb.BuildRequest(id=82, buildsetid=8822),
            fakedb.Build(id=13, builderid=77, masterid=88, buildslaveid=13,
                         buildrequestid=82, number=3),
            fakedb.Build(id=14, builderid=77, masterid=88, buildslaveid=13,
                         buildrequestid=82, number=4),
            fakedb.Build(id=15, builderid=78, masterid=88, buildslaveid=13,
                         buildrequestid=83, number=5),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    @defer.inlineCallbacks
    def test_get_all(self):
        builds = yield self.callGet(('build',))
        [self.validateData(build) for build in builds]
        self.assertEqual(sorted([b['number'] for b in builds]),
                         [3, 4, 5])

    @defer.inlineCallbacks
    def test_get_builder(self):
        builds = yield self.callGet(('builder', 78, 'build'))
        [self.validateData(build) for build in builds]
        self.assertEqual(sorted([b['number'] for b in builds]), [5])

    @defer.inlineCallbacks
    def test_get_buildrequest(self):
        builds = yield self.callGet(('buildrequest', 82, 'build'))
        [self.validateData(build) for build in builds]
        self.assertEqual(sorted([b['number'] for b in builds]), [3, 4])


class Build(interfaces.InterfaceTests, unittest.TestCase):
    new_build_event = {'builderid': 10,
                       'buildid': 100,
                       'buildrequestid': 13,
                       'buildslaveid': 20,
                       'complete': False,
                       'complete_at': None,
                       'masterid': 824,
                       'number': 1,
                       'results': None,
                       'started_at': 1,
                       'state_strings': [u'starting']}

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
            self.master.data.updates.newBuild,  # fake
            self.rtype.newBuild)  # real
        def newBuild(self, builderid, buildrequestid, buildslaveid):
            pass

    def test_newBuild(self):
        return self.do_test_callthrough('addBuild', self.rtype.newBuild,
                                        builderid=10, buildrequestid=13, buildslaveid=20,
                                        exp_kwargs=dict(builderid=10, buildrequestid=13,
                                                        buildslaveid=20, masterid=self.master.masterid,
                                                        state_strings=['starting']))

    def test_newBuildEvent(self):
        return self.do_test_event(self.rtype.newBuild,
                                  builderid=10, buildrequestid=13, buildslaveid=20,
                                  exp_events=[(('builder', '10', 'build', '1', 'new'), self.new_build_event),
                                 (('build', '100', 'new'), self.new_build_event)])

    def test_signature_setBuildStateStrings(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.setBuildStateStrings,  # fake
            self.rtype.setBuildStateStrings)  # real
        def setBuildStateStrings(self, buildid, state_strings):
            pass

    def test_setBuildStateStrings(self):
        return self.do_test_callthrough('setBuildStateStrings',
                                        self.rtype.setBuildStateStrings,
                                        buildid=10, state_strings=['a', 'b'])

    def test_signature_finishBuild(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.finishBuild,  # fake
            self.rtype.finishBuild)  # real
        def finishBuild(self, buildid, results):
            pass

    def test_finishBuild(self):
        return self.do_test_callthrough('finishBuild', self.rtype.finishBuild,
                                        buildid=15, results=3)
