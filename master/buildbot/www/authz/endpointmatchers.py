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

import inspect
from typing import TYPE_CHECKING
from typing import Any

from twisted.internet import defer

from buildbot.data.exceptions import InvalidPathError
from buildbot.util import bytes2unicode

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class EndpointMatcherBase:
    def __init__(self, role: str, defaultDeny: bool = True) -> None:
        self.role = role
        self.defaultDeny = defaultDeny
        self.owner = None

    def setAuthz(self, authz: Any) -> None:
        self.authz = authz
        self.master = authz.master

    def match(
        self, ep: str, action: str = "get", options: dict[str, Any] | None = None
    ) -> defer.Deferred[Match | None]:
        if options is None:
            options = {}
        try:
            epobject, epdict = self.master.data.getEndpoint(ep)
            for klass in inspect.getmro(epobject.__class__):
                m = getattr(self, "match_" + klass.__name__ + "_" + action, None)
                if m is not None:
                    return m(epobject, epdict, options)
                m = getattr(self, "match_" + klass.__name__, None)
                if m is not None:
                    return m(epobject, epdict, options)
        except InvalidPathError:
            return defer.succeed(None)
        return defer.succeed(None)

    def __repr__(self) -> str:
        # a repr for debugging. displays the class, and string attributes
        args = []
        for k, v in self.__dict__.items():
            if isinstance(v, str):
                args.append(f"{k}='{v}'")
        return f'{self.__class__.__name__}({", ".join(args)})'


class Match:
    def __init__(
        self,
        master: Any,
        build: dict[str, Any] | None = None,
        buildrequest: dict[str, Any] | None = None,
        buildset: dict[str, Any] | None = None,
    ) -> None:
        self.master = master
        self.build = build
        self.buildrequest = buildrequest
        self.buildset = buildset

    def getOwner(self) -> defer.Deferred[str | None]:
        if self.buildset:
            return self.getOwnerFromBuildSet(self.buildset)
        elif self.buildrequest:
            return self.getOwnerFromBuildRequest(self.buildrequest)
        elif self.build:
            return self.getOwnerFromBuild(self.build)
        return defer.succeed(None)

    @defer.inlineCallbacks
    def getOwnerFromBuild(self, build: dict[str, Any]) -> InlineCallbacksType[str | None]:
        br = yield self.master.data.get(("buildrequests", build['buildrequestid']))
        owner = yield self.getOwnerFromBuildRequest(br)
        return owner

    @defer.inlineCallbacks
    def getOwnerFromBuildsetOrBuildRequest(
        self, buildsetorbuildrequest: dict[str, Any]
    ) -> InlineCallbacksType[str | None]:
        props = yield self.master.data.get((
            "buildsets",
            buildsetorbuildrequest['buildsetid'],
            "properties",
        ))
        if 'owner' in props:
            return props['owner'][0]
        return None

    getOwnerFromBuildRequest = getOwnerFromBuildsetOrBuildRequest
    getOwnerFromBuildSet = getOwnerFromBuildsetOrBuildRequest


class AnyEndpointMatcher(EndpointMatcherBase):
    def match(
        self, ep: str, action: str = "get", options: dict[str, Any] | None = None
    ) -> defer.Deferred[Match | None]:
        return defer.succeed(Match(self.master))


class AnyControlEndpointMatcher(EndpointMatcherBase):
    def match(
        self, ep: str, action: str = "", options: dict[str, Any] | None = None
    ) -> defer.Deferred[Match | None]:
        if bytes2unicode(action).lower() != "get":
            return defer.succeed(Match(self.master))
        return defer.succeed(None)


