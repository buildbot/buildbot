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

import mock

from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse
from twisted.cred.credentials import UsernamePassword
from twisted.cred.error import UnauthorizedLogin
from twisted.internet import defer
from twisted.trial import unittest
from twisted.web.error import Error
from twisted.web.guard import BasicCredentialFactory
from twisted.web.guard import HTTPAuthSessionWrapper
from twisted.web.resource import IResource

from buildbot.test.util import www
from buildbot.test.util.misc import TestReactorMixin
from buildbot.www import auth


class AuthResourceMixin:

    def setUpAuthResource(self):
        self.master = self.make_master(url='h:/a/b/')
        self.auth = self.master.config.www['auth']
        self.master.www.auth = self.auth
        self.auth.master = self.master


class AuthRootResource(TestReactorMixin, www.WwwTestMixin, AuthResourceMixin,
                       unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        self.setUpAuthResource()
        self.rsrc = auth.AuthRootResource(self.master)

    def test_getChild_login(self):
        glr = mock.Mock(name='glr')
        self.master.www.auth.getLoginResource = glr
        child = self.rsrc.getChild(b'login', mock.Mock(name='req'))
        self.assertIdentical(child, glr())

    def test_getChild_logout(self):
        glr = mock.Mock(name='glr')
        self.master.www.auth.getLogoutResource = glr
        child = self.rsrc.getChild(b'logout', mock.Mock(name='req'))
        self.assertIdentical(child, glr())


class AuthBase(TestReactorMixin, www.WwwTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        self.auth = auth.AuthBase()
        self.master = self.make_master(url='h:/a/b/')
        self.auth.master = self.master
        self.req = self.make_request(b'/')

    @defer.inlineCallbacks
    def test_maybeAutoLogin(self):
        self.assertEqual((yield self.auth.maybeAutoLogin(self.req)), None)

    def test_getLoginResource(self):
        with self.assertRaises(Error):
            self.auth.getLoginResource()

    @defer.inlineCallbacks
    def test_updateUserInfo(self):
        self.auth.userInfoProvider = auth.UserInfoProviderBase()
        self.auth.userInfoProvider.getUserInfo = lambda un: {'info': un}
        self.req.session.user_info = {'username': 'elvira'}
        yield self.auth.updateUserInfo(self.req)
        self.assertEqual(self.req.session.user_info,
                         {'info': 'elvira', 'username': 'elvira'})

    def getConfigDict(self):
        self.assertEqual(auth.getConfigDict(),
                         {'name': 'AuthBase'})


class UseAuthInfoProviderBase(unittest.TestCase):

    @defer.inlineCallbacks
    def test_getUserInfo(self):
        uip = auth.UserInfoProviderBase()
        self.assertEqual((yield uip.getUserInfo('jess')),
                         {'email': 'jess'})


class NoAuth(unittest.TestCase):

    def test_exists(self):
        assert auth.NoAuth


class RemoteUserAuth(TestReactorMixin, www.WwwTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        self.auth = auth.RemoteUserAuth(header=b'HDR')
        self.make_master()
        self.request = self.make_request(b'/')

    @defer.inlineCallbacks
    def test_maybeAutoLogin(self):
        self.request.input_headers[b'HDR'] = b'rachel@foo.com'
        yield self.auth.maybeAutoLogin(self.request)
        self.assertEqual(self.request.session.user_info, {
                         'username': 'rachel',
                         'realm': 'foo.com',
                         'email': 'rachel'})

    @defer.inlineCallbacks
    def test_maybeAutoLogin_no_header(self):
        try:
            yield self.auth.maybeAutoLogin(self.request)
        except Error as e:
            self.assertEqual(int(e.status), 403)
        else:
            self.fail("403 expected")

    @defer.inlineCallbacks
    def test_maybeAutoLogin_mismatched_value(self):
        self.request.input_headers[b'HDR'] = b'rachel'
        try:
            yield self.auth.maybeAutoLogin(self.request)
        except Error as e:
            self.assertEqual(int(e.status), 403)
        else:
            self.fail("403 expected")


class AuthRealm(TestReactorMixin, www.WwwTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        self.auth = auth.RemoteUserAuth(header=b'HDR')
        self.auth = auth.NoAuth()
        self.make_master()

    def test_requestAvatar(self):
        realm = auth.AuthRealm(self.master, self.auth)
        itfc, rsrc, logout = realm.requestAvatar("me", None, IResource)
        self.assertIdentical(itfc, IResource)
        self.assertIsInstance(rsrc, auth.PreAuthenticatedLoginResource)


class TwistedICredAuthBase(TestReactorMixin, www.WwwTestMixin,
                           unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()

    # twisted.web makes it difficult to simulate the authentication process, so
    # this only tests the mechanics of the getLoginResource method.

    def test_getLoginResource(self):
        self.auth = auth.TwistedICredAuthBase(
            credentialFactories=[BasicCredentialFactory("buildbot")],
            checkers=[InMemoryUsernamePasswordDatabaseDontUse(good=b'guy')])
        self.auth.master = self.make_master(url='h:/a/b/')
        rsrc = self.auth.getLoginResource()
        self.assertIsInstance(rsrc, HTTPAuthSessionWrapper)


class UserPasswordAuth(www.WwwTestMixin, unittest.TestCase):

    def test_passwordStringToBytes(self):
        login = {"user_string": "password",
                 "user_bytes": b"password"}
        correct_login = {b"user_string": b"password",
                         b"user_bytes": b"password"}
        self.auth = auth.UserPasswordAuth(login)
        self.assertEqual(self.auth.checkers[0].users, correct_login)

        login = [("user_string", "password"),
                 ("user_bytes", b"password")]
        correct_login = {b"user_string": b"password",
                         b"user_bytes": b"password"}
        self.auth = auth.UserPasswordAuth(login)
        self.assertEqual(self.auth.checkers[0].users, correct_login)


class CustomAuth(TestReactorMixin, www.WwwTestMixin, unittest.TestCase):

    class MockCustomAuth(auth.CustomAuth):
        def check_credentials(self, us, ps):
            return us == 'fellow' and ps == 'correct'

    def setUp(self):
        self.setUpTestReactor()

    @defer.inlineCallbacks
    def test_callable(self):
        self.auth = self.MockCustomAuth()
        cred_good = UsernamePassword('fellow', 'correct')
        result_good = yield self.auth.checkers[0].requestAvatarId(cred_good)
        self.assertEqual(result_good, 'fellow')
        cred_bad = UsernamePassword('bandid', 'incorrect')
        defer_bad = self.auth.checkers[0].requestAvatarId(cred_bad)
        yield self.assertFailure(defer_bad, UnauthorizedLogin)


class LoginResource(TestReactorMixin, www.WwwTestMixin, AuthResourceMixin,
                    unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        self.setUpAuthResource()

    @defer.inlineCallbacks
    def test_render(self):
        self.rsrc = auth.LoginResource(self.master)
        self.rsrc.renderLogin = mock.Mock(
            spec=self.rsrc.renderLogin, return_value=defer.succeed(b'hi'))

        yield self.render_resource(self.rsrc, b'/auth/login')
        self.rsrc.renderLogin.assert_called_with(mock.ANY)


class PreAuthenticatedLoginResource(TestReactorMixin, www.WwwTestMixin,
                                    AuthResourceMixin, unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        self.setUpAuthResource()
        self.rsrc = auth.PreAuthenticatedLoginResource(self.master, 'him')

    @defer.inlineCallbacks
    def test_render(self):
        self.auth.maybeAutoLogin = mock.Mock()

        def updateUserInfo(request):
            session = request.getSession()
            session.user_info['email'] = session.user_info['username'] + "@org"
            session.updateSession(request)

        self.auth.updateUserInfo = mock.Mock(side_effect=updateUserInfo)

        res = yield self.render_resource(self.rsrc, b'/auth/login')
        self.assertEqual(res, {'redirected': b'h:/a/b/#/'})
        self.assertFalse(self.auth.maybeAutoLogin.called)
        self.auth.updateUserInfo.assert_called_with(mock.ANY)
        self.assertEqual(self.master.session.user_info,
                         {'email': 'him@org', 'username': 'him'})


class LogoutResource(TestReactorMixin, www.WwwTestMixin, AuthResourceMixin,
                     unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        self.setUpAuthResource()
        self.rsrc = auth.LogoutResource(self.master)

    @defer.inlineCallbacks
    def test_render(self):
        self.master.session.expire = mock.Mock()
        res = yield self.render_resource(self.rsrc, b'/auth/logout')
        self.assertEqual(res, {'redirected': b'h:/a/b/#/'})
        self.master.session.expire.assert_called_with()

    @defer.inlineCallbacks
    def test_render_with_crlf(self):
        self.master.session.expire = mock.Mock()
        res = yield self.render_resource(self.rsrc, b'/auth/logout?redirect=%0d%0abla')
        # everything after a %0d shall be stripped
        self.assertEqual(res, {'redirected': b'h:/a/b/#'})
        self.master.session.expire.assert_called_with()
