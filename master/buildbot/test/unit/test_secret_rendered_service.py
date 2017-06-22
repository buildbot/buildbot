from __future__ import absolute_import
from __future__ import print_function

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.secrets.manager import SecretManager
from buildbot.test.fake import fakemaster
from buildbot.test.fake.fakebuild import FakeBuild
from buildbot.test.fake.secrets import FakeSecretStorage
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.util.service import BuildbotService


class FakeBuildWithMaster(FakeBuild):

    def __init__(self, master):
        super(FakeBuildWithMaster, self).__init__()
        self.master = master


class FakeServiceUsingSecrets(BuildbotService):

    name = "FakeServiceUsingSecrets"
    render_secrets = ["secret_to_render"]

    @defer.inlineCallbacks
    def reconfigService(self, secret):
        self.secret_to_render = secret
        yield self.configureService()

    def returnRenderedSecrets(self, secretKey):
        try:
            return getattr(self, secretKey)
        except Exception:
            raise Exception


class TestRenderSecrets(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master()
        fakeStorageService = FakeSecretStorage()
        fakeStorageService.reconfigService(secretdict={"foo": "bar",
                                                       "other": "value"})
        self.secretsrv = SecretManager()
        self.secretsrv.services = [fakeStorageService]
        self.secretsrv.setServiceParent(self.master)
        self.srvtest = FakeServiceUsingSecrets(["foo", "other"])
        self.srvtest.setServiceParent(self.master)

    @defer.inlineCallbacks
    def test_secret_rendered(self):
        yield self.srvtest.reconfigService(["foo", "other"])
        self.assertEqual("bar", self.srvtest.returnRenderedSecrets("foo"))

    @defer.inlineCallbacks
    def test_secret_rendered_not_found(self):
        yield self.assertFailure(self.srvtest.reconfigService(["more"]), KeyError)

    @defer.inlineCallbacks
    def test_secret_render_no_secretkey(self):
        yield self.srvtest.reconfigService(["foo", "other"])
        self.assertRaises(Exception, self.srvtest.returnRenderedSecrets, "more")
