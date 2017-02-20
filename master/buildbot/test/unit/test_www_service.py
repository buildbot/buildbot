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

import calendar
import datetime

import jwt

import mock

from twisted.cred import strcred
from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse
from twisted.internet import defer
from twisted.trial import unittest
from twisted.web._auth.wrapper import HTTPAuthSessionWrapper
from twisted.web.server import Request

from buildbot.test.unit import test_www_hooks_base
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
        self.master = self.make_master(url='h:/a/b/')
        self.svc = self.master.www = service.WWWService()
        self.svc.setServiceParent(self.master)

    def makeConfig(self, **kwargs):
        w = dict(port=None, auth=auth.NoAuth(), logfileName='l')
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

    def test_reconfigService_expiration_time(self):
        new_config = self.makeConfig(port=80, cookie_expiration_time=datetime.timedelta(minutes=1))
        d = self.svc.reconfigServiceWithBuildbotConfig(new_config)

        @d.addCallback
        def check(_):
            self.assertNotEqual(self.svc.site, None)
            self.assertNotEqual(self.svc.port_service, None)
            self.assertEqual(service.BuildbotSession.expDelay, datetime.timedelta(minutes=1))
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
        self.assertIsInstance(root.getChildWithDefault(b'api', req),
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
        self.assertIsInstance(root.getChildWithDefault(b'change_hook', req),
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
        ep = root.getChildWithDefault(b'change_hook', req)
        self.assertIsInstance(ep,
                              change_hook.ChangeHookResource)

        # not yet configured
        self.assertEqual(ep.dialects, {})

        yield self.svc.reconfigServiceWithBuildbotConfig(new_config)

        # now configured
        self.assertEqual(ep.dialects, {'base': True})

        rsrc = self.svc.site.resource.getChildWithDefault(b'change_hook', mock.Mock())
        path = b'/change_hook/base'
        request = test_www_hooks_base._prepare_request({})
        self.master.addChange = mock.Mock()
        yield self.render_resource(rsrc, path, request=request)
        self.master.addChange.assert_called()

    @defer.inlineCallbacks
    def test_setupSiteWithHookAndAuth(self):
        fn = self.mktemp()
        with open(fn, 'w') as f:
            f.write("user:pass")
        new_config = self.makeConfig(
            port=8080,
            plugins={},
            change_hook_dialects={'base': True},
            change_hook_auth=[strcred.makeChecker("file:" + fn)])
        self.svc.setupSite(new_config)

        yield self.svc.reconfigServiceWithBuildbotConfig(new_config)
        rsrc = self.svc.site.resource.getChildWithDefault(b'', mock.Mock())

        res = yield self.render_resource(rsrc, b'')
        self.assertIn(b'{"type": "file"}', res)

        rsrc = self.svc.site.resource.getChildWithDefault(
            b'change_hook', mock.Mock())
        res = yield self.render_resource(rsrc, b'/change_hook/base')
        # as UnauthorizedResource is in private namespace, we cannot use
        # assertIsInstance :-(
        self.assertIn('UnauthorizedResource', repr(res))


class TestBuildbotSite(unittest.SynchronousTestCase):
    SECRET = 'secret'

    def setUp(self):
        self.site = service.BuildbotSite(None, "logs", 0, 0)
        self.site.setSessionSecret(self.SECRET)

    def test_getSession_from_bad_jwt(self):
        """ if the cookie is bad (maybe from previous version of buildbot),
            then we should raise KeyError for consumption by caller,
            and log the JWT error
        """
        self.assertRaises(KeyError, self.site.getSession, "xxx")
        self.flushLoggedErrors(jwt.exceptions.DecodeError)

    def test_getSession_from_correct_jwt(self):
        payload = {'user_info': {'some': 'payload'}}
        uid = jwt.encode(payload, self.SECRET, algorithm=service.SESSION_SECRET_ALGORITHM)
        session = self.site.getSession(uid)
        self.assertEqual(session.user_info, {'some': 'payload'})

    def test_getSession_from_expired_jwt(self):
        # expired one week ago
        exp = datetime.datetime.utcnow() - datetime.timedelta(weeks=1)
        exp = calendar.timegm(datetime.datetime.timetuple(exp))
        payload = {'user_info': {'some': 'payload'}, 'exp': exp}
        uid = jwt.encode(payload, self.SECRET, algorithm=service.SESSION_SECRET_ALGORITHM)
        self.assertRaises(KeyError, self.site.getSession, uid)

    def test_getSession_with_no_user_info(self):
        payload = {'foo': 'bar'}
        uid = jwt.encode(payload, self.SECRET, algorithm=service.SESSION_SECRET_ALGORITHM)
        self.assertRaises(KeyError, self.site.getSession, uid)

    def test_makeSession(self):
        session = self.site.makeSession()
        self.assertEqual(session.user_info, {'anonymous': True})

    def test_updateSession(self):
        session = self.site.makeSession()

        class FakeChannel(object):
            transport = None

            def isSecure(self):
                return False
        request = Request(FakeChannel(), False)
        request.sitepath = [b"bb"]
        session.updateSession(request)
        self.assertEqual(len(request.cookies), 1)
        name, value = request.cookies[0].split(b";")[0].split(b"=")
        decoded = jwt.decode(value, self.SECRET,
                             algorithm=service.SESSION_SECRET_ALGORITHM)
        self.assertEqual(decoded['user_info'], {'anonymous': True})
        self.assertIn('exp', decoded)
