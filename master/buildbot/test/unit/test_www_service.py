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
import os

import mock
from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse
from twisted.internet import defer
from twisted.trial import unittest
from twisted.web._auth.wrapper import HTTPAuthSessionWrapper

from buildbot.test.fake import fakemaster
from buildbot.test.util import www
from buildbot.www import auth
from buildbot.www import change_hook
from buildbot.www import resource
from buildbot.www import rest
from buildbot.www import service


class NeedsReconfigResource(resource.Resource):

    needsReconfig = True
    reconfigs = 0

    def reconfigResource(self, config):
        NeedsReconfigResource.reconfigs += 1


class Test(www.WwwTestMixin, unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master()
        self.svc = self.master.www = service.WWWService()
        self.svc.setServiceParent(self.master)

    def makeConfig(self, **kwargs):
        pwd = os.getcwd()
        w = dict(
            port=None, public_html=pwd, auth=auth.NoAuth(), logfileName='l')
        w.update(kwargs)
        new_config = mock.Mock()
        new_config.www = w
        new_config.buildbotURL = 'h:/'
        self.master.config = new_config
        return new_config

    def test_reconfigService_no_port(self):
        new_config = self.makeConfig()
        d = self.svc.reconfigServiceWithBuildbotConfig(new_config)

        @d.addCallback
        def check(_):
            self.assertEqual(self.svc.site, None)
        return d

    @defer.inlineCallbacks
    def test_reconfigService_reconfigResources(self):
        new_config = self.makeConfig(port=8080)
        self.patch(rest, 'RestRootResource', NeedsReconfigResource)
        NeedsReconfigResource.reconfigs = 0

        # first time, reconfigResource gets called along with setupSite
        yield self.svc.reconfigServiceWithBuildbotConfig(new_config)
        self.assertEqual(NeedsReconfigResource.reconfigs, 1)

        # and the next time, setupSite isn't called, but reconfigResource is
        yield self.svc.reconfigServiceWithBuildbotConfig(new_config)
        self.assertEqual(NeedsReconfigResource.reconfigs, 2)

    def test_reconfigService_port(self):
        new_config = self.makeConfig(port=20)
        d = self.svc.reconfigServiceWithBuildbotConfig(new_config)

        @d.addCallback
        def check(_):
            self.assertNotEqual(self.svc.site, None)
            self.assertNotEqual(self.svc.port_service, None)
            self.assertEqual(self.svc.port, 20)
        return d

    def test_reconfigService_port_changes(self):
        new_config = self.makeConfig(port=20)
        d = self.svc.reconfigServiceWithBuildbotConfig(new_config)

        @d.addCallback
        def reconfig(_):
            newer_config = self.makeConfig(port=999)
            return self.svc.reconfigServiceWithBuildbotConfig(newer_config)

        @d.addCallback
        def check(_):
            self.assertNotEqual(self.svc.site, None)
            self.assertNotEqual(self.svc.port_service, None)
            self.assertEqual(self.svc.port, 999)
        return d

    def test_reconfigService_port_changes_to_none(self):
        new_config = self.makeConfig(port=20)
        d = self.svc.reconfigServiceWithBuildbotConfig(new_config)

        @d.addCallback
        def reconfig(_):
            newer_config = self.makeConfig()
            return self.svc.reconfigServiceWithBuildbotConfig(newer_config)

        @d.addCallback
        def check(_):
            # (note the site sticks around)
            self.assertEqual(self.svc.port_service, None)
            self.assertEqual(self.svc.port, None)
        return d

    def test_setupSite(self):
        self.svc.setupSite(self.makeConfig())
        site = self.svc.site

        # check that it has the right kind of resources attached to its
        # root
        root = site.resource
        req = mock.Mock()
        self.assertIsInstance(root.getChildWithDefault('api', req),
                              rest.RestRootResource)

    def test_setupSiteWithProtectedHook(self):
        checker = InMemoryUsernamePasswordDatabaseDontUse()
        checker.addUser("guest", "password")

        self.svc.setupSite(self.makeConfig(
            change_hook_dialects={'base': True},
            change_hook_auth=[checker]))
        site = self.svc.site

        # check that it has the right kind of resources attached to its
        # root
        root = site.resource
        req = mock.Mock()
        self.assertIsInstance(root.getChildWithDefault('change_hook', req),
                              HTTPAuthSessionWrapper)

    @defer.inlineCallbacks
    def test_setupSiteWithHook(self):
        new_config = self.makeConfig(
            change_hook_dialects={'base': True})
        self.svc.setupSite(new_config)
        site = self.svc.site

        # check that it has the right kind of resources attached to its
        # root
        root = site.resource
        req = mock.Mock()
        ep = root.getChildWithDefault('change_hook', req)
        self.assertIsInstance(ep,
                              change_hook.ChangeHookResource)

        # not yet configured
        self.assertEqual(ep.dialects, {})

        yield self.svc.reconfigServiceWithBuildbotConfig(new_config)

        # now configured
        self.assertEqual(ep.dialects, {'base': True})
