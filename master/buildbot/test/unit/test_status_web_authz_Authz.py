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

from zope.interface import implements
from twisted.trial import unittest
from twisted.internet import defer

from buildbot.status.web.authz import Authz
from buildbot.status.web.auth import IAuth, AuthBase

class StubRequest(object):
    # all we need from a request is username/password
    def __init__(self, username=None, passwd=None):
        self.args = {
            'username' : [ username ],
            'passwd' : [ passwd ],
        }
        self.received_cookies = {}
        self.send_cookies = []
    def getUser(self):
        return ''

    def getPassword(self):
        return None
    def addCookie(self, key, cookie, expires, path):
        self.send_cookies.append((key, cookie, expires, path))

class StubHttpAuthRequest(object):
    # all we need from a request is username/password
    def __init__(self, username, passwd):
        self.args = {}
        self.username = username
        self.passwd = passwd

    def getUser(self):
        return self.username

    def getPassword(self):
        return self.passwd

class StubAuth(AuthBase):
    implements(IAuth)
    def __init__(self, user):
        self.user = user

    def authenticate(self, user, pw):
        return user == self.user
class TestAuthz(unittest.TestCase):

    def test_actionAllowed_Defaults(self):
        "by default, nothing is allowed"
        z = Authz()
        self.failedActions = []
        self.dl = []
        for a in Authz.knownActions:
            md = z.actionAllowed(a, StubRequest('foo', 'bar'))
            def check(res):
                if res:
                    self.failedActions.append(a)
                return
            md.addCallback(check)
            self.dl.append(md)
        d = defer.DeferredList(self.dl)
        def check_failed(_):
            if self.failedActions:
                raise unittest.FailTest("action(s) %s do not default to False"
                                        % (self.failedActions,))
        d.addCallback(check_failed)
        return d

    def test_actionAllowed_Positive(self):
        "'True' should always permit access"
        z = Authz(forceBuild=True)
        d = z.actionAllowed('forceBuild', StubRequest('foo', 'bar'))
        def check(res):
            self.assertEqual(res, True)
        d.addCallback(check)
        return d

    def test_actionAllowed_AuthPositive(self):
        z = Authz(auth=StubAuth('jrobinson'),
                  stopBuild='auth')
        d = z.actionAllowed('stopBuild', StubRequest('jrobinson', 'bar'))
        def check(res):
            self.assertEqual(res, True)
        d.addCallback(check)
        return d

    def test_actionAllowed_AuthNegative(self):
        z = Authz(auth=StubAuth('jrobinson'),
                  stopBuild='auth')
        d = z.actionAllowed('stopBuild', StubRequest('apeterson', 'bar'))
        def check(res):
            self.assertEqual(res, False)
        d.addCallback(check)
        return d

    def test_actionAllowed_AuthCallable(self):
        myargs = []
        def myAuthzFn(*args):
            myargs.extend(args)
        z = Authz(auth=StubAuth('uu'),
                  stopBuild=myAuthzFn)
        d = z.actionAllowed('stopBuild', StubRequest('uu', 'shh'), 'arg', 'arg2')
        def check(res):
            self.assertEqual(myargs, ['uu', 'arg', 'arg2'])
        d.addCallback(check)
        return d

    def test_actionAllowed_AuthCallableTrue(self):
        def myAuthzFn(*args):
            return True
        z = Authz(auth=StubAuth('uu'),
                  stopBuild=myAuthzFn)
        d = z.actionAllowed('stopBuild', StubRequest('uu', 'shh'))
        def check(res):
            self.assertEqual(res, True)
        d.addCallback(check)
        return d

    def test_actionAllowed_AuthCallableFalse(self):
        def myAuthzFn(*args):
            return False
        z = Authz(auth=StubAuth('uu'),
                  stopBuild=myAuthzFn)
        d = z.actionAllowed('stopBuild', StubRequest('uu', 'shh'))
        def check(res):
            self.assertEqual(res, False)
        d.addCallback(check)
        return d

    def test_advertiseAction_False(self):
        z = Authz(forceBuild = False)
        assert not z.advertiseAction('forceBuild',StubRequest())

    def test_advertiseAction_True(self):
        z = Authz(forceAllBuilds = True)
        assert z.advertiseAction('forceAllBuilds',StubRequest())

    def test_advertiseAction_auth(self):
        z = Authz(stopBuild = 'auth')
        assert not z.advertiseAction('stopBuild',StubRequest())

    def test_advertiseAction_auth_authenticated(self):
        z = Authz(auth=StubAuth('uu'),stopBuild = 'auth')
        r = StubRequest('uu','aa')
        d = z.login(r)
        def check(c):
            assert z.advertiseAction('stopBuild',r)
        d.addCallback(check)

    def test_advertiseAction_callable(self):
        z = Authz(auth=StubAuth('uu'), stopAllBuilds = lambda u : False)
        r = StubRequest('uu','aa')
        d = z.login(r)
        @d.addCallback
        def check(c):
            assert z.advertiseAction('stopAllBuilds',r)
        return d

    def test_authenticated_False(self):
        z = Authz(forceBuild = False)
        assert not z.authenticated(StubRequest())

    def test_authenticated_True(self):
        z = Authz(auth=StubAuth('uu'), forceBuild = True)
        r = StubRequest('uu','aa')
        d = z.login(r)
        @d.addCallback
        def check(c):
            assert z.authenticated(r)
        return d

    def test_authenticated_http_False(self):
        z = Authz(useHttpHeader = True)
        assert not z.authenticated(StubRequest())

    def test_authenticated_http_True(self):
        z = Authz(useHttpHeader = True)
        assert z.authenticated(StubHttpAuthRequest('foo', 'bar'))

    def test_constructor_invalidAction(self):
        self.assertRaises(ValueError, Authz, someRandomAction=3)

    def test_getUsername_http(self):
        z = Authz(useHttpHeader = True)
        assert z.getUsername(StubHttpAuthRequest('foo', 'bar')) == 'foo'

    def test_getPassword_http(self):
        z = Authz(useHttpHeader = True)
        assert z.getPassword(StubHttpAuthRequest('foo', 'bar')) == 'bar'

    def test_getUsername_http_missing(self):
        z = Authz(useHttpHeader = True)
        assert z.getUsername(StubRequest('foo', 'bar')) == ''

    def test_getPassword_http_missing(self):
        z = Authz(useHttpHeader = True)
        assert z.getPassword(StubRequest('foo', 'bar')) == None

    def test_getUsername_request(self):
        z = Authz()
        assert z.getUsername(StubRequest('foo', 'bar')) == 'foo'

    def test_getPassword_request(self):
        z = Authz()
        assert z.getPassword(StubRequest('foo', 'bar')) == 'bar'

    def test_advertiseAction_invalidAction(self):
        z = Authz()
        self.assertRaises(KeyError, z.advertiseAction, 'someRandomAction', StubRequest('snow', 'foo'))

    def test_actionAllowed_invalidAction(self):
        z = Authz()
        self.assertRaises(KeyError, z.actionAllowed, 'someRandomAction', StubRequest('snow', 'foo'))
