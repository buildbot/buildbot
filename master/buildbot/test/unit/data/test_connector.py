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
from typing import Any
from unittest import mock

from twisted.internet import defer
from twisted.python import reflect
from twisted.trial import unittest

from buildbot.data import base
from buildbot.data import connector
from buildbot.data import exceptions
from buildbot.data import resultspec
from buildbot.data import types
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import interfaces
from buildbot.test.util.warnings import assertProducesWarnings
from buildbot.warnings import DeprecatedApiWarning

if TYPE_CHECKING:
    from collections.abc import Callable

    from buildbot.util.twisted import InlineCallbacksType


class Tests(interfaces.InterfaceTests):
    data: connector.DataConnector

    def setUp(self) -> None:
        raise NotImplementedError

    def test_signature_get(self) -> None:
        @self.assertArgSpecMatches(self.data.get)
        def get(
            self: object,
            path: tuple[str | int, ...],
            filters: list[resultspec.Filter] | None = None,
            fields: list[str] | None = None,
            order: list[str] | tuple[str, ...] | None = None,
            limit: int | None = None,
            offset: int | None = None,
        ) -> None:
            pass

    def test_signature_getEndpoint(self) -> None:
        @self.assertArgSpecMatches(self.data.getEndpoint)
        def getEndpoint(self: object, path: tuple[str | int, ...]) -> None:
            pass

    def test_signature_control(self) -> None:
        @self.assertArgSpecMatches(self.data.control)
        def control(
            self: object, action: str, args: dict[str, Any], path: tuple[str | int, ...]
        ) -> None:
            pass

    def test_signature_updates_addChange(self) -> None:
        @self.assertArgSpecMatches(self.data.updates.addChange)
        def addChange(
            self: object,
            files: list[str] | None = None,
            comments: str | None = None,
            author: str | None = None,
            committer: str | None = None,
            revision: str | None = None,
            when_timestamp: int | None = None,
            branch: str | None = None,
            category: str | Callable | None = None,
            revlink: str | None = '',
            properties: dict[str, Any] | None = None,
            repository: str = '',
            codebase: str | None = None,
            project: str = '',
            src: str | None = None,
        ) -> None:
            pass

    def test_signature_updates_masterActive(self) -> None:
        @self.assertArgSpecMatches(self.data.updates.masterActive)
        def masterActive(self: object, name: str, masterid: int) -> None:
            pass

    def test_signature_updates_masterStopped(self) -> None:
        @self.assertArgSpecMatches(self.data.updates.masterStopped)
        def masterStopped(self: object, name: str, masterid: int) -> None:
            pass

    def test_signature_updates_addBuildset(self) -> None:
        @self.assertArgSpecMatches(self.data.updates.addBuildset)
        def addBuildset(
            self: object,
            waited_for: bool,
            scheduler: str | None = None,
            sourcestamps: list[dict[str, Any] | str] | None = None,
            reason: str = '',
            properties: dict[str, Any] | None = None,
            builderids: list[int] | None = None,
            external_idstring: str | None = None,
            rebuilt_buildid: int | None = None,
            parent_buildid: int | None = None,
            parent_relationship: str | None = None,
            priority: int = 0,
        ) -> None:
            pass

    def test_signature_updates_maybeBuildsetComplete(self) -> None:
        @self.assertArgSpecMatches(self.data.updates.maybeBuildsetComplete)
        def maybeBuildsetComplete(self: object, bsid: int) -> None:
            pass

    def test_signature_updates_updateBuilderList(self) -> None:
        @self.assertArgSpecMatches(self.data.updates.updateBuilderList)
        def updateBuilderList(self: object, masterid: int, builderNames: list[str]) -> None:
            pass


class TestFakeData(TestReactorMixin, unittest.TestCase, Tests):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantMq=True, wantData=True, wantDb=True)
        self.data = self.master.data


class TestDataConnector(TestReactorMixin, unittest.TestCase, Tests):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantMq=True)
        self.data = connector.DataConnector()
        yield self.data.setServiceParent(self.master)


