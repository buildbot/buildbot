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

from buildbot.test.fake.fakemaster import make_master
from buildbot.util import state


class FakeObject(state.StateMixin):
    name = "fake-name"

    def __init__(self, master):
        self.master = master


class TestStateMixin(unittest.TestCase):

    OBJECTID = 19

    def setUp(self):
        self.master = make_master(wantDb=True, testcase=self)
        self.object = FakeObject(self.master)

    def test_getState(self):
        self.master.db.state.fakeState('fake-name', 'FakeObject',
                                       fav_color=['red', 'purple'])
        d = self.object.getState('fav_color')

        @d.addCallback
        def check(res):
            self.assertEqual(res, ['red', 'purple'])
        return d

    def test_getState_default(self):
        d = self.object.getState('fav_color', 'black')

        @d.addCallback
        def check(res):
            self.assertEqual(res, 'black')
        return d

    def test_getState_KeyError(self):
        self.master.db.state.fakeState('fake-name', 'FakeObject',
                                       fav_color=['red', 'purple'])
        d = self.object.getState('fav_book')

        def cb(_):
            self.fail("should not succeed")

        def check_exc(f):
            f.trap(KeyError)
            pass
        d.addCallbacks(cb, check_exc)
        return d

    def test_setState(self):
        d = self.object.setState('y', 14)

        @d.addCallback
        def check(_):
            self.master.db.state.assertStateByClass('fake-name', 'FakeObject',
                                                    y=14)
        return d

    def test_setState_existing(self):
        self.master.db.state.fakeState('fake-name', 'FakeObject', x=13)
        d = self.object.setState('x', 14)

        @d.addCallback
        def check(_):
            self.master.db.state.assertStateByClass('fake-name', 'FakeObject',
                                                    x=14)
        return d
