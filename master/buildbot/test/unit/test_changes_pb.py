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
from twisted.trial import unittest
from twisted.internet import defer
from buildbot.changes import pb
from buildbot.test.util import changesource, pbmanager

class TestPBChangeSource(
            changesource.ChangeSourceMixin,
            pbmanager.PBManagerMixin,
            unittest.TestCase):

    def setUp(self):
        self.setUpPBChangeSource()
        d = self.setUpChangeSource()

        def setup(_):
            # fill in some extra details of the master
            self.master.slavePortnum = '9999'
            self.master.pbmanager = self.pbmanager
        d.addCallback(setup)

        return d

    def test_registration_slaveport(self):
        return self._test_registration(('9999', 'alice', 'sekrit'),
                user='alice', passwd='sekrit')

    def test_registration_custom_port(self):
        return self._test_registration(('8888', 'alice', 'sekrit'),
                user='alice', passwd='sekrit', port='8888')

    def test_registration_no_userpass(self):
        return self._test_registration(('9999', 'change', 'changepw'))

    def _test_registration(self, exp_registration, **constr_kwargs):
        self.attachChangeSource(pb.PBChangeSource(**constr_kwargs))
        self.startChangeSource()
        self.assertRegistered(*exp_registration)
        d = self.stopChangeSource()
        def check(_):
            self.assertUnregistered(*exp_registration)
        d.addCallback(check)
        return d

    def test_perspective(self):
        self.attachChangeSource(pb.PBChangeSource('alice', 'sekrit', port='8888'))
        persp = self.changesource.getPerspective(mock.Mock(), 'alice')
        self.assertIsInstance(persp, pb.ChangePerspective)

    def test_describe(self):
        cs = pb.PBChangeSource()
        self.assertSubstring("PBChangeSource", cs.describe())

class TestChangePerspective(unittest.TestCase):
    def setUp(self):
        self.added_changes = []
        self.master = mock.Mock()
        def addChange(**chdict):
            self.added_changes.append(chdict)
            return defer.succeed(None)
        self.master.addChange = addChange

    def test_addChange_noprefix(self):
        cp = pb.ChangePerspective(self.master, None)
        d = cp.perspective_addChange(dict(who="bar", files=['a']))
        def check(_):
            self.assertEqual(self.added_changes,
                    [ dict(who="bar", files=['a']) ])
        d.addCallback(check)
        return d

    def test_addChange_prefix(self):
        cp = pb.ChangePerspective(self.master, 'xx/')
        d = cp.perspective_addChange(
                dict(who="bar", files=['xx/a', 'yy/b']))
        def check(_):
            self.assertEqual(self.added_changes,
                    [ dict(who="bar", files=['a']) ])
        d.addCallback(check)
        return d
