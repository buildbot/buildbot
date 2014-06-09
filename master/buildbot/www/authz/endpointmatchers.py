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

    def setAuthz(self, authz):
        self.authz = authz
        self.master = authz.master

    def match(self, ep, action="get"):
        try:
            epobject, epdict = self.master.data.getEndpoint(ep)
            for klass in inspect.getmro(epobject.__class__):
                m = getattr(self, "match_" + klass.__name__ + "_" + action, None)
                if m is not None:
                    return m(epobject, epdict)
                m = getattr(self, "match_" + klass.__name__, None)
                if m is not None:
                    return m(epobject, epdict)
        except InvalidPathError:
            return defer.succeed(False)
        return defer.succeed(False)


class AnyEndpointMatcher(EndpointMatcherBase):
    def __init__(self, **kwargs):
        EndpointMatcherBase.__init__(self, **kwargs)

    def match(self, ep, action="get"):
        return defer.succeed(True)


class ViewBuildsEndpointMatcher(EndpointMatcherBase):
    def __init__(self, branch=None, project=None, builder=None, **kwargs):
        EndpointMatcherBase.__init__(self, **kwargs)
        self.branch = branch
        self.project = project
        self.builder = builder

    def match_BuildEndpoint_get(self, epobject, epdict):
        return defer.succeed(True)


class StopBuildEndpointMatcher(EndpointMatcherBase):
    def __init__(self, builder=None, **kwargs):
        self.builder = builder
        EndpointMatcherBase.__init__(self, **kwargs)

    @defer.inlineCallbacks
    def match_BuildEndpoint_stop(self, epobject, epdict):
        if self.builder is None:
            # no filtering needed: we match!
            defer.returnValue(True)
        # if filtering needed, we need to get some more info
        build = yield epobject.get({}, epdict)
        builder = yield self.master.data.get(('builders', build['builderid']))
        buildername = builder['name']
        defer.returnValue(self.authz.match(buildername, self.builder))

    def match_BuildRequestEndpoint_stop(self, epobject, epdict):
        return defer.succeed(True)


class BranchEndpointMatcher(EndpointMatcherBase):
    def __init__(self, **kwargs):
        EndpointMatcherBase.__init__(self, **kwargs)


class ForceBuildEndpointMatcher(EndpointMatcherBase):
    def __init__(self, **kwargs):
        EndpointMatcherBase.__init__(self, **kwargs)
