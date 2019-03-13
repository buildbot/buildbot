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

import inspect

from twisted.internet import defer

from buildbot.data.exceptions import InvalidPathError
from buildbot.util import bytes2unicode


class EndpointMatcherBase:

    def __init__(self, role, defaultDeny=True):
        self.role = role
        self.defaultDeny = defaultDeny
        self.owner = None

    def setAuthz(self, authz):
        self.authz = authz
        self.master = authz.master

    def match(self, ep, action="get", options=None):
        if options is None:
            options = {}
        try:
            epobject, epdict = self.master.data.getEndpoint(ep)
            for klass in inspect.getmro(epobject.__class__):
                m = getattr(
                    self, "match_" + klass.__name__ + "_" + action, None)
                if m is not None:
                    return m(epobject, epdict, options)
                m = getattr(self, "match_" + klass.__name__, None)
                if m is not None:
                    return m(epobject, epdict, options)
        except InvalidPathError:
            return defer.succeed(None)
        return defer.succeed(None)

    def __repr__(self):
        # a repr for debugging. displays the class, and string attributes
        args = []
        for k, v in self.__dict__.items():
            if isinstance(v, str):
                args.append("%s='%s'" % (k, v))
        return "%s(%s)" % (self.__class__.__name__, ", ".join(args))


class Match:

    def __init__(self, master, build=None, buildrequest=None, buildset=None):
        self.master = master
        self.build = build
        self.buildrequest = buildrequest
        self.buildset = buildset

    def getOwner(self):
        if self.buildset:
            return self.getOwnerFromBuildset(self.buildset)
        elif self.buildrequest:
            return self.getOwnerFromBuildRequest(self.buildrequest)
        elif self.build:
            return self.getOwnerFromBuild(self.build)
        return defer.succeed(None)

    @defer.inlineCallbacks
    def getOwnerFromBuild(self, build):
        br = yield self.master.data.get(("buildrequests", build['buildrequestid']))
        owner = yield self.getOwnerFromBuildRequest(br)
        return owner

    @defer.inlineCallbacks
    def getOwnerFromBuildsetOrBuildRequest(self, buildsetorbuildrequest):
        props = yield self.master.data.get(("buildsets", buildsetorbuildrequest['buildsetid'], "properties"))
        if 'owner' in props:
            return props['owner'][0]
        return None

    getOwnerFromBuildRequest = getOwnerFromBuildsetOrBuildRequest
    getOwnerFromBuildSet = getOwnerFromBuildsetOrBuildRequest


class AnyEndpointMatcher(EndpointMatcherBase):

    def match(self, ep, action="get", options=None):
        return defer.succeed(Match(self.master))


class AnyControlEndpointMatcher(EndpointMatcherBase):

    def match(self, ep, action="", options=None):
        if bytes2unicode(action).lower() != "get":
            return defer.succeed(Match(self.master))
        return defer.succeed(None)


class StopBuildEndpointMatcher(EndpointMatcherBase):

    def __init__(self, builder=None, **kwargs):
        self.builder = builder
        super().__init__(**kwargs)

    @defer.inlineCallbacks
    def matchFromBuilderId(self, builderid):
        if builderid is not None:
            builder = yield self.master.data.get(('builders', builderid))
            buildername = builder['name']
            return self.authz.match(buildername, self.builder)
        return False

    @defer.inlineCallbacks
    def match_BuildEndpoint_stop(self, epobject, epdict, options):
        build = yield epobject.get({}, epdict)
        if self.builder is None:
            # no filtering needed: we match!
            return Match(self.master, build=build)
        # if filtering needed, we need to get some more info
        ret = yield self.matchFromBuilderId(build['builderid'])
        if ret:
            return Match(self.master, build=build)

        return None

    @defer.inlineCallbacks
    def match_BuildRequestEndpoint_stop(self, epobject, epdict, options):
        buildrequest = yield epobject.get({}, epdict)
        if self.builder is None:
            # no filtering needed: we match!
            return Match(self.master, buildrequest=buildrequest)
        # if filtering needed, we need to get some more info
        ret = yield self.matchFromBuilderId(buildrequest['builderid'])
        if ret:
            return Match(self.master, buildrequest=buildrequest)
        return None


class ForceBuildEndpointMatcher(EndpointMatcherBase):

    def __init__(self, builder=None, **kwargs):
        self.builder = builder
        super().__init__(**kwargs)

    @defer.inlineCallbacks
    def match_ForceSchedulerEndpoint_force(self, epobject, epdict, options):
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

    def __init__(self, builder=None, **kwargs):
        self.builder = builder
        super().__init__(**kwargs)

    @defer.inlineCallbacks
    def match_BuildEndpoint_rebuild(self, epobject, epdict, options):
        build = yield epobject.get({}, epdict)
        return Match(self.master, build=build)


class EnableSchedulerEndpointMatcher(EndpointMatcherBase):

    def match_SchedulerEndpoint_enable(self, epobject, epdict, options):
        return defer.succeed(Match(self.master))

#####
# not yet implemented


class ViewBuildsEndpointMatcher(EndpointMatcherBase):

    def __init__(self, branch=None, project=None, builder=None, **kwargs):
        super().__init__(**kwargs)
        self.branch = branch
        self.project = project
        self.builder = builder


class BranchEndpointMatcher(EndpointMatcherBase):

    def __init__(self, branch, **kwargs):
        self.branch = branch
        super().__init__(**kwargs)
