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
from typing import Any

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import scheduler
from buildbot.test.util.state import StateTestMixin
from buildbot.util import codebase
from buildbot.util import state

if TYPE_CHECKING:
    from buildbot.test.fake.fakemaster import FakeMaster
    from buildbot.util.twisted import InlineCallbacksType


class FakeObject(codebase.AbsoluteSourceStampsMixin, state.StateMixin):
    name = 'fake-name'

    def __init__(
        self,
        master: FakeMaster,
        codebases: dict[str, Any],
    ) -> None:
        self.master = master
        self.codebases = codebases


class TestAbsoluteSourceStampsMixin(
    scheduler.SchedulerMixin, StateTestMixin, TestReactorMixin, unittest.TestCase
):
    codebases = {
        'a': {'repository': '', 'branch': 'master'},
        'b': {'repository': '', 'branch': 'master'},
    }

    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantDb=True, wantData=True)
        self.object = FakeObject(self.master, self.codebases)

    @defer.inlineCallbacks
    def mkch(self, **kwargs: Any) -> InlineCallbacksType[scheduler.SchedulerMixin.FakeChange]:
        ch = self.makeFakeChange(**kwargs)
        ch = yield self.addFakeChange(ch)
        return ch

    @defer.inlineCallbacks
    def test_getCodebaseDict(self) -> InlineCallbacksType[None]:
        cbd = yield self.object.getCodebaseDict('a')
        self.assertEqual(cbd, {'repository': '', 'branch': 'master'})

    @defer.inlineCallbacks
    def test_getCodebaseDict_not_found(self) -> InlineCallbacksType[None]:
        with self.assertRaises(KeyError):
            yield self.object.getCodebaseDict('c')

    @defer.inlineCallbacks
    def test_getCodebaseDict_existing(self) -> InlineCallbacksType[None]:
        yield self.set_fake_state(
            self.object,
            'lastCodebases',
            {
                'a': {
                    'repository': 'A',
                    'revision': '1234:abc',
                    'branch': 'master',
                    'lastChange': 10,
                }
            },
        )
        cbd = yield self.object.getCodebaseDict('a')
        self.assertEqual(
            cbd, {'repository': 'A', 'revision': '1234:abc', 'branch': 'master', 'lastChange': 10}
        )
        cbd = yield self.object.getCodebaseDict('b')
        self.assertEqual(cbd, {'repository': '', 'branch': 'master'})

    @defer.inlineCallbacks
    def test_recordChange(self) -> InlineCallbacksType[None]:
        yield self.object.recordChange(
            (
                yield self.mkch(
                    codebase='a', repository='A', revision='1234:abc', branch='master', number=500
                )
            )
        )
        yield self.assert_state_by_class(
            'fake-name',
            'FakeObject',
            lastCodebases={
                'a': {
                    'repository': 'A',
                    'revision': '1234:abc',
                    'branch': 'master',
                    'lastChange': 500,
                }
            },
        )

    @defer.inlineCallbacks
    def test_recordChange_older(self) -> InlineCallbacksType[None]:
        yield self.set_fake_state(
            self.object,
            'lastCodebases',
            {
                'a': {
                    'repository': 'A',
                    'revision': '2345:bcd',
                    'branch': 'master',
                    'lastChange': 510,
                }
            },
        )
        yield self.object.getCodebaseDict('a')
        yield self.object.recordChange(
            (
                yield self.mkch(
                    codebase='a', repository='A', revision='1234:abc', branch='master', number=500
                )
            )
        )
        yield self.assert_state_by_class(
            'fake-name',
            'FakeObject',
            lastCodebases={
                'a': {
                    'repository': 'A',
                    'revision': '2345:bcd',
                    'branch': 'master',
                    'lastChange': 510,
                }
            },
        )

    @defer.inlineCallbacks
    def test_recordChange_newer(self) -> InlineCallbacksType[None]:
        yield self.set_fake_state(
            self.object,
            'lastCodebases',
            {
                'a': {
                    'repository': 'A',
                    'revision': '1234:abc',
                    'branch': 'master',
                    'lastChange': 490,
                }
            },
        )

        yield self.object.getCodebaseDict('a')
        yield self.object.recordChange(
            (
                yield self.mkch(
                    codebase='a', repository='A', revision='2345:bcd', branch='master', number=500
                )
            )
        )
        yield self.assert_state_by_class(
            'fake-name',
            'FakeObject',
            lastCodebases={
                'a': {
                    'repository': 'A',
                    'revision': '2345:bcd',
                    'branch': 'master',
                    'lastChange': 500,
                }
            },
        )
