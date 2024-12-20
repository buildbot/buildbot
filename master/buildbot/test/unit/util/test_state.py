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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util.state import StateTestMixin
from buildbot.util import state


class FakeObject(state.StateMixin):
    name = "fake-name"

    def __init__(self, master):
        self.master = master


class TestStateMixin(TestReactorMixin, StateTestMixin, unittest.TestCase):
    OBJECTID = 19

    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantDb=True)
        self.object = FakeObject(self.master)

    @defer.inlineCallbacks
    def test_getState(self):
        yield self.set_fake_state(self.object, 'fav_color', ['red', 'purple'])
        res = yield self.object.getState('fav_color')

        self.assertEqual(res, ['red', 'purple'])

    @defer.inlineCallbacks
    def test_getState_default(self):
        res = yield self.object.getState('fav_color', 'black')

        self.assertEqual(res, 'black')

    @defer.inlineCallbacks
    def test_getState_KeyError(self):
        yield self.set_fake_state(self.object, 'fav_color', ['red', 'purple'])
        with self.assertRaises(KeyError):
            yield self.object.getState('fav_book')
        self.flushLoggedErrors(KeyError)

    @defer.inlineCallbacks
    def test_setState(self):
        yield self.object.setState('y', 14)

        yield self.assert_state_by_class('fake-name', 'FakeObject', y=14)

    @defer.inlineCallbacks
    def test_setState_existing(self):
        yield self.set_fake_state(self.object, 'x', 13)
        yield self.object.setState('x', 14)

        yield self.assert_state_by_class('fake-name', 'FakeObject', x=14)
