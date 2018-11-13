from __future__ import absolute_import
from __future__ import print_function

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process.properties import Secret
from buildbot.secrets.manager import SecretManager
from buildbot.test.fake import fakemaster
from buildbot.test.fake.secrets import FakeSecretStorage
from buildbot.util.service import BuildbotService


class FakeServiceUsingSecrets(BuildbotService):

    name = "FakeServiceUsingSecrets"
    secrets = ["foo", "bar", "secret"]

    def reconfigService(self, foo=None, bar=None, secret=None, other=None):
        self.foo = foo
        self.bar = bar
        self.secret = secret

    def returnRenderedSecrets(self, secretKey):
        try:
            return getattr(self, secretKey)
        except Exception:
            raise Exception


class TestRenderSecrets(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master()
        fakeStorageService = FakeSecretStorage(secretdict={"foo": "bar",
                                                       "other": "value"})
        self.secretsrv = SecretManager()
        self.secretsrv.services = [fakeStorageService]
        self.secretsrv.setServiceParent(self.master)
        self.srvtest = FakeServiceUsingSecrets()
        self.srvtest.setServiceParent(self.master)
        self.successResultOf(self.master.startService())

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.master.stopService()

    @defer.inlineCallbacks
    def test_secret_rendered(self):
        yield self.srvtest.configureService()
        new = FakeServiceUsingSecrets(foo=Secret("foo"), other=Secret("other"))
        yield self.srvtest.reconfigServiceWithSibling(new)
        self.assertEqual("bar", self.srvtest.returnRenderedSecrets("foo"))

    @defer.inlineCallbacks
    def test_secret_rendered_not_found(self):
        new = FakeServiceUsingSecrets(foo=Secret("foo"))
        yield self.srvtest.reconfigServiceWithSibling(new)
        with self.assertRaises(Exception):
            self.srvtest.returnRenderedSecrets("more")
