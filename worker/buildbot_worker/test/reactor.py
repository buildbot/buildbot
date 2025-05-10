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
from typing import cast

from twisted.internet import threads
from twisted.python import threadpool
from twisted.trial.unittest import TestCase

from buildbot_worker.test.fake.reactor import NonThreadPool
from buildbot_worker.test.fake.reactor import TestReactor

if TYPE_CHECKING:
    from typing import Callable
    from typing import TypeVar

    from twisted.internet.defer import Deferred
    from twisted.internet.interfaces import IReactorFromThreads
    from twisted.python.threadpool import ThreadPool
    from typing_extensions import ParamSpec

    _T = TypeVar('_T')
    _P = ParamSpec('_P')


class TestReactorMixin:
    """
    Mix this in to get TestReactor as self.reactor which is correctly cleaned up
    at the end
    """

    def setup_test_reactor(self) -> None:
        assert isinstance(self, TestCase)
        self.patch(threadpool, 'ThreadPool', NonThreadPool)
        self.reactor = TestReactor()

        def deferToThread(
            f: Callable[_P, _T],
            *args: _P.args,
            **kwargs: _P.kwargs,
        ) -> Deferred[_T]:
            return threads.deferToThreadPool(
                cast("IReactorFromThreads", self.reactor),
                cast("ThreadPool", self.reactor.getThreadPool()),
                f,
                *args,
                **kwargs,
            )

        self.patch(threads, 'deferToThread', deferToThread)

        self.addCleanup(self.reactor.stop)
