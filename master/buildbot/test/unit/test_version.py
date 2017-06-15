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

from buildbot import gitDescribeToPep440


class GitDescribeToPep440(unittest.SynchronousTestCase):

    def test_devVersion(self):
        self.assertEqual(gitDescribeToPep440("v0.9.8-20-gf0f45ca"), "0.9.9-dev20")

    def test_tag(self):
        self.assertEqual(gitDescribeToPep440("v0.9.8"), "0.9.8")
