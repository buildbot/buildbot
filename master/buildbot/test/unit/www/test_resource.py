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
from buildbot.www import resource

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class ResourceSubclass(resource.Resource):
    needsReconfig = True


class Resource(TestReactorMixin, www.WwwTestMixin, unittest.TestCase):
    def setUp(self) -> None:
        self.setup_test_reactor()

    @defer.inlineCallbacks
    def test_base_url(self) -> InlineCallbacksType[None]:
        master = yield self.make_master(url=b'h:/a/b/')  # type: ignore[arg-type]
        rsrc = resource.Resource(master)
        self.assertEqual(rsrc.base_url, b'h:/a/b/')

    @defer.inlineCallbacks
    def test_reconfigResource_registration(self) -> InlineCallbacksType[None]:
        master = yield self.make_master(url=b'h:/a/b/')  # type: ignore[arg-type]
        rsrc = ResourceSubclass(master)
        master.www.resourceNeedsReconfigs.assert_called_with(rsrc)


class RedirectResource(TestReactorMixin, www.WwwTestMixin, unittest.TestCase):
    def setUp(self) -> None:
        self.setup_test_reactor()

    @defer.inlineCallbacks
    def test_redirect(self) -> InlineCallbacksType[None]:
        master = yield self.make_master(url=b'h:/a/b/')  # type: ignore[arg-type]
        rsrc = resource.RedirectResource(master, b'foo')  # type: ignore[arg-type]
        self.render_resource(rsrc, b'/')
        self.assertEqual(self.request.redirected_to, b'h:/a/b/foo')

    @defer.inlineCallbacks
    def test_redirect_cr_lf(self) -> InlineCallbacksType[None]:
        master = yield self.make_master(url=b'h:/a/b/')  # type: ignore[arg-type]
        rsrc = resource.RedirectResource(master, b'foo\r\nbar')  # type: ignore[arg-type]
        self.render_resource(rsrc, b'/')
        self.assertEqual(self.request.redirected_to, b'h:/a/b/foo')
