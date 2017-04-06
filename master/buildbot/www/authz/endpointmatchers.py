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
from future.utils import string_types

import inspect

from twisted.internet import defer

from buildbot.data.exceptions import InvalidPathError
from buildbot.util import bytes2NativeString


class EndpointMatcherBase(object):

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
            if isinstance(v, string_types):
                args.append("%s='%s'" % (k, v))
        return "%s(%s)" % (self.__class__.__name__, ", ".join(args))


class Match(object):

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
        defer.returnValue(owner)

    @defer.inlineCallbacks
    def getOwnerFromBuildsetOrBuildRequest(self, buildsetorbuildrequest):
        props = yield self.master.data.get(("buildsets", buildsetorbuildrequest['buildsetid'], "properties"))
        if 'owner' in props:
            defer.returnValue(props['owner'][0])
        defer.returnValue(None)

    getOwnerFromBuildRequest = getOwnerFromBuildsetOrBuildRequest
    getOwnerFromBuildSet = getOwnerFromBuildsetOrBuildRequest


class AnyEndpointMatcher(EndpointMatcherBase):

    def __init__(self, **kwargs):
        EndpointMatcherBase.__init__(self, **kwargs)

    def match(self, ep, action="get", options=None):
        return defer.succeed(Match(self.master))


class AnyControlEndpointMatcher(EndpointMatcherBase):

    def __init__(self, **kwargs):
        EndpointMatcherBase.__init__(self, **kwargs)

    def match(self, ep, action="", options=None):
        if bytes2NativeString(action).lower() != "get":
            return defer.succeed(Match(self.master))
        return defer.succeed(None)


class StopBuildEndpointMatcher(EndpointMatcherBase):

    def __init__(self, builder=None, **kwargs):
        self.builder = builder
        EndpointMatcherBase.__init__(self, **kwargs)

    @defer.inlineCallbacks
    def matchFromBuilderId(self, builderid):
        if builderid is not None:
            builder = yield self.master.data.get(('builders', builderid))
            buildername = builder['name']
            defer.returnValue(self.authz.match(buildername, self.builder))
        defer.returnValue(False)

    @defer.inlineCallbacks
    def match_BuildEndpoint_stop(self, epobject, epdict, options):
        build = yield epobject.get({}, epdict)
        if self.builder is None:
            # no filtering needed: we match!
            defer.returnValue(Match(self.master, build=build))
        # if filtering needed, we need to get some more info
        ret = yield self.matchFromBuilderId(build['builderid'])
        if ret:
            defer.returnValue(Match(self.master, build=build))

        defer.returnValue(None)

    @defer.inlineCallbacks
    def match_BuildRequestEndpoint_stop(self, epobject, epdict, options):
        buildrequest = yield epobject.get({}, epdict)
        if self.builder is None:
            # no filtering needed: we match!
            defer.returnValue(Match(self.master, buildrequest=buildrequest))
        # if filtering needed, we need to get some more info
        ret = yield self.matchFromBuilderId(buildrequest['builderid'])
        if ret:
            defer.returnValue(Match(self.master, buildrequest=buildrequest))
        defer.returnValue(None)


class ForceBuildEndpointMatcher(EndpointMatcherBase):

    def __init__(self, builder=None, **kwargs):
        self.builder = builder
        EndpointMatcherBase.__init__(self, **kwargs)

    @defer.inlineCallbacks
    def match_ForceSchedulerEndpoint_force(self, epobject, epdict, options):
        if self.builder is None:
            # no filtering needed: we match without querying!
            defer.returnValue(Match(self.master))
        sched = yield epobject.findForceScheduler(epdict['schedulername'])
        if sched is not None:
            builderNames = options.get('builderNames')
            builderid = options.get('builderid')
            builderNames = yield sched.computeBuilderNames(builderNames, builderid)
            for buildername in builderNames:
                if self.authz.match(buildername, self.builder):
                    defer.returnValue(Match(self.master))
        defer.returnValue(None)


class RebuildBuildEndpointMatcher(EndpointMatcherBase):

    def __init__(self, builder=None, **kwargs):
        self.builder = builder
        EndpointMatcherBase.__init__(self, **kwargs)

    @defer.inlineCallbacks
    def match_BuildEndpoint_rebuild(self, epobject, epdict, options):
        build = yield epobject.get({}, epdict)
        defer.returnValue(Match(self.master, build=build))


class EnableSchedulerEndpointMatcher(EndpointMatcherBase):

    def match_SchedulerEndpoint_enable(self, epobject, epdict, options):
        return defer.succeed(Match(self.master))

#####
# not yet implemented


class ViewBuildsEndpointMatcher(EndpointMatcherBase):

    def __init__(self, branch=None, project=None, builder=None, **kwargs):
        EndpointMatcherBase.__init__(self, **kwargs)
        self.branch = branch
        self.project = project
        self.builder = builder


class BranchEndpointMatcher(EndpointMatcherBase):

    def __init__(self, branch, **kwargs):
        self.branch = branch
        EndpointMatcherBase.__init__(self, **kwargs)
