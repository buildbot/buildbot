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

import base64
import mock

from buildbot.test.util import www
from buildbot.www import auth
from twisted.internet import defer
from twisted.trial import unittest
from twisted.web._auth.wrapper import UnauthorizedResource
from twisted.web.resource import IResource


class SessionConfigResource(www.WwwTestMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def test_render(self):
        _auth = auth.NoAuth()
        _auth.maybeAutoLogin = mock.Mock()
        master = self.make_master(url='h:/a/b/', auth=_auth)
        rsrc = auth.SessionConfigResource(master)
        rsrc.reconfigResource(master.config)

        res = yield self.render_resource(rsrc, '/')
        _auth.maybeAutoLogin.assert_called()
        exp = 'this.config = {"url": "h:/a/b/", "user": {"anonymous": true}, "auth": {"name": "NoAuth"}, "port": null}'
        self.assertEqual(res, exp)

        master.session.user_info = dict(name="me", email="me@me.org")
        res = yield self.render_resource(rsrc, '/')
        exp = 'this.config = {"url": "h:/a/b/", "user": {"email": "me@me.org", "name": "me"}, "auth": {"name": "NoAuth"}, "port": null}'
        self.assertEqual(res, exp)

        master = self.make_master(url='h:/a/c/', auth=_auth)
        rsrc.reconfigResource(master.config)
        res = yield self.render_resource(rsrc, '/')
        exp = 'this.config = {"url": "h:/a/c/", "user": {"anonymous": true}, "auth": {"name": "NoAuth"}, "port": null}'
        self.assertEqual(res, exp)


class LoginResource(www.WwwTestMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def test_render(self):
        _auth = auth.NoAuth()
        _auth.maybeAutoLogin = mock.Mock()

        def authenticateViaLogin(request):
            request.getSession().user_info = dict(name="me")
        _auth.authenticateViaLogin = mock.Mock(side_effect=authenticateViaLogin)
        master = self.make_master(url='h:/a/b/', auth=_auth)
        rsrc = _auth.getLoginResource(master)
        rsrc.reconfigResource(master.config)

        res = yield self.render_resource(rsrc, '/')
        _auth.maybeAutoLogin.assert_not_called()
        self.assertEqual(res, "")
        _auth.authenticateViaLogin.assert_called()


class PreAuthenticatedLoginResource(www.WwwTestMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def test_render(self):
        _auth = auth.NoAuth()
        _auth.maybeAutoLogin = mock.Mock()
        _auth.authenticateViaLogin = mock.Mock()

        def updateUserInfo(request):
            session = request.getSession()
            session.user_info['email'] = session.user_info['username'] + "@org"
        _auth.updateUserInfo = mock.Mock(side_effect=updateUserInfo)
        master = self.make_master(url='h:/a/b/', auth=_auth)
        rsrc = auth.PreAuthenticatedLoginResource(master, _auth, "him")
        rsrc.reconfigResource(master.config)

        res = yield self.render_resource(rsrc, '/')
        self.assertEqual(res, "")
        _auth.maybeAutoLogin.assert_not_called()
        _auth.authenticateViaLogin.assert_not_called()
        _auth.updateUserInfo.assert_called()
        self.assertEqual(master.session.user_info, {'email': 'him@org', 'username': 'him'})


class LogoutResource(www.WwwTestMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def test_render(self):
        _auth = auth.NoAuth()
        master = self.make_master(url='h:/a/b/', auth=_auth)
        master.session.expire = mock.Mock()
        rsrc = auth.LogoutResource(master)
        rsrc.reconfigResource(master.config)

        yield self.render_resource(rsrc, '/')
        master.session.expire.assert_not_called()


class RemoteUserAuth(www.WwwTestMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def test_RemoteUserAuth(self):
        _auth = auth.RemoteUserAuth()
        master = self.make_master(url='h:/a/b/', auth=_auth)
        rsrc = auth.SessionConfigResource(master)
        rsrc.reconfigResource(master.config)

        res = yield self.render_resource(rsrc, '/')
        warning = 'missing http header REMOTE_USER. Check your reverse proxy config!'
        exp = ('this.config = {"url": "h:/a/b/", "on_load_warning": "%(warning)s"'
               ', "user": {"anonymous": true},'
               ' "auth": {"name": "RemoteUserAuth"}, "port": null}')
        self.assertEqual(res, exp % dict(warning=warning))

        res = yield self.render_resource(rsrc, '/', extraHeaders=dict(REMOTE_USER="NOGOOD"))
        warning = ('http header does not match regex! \\"NOGOOD\\" not matching'
                   ' (?P<username>[^ @]+)@(?P<realm>[^ @]+)')
        self.assertEqual(res, exp % dict(warning=warning))

        res = yield self.render_resource(rsrc, '/', extraHeaders=dict(REMOTE_USER="GOOD@ORG"))
        exp = ('this.config = {"url": "h:/a/b/", "user": {"username": "GOOD", "realm": "ORG", '
               '"email": "GOOD"}, "auth": {"name": "RemoteUserAuth"}, "port": null}')
        self.assertEqual(res, exp)

        rsrc = auth.LoginResource(master)
        rsrc.reconfigResource(master.config)
        res = yield self.render_resource(rsrc, '/')
        self.assertEqual(res, 'Please check with your administrator,'
                              ' there is an issue with the reverse proxy')


class TwistedICredAuthBase(www.WwwTestMixin, unittest.TestCase):

    def setUp(self):
        self.auth = _auth = auth.BasicAuth({"foo": "bar"})
        self.master = master = self.make_master(url='h:/a/b/', auth=_auth)
        self.rsrc = _auth.getLoginResource(master)
        self.auth.reconfigAuth(master, master.config)

    @defer.inlineCallbacks
    def test_no_user(self):
        res = yield self.render_resource(self.rsrc, '/')
        self.assertTrue(isinstance(res, UnauthorizedResource))

    @defer.inlineCallbacks
    def test_bad_user(self):
        auth = "Basic " + base64.b64encode("bad:guy")
        res = yield self.render_resource(self.rsrc, '/', extraHeaders=dict(authorization=auth))
        self.assertTrue(isinstance(res, UnauthorizedResource))

    @defer.inlineCallbacks
    def test_good_user(self):
        # to keep WwwTestMixin simple, we cannot really test more than that
        # ICred is a bit complex, and would require a lot of fakeing
        auth = "Basic " + base64.b64encode("foo:bar")
        res = yield self.render_resource(self.rsrc, '/', extraHeaders=dict(authorization=auth))
        self.assertFalse(isinstance(res, UnauthorizedResource))


class AuthRealm(www.WwwTestMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def test_AuthRealm(self):
        _auth = auth.BasicAuth({"foo": "bar"})
        master = self.make_master(url='h:/a/b/', auth=_auth)
        realm = auth.AuthRealm(master, _auth)
        _, rsrc, _ = realm.requestAvatar("me", None, IResource)
        res = yield self.render_resource(rsrc, '/')
        self.assertEqual(res, "")
        self.assertEqual(master.session.user_info, {'email': 'me', 'username': 'me'})
