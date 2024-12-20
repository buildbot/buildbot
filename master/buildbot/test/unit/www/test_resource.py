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

from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import www
from buildbot.www import resource


class ResourceSubclass(resource.Resource):
    needsReconfig = True


class Resource(TestReactorMixin, www.WwwTestMixin, unittest.TestCase):
    def setUp(self):
        self.setup_test_reactor()

    @defer.inlineCallbacks
    def test_base_url(self):
        master = yield self.make_master(url=b'h:/a/b/')
        rsrc = resource.Resource(master)
        self.assertEqual(rsrc.base_url, b'h:/a/b/')

    @defer.inlineCallbacks
    def test_reconfigResource_registration(self):
        master = yield self.make_master(url=b'h:/a/b/')
        rsrc = ResourceSubclass(master)
        master.www.resourceNeedsReconfigs.assert_called_with(rsrc)


class RedirectResource(TestReactorMixin, www.WwwTestMixin, unittest.TestCase):
    def setUp(self):
        self.setup_test_reactor()

    @defer.inlineCallbacks
    def test_redirect(self):
        master = yield self.make_master(url=b'h:/a/b/')
        rsrc = resource.RedirectResource(master, b'foo')
        self.render_resource(rsrc, b'/')
        self.assertEqual(self.request.redirected_to, b'h:/a/b/foo')

    @defer.inlineCallbacks
    def test_redirect_cr_lf(self):
        master = yield self.make_master(url=b'h:/a/b/')
        rsrc = resource.RedirectResource(master, b'foo\r\nbar')
        self.render_resource(rsrc, b'/')
        self.assertEqual(self.request.redirected_to, b'h:/a/b/foo')
