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

from twisted.internet import defer
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

    @defer.inlineCallbacks
    def test_getState(self):
        self.master.db.state.fakeState('fake-name', 'FakeObject',
                                       fav_color=['red', 'purple'])
        res = yield self.object.getState('fav_color')

        self.assertEqual(res, ['red', 'purple'])

    @defer.inlineCallbacks
    def test_getState_default(self):
        res = yield self.object.getState('fav_color', 'black')

        self.assertEqual(res, 'black')

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

    @defer.inlineCallbacks
    def test_setState(self):
        yield self.object.setState('y', 14)

        self.master.db.state.assertStateByClass('fake-name', 'FakeObject',
                                                y=14)

    @defer.inlineCallbacks
    def test_setState_existing(self):
        self.master.db.state.fakeState('fake-name', 'FakeObject', x=13)
        yield self.object.setState('x', 14)

        self.master.db.state.assertStateByClass('fake-name', 'FakeObject',
                                                x=14)
