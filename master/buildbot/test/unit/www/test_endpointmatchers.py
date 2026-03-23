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

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.schedulers.forcesched import ForceScheduler
from buildbot.test import fakedb
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import www
from buildbot.www.authz import endpointmatchers


class EndpointBase(TestReactorMixin, www.WwwTestMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = yield self.make_master(url='h:/a/b/')
        self.matcher = self.makeMatcher()
        self.matcher.setAuthz(self.master.authz)
        yield self.insertData()

    def makeMatcher(self) -> endpointmatchers.EndpointMatcherBase:
        raise NotImplementedError()

    def assertMatch(self, match: object) -> None:
        self.assertTrue(match is not None)

    def assertNotMatch(self, match: object) -> None:
        self.assertTrue(match is None)

    @defer.inlineCallbacks
    def insertData(self) -> InlineCallbacksType[None]:
        yield self.master.db.insert_test_data([
            fakedb.Builder(id=21, name="builder"),
            fakedb.SourceStamp(id=13, branch='secret'),
            fakedb.Master(id=1),
            fakedb.Worker(id=2, name='worker'),
            fakedb.Build(id=15, buildrequestid=16, masterid=1, workerid=2, builderid=21),
            fakedb.BuildRequest(id=16, buildsetid=17, builderid=21),
            fakedb.Buildset(id=17),
            fakedb.BuildsetSourceStamp(id=20, buildsetid=17, sourcestampid=13),
        ])


class ValidEndpointMixin:
    @defer.inlineCallbacks
    def test_invalidPath(self) -> InlineCallbacksType[None]:
        ret = yield self.matcher.match(("foo", "bar"))  # type: ignore[attr-defined]
        self.assertNotMatch(ret)  # type: ignore[attr-defined]


class AnyEndpointMatcher(EndpointBase):
    def makeMatcher(self) -> endpointmatchers.EndpointMatcherBase:
        return endpointmatchers.AnyEndpointMatcher(role="foo")

    @defer.inlineCallbacks
    def test_nominal(self) -> InlineCallbacksType[None]:
        ret = yield self.matcher.match(("foo", "bar"))
        self.assertMatch(ret)


class AnyControlEndpointMatcher(EndpointBase):
    def makeMatcher(self) -> endpointmatchers.EndpointMatcherBase:
        return endpointmatchers.AnyControlEndpointMatcher(role="foo")

    @defer.inlineCallbacks
    def test_default_action(self) -> InlineCallbacksType[None]:
        ret = yield self.matcher.match(("foo", "bar"))
        self.assertMatch(ret)

    @defer.inlineCallbacks
    def test_get(self) -> InlineCallbacksType[None]:
        ret = yield self.matcher.match(("foo", "bar"), action="GET")
        self.assertNotMatch(ret)

    @defer.inlineCallbacks
    def test_other_action(self) -> InlineCallbacksType[None]:
        ret = yield self.matcher.match(("foo", "bar"), action="foo")
        self.assertMatch(ret)


class ViewBuildsEndpointMatcherBranch(EndpointBase, ValidEndpointMixin):
    def makeMatcher(self) -> endpointmatchers.EndpointMatcherBase:
        return endpointmatchers.ViewBuildsEndpointMatcher(branch="secret", role="agent")

    @defer.inlineCallbacks
    def test_build(self) -> InlineCallbacksType[None]:
        ret = yield self.matcher.match(("builds", "15"))
        self.assertMatch(ret)

    test_build.skip = "ViewBuildsEndpointMatcher is not implemented yet"  # type: ignore[attr-defined]


class StopBuildEndpointMatcherBranch(EndpointBase, ValidEndpointMixin):
    def makeMatcher(self) -> endpointmatchers.EndpointMatcherBase:
        return endpointmatchers.StopBuildEndpointMatcher(builder="builder", role="owner")

    @defer.inlineCallbacks
    def test_build(self) -> InlineCallbacksType[None]:
        ret = yield self.matcher.match(("builds", "15"), "stop")
        self.assertMatch(ret)

    @defer.inlineCallbacks
    def test_build_no_match(self) -> InlineCallbacksType[None]:
        self.matcher.builder = "foo"  # type: ignore[attr-defined]
        ret = yield self.matcher.match(("builds", "15"), "stop")
        self.assertNotMatch(ret)

    @defer.inlineCallbacks
    def test_build_no_builder(self) -> InlineCallbacksType[None]:
        self.matcher.builder = None  # type: ignore[attr-defined]
        ret = yield self.matcher.match(("builds", "15"), "stop")
        self.assertMatch(ret)


class ForceBuildEndpointMatcherBranch(EndpointBase, ValidEndpointMixin):
    def makeMatcher(self) -> endpointmatchers.EndpointMatcherBase:
        return endpointmatchers.ForceBuildEndpointMatcher(builder="builder", role="owner")

    @defer.inlineCallbacks
    def insertData(self) -> InlineCallbacksType[None]:
        yield super().insertData()
        self.master.allSchedulers = lambda: [
            ForceScheduler(name="sched1", builderNames=["builder"])
        ]

    @defer.inlineCallbacks
    def test_build(self) -> InlineCallbacksType[None]:
        ret = yield self.matcher.match(("builds", "15"), "stop")
        self.assertNotMatch(ret)

    @defer.inlineCallbacks
    def test_forcesched(self) -> InlineCallbacksType[None]:
        ret = yield self.matcher.match(("forceschedulers", "sched1"), "force")
        self.assertMatch(ret)

    @defer.inlineCallbacks
    def test_noforcesched(self) -> InlineCallbacksType[None]:
        ret = yield self.matcher.match(("forceschedulers", "sched2"), "force")
        self.assertNotMatch(ret)

    @defer.inlineCallbacks
    def test_forcesched_builder_no_match(self) -> InlineCallbacksType[None]:
        self.matcher.builder = "foo"  # type: ignore[attr-defined]
        ret = yield self.matcher.match(("forceschedulers", "sched1"), "force")
        self.assertNotMatch(ret)

    @defer.inlineCallbacks
    def test_forcesched_nobuilder(self) -> InlineCallbacksType[None]:
        self.matcher.builder = None  # type: ignore[attr-defined]
        ret = yield self.matcher.match(("forceschedulers", "sched1"), "force")
        self.assertMatch(ret)


class EnableSchedulerEndpointMatcher(EndpointBase, ValidEndpointMixin):
    def makeMatcher(self) -> endpointmatchers.EndpointMatcherBase:
        return endpointmatchers.EnableSchedulerEndpointMatcher(role="agent")

    @defer.inlineCallbacks
    def test_build(self) -> InlineCallbacksType[None]:
        ret = yield self.matcher.match(("builds", "15"), "stop")
        self.assertNotMatch(ret)

    @defer.inlineCallbacks
    def test_scheduler_enable(self) -> InlineCallbacksType[None]:
        ret = yield self.matcher.match(("schedulers", "15"), "enable")
        self.assertMatch(ret)