class StopBuildEndpointMatcher(EndpointMatcherBase):
    def __init__(self, builder: str | None = None, **kwargs: Any) -> None:
        self.builder = builder
        super().__init__(**kwargs)

    @defer.inlineCallbacks
    def matchFromBuilderId(self, builderid: int) -> InlineCallbacksType[bool]:
        builder = yield self.master.data.get(('builders', int(builderid)))
        buildername = builder['name']
        return self.authz.match(buildername, self.builder)

    @defer.inlineCallbacks
    def match_BuildEndpoint_stop(
        self, epobject: Any, epdict: dict[str, Any], options: dict[str, Any]
    ) -> InlineCallbacksType[Match | None]:
        build = yield epobject.get({}, epdict)
        if self.builder is None:
            # no filtering needed: we match!
            return Match(self.master, build=build)

        # if filtering needed, we need to get some more info
        if build is not None:
            ret = yield self.matchFromBuilderId(build['builderid'])
            if ret:
                return Match(self.master, build=build)

        return None

    @defer.inlineCallbacks
    def match_BuildRequestEndpoint_stop(
        self, epobject: Any, epdict: dict[str, Any], options: dict[str, Any]
    ) -> InlineCallbacksType[Match | None]:
        buildrequest = yield epobject.get({}, epdict)
        if self.builder is None:
            # no filtering needed: we match!
            return Match(self.master, buildrequest=buildrequest)

        # if filtering needed, we need to get some more info
        if buildrequest is not None:
            ret = yield self.matchFromBuilderId(buildrequest['builderid'])
            if ret:
                return Match(self.master, buildrequest=buildrequest)

        return None


class ForceBuildEndpointMatcher(EndpointMatcherBase):
    def __init__(self, builder: str | None = None, **kwargs: Any) -> None:
        self.builder = builder
        super().__init__(**kwargs)

    @defer.inlineCallbacks
    def match_ForceSchedulerEndpoint_force(
        self, epobject: Any, epdict: dict[str, Any], options: dict[str, Any]
    ) -> InlineCallbacksType[Match | None]:
        if self.builder is None:
            # no filtering needed: we match without querying!
            return Match(self.master)
        sched = yield epobject.findForceScheduler(epdict['schedulername'])
        if sched is not None:
            builderNames = options.get('builderNames')
            builderid = options.get('builderid')
            builderNames = yield sched.computeBuilderNames(builderNames, builderid)
            for buildername in builderNames:
                if self.authz.match(buildername, self.builder):
                    return Match(self.master)
        return None


class RebuildBuildEndpointMatcher(EndpointMatcherBase):
    def __init__(self, builder: str | None = None, **kwargs: Any) -> None:
        self.builder = builder
        super().__init__(**kwargs)

    @defer.inlineCallbacks
    def matchFromBuilderId(self, builderid: int) -> InlineCallbacksType[bool]:
        builder = yield self.master.data.get(('builders', builderid))
        buildername = builder['name']
        return self.authz.match(buildername, self.builder)

    @defer.inlineCallbacks
    def match_BuildEndpoint_rebuild(
        self, epobject: Any, epdict: dict[str, Any], options: dict[str, Any]
    ) -> InlineCallbacksType[Match | None]:
        build = yield epobject.get({}, epdict)
        if self.builder is None:
            # no filtering needed: we match!
            return Match(self.master, build=build)

        # if filtering needed, we need to get some more info
        if build is not None:
            ret = yield self.matchFromBuilderId(build['builderid'])
            if ret:
                return Match(self.master, build=build)

        return None


class EnableSchedulerEndpointMatcher(EndpointMatcherBase):
    def match_SchedulerEndpoint_enable(
        self, epobject: Any, epdict: dict[str, Any], options: dict[str, Any]
    ) -> defer.Deferred[Match]:
        return defer.succeed(Match(self.master))


#####
# not yet implemented


class ViewBuildsEndpointMatcher(EndpointMatcherBase):
    def __init__(
        self,
        branch: str | None = None,
        project: str | None = None,
        builder: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.branch = branch
        self.project = project
        self.builder = builder


class BranchEndpointMatcher(EndpointMatcherBase):
    def __init__(self, branch: str, **kwargs: Any) -> None:
        self.branch = branch
        super().__init__(**kwargs)
