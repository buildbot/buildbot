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
from twisted.trial import unittest

from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import www
from buildbot.www import mcp

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class McpResource(TestReactorMixin, www.WwwTestMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = yield self.make_master(url=b'h:/a/b/')  # type: ignore[arg-type]
        self.mcp = mcp.McpResource(self.master)

    @defer.inlineCallbacks
    def test_not_implemented(self) -> InlineCallbacksType[None]:
        # The scaffold endpoint is reachable but not yet implemented; it must
        # respond with a clean 501 rather than erroring.
        yield self.render_resource(self.mcp, b'/')
        self.assertRequest(responseCode=501)
