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


"""
Test the PB change source.
"""

import mock
from twisted.trial.unittest import TestCase

from buildbot.test.util import pbmanager, changesource
from buildbot.changes.pb import ChangePerspective, PBChangeSource

class TestPBChangeSource(
            changesource.ChangeSourceMixin,
            pbmanager.PBManagerMixin,
            TestCase):

    def setUp(self):
        self.setUpPBChangeSource()
        d = self.setUpChangeSource()

        def setup(_):
            # set up a fake service hierarchy
            self.master = mock.Mock()
            self.master.slavePortnum = '9999'
            self.master.pbmanager = self.pbmanager
            self.master.change_svc = self.changemaster
            self.master.change_svc.parent = self.master

            # and a change source
            self.change_source = PBChangeSource('alice', 'sekrit')
            self.change_source.parent = self.master.change_svc
        d.addCallback(setup)

        return d

    def test_describe(self):
        self.assertIn("PBChangeSource", self.change_source.describe())

    def test_registration(self):
        self.change_source.startService()
        self.assertRegistered('9999', 'alice', 'sekrit')
        d = self.change_source.stopService()
        def check(_):
            self.assertUnregistered('9999', 'alice', 'sekrit')
        d.addCallback(check)
        return d

    def test_perspective(self):
        persp = self.change_source.getPerspective(mock.Mock(), 'alice')
        self.assertIsInstance(persp, ChangePerspective)
        persp.perspective_addChange(dict(who='me', files=['a'], comments='comm'))
        self.assertEqual(len(self.changes_added), 1)
