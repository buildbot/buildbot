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

from twisted.trial import unittest
from twisted.internet import defer

from buildbot.test.util import www
from buildbot.www.authz import endpointmatchers
from buildbot.test.fake import fakedb

# AnyEndpointMatcher
# ForceBuildEndpointMatcher
# BranchEndpointMatcher
# ViewBuildsEndpointMatcher
# StopBuildEndpointMatcher


class EndpointBase(www.WwwTestMixin, unittest.TestCase):
    def setUp(self):
        self.master = self.make_master(url='h:/a/b/')
        self.db = self.master.db
        self.matcher = self.makeMatcher()
        self.matcher.setAuthz(self.master.authz)
        self.insertData()

    def insertData(self):
        pass


class AnyEndpointMatcher(EndpointBase):
    def makeMatcher(self):
        return endpointmatchers.AnyEndpointMatcher(role="foo")

    @defer.inlineCallbacks
    def test_nominal(self):
        ret = yield self.matcher.match(("foo", "bar"))
        self.assertEqual(ret, True)


class ViewBuildsEndpointMatcherBranch(EndpointBase):
    def makeMatcher(self):
        return endpointmatchers.ViewBuildsEndpointMatcher(branch="secret", role="agent")

    def insertData(self):
        self.db.insertTestData([
            fakedb.SourceStamp(id=13, branch=u'secret'),
            fakedb.Build(id=15, buildrequestid=16, masterid=1, buildslaveid=2),
            fakedb.BuildRequest(id=16, buildsetid=17),
            fakedb.Buildset(id=17),
            fakedb.BuildsetSourceStamp(id=20, buildsetid=17, sourcestampid=13),
        ])

    @defer.inlineCallbacks
    def test_nominal(self):
        ret = yield self.matcher.match(("foo", "bar"))
        self.assertEqual(ret, True)
