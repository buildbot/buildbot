from zope.interface import implements
from twisted.trial import unittest

from buildbot.status.web.authz import Authz
from buildbot.status.web.auth import IAuth

class StubRequest(object):
    # all we need from a request is username/password
    def __init__(self, username, passwd):
        self.args = {
            'username' : [ username ],
            'passwd' : [ passwd ],
        }

class StubAuth(object):
    implements(IAuth)
    def __init__(self, user):
        self.user = user

    def authenticate(self, user, pw):
        return user == self.user

class TestAuthz(unittest.TestCase):

    def test_actionAllowed_Defaults(self):
        "by default, nothing is allowed"
        z = Authz()
        failedActions = []
        for a in Authz.knownActions:
            if z.actionAllowed(a, StubRequest('foo', 'bar')):
                failedActions.append(a)
        if failedActions:
            raise unittest.FailTest("action(s) %s do not default to False"
                        % (failedActions,))

    def test_actionAllowed_Positive(self):
        "'True' should always permit access"
        z = Authz(forceBuild=True)
        assert z.actionAllowed('forceBuild',
                            StubRequest('foo', 'bar'))

    def test_actionAllowed_AuthPositive(self):
        z = Authz(auth=StubAuth('jrobinson'),
                  stopBuild='auth')
        assert z.actionAllowed('stopBuild',
                            StubRequest('jrobinson', 'bar'))

    def test_actionAllowed_AuthNegative(self):
        z = Authz(auth=StubAuth('jrobinson'),
                  stopBuild='auth')
        assert not z.actionAllowed('stopBuild',
                            StubRequest('apeterson', 'bar'))

    def test_actionAllowed_AuthCallable(self):
        myargs = []
        def myAuthzFn(*args):
            myargs.extend(args)
        z = Authz(auth=StubAuth('uu'),
                  stopBuild=myAuthzFn)
        z.actionAllowed('stopBuild', StubRequest('uu', 'shh'), 'arg', 'arg2')
        self.assertEqual(myargs, ['uu', 'arg', 'arg2'])

    def test_actionAllowed_AuthCallableTrue(self):
        def myAuthzFn(*args):
            return True
        z = Authz(auth=StubAuth('uu'),
                  stopBuild=myAuthzFn)
        self.assertTrue(z.actionAllowed('stopBuild',
                            StubRequest('uu', 'shh')))

    def test_actionAllowed_AuthCallableFalse(self):
        def myAuthzFn(*args):
            return False
        z = Authz(auth=StubAuth('uu'),
                  stopBuild=myAuthzFn)
        self.assertFalse(z.actionAllowed('stopBuild',
                            StubRequest('uu', 'shh')))

    def test_advertiseAction_False(self):
        z = Authz(forceBuild = False)
        assert not z.advertiseAction('forceBuild')

    def test_advertiseAction_True(self):
        z = Authz(forceAllBuilds = True)
        assert z.advertiseAction('forceAllBuilds')

    def test_advertiseAction_auth(self):
        z = Authz(stopBuild = 'auth')
        assert z.advertiseAction('stopBuild')

    def test_advertiseAction_callable(self):
        z = Authz(stopAllBuilds = lambda u : False)
        assert z.advertiseAction('stopAllBuilds')

    def test_needAuthForm_False(self):
        z = Authz(forceBuild = False)
        assert not z.needAuthForm('forceBuild')

    def test_needAuthForm_True(self):
        z = Authz(forceAllBuilds = True)
        assert not z.needAuthForm('forceAllBuilds')

    def test_needAuthForm_auth(self):
        z = Authz(stopBuild = 'auth')
        assert z.needAuthForm('stopBuild')

    def test_needAuthForm_callable(self):
        z = Authz(stopAllBuilds = lambda u : False)
        assert z.needAuthForm('stopAllBuilds')

    def test_constructor_invalidAction(self):
        self.assertRaises(ValueError, Authz, someRandomAction=3)

    def test_advertiseAction_invalidAction(self):
        z = Authz()
        self.assertRaises(KeyError, z.advertiseAction, 'someRandomAction')

    def test_needAuthForm_invalidAction(self):
        z = Authz()
        self.assertRaises(KeyError, z.needAuthForm, 'someRandomAction')

    def test_actionAllowed_invalidAction(self):
        z = Authz()
        self.assertRaises(KeyError, z.actionAllowed, 'someRandomAction', StubRequest('snow', 'foo'))
