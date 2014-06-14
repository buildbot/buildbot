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

from twisted.internet import defer
from buildbot.data.exceptions import InvalidPathError
import inspect


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
                m = getattr(self, "match_" + klass.__name__ + "_" + action, None)
                if m is not None:
                    return m(epobject, epdict, options)
                m = getattr(self, "match_" + klass.__name__, None)
                if m is not None:
                    return m(epobject, epdict, options)
        except InvalidPathError:
            return defer.succeed(False)
        return defer.succeed(False)

    def __repr__(self):
        # a repr for debugging. displays the class, and string attributes
        args = []
        for k, v in self.__dict__.items():
            if isinstance(v, basestring):
                args.append("%s='%s'" % (k, v))
        return "%s(%s)" % (self.__class__.__name__, ", ".join(args))


class AnyEndpointMatcher(EndpointMatcherBase):
    def __init__(self, **kwargs):
        EndpointMatcherBase.__init__(self, **kwargs)

    def match(self, ep, action="get", options=None):
        return defer.succeed(True)


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
    def getOwnerFromBuild(self, build):
        br = yield self.master.data.get(("buildrequests", build['buildrequestid']))
        owner = yield self.getOwnerFromBuildRequest(br)
        defer.returnValue(owner)

    @defer.inlineCallbacks
    def getOwnerFromBuildRequest(self, buildrequest):
        props = yield self.master.data.get(("buildsets", buildrequest['buildsetid'], "properties"))
        if 'owner' in props:
            defer.returnValue(props['owner'][0])
        defer.returnValue(None)

    @defer.inlineCallbacks
    def match_BuildEndpoint_stop(self, epobject, epdict, options):
        build = yield epobject.get({}, epdict)
        self.owner = yield self.getOwnerFromBuild(build)
        if self.builder is None:
            # no filtering needed: we match!
            defer.returnValue(True)
        # if filtering needed, we need to get some more info
        ret = yield self.matchFromBuilderId(build['builderid'])
        defer.returnValue(ret)

    def match_BuildRequestEndpoint_stop(self, epobject, epdict, options):
        buildrequest = yield epobject.get({}, epdict)
        self.owner = yield self.getOwnerFromBuildRequest(build)
        if self.builder is None:
            # no filtering needed: we match!
            defer.returnValue(True)
        # if filtering needed, we need to get some more info
        ret = yield self.matchFromBuilderId(buildrequest['builderid'])
        defer.returnValue(ret)


class ForceBuildEndpointMatcher(EndpointMatcherBase):
    def __init__(self, builder=None, **kwargs):
        self.builder = builder
        EndpointMatcherBase.__init__(self, **kwargs)

    @defer.inlineCallbacks
    def match_ForceSchedulerEndpoint_force(self, epobject, epdict, options):
        if self.builder is None:
            # no filtering needed: we match without querying!
            defer.returnValue(True)
        sched = yield epobject.findForceScheduler(epdict['schedulername'])
        if sched is not None:
            builderNames = options.get('builderNames')
            builderid = options.get('builderid')
            builderNames = yield sched.computeBuilderNames(builderNames, builderid)
            for buildername in builderNames:
                if self.authz.match(buildername, self.builder):
                    defer.returnValue(True)
        defer.returnValue(False)

#####
# not yet implemented


class ViewBuildsEndpointMatcher(EndpointMatcherBase):
    def __init__(self, branch=None, project=None, builder=None, **kwargs):
        EndpointMatcherBase.__init__(self, **kwargs)
        self.branch = branch
        self.project = project
        self.builder = builder

    def match_BuildEndpoint_get(self, epobject, epdict, options):
        return defer.succeed(True)


class BranchEndpointMatcher(EndpointMatcherBase):
    def __init__(self, branch, **kwargs):
        self.branch = branch
        EndpointMatcherBase.__init__(self, **kwargs)

    def match_BuildEndpoint_get(self, epobject, epdict, options):
        return defer.succeed(True)
