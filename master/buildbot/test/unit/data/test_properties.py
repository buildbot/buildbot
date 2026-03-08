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
from twisted.trial import unittest

from buildbot.data import properties
from buildbot.process.properties import Properties as processProperties
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import endpoint
from buildbot.test.util import interfaces

if TYPE_CHECKING:
    from collections.abc import Callable

    from buildbot.util.twisted import InlineCallbacksType


class BuildsetPropertiesEndpoint(endpoint.EndpointMixin, unittest.TestCase):
    endpointClass = properties.BuildsetPropertiesEndpoint
    resourceTypeClass = properties.Properties

    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        yield self.setUpEndpoint()
        yield self.master.db.insert_test_data([
            fakedb.Buildset(id=13, reason='because I said so'),
            fakedb.SourceStamp(id=92),
            fakedb.SourceStamp(id=93),
            fakedb.BuildsetSourceStamp(buildsetid=13, sourcestampid=92),
            fakedb.BuildsetSourceStamp(buildsetid=13, sourcestampid=93),
            fakedb.Buildset(id=14, reason='no sourcestamps'),
            fakedb.BuildsetProperty(buildsetid=14),
        ])

    @defer.inlineCallbacks
    def test_get_properties(self) -> InlineCallbacksType[None]:
        props = yield self.callGet(('buildsets', 14, 'properties'))

        self.assertEqual(props, {'prop': (22, 'fakedb')})


class BuildPropertiesEndpoint(endpoint.EndpointMixin, unittest.TestCase):
    endpointClass = properties.BuildPropertiesEndpoint
    resourceTypeClass = properties.Properties

    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        yield self.setUpEndpoint()
        yield self.master.db.insert_test_data([
            fakedb.Builder(id=1),
            fakedb.Buildset(id=28),
            fakedb.BuildRequest(id=5, buildsetid=28, builderid=1),
            fakedb.Master(id=3),
            fakedb.Worker(id=42, name="Friday"),
            fakedb.Build(id=786, buildrequestid=5, masterid=3, workerid=42, builderid=1, number=5),
            fakedb.BuildProperty(buildid=786, name="year", value=1651, source="Wikipedia"),
            fakedb.BuildProperty(buildid=786, name="island_name", value="despair", source="Book"),
        ])

    @defer.inlineCallbacks
    def test_get_properties(self) -> InlineCallbacksType[None]:
        props = yield self.callGet(('builds', 786, 'properties'))

        self.assertEqual(props, {'year': (1651, 'Wikipedia'), 'island_name': ("despair", 'Book')})

    @defer.inlineCallbacks
    def test_get_properties_from_builder(self) -> InlineCallbacksType[None]:
        props = yield self.callGet(('builders', 1, 'builds', 5, 'properties'))
        self.assertEqual(props, {'year': (1651, 'Wikipedia'), 'island_name': ("despair", 'Book')})


class Properties(interfaces.InterfaceTests, TestReactorMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantMq=False, wantDb=True, wantData=True)
        self.rtype = properties.Properties(self.master)

    @defer.inlineCallbacks
    def do_test_callthrough(
        self,
        dbMethodName: str,
        method: Callable[..., defer.Deferred[Any]],
        exp_args: tuple[Any, ...] | None = None,
        exp_kwargs: dict[str, Any] | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> InlineCallbacksType[None]:
        rv = (1, 2)
        m = mock.Mock(return_value=defer.succeed(rv))
        setattr(self.master.db.builds, dbMethodName, m)
        res = yield method(*args, **kwargs)
        self.assertIdentical(res, rv)
        m.assert_called_with(
            *(exp_args or args),
            **(((exp_kwargs is None) and kwargs) or exp_kwargs),  # type: ignore[arg-type]
        )

    def test_signature_setBuildProperty(self) -> None:
        @self.assertArgSpecMatches(
            self.master.data.updates.setBuildProperty,  # fake
            self.rtype.setBuildProperty,
        )  # real
        def setBuildProperty(
            self: object, buildid: int, name: str, value: Any, source: str
        ) -> None:
            pass

    def test_setBuildProperty(self) -> defer.Deferred[None]:
        return self.do_test_callthrough(
            'setBuildProperty',
            self.rtype.setBuildProperty,
            buildid=1234,
            name='property',
            value=[42, 45],
            source='testsuite',
            exp_args=(1234, 'property', [42, 45], 'testsuite'),
            exp_kwargs={},
        )

    @defer.inlineCallbacks
    def test_setBuildProperties(self) -> InlineCallbacksType[None]:
        yield self.master.db.insert_test_data([
            fakedb.Builder(id=1),
            fakedb.Buildset(id=28),
            fakedb.BuildRequest(id=5, builderid=1, buildsetid=28),
            fakedb.Master(id=3),
            fakedb.Worker(id=42, name="Friday"),
            fakedb.Build(id=1234, builderid=1, buildrequestid=5, masterid=3, workerid=42),
        ])

        self.master.db.builds.setBuildProperty = mock.Mock(
            wraps=self.master.db.builds.setBuildProperty
        )
        props = processProperties.fromDict({"a": (1, 't'), "b": (['abc', 9], 't')})
        yield self.rtype.setBuildProperties(1234, props)
        setBuildPropertiesCalls = sorted(self.master.db.builds.setBuildProperty.mock_calls)
        self.assertEqual(
            setBuildPropertiesCalls,
            [mock.call(1234, 'a', 1, 't'), mock.call(1234, 'b', ['abc', 9], 't')],
        )
        self.master.mq.assertProductions([
            (('builds', '1234', 'properties', 'update'), {'a': (1, 't'), 'b': (['abc', 9], 't')}),
        ])
        # sync without changes: no db write
        self.master.db.builds.setBuildProperty.reset_mock()
        self.master.mq.clearProductions()
        yield self.rtype.setBuildProperties(1234, props)
        self.master.db.builds.setBuildProperty.assert_not_called()
        self.master.mq.assertProductions([])

        # sync with one changes: one db write
        props.setProperty('b', 2, 'step')
        self.master.db.builds.setBuildProperty.reset_mock()
        yield self.rtype.setBuildProperties(1234, props)

        self.master.db.builds.setBuildProperty.assert_called_with(1234, 'b', 2, 'step')
        self.master.mq.assertProductions([
            (('builds', '1234', 'properties', 'update'), {'b': (2, 'step')})
        ])
