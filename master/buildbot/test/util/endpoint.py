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

from twisted import trial
from twisted.internet import defer

from buildbot.data import base
from buildbot.data import resultspec
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import interfaces
from buildbot.test.util import validation
from buildbot.util import pathmatch

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class EndpointMixin(TestReactorMixin, interfaces.InterfaceTests):
    # test mixin for testing Endpoint subclasses

    # class being tested
    endpointClass: type[base.Endpoint] | None = None

    # the corresponding resource type - this will be instantiated at
    # self.data.rtypes[rtype.type] and self.rtype
    resourceTypeClass: type[base.ResourceType] | None = None

    @defer.inlineCallbacks
    def setUpEndpoint(self) -> InlineCallbacksType[None]:
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantMq=True, wantDb=True, wantData=True)
        self.data = self.master.data
        self.matcher: pathmatch.Matcher[Any] = pathmatch.Matcher()

        assert self.resourceTypeClass is not None
        rtype = self.rtype = self.resourceTypeClass(self.master)
        assert rtype.name is not None
        setattr(self.data.rtypes, rtype.name, rtype)

        assert self.endpointClass is not None
        self.ep = self.endpointClass(rtype, self.master)

        # this usually fails when a single-element pathPattern does not have a
        # trailing comma
        pathPatterns = self.ep.pathPatterns
        for pp in pathPatterns:
            if pp == '/':
                continue
            if not pp.startswith('/') or pp.endswith('/'):
                raise AssertionError(f"invalid pattern {pp!r}")
        parsed_patterns: list[tuple[str, ...]] = [tuple(pp.split('/')[1:]) for pp in pathPatterns]
        for pat in parsed_patterns:
            self.matcher[pat] = self.ep

        self.pathArgs = [
            {arg.split(':', 1)[1] for arg in pat if ':' in arg}
            for pat in parsed_patterns
            if pat is not None
        ]

    def validateData(self, object: dict[str, Any]) -> None:
        validation.verifyData(self, self.rtype.entityType, {}, object)

    # call methods, with extra checks

    @defer.inlineCallbacks
    def callGet(
        self, path: tuple[str | int, ...], resultSpec: resultspec.ResultSpec | None = None
    ) -> InlineCallbacksType[Any]:
        self.assertIsInstance(path, tuple)
        if resultSpec is None:
            resultSpec = resultspec.ResultSpec()
        endpoint, kwargs = self.matcher[path]  # type: ignore[index]
        self.assertIdentical(endpoint, self.ep)
        rv = yield endpoint.get(resultSpec, kwargs)

        if self.ep.kind == base.EndpointKind.COLLECTION:
            self.assertIsInstance(rv, (list, base.ListResult))
        else:
            self.assertIsInstance(rv, (dict, type(None)))
        return rv

    def callControl(
        self, action: str, args: dict[str, Any], path: tuple[str | int, ...]
    ) -> defer.Deferred[Any]:
        self.assertIsInstance(path, tuple)
        endpoint, kwargs = self.matcher[path]  # type: ignore[index]
        self.assertIdentical(endpoint, self.ep)
        d = self.ep.control(action, args, kwargs)
        self.assertIsInstance(d, defer.Deferred)
        return d

    # interface tests

    def test_get_spec(self) -> None:
        try:

            @self.assertArgSpecMatches(self.ep.get)
            def get(self, resultSpec, kwargs):  # type: ignore[no-untyped-def,unused-ignore]
                pass

        except trial.unittest.FailTest:

            @self.assertArgSpecMatches(self.ep.get)
            def get(self, result_spec, kwargs):  # type: ignore[no-untyped-def,unused-ignore]
                pass

    def test_control_spec(self) -> None:
        @self.assertArgSpecMatches(self.ep.control)
        def control(self, action, args, kwargs):  # type: ignore[no-untyped-def,unused-ignore]
            pass

    def test_rootLinkName(self) -> None:
        rootLinkName = self.ep.rootLinkName
        if not rootLinkName:
            return
        try:
            self.assertEqual(self.matcher[(rootLinkName,)][0], self.ep)
        except KeyError:
            self.fail('No match for rootlink: ' + rootLinkName)
