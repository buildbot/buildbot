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

from __future__ import annotations

from typing import TYPE_CHECKING

from twisted.internet import defer

if TYPE_CHECKING:
    from typing import Any

    from twisted.trial import unittest

    from buildbot.test.fake import fakemaster
    from buildbot.util.twisted import InlineCallbacksType

    _StateTestMixinBase = unittest.TestCase
else:
    _StateTestMixinBase = object


class StateTestMixin(_StateTestMixinBase):
    master: fakemaster.FakeMaster

    @defer.inlineCallbacks
    def set_fake_state(self, object: Any, name: str, value: Any) -> InlineCallbacksType[None]:
        objectid = yield self.master.db.state.getObjectId(object.name, object.__class__.__name__)
        yield self.master.db.state.setState(objectid, name, value)

    @defer.inlineCallbacks
    def assert_state(self, objectid: int, **kwargs: Any) -> InlineCallbacksType[None]:
        for k, v in kwargs.items():
            value = yield self.master.db.state.getState(objectid, k)
            self.assertEqual(value, v, f"state for {k!r} is {v!r}")

    @defer.inlineCallbacks
    def assert_state_by_class(
        self, name: str, class_name: str, **kwargs: Any
    ) -> InlineCallbacksType[None]:
        objectid = yield self.master.db.state.getObjectId(name, class_name)
        yield self.assert_state(objectid, **kwargs)