class DataConnector(TestReactorMixin, unittest.TestCase):
    maxDiff = None

    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self)
        # don't load by default
        self.patch(connector.DataConnector, 'submodules', [])
        self.data = connector.DataConnector()
        yield self.data.setServiceParent(self.master)

    def patchFooPattern(self) -> base.Endpoint:
        cls = type('FooEndpoint', (base.Endpoint,), {})
        ep = cls(None, self.master)
        ep.get = mock.Mock(name='FooEndpoint.get')
        ep.get.return_value = defer.succeed({'val': 9999})
        self.data.matcher[('foo', 'n:fooid', 'bar')] = ep
        return ep

    def patchFooListPattern(self) -> base.Endpoint:
        cls = type('FoosEndpoint', (base.Endpoint,), {})
        ep = cls(None, self.master)
        ep.get = mock.Mock(name='FoosEndpoint.get')
        ep.get.return_value = defer.succeed([{'val': v} for v in range(900, 920)])
        self.data.matcher[('foo',)] = ep
        return ep

    # tests

    def test_sets_master(self) -> None:
        self.assertIdentical(self.master, self.data.master)

    def test_scanModule(self) -> None:
        # use this module as a test
        mod = reflect.namedModule('buildbot.test.unit.data.test_connector')
        self.data._scanModule(mod)

        # check that it discovered MyResourceType and updated endpoints
        match = self.data.matcher[('test', '10')]
        self.assertIsInstance(match[0], TestEndpoint)
        self.assertEqual(match[1], {"testid": 10})
        match = self.data.matcher[('test', '10', 'p1')]
        self.assertIsInstance(match[0], TestEndpoint)
        match = self.data.matcher[('test', '10', 'p2')]
        self.assertIsInstance(match[0], TestEndpoint)
        match = self.data.matcher[('tests',)]
        self.assertIsInstance(match[0], TestsEndpoint)
        self.assertEqual(match[1], {})
        match = self.data.matcher[('test', 'foo')]
        self.assertIsInstance(match[0], TestsEndpointSubclass)
        self.assertEqual(match[1], {})

        # and that it found the update method
        self.assertEqual(self.data.updates.testUpdate(), "testUpdate return")

        # and that it added the single root link
        self.assertEqual(self.data.rootLinks, [{'name': 'tests'}])

        # and that it added an attribute
        self.assertIsInstance(self.data.rtypes.test, TestResourceType)

    def test_scanModule_path_pattern_multiline_string_deprecation(self) -> None:
        mod = reflect.namedModule('buildbot.test.unit.data.test_connector')

        TestEndpoint.pathPatterns = """
            /test/n:testid
            /test/n:testid/p1
            /test/n:testid/p2
        """  # type: ignore[assignment]

        with assertProducesWarnings(
            DeprecatedApiWarning,
            message_pattern='.*Endpoint.pathPatterns as a multiline string is deprecated.*',
        ):
            self.data._scanModule(mod)

    def test_getEndpoint(self) -> None:
        ep = self.patchFooPattern()
        got = self.data.getEndpoint(('foo', '10', 'bar'))
        self.assertEqual(got, (ep, {'fooid': 10}))

    def test_getEndpoint_missing(self) -> None:
        with self.assertRaises(exceptions.InvalidPathError):
            self.data.getEndpoint(('xyz',))

    @defer.inlineCallbacks
    def test_get(self) -> InlineCallbacksType[None]:
        ep = self.patchFooPattern()
        gotten = yield self.data.get(('foo', '10', 'bar'))

        self.assertEqual(gotten, {'val': 9999})
        ep.get.assert_called_once_with(mock.ANY, {'fooid': 10})  # type: ignore[attr-defined]

    @defer.inlineCallbacks
    def test_get_filters(self) -> InlineCallbacksType[None]:
        ep = self.patchFooListPattern()
        gotten = yield self.data.get(('foo',), filters=[resultspec.Filter('val', 'lt', [902])])

        self.assertEqual(gotten, base.ListResult([{'val': 900}, {'val': 901}], total=2))
        ep.get.assert_called_once_with(mock.ANY, {})  # type: ignore[attr-defined]

    @defer.inlineCallbacks
    def test_get_resultSpec_args(self) -> InlineCallbacksType[None]:
        ep = self.patchFooListPattern()
        f = resultspec.Filter('val', 'gt', [909])
        gotten = yield self.data.get(('foo',), filters=[f], fields=['val'], order=['-val'], limit=2)

        self.assertEqual(gotten, base.ListResult([{'val': 919}, {'val': 918}], total=10, limit=2))
        ep.get.assert_called_once_with(mock.ANY, {})  # type: ignore[attr-defined]

    @defer.inlineCallbacks
    def test_control(self) -> InlineCallbacksType[None]:
        ep = self.patchFooPattern()
        ep.control = mock.Mock(name='MyEndpoint.control')  # type: ignore[method-assign]
        ep.control.return_value = defer.succeed('controlled')

        gotten = yield self.data.control('foo!', {'arg': 2}, ('foo', '10', 'bar'))

        self.assertEqual(gotten, 'controlled')
        ep.control.assert_called_once_with('foo!', {'arg': 2}, {'fooid': 10})


# classes discovered by test_scanModule, above


class TestsEndpoint(base.Endpoint):
    pathPatterns = [
        "/tests",
    ]
    rootLinkName = 'tests'


class TestsEndpointParentClass(base.Endpoint):
    rootLinkName = 'shouldnt-see-this'


class TestsEndpointSubclass(TestsEndpointParentClass):
    pathPatterns = [
        "/test/foo",
    ]


class TestEndpoint(base.Endpoint):
    pathPatterns = [
        "/test/n:testid",
        "/test/n:testid/p1",
        "/test/n:testid/p2",
    ]


class TestResourceType(base.ResourceType):
    name = 'test'
    plural = 'tests'

    endpoints = [TestsEndpoint, TestEndpoint, TestsEndpointSubclass]

    class EntityType(types.Entity):
        testid = types.Integer()

    entityType = EntityType(name)

    @base.updateMethod
    def testUpdate(self) -> str:
        return "testUpdate return"
