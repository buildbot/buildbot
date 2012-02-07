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

import exceptions
from zope.interface import implements
from twisted.trial import unittest
from twisted.internet import defer
from buildbot.process.build import Build
from buildbot.process.properties import WithSource

from mock import Mock

class FakeChange:
    def __init__(self, number = None):
        self.number = number
        self.who = "me"
        
class FakeSource:
    def __init__(self):
        self.branch = None
        self.codebase = ''
        self.project = ''
        self.repository = ''
        self.revision = None

    def asDict(self):
        result = {}
        result['branch'] = self.branch
        result['codebase'] = self.codebase
        result['project'] = self.project
        result['repository'] = self.repository
        result['revision'] = self.revision
        return result
        
        
class FakeRequest:
    def __init__(self):
        self.sources = []

class FakeBuild:
    def __init__(self, requests):
        self.sources = []
        for request in requests:
            for source in request.sources:
                self.sources.append(source)
        
    def getSourceStamp(self, codebase=None):
        for source in self.sources:
            if source.codebase == codebase:
                return source
        return None

class FakeProperties:
    def __init__(self, build):
        self.build = build
        
    def getBuild(self):
        return self.build
        
        
class TestWithSource(unittest.TestCase):

    def setUp(self):
        r = FakeRequest()
        r.sources = [FakeSource(), FakeSource()]
        r.sources[0].changes = [FakeChange()]
        r.sources[0].revision = "12345"
        r.sources[0].repository = "ssh://repoA"
        r.sources[0].codebase = "codebaseA"
        r.sources[1].changes = [FakeChange()]
        r.sources[1].revision = "23456"
        r.sources[1].repository = "telnet://repoB"
        r.sources[1].codebase = "codebaseB"
        
        build = FakeBuild([r])
        self.properties = FakeProperties(build)

    def test_codebase_with_args(self):
        ws = WithSource("codebaseB", "repository = %s", "repository")
        rendering = ws.getRenderingFor(self.properties)
        self.assertEqual(rendering, "repository = telnet://repoB")

    def test_codebase_not_found_with_args(self):
        ws = WithSource("codebaseC", "repository = %s", "repository")
        d = defer.succeed(None)
        d.addCallback(lambda _: ws.getRenderingFor(self.properties))
        return self.assertFailure(d, ValueError)

    def test_codebase_with_args_notfound(self):
        ws = WithSource("codebaseB", "repo = %s", "repo")
        d = defer.succeed(None)
        d.addCallback(lambda _: ws.getRenderingFor(self.properties))
        return self.assertFailure(d, ValueError)

    def test_codebase_with_dictionary_style(self):
        ws = WithSource("codebaseB", "repository = %(repository)s")
        rendering = ws.getRenderingFor(self.properties)
        self.assertEqual(rendering, "repository = telnet://repoB")
        
    def test_codebase_with_lambda(self):
        ws = WithSource("codebaseB", "scheme = %(scheme)s", scheme = lambda ss: ss.repository[:ss.repository.find(':')])
        rendering = ws.getRenderingFor(self.properties)
        self.assertEqual(rendering, "scheme = telnet")

    def test_codebase_with_dictionary_style_notfound(self):
        ws = WithSource("codebaseB", "repository = %(repositorie)s")
        d = defer.succeed(None)
        d.addCallback(lambda _: ws.getRenderingFor(self.properties))
        return self.assertFailure(d, ValueError)
