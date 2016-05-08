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
from twisted.trial import unittest

from buildbot.test.fake import fakedb
from buildbot.test.util import www
from buildbot.www import authz
from buildbot.www.authz.endpointmatchers import AnyEndpointMatcher
from buildbot.www.authz.endpointmatchers import BranchEndpointMatcher
from buildbot.www.authz.endpointmatchers import ForceBuildEndpointMatcher
from buildbot.www.authz.endpointmatchers import RebuildBuildEndpointMatcher
from buildbot.www.authz.endpointmatchers import StopBuildEndpointMatcher
from buildbot.www.authz.endpointmatchers import ViewBuildsEndpointMatcher
from buildbot.www.authz.roles import RolesFromEmails
from buildbot.www.authz.roles import RolesFromGroups
from buildbot.www.authz.roles import RolesFromOwner


class Authz(www.WwwTestMixin, unittest.TestCase):

    def setUp(self):
        authzcfg = authz.Authz(
            # simple matcher with '*' glob character
            stringsMatcher=authz.fnmatchStrMatcher,
            # stringsMatcher = authz.Authz.reStrMatcher,  # if you prefer
            # regular expressions
            allowRules=[
                # admins can do anything,
                # defaultDeny=False: if user does not have the admin role, we
                # continue parsing rules
                AnyEndpointMatcher(role="admins", defaultDeny=False),

                # rules for viewing builds, builders, step logs
                # depending on the sourcestamp or buildername
                ViewBuildsEndpointMatcher(
                    branch="secretbranch", role="agents"),
                ViewBuildsEndpointMatcher(
                    project="secretproject", role="agents"),
                ViewBuildsEndpointMatcher(branch="*", role="*"),
                ViewBuildsEndpointMatcher(project="*", role="*"),

                StopBuildEndpointMatcher(role="owner"),
                RebuildBuildEndpointMatcher(role="owner"),

                # nine-* groups can do stuff on the nine branch
                BranchEndpointMatcher(branch="nine", role="nine-*"),
                # eight-* groups can do stuff on the eight branch
                BranchEndpointMatcher(branch="eight", role="eight-*"),

                # *-try groups can start "try" builds
                ForceBuildEndpointMatcher(builder="try", role="*-developers"),
                # *-mergers groups can start "merge" builds
                ForceBuildEndpointMatcher(builder="merge", role="*-mergers"),
                # *-releasers groups can start "release" builds
                ForceBuildEndpointMatcher(
                    builder="release", role="*-releasers"),
            ],
            roleMatchers=[
                RolesFromGroups(groupPrefix="buildbot-"),
                RolesFromEmails(admins=["homer@springfieldplant.com"],
                                agents=["007@mi6.uk"]),
                RolesFromOwner(role="owner")
            ]
        )
        self.users = dict(homer=dict(email="homer@springfieldplant.com"),
                          bond=dict(email="007@mi6.uk"),
                          nineuser=dict(email="user@nine.com", groups=["buildbot-nine-mergers",
                                                                       "buildbot-nine-developers"]),
                          eightuser=dict(
                              email="user@eight.com", groups=["buildbot-eight-deverlopers"])
                          )
        self.master = self.make_master(url='h:/a/b/', authz=authzcfg)
        self.authz = self.master.authz
        self.master.db.insertTestData([
            fakedb.Builder(id=77, name="mybuilder"),
            fakedb.Master(id=88),
            fakedb.Worker(id=13, name='sl'),
            fakedb.Buildset(id=8822),
            fakedb.BuildsetProperty(buildsetid=8822, property_name='owner',
                                    property_value='["user@nine.com", "force"]'),
            fakedb.BuildRequest(id=82, buildsetid=8822, builderid=77),
            fakedb.Build(id=13, builderid=77, masterid=88, workerid=13,
                         buildrequestid=82, number=3),
            fakedb.Build(id=14, builderid=77, masterid=88, workerid=13,
                         buildrequestid=82, number=4),
            fakedb.Build(id=15, builderid=77, masterid=88, workerid=13,
                         buildrequestid=82, number=5),
        ])

    def assertUserAllowed(self, ep, action, options, user):
        return self.authz.assertUserAllowed(tuple(ep.split("/")), action, options, self.users[user])

    @defer.inlineCallbacks
    def assertUserForbidden(self, ep, action, options, user):
        try:
            yield self.authz.assertUserAllowed(tuple(ep.split("/")), action, options, self.users[user])
        except authz.Forbidden, e:
            self.assertIn("need to have role", repr(e))

    @defer.inlineCallbacks
    def test_anyEndpoint(self):
        yield self.assertUserAllowed("foo/bar", "get", {}, "homer")
        yield self.assertUserForbidden("foo/bar", "get", {}, "bond")

    @defer.inlineCallbacks
    def test_stopBuild(self):
        # admin can always stop
        yield self.assertUserAllowed("builds/13", "stop", {}, "homer")
        # owner can always stop
        yield self.assertUserAllowed("builds/13", "stop", {}, "nineuser")
        yield self.assertUserAllowed("buildrequests/82", "stop", {}, "nineuser")
        # not owner cannot stop
        yield self.assertUserForbidden("builds/13", "stop", {}, "eightuser")
        yield self.assertUserForbidden("buildrequests/82", "stop", {}, "eightuser")

    @defer.inlineCallbacks
    def test_rebuildBuild(self):
        # admin can rebuild
        yield self.assertUserAllowed("builds/13", "rebuild", {}, "homer")
        # owner can always rebuild
        yield self.assertUserAllowed("builds/13", "rebuild", {}, "nineuser")
        yield self.assertUserAllowed("buildrequests/82", "rebuild", {}, "nineuser")
        # not owner cannot rebuild
        yield self.assertUserForbidden("builds/13", "rebuild", {}, "eightuser")
        yield self.assertUserForbidden("buildrequests/82", "rebuild", {}, "eightuser")
