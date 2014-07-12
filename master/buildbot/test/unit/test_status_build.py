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

import mock

from buildbot import interfaces
from buildbot import util
from buildbot.status import build
from buildbot.test.fake import fakemaster
from twisted.trial import unittest
from zope.interface import implements


class FakeBuilderStatus:
    implements(interfaces.IBuilderStatus)


class FakeSource(util.ComparableMixin):
    compare_attrs = ('codebase', 'revision')

    def __init__(self, codebase, revision):
        self.codebase = codebase
        self.revision = revision

    def clone(self):
        return FakeSource(self.codebase, self.revision)

    def getAbsoluteSourceStamp(self, revision):
        return FakeSource(self.codebase, revision)

    def __repr__(self):
        # note: this won't work for VC systems with huge 'revision' strings
        text = []
        if self.codebase:
            text.append("(%s)" % self.codebase)
        if self.revision is None:
            return text + ["latest"]
        text.append(str(self.revision))
        return "FakeSource(%s)" % (', '.join(text),)


class TestBuildProperties(unittest.TestCase):

    """
    Test that a BuildStatus has the necessary L{IProperties} methods and that
    they delegate to its C{properties} attribute properly - so really just a
    test of the L{IProperties} adapter.
    """

    BUILD_NUMBER = 33

    def setUp(self):
        self.builder_status = FakeBuilderStatus()
        self.master = fakemaster.make_master()
        self.build_status = build.BuildStatus(self.builder_status, self.master,
                                              self.BUILD_NUMBER)
        self.build_status.properties = mock.Mock()

    def test_getProperty(self):
        self.build_status.getProperty('x')
        self.build_status.properties.getProperty.assert_called_with('x', None)

    def test_getProperty_default(self):
        self.build_status.getProperty('x', 'nox')
        self.build_status.properties.getProperty.assert_called_with('x', 'nox')

    def test_setProperty(self):
        self.build_status.setProperty('n', 'v', 's')
        self.build_status.properties.setProperty.assert_called_with('n', 'v',
                                                                    's', runtime=True)

    def test_hasProperty(self):
        self.build_status.properties.hasProperty.return_value = True
        self.assertTrue(self.build_status.hasProperty('p'))
        self.build_status.properties.hasProperty.assert_called_with('p')

    def test_render(self):
        self.build_status.render("xyz")
        self.build_status.properties.render.assert_called_with("xyz")
