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

from typing import TYPE_CHECKING

from twisted.internet import threads
from twisted.python import threadpool

from buildbot.test.fake.reactor import NonThreadPool
from buildbot.test.fake.reactor import TestReactor
from buildbot.util import twisted
from buildbot.util.eventual import _setReactor
from buildbot.warnings import warn_deprecated

if TYPE_CHECKING:
    from twisted.trial import unittest

    _TestReactorMixinBase = unittest.TestCase
else:
    _TestReactorMixinBase = object


class TestReactorMixin(_TestReactorMixinBase):
    """
    Mix this in to get TestReactor as self.reactor which is correctly cleaned up
    at the end
    """

    def setup_test_reactor(self, use_asyncio=False, auto_tear_down=True) -> None:
        if use_asyncio:
            warn_deprecated('4.2.0', 'use_asyncio=True is deprecated')
        if not auto_tear_down:
            warn_deprecated('4.2.0', 'auto_tear_down=False is deprecated')

        self.patch(threadpool, 'ThreadPool', NonThreadPool)
        self.patch(twisted, 'ThreadPool', NonThreadPool)
        self.reactor = TestReactor()
        self.reactor.set_test_case(self)

        _setReactor(self.reactor)

        def deferToThread(f, *args, **kwargs):
            return threads.deferToThreadPool(
                self.reactor, self.reactor.getThreadPool(), f, *args, **kwargs
            )

        self.patch(threads, 'deferToThread', deferToThread)

        if auto_tear_down:
            self.addCleanup(self.tear_down_test_reactor)
        self._reactor_tear_down_called = False

    def tear_down_test_reactor(self) -> None:
        if self._reactor_tear_down_called:
            return

        self._reactor_tear_down_called = True

        # During shutdown sequence we must first stop the reactor and only then set unset the
        # reactor used for eventually() because any callbacks that are run during reactor.stop()
        # may use eventually() themselves.
        self.reactor.stop()
        self.reactor.assert_no_remaining_calls()
        _setReactor(None)
