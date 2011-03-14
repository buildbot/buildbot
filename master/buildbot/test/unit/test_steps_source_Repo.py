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

from buildbot.steps.source import Repo

class RepoURL(unittest.TestCase):

    def test_parse1(self):
        r = Repo()
        self.assertEqual(r.parseDownloadProperty("repo download test/bla 564/12"),["test/bla 564/12"])
    def test_parse2(self):
        r = Repo()
        self.assertEqual(r.parseDownloadProperty("repo download test/bla 564/12 repo download test/bla 564/2"),["test/bla 564/12","test/bla 564/2"])
    def test_parse3(self):
        r = Repo()
        self.assertEqual(r.parseDownloadProperty("repo download test/bla 564/12 repo download test/bla 564/2 test/foo 5/1"),["test/bla 564/12","test/bla 564/2","test/foo 5/1"])
        self.assertEqual(r.parseDownloadProperty("repo download test/bla 564/12"),["test/bla 564/12"])
