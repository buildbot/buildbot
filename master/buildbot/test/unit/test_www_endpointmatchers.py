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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.schedulers.forcesched import ForceScheduler
from buildbot.test.fake import fakedb
from buildbot.test.util import www
from buildbot.www.authz import endpointmatchers


class EndpointBase(www.WwwTestMixin, unittest.TestCase):

    def setUp(self):
        self.master = self.make_master(url='h:/a/b/')
        self.db = self.master.db
        self.matcher = self.makeMatcher()
        self.matcher.setAuthz(self.master.authz)
        self.insertData()

    def makeMatcher(self):
        raise NotImplementedError()

    def assertMatch(self, match):
        self.assertTrue(match is not None)

    def assertNotMatch(self, match):
        self.assertTrue(match is None)

    def insertData(self):
        self.db.insertTestData([
            fakedb.SourceStamp(id=13, branch=u'secret'),
            fakedb.Build(
                id=15, buildrequestid=16, masterid=1, workerid=2, builderid=21),
            fakedb.BuildRequest(id=16, buildsetid=17),
            fakedb.Buildset(id=17),
            fakedb.BuildsetSourceStamp(id=20, buildsetid=17, sourcestampid=13),
            fakedb.Builder(id=21, name="builder"),
        ])


class ValidEndpointMixin(object):

    @defer.inlineCallbacks
    def test_invalidPath(self):
        ret = yield self.matcher.match(("foo", "bar"))
        self.assertNotMatch(ret)


class AnyEndpointMatcher(EndpointBase):

    def makeMatcher(self):
        return endpointmatchers.AnyEndpointMatcher(role="foo")

    @defer.inlineCallbacks
    def test_nominal(self):
        ret = yield self.matcher.match(("foo", "bar"))
        self.assertMatch(ret)


class AnyControlEndpointMatcher(EndpointBase):

    def makeMatcher(self):
        return endpointmatchers.AnyControlEndpointMatcher(role="foo")

    @defer.inlineCallbacks
    def test_default_action(self):
        ret = yield self.matcher.match(("foo", "bar"))
        self.assertMatch(ret)

    @defer.inlineCallbacks
    def test_get(self):
        ret = yield self.matcher.match(("foo", "bar"), action="GET")
        self.assertNotMatch(ret)

    @defer.inlineCallbacks
    def test_other_action(self):
        ret = yield self.matcher.match(("foo", "bar"), action="foo")
        self.assertMatch(ret)


class ViewBuildsEndpointMatcherBranch(EndpointBase, ValidEndpointMixin):

    def makeMatcher(self):
        return endpointmatchers.ViewBuildsEndpointMatcher(branch="secret", role="agent")

    @defer.inlineCallbacks
    def test_build(self):
        ret = yield self.matcher.match(("builds", "15"))
        self.assertMatch(ret)
    test_build.skip = "ViewBuildsEndpointMatcher is not implemented yet"


class StopBuildEndpointMatcherBranch(EndpointBase, ValidEndpointMixin):

    def makeMatcher(self):
        return endpointmatchers.StopBuildEndpointMatcher(builder="builder", role="owner")

    @defer.inlineCallbacks
    def test_build(self):
        ret = yield self.matcher.match(("builds", "15"), "stop")
        self.assertMatch(ret)

    @defer.inlineCallbacks
    def test_build_no_match(self):
        self.matcher.builder = "foo"
        ret = yield self.matcher.match(("builds", "15"), "stop")
        self.assertNotMatch(ret)

    @defer.inlineCallbacks
    def test_build_no_builder(self):
        self.matcher.builder = None
        ret = yield self.matcher.match(("builds", "15"), "stop")
        self.assertMatch(ret)


class ForceBuildEndpointMatcherBranch(EndpointBase, ValidEndpointMixin):

    def makeMatcher(self):
        return endpointmatchers.ForceBuildEndpointMatcher(builder="builder", role="owner")

    def insertData(self):
        EndpointBase.insertData(self)
        self.master.allSchedulers = lambda: [
            ForceScheduler(name="sched1", builderNames=["builder"])]

    @defer.inlineCallbacks
    def test_build(self):
        ret = yield self.matcher.match(("builds", "15"), "stop")
        self.assertNotMatch(ret)

    @defer.inlineCallbacks
    def test_forcesched(self):
        ret = yield self.matcher.match(("forceschedulers", "sched1"), "force")
        self.assertMatch(ret)

    @defer.inlineCallbacks
    def test_noforcesched(self):
        ret = yield self.matcher.match(("forceschedulers", "sched2"), "force")
        self.assertNotMatch(ret)

    @defer.inlineCallbacks
    def test_forcesched_builder_no_match(self):
        self.matcher.builder = "foo"
        ret = yield self.matcher.match(("forceschedulers", "sched1"), "force")
        self.assertNotMatch(ret)

    @defer.inlineCallbacks
    def test_forcesched_nobuilder(self):
        self.matcher.builder = None
        ret = yield self.matcher.match(("forceschedulers", "sched1"), "force")
        self.assertMatch(ret)


class EnableSchedulerEndpointMatcher(EndpointBase, ValidEndpointMixin):

    def makeMatcher(self):
        return endpointmatchers.EnableSchedulerEndpointMatcher(role="agent")

    @defer.inlineCallbacks
    def test_build(self):
        ret = yield self.matcher.match(("builds", "15"), "stop")
        self.assertNotMatch(ret)

    @defer.inlineCallbacks
    def test_scheduler_enable(self):
        ret = yield self.matcher.match(("schedulers", "15"), "enable")
        self.assertMatch(ret)
