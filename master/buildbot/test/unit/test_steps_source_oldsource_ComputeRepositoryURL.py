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

from buildbot.interfaces import IRenderable
from buildbot.process.properties import Properties, WithProperties
from buildbot.steps.source.oldsource import _ComputeRepositoryURL


class SourceStamp(object):
    repository = "test"

class Build(object):
    s = SourceStamp()
    props = Properties(foo = "bar")
    def getSourceStamp(self, codebase):
        assert codebase == ''
        return self.s
    def getProperties(self):
        return self.props
    def render(self, value):
        self.props.build = self
        return defer.maybeDeferred(IRenderable(value).getRenderingFor, self.props)

class FakeStep(object):
    codebase = ''

class RepoURL(unittest.TestCase):
    def setUp(self):
        self.build = Build()

    def test_backward_compatibility(self):
        url = _ComputeRepositoryURL(FakeStep(), "repourl")
        d = self.build.render(url)
        @d.addCallback
        def callback(res):
            self.assertEquals(res, "repourl")
        return d

    def test_format_string(self):
        url = _ComputeRepositoryURL(FakeStep(), "http://server/%s")
        d = self.build.render(url)
        @d.addCallback
        def callback(res):
            self.assertEquals(res, "http://server/test")
        return d

    def test_dict(self):
        dict = {}
        dict['test'] = "ssh://server/testrepository"
        url = _ComputeRepositoryURL(FakeStep(), dict)
        d = self.build.render(url)
        @d.addCallback
        def callback(res):
            self.assertEquals(res, "ssh://server/testrepository")
        return d

    def test_callable(self):
        func = lambda x: x[::-1]
        url = _ComputeRepositoryURL(FakeStep(), func)
        d = self.build.render(url)
        @d.addCallback
        def callback(res):
            self.assertEquals(res, "tset")
        return d

    def test_backward_compatibility_render(self):
        url = _ComputeRepositoryURL(FakeStep(), WithProperties("repourl%(foo)s"))
        d = self.build.render(url)
        @d.addCallback
        def callback(res):
            self.assertEquals(res, "repourlbar")
        return d

    def test_dict_render(self):
        d = dict(test=WithProperties("repourl%(foo)s"))
        url = _ComputeRepositoryURL(FakeStep(), d)
        d = self.build.render(url)
        @d.addCallback
        def callback(res):
            self.assertEquals(res, "repourlbar")
        return d

    def test_callable_render(self):
        func = lambda x: WithProperties(x+"%(foo)s")
        url = _ComputeRepositoryURL(FakeStep(), func)
        d = self.build.render(url)
        @d.addCallback
        def callback(res):
            self.assertEquals(res, "testbar")
        return d
