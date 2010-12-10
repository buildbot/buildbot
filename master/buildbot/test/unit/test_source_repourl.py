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

from buildbot.steps.source import Source

class SourceStamp(object):
    repository = "test"

class Properties(object):
    def render(self, value):
        return value % dict(foo="bar")

class Build(object):
    s = SourceStamp()
    props = Properties()
    def getSourceStamp(self):
        return self.s
    def getProperties(self):
        return self.props

class RepoURL(unittest.TestCase):

    def test_backward_compatibility(self):
        s = Source()
        s.build = Build()
        self.assertEqual(s.computeRepositoryURL("repourl"), "repourl")

    def test_format_string(self):
        s = Source()
        s.build = Build()
        self.assertEquals(s.computeRepositoryURL("http://server/%s"), "http://server/test")

    def test_dict(self):
        s = Source()
        s.build = Build()
        dict = {}
        dict['test'] = "ssh://server/testrepository"
        self.assertEquals(s.computeRepositoryURL(dict), "ssh://server/testrepository")

    def test_callable(self):
        s = Source()
        s.build = Build()
        func = lambda x: x[::-1]
        self.assertEquals(s.computeRepositoryURL(func), "tset")

    def test_backward_compatibility_render(self):
        s = Source()
        s.build = Build()
        self.assertEquals(s.computeRepositoryURL("repourl%(foo)s"), "repourlbar")

    def test_dict_render(self):
        s = Source()
        s.build = Build()
        d = dict(test="repourl%(foo)s")
        self.assertEquals(s.computeRepositoryURL(d), "repourlbar")

    def test_callable_render(self):
        s = Source()
        s.build = Build()
        func = lambda x: x+"%(foo)s"
        self.assertEquals(s.computeRepositoryURL(func), "testbar")


