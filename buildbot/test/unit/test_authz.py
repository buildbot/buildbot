from zope.interface import implements
from twisted.trial import unittest

from buildbot.status.web.authz import Authz
from buildbot.status.web.auth import IAuth

class MockRequest(object):
    # all we need from a request is username/password
    def __init__(self, username, passwd):
        self.args = {
            'username' : [ username ],
            'passwd' : [ passwd ],
        }

class MockAuth(object):
    implements(IAuth)
    def __init__(self, user):
        self.user = user

    def authenticate(self, user, pw):
        return user == self.user

class TestAuthz(unittest.TestCase):

    def testDefaults(self):
        "by default, nothing is allowed"
        z = Authz()
        for a in Authz.knownActions:
            assert not z.actionAllowed(a,
                            MockRequest('foo', 'bar'))

    def testPositive(self):
        "'True' should always permit access"
        z = Authz(forceBuild=True)
        assert z.actionAllowed('forceBuild',
                            MockRequest('foo', 'bar'))

    def testAuthPositive(self):
        z = Authz(auth=MockAuth('foo'),
                  stopBuild='auth')
        assert z.actionAllowed('stopBuild',
                            MockRequest('foo', 'bar'))

    def testAuthNegative(self):
        z = Authz(auth=MockAuth('foo'),
                  stopBuild='auth')
        assert not z.actionAllowed('stopBuild',
                            MockRequest('not-foo', 'bar'))

    def testAuthFunction(self):
        for expected in True, False:
            myargs = []
            def myAuthzFn(*args):
                myargs.extend(args)
                return expected
            z = Authz(auth=MockAuth('uu'),
                      stopBuild=myAuthzFn)
            self.assertEqual(z.actionAllowed('stopBuild',
                                MockRequest('uu', 'shh'), 'a', 'b'),
                             expected)
            self.assertEqual(myargs, ['uu', 'a', 'b'])

    def testAdvertise(self):
        z = Authz(
                forceBuild = False,
                forceAllBuilds = True,
                stopBuild = 'auth',
                stopAllBuilds = lambda u : False)
        assert not z.advertiseAction('forceBuild')
        assert z.advertiseAction('forceAllBuilds')
        assert z.advertiseAction('stopBuild')
        assert z.advertiseAction('stopAllBuilds')

    def testNeedAuthForm(self):
        z = Authz(
                forceBuild = False,
                forceAllBuilds = True,
                stopBuild = 'auth',
                stopAllBuilds = lambda u : False)
        assert not z.needAuthForm('forceBuild')
        assert not z.needAuthForm('forceAllBuilds')
        assert z.needAuthForm('stopBuild')
        assert z.needAuthForm('stopAllBuilds')

    def testConstructorExceptions(self):
        self.assertRaises(ValueError, Authz, someRandomAction=3)

    def testMethodExceptions(self):
        z = Authz()
        self.assertRaises(KeyError, z.advertiseAction, 'joe')
        self.assertRaises(KeyError, z.needAuthForm, 'joe')
        self.assertRaises(KeyError, z.actionAllowed, 'joe', MockRequest('snow', 'foo'))
