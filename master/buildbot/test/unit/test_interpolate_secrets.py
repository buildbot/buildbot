from __future__ import absolute_import
from __future__ import print_function

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process.properties import Interpolate
from buildbot.secrets.manager import SecretManager
from buildbot.test.fake import fakemaster
from buildbot.test.fake.fakebuild import FakeBuild
from buildbot.test.fake.secrets import FakeSecretStorage
from buildbot.test.util.config import ConfigErrorsMixin


class FakeBuildWithMaster(FakeBuild):

    def __init__(self, master):
        super(FakeBuildWithMaster, self).__init__()
        self.master = master


class TestInterpolateSecrets(unittest.TestCase, ConfigErrorsMixin):

    def setUp(self):
        self.master = fakemaster.make_master()
        fakeStorageService = FakeSecretStorage()
        fakeStorageService.reconfigService(secretdict={"foo": "bar",
                                                       "other": "value"})
        self.secretsrv = SecretManager()
        self.secretsrv.services = [fakeStorageService]
        self.secretsrv.setServiceParent(self.master)
        self.build = FakeBuildWithMaster(self.master)

    @defer.inlineCallbacks
    def test_secret(self):
        command = Interpolate("echo %(secret:foo)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo bar")

    def test_secret_not_found(self):
        command = Interpolate("echo %(secret:fuo)s")
        self.assertFailure(self.build.render(command), defer.FirstError)
        self.flushLoggedErrors(defer.FirstError)
        self.flushLoggedErrors(KeyError)


class TestInterpolateSecretsNoService(unittest.TestCase, ConfigErrorsMixin):

    def setUp(self):
        self.master = fakemaster.make_master()
        self.build = FakeBuildWithMaster(self.master)

    def test_secret(self):
        command = Interpolate("echo %(secret:fuo)s")
        self.assertFailure(self.build.render(command), defer.FirstError)
        self.flushLoggedErrors(defer.FirstError)
        self.flushLoggedErrors(KeyError)


class TestInterpolateSecretsHiddenSecrets(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master()
        fakeStorageService = FakeSecretStorage()
        fakeStorageService.reconfigService(secretdict={"foo": "bar",
                                                       "other": "value"})
        self.secretsrv = SecretManager()
        self.secretsrv.services = [fakeStorageService]
        self.secretsrv.setServiceParent(self.master)
        self.build = FakeBuildWithMaster(self.master)

    @defer.inlineCallbacks
    def test_secret(self):
        command = Interpolate("echo %(secret:foo)s")
        rendered = yield self.build.render(command)
        cleantext = self.build.build_status.properties.cleanupTextFromSecrets(rendered)
        self.assertEqual(cleantext, "echo <foo>")
