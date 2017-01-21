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

from buildbot import config
from buildbot.test.fake import fakemaster
from buildbot.test.fake import fakestats


class TestStatusMaster(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self, wantMq=True,
                                             wantData=True, wantDb=True)
        self.master.config = config.MasterConfig()
        self.master.config.www['port'] = 8010
        self.status_service = fakestats.FakeStatusService(master=self.master)

    def test_getBuildURLAliases_empty(self):
        self.assertEqual(self.master.config.buildbotURLAliases, [])

    def test_getBuildURLAliases_set(self):
        self.master.config.buildbotURLAliases.append('http://localhost2:8010')
        self.assertEqual(self.master.config.buildbotURLAliases,
                         ['http://localhost2:8010'])

    def test_getBuildURLAliases_usefn(self):
        b = self.status_service.getBuildbotURLAliases()
        self.assertEqual(b, ['http://localhost:8010/'])
