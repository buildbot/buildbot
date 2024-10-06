import gc

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process.properties import Interpolate
from buildbot.secrets.manager import SecretManager
from buildbot.test.fake import fakemaster
from buildbot.test.fake.fakebuild import FakeBuild
from buildbot.test.fake.secrets import FakeSecretStorage
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util.config import ConfigErrorsMixin


class FakeBuildWithMaster(FakeBuild):
    def __init__(self, master):
        super().__init__()
        self.master = master


class TestInterpolateSecrets(TestReactorMixin, unittest.TestCase, ConfigErrorsMixin):
    async def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self)
        fakeStorageService = FakeSecretStorage()
        fakeStorageService.reconfigService(secretdict={"foo": "bar", "other": "value"})
        self.secretsrv = SecretManager()
        self.secretsrv.services = [fakeStorageService]
        await self.secretsrv.setServiceParent(self.master)
        self.build = FakeBuildWithMaster(self.master)

    async def test_secret(self):
        command = Interpolate("echo %(secret:foo)s")
        rendered = await self.build.render(command)
        self.assertEqual(rendered, "echo bar")

    async def test_secret_not_found(self):
        command = Interpolate("echo %(secret:fuo)s")
        await self.assertFailure(self.build.render(command), defer.FirstError)
        gc.collect()
        self.flushLoggedErrors(defer.FirstError)
        self.flushLoggedErrors(KeyError)


class TestInterpolateSecretsNoService(TestReactorMixin, unittest.TestCase, ConfigErrorsMixin):
    def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self)
        self.build = FakeBuildWithMaster(self.master)

    async def test_secret(self):
        command = Interpolate("echo %(secret:fuo)s")
        await self.assertFailure(self.build.render(command), defer.FirstError)
        gc.collect()
        self.flushLoggedErrors(defer.FirstError)
        self.flushLoggedErrors(KeyError)


class TestInterpolateSecretsHiddenSecrets(TestReactorMixin, unittest.TestCase):
    async def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self)
        fakeStorageService = FakeSecretStorage()
        password = "bar"
        fakeStorageService.reconfigService(
            secretdict={"foo": password, "other": password + "random", "empty": ""}
        )
        self.secretsrv = SecretManager()
        self.secretsrv.services = [fakeStorageService]
        await self.secretsrv.setServiceParent(self.master)
        self.build = FakeBuildWithMaster(self.master)

    async def test_secret(self):
        command = Interpolate("echo %(secret:foo)s")
        rendered = await self.build.render(command)
        cleantext = self.build.properties.cleanupTextFromSecrets(rendered)
        self.assertEqual(cleantext, "echo <foo>")

    async def test_secret_replace(self):
        command = Interpolate("echo %(secret:foo)s %(secret:other)s")
        rendered = await self.build.render(command)
        cleantext = self.build.properties.cleanupTextFromSecrets(rendered)
        self.assertEqual(cleantext, "echo <foo> <other>")

    async def test_secret_replace_with_empty_secret(self):
        command = Interpolate("echo %(secret:empty)s %(secret:other)s")
        rendered = await self.build.render(command)
        cleantext = self.build.properties.cleanupTextFromSecrets(rendered)
        self.assertEqual(cleantext, "echo  <other>")
