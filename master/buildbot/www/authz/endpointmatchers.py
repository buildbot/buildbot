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


class EndpointMatcherBase(object):
    def __init__(self, role, defaultDeny=True):
        self.role = role
        self.defaultDeny = defaultDeny

    def setAuthz(self, authz):
        self.authz = authz
        self.master = authz.master


class AnyEndpointMatcher(EndpointMatcherBase):
    def __init__(self, **kwargs):
        EndpointMatcherBase.__init__(self, **kwargs)

    def match(self, ep):
        return defer.succeed(True)


class ViewBuildsEndpointMatcher(EndpointMatcherBase):
    def __init__(self, branch=None, project=None, builder=None, **kwargs):
        EndpointMatcherBase.__init__(self, **kwargs)
        self.branch = branch
        self.project = project
        self.builder = builder

    def match(self, ep):
        return True


class StopBuildEndpointMatcher(EndpointMatcherBase):
    def __init__(self, **kwargs):
        EndpointMatcherBase.__init__(self, **kwargs)


class BranchEndpointMatcher(EndpointMatcherBase):
    def __init__(self, **kwargs):
        EndpointMatcherBase.__init__(self, **kwargs)


class ForceBuildEndpointMatcher(EndpointMatcherBase):
    def __init__(self, **kwargs):
        EndpointMatcherBase.__init__(self, **kwargs)
