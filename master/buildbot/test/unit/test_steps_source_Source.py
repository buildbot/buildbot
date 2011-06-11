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

from buildbot.interfaces import IRenderable
from buildbot.process.properties import Properties, WithProperties
from buildbot.steps.source import _ComputeRepositoryURL

class SourceStamp(object):
    repository = "test"

class Build(object):
    s = SourceStamp()
    props = Properties(foo = "bar")
    def getSourceStamp(self):
        return self.s
    def getProperties(self):
        return self.props
    def render(self, value):
        return IRenderable(value).getRenderingFor(self)

class RepoURL(unittest.TestCase):
    def setUp(self):
        self.build = Build()

    def test_backward_compatibility(self):
        url = _ComputeRepositoryURL("repourl")
        self.assertEqual(self.build.render(url), "repourl")

    def test_format_string(self):
        url = _ComputeRepositoryURL("http://server/%s")
        self.assertEquals(self.build.render(url), "http://server/test")

    def test_dict(self):
        dict = {}
        dict['test'] = "ssh://server/testrepository"
        url = _ComputeRepositoryURL(dict)
        self.assertEquals(self.build.render(url), "ssh://server/testrepository")

    def test_callable(self):
        func = lambda x: x[::-1]
        url = _ComputeRepositoryURL(func)
        self.assertEquals(self.build.render(url), "tset")

    def test_backward_compatibility_render(self):
        url = _ComputeRepositoryURL(WithProperties("repourl%(foo)s"))
        self.assertEquals(self.build.render(url), "repourlbar")

    def test_dict_render(self):
        d = dict(test=WithProperties("repourl%(foo)s"))
        url = _ComputeRepositoryURL(d)
        self.assertEquals(self.build.render(url), "repourlbar")

    def test_callable_render(self):
        func = lambda x: WithProperties(x+"%(foo)s")
        url = _ComputeRepositoryURL(func)
        self.assertEquals(self.build.render(url), "testbar")


