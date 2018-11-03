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

from __future__ import absolute_import
from __future__ import print_function

from twisted.trial import unittest


class VersioningUtilsTests(unittest.SynchronousTestCase):
    # Version utils are copied in three packages.
    # this unit test is made to be able to test the three versions
    # with the same test
    module_under_test = "buildbot"

    def setUp(self):
        try:
            self.m = __import__(self.module_under_test)
        except ImportError:
            raise unittest.SkipTest(self.module_under_test + " package is not installed")

    def test_gitDescribeToPep440devVersion(self):
        self.assertEqual(self.m.gitDescribeToPep440("v0.9.8-20-gf0f45ca"), "0.9.9-dev20")

    def test_gitDescribeToPep440tag(self):
        self.assertEqual(self.m.gitDescribeToPep440("v0.9.8"), "0.9.8")

    def test_gitDescribeToPep440p1tag(self):
        self.assertEqual(self.m.gitDescribeToPep440("v0.9.9.post1"), "0.9.9.post1")

    def test_gitDescribeToPep440p1dev(self):
        self.assertEqual(self.m.gitDescribeToPep440("v0.9.9.post1-20-gf0f45ca"), "0.9.10-dev20")

    def test_getVersionFromArchiveIdNoTag(self):
        self.assertEqual(self.m.getVersionFromArchiveId("1514651968  (git-archive-version)"), "2017.12.30")

    def test_getVersionFromArchiveIdtag(self):
        self.assertEqual(self.m.getVersionFromArchiveId('1514808197  (HEAD -> master, tag: v1.0.0)'), "1.0.0")


class VersioningUtilsTests_PKG(VersioningUtilsTests):
    module_under_test = "buildbot_pkg"


class VersioningUtilsTests_WORKER(VersioningUtilsTests):
    module_under_test = "buildbot_worker"
