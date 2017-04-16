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

from twisted.internet.defer import inlineCallbacks
from twisted.trial import unittest

from buildbot.status.web import redirectstatus
from buildbot.test.fake.web import FakeRequest


class TestRedirectStatusResource(unittest.TestCase):

    @inlineCallbacks
    def testReturnWaterfallRedirectOnNotBuiltRevision(self):
        status = FakeStatus()
        self.request = FakeRequest(
            {'builder': ['TestBuilder'], 'revision': ['nope']})
        self.request.uri = "/redirect"
        self.request.method = "GET"

        yield self.request.test_render(
            redirectstatus.RedirectStatusResource(status))

        self.assertEqual(self.request.redirected_to,
                         "/waterfall")

    @inlineCallbacks
    def testReturnCorrectBuildRedirectOnBuiltRevision(self):
        status = FakeStatus()
        self.request = FakeRequest(
            {'builder': ['TestBuilder'], 'revision': ['okay']})
        self.request.uri = "/redirect"
        self.request.method = "GET"

        yield self.request.test_render(
            redirectstatus.RedirectStatusResource(status))

        self.assertEqual(self.request.redirected_to,
                         "/builders/TestBuilder/builds/2")

    @inlineCallbacks
    def testReturnBuildRedirectOnNoBuilder(self):
        status = FakeStatus()
        self.request = FakeRequest({'revision': ['okay']})
        self.request.uri = "/redirect"
        self.request.method = "GET"

        yield self.request.test_render(
            redirectstatus.RedirectStatusResource(status))

        self.assertEqual(self.request.redirected_to,
                         "/builders/TestBuilder/builds/2")

    @inlineCallbacks
    def testReturnWaterfallRedirectOnNoDataGiven(self):
        status = FakeStatus()
        self.request = FakeRequest({})
        self.request.uri = "/redirect"
        self.request.method = "GET"

        yield self.request.test_render(
            redirectstatus.RedirectStatusResource(status))

        self.assertEqual(self.request.redirected_to,
                         "/waterfall")


class FakeStatus(object):

    def __init__(self, build_number=2):
        self._build_number = build_number

    def getBuilderNames(self):
        return ['TestBuilder']

    def getBuilder(self, ignore):
        return FakeBuilder(self._build_number)


class FakeBuilder(object):

    def __init__(self, build_number):
        self._build_number = build_number

    def getBuild(self, number=0, revision=None):
        if revision == "nope":
            return None
        else:
            return FakeBuild(self._build_number)


class FakeBuild(object):

    def __init__(self, build_number):
        self._build_number = build_number

    def getNumber(self):
        return self._build_number
