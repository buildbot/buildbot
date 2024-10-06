from twisted.trial import unittest

from buildbot.secrets.manager import SecretManager
from buildbot.secrets.secret import SecretDetails
from buildbot.test.fake import fakemaster
from buildbot.test.fake.secrets import FakeSecretStorage
from buildbot.test.reactor import TestReactorMixin


class TestSecretsManager(TestReactorMixin, unittest.TestCase):
    def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self)
        self.master.config.secretsProviders = [
            FakeSecretStorage(secretdict={"foo": "bar", "other": "value"})
        ]

    async def testGetManagerService(self):
        secret_service_manager = SecretManager()
        fakeStorageService = FakeSecretStorage()
        fakeStorageService.reconfigService(secretdict={"foo": "bar", "other": "value"})
        secret_service_manager.services = [fakeStorageService]
        expectedClassName = FakeSecretStorage.__name__
        expectedSecretDetail = SecretDetails(expectedClassName, "foo", "bar")
        secret_result = await secret_service_manager.get("foo")
        strExpectedSecretDetail = str(secret_result)
        self.assertEqual(secret_result, expectedSecretDetail)
        self.assertEqual(secret_result.key, "foo")
        self.assertEqual(secret_result.value, "bar")
        self.assertEqual(secret_result.source, expectedClassName)
        self.assertEqual(strExpectedSecretDetail, "FakeSecretStorage foo: 'bar'")

    async def testGetNoDataManagerService(self):
        secret_service_manager = SecretManager()
        fakeStorageService = FakeSecretStorage()
        fakeStorageService.reconfigService(secretdict={"foo": "bar", "other": "value"})
        secret_service_manager.services = [fakeStorageService]
        secret_result = await secret_service_manager.get("foo2")
        self.assertEqual(secret_result, None)

    async def testGetDataMultipleManagerService(self):
        secret_service_manager = SecretManager()
        fakeStorageService = FakeSecretStorage()
        fakeStorageService.reconfigService(secretdict={"foo": "bar", "other": "value"})
        otherFakeStorageService = FakeSecretStorage()
        otherFakeStorageService.reconfigService(secretdict={"foo2": "bar", "other2": "value"})

        secret_service_manager.services = [fakeStorageService, otherFakeStorageService]
        expectedSecretDetail = SecretDetails(FakeSecretStorage.__name__, "foo2", "bar")
        secret_result = await secret_service_manager.get("foo2")
        self.assertEqual(secret_result, expectedSecretDetail)

    async def testGetDataMultipleManagerValues(self):
        secret_service_manager = SecretManager()
        fakeStorageService = FakeSecretStorage()
        fakeStorageService.reconfigService(secretdict={"foo": "bar", "other": ""})
        otherFakeStorageService = FakeSecretStorage()
        otherFakeStorageService.reconfigService(secretdict={"foo2": "bar2", "other": ""})

        secret_service_manager.services = [fakeStorageService, otherFakeStorageService]
        expectedSecretDetail = SecretDetails(FakeSecretStorage.__name__, "other", "")
        secret_result = await secret_service_manager.get("other")
        self.assertEqual(secret_result, expectedSecretDetail)

    async def testGetDataMultipleManagerServiceNoDatas(self):
        secret_service_manager = SecretManager()
        fakeStorageService = FakeSecretStorage()
        fakeStorageService.reconfigService(secretdict={"foo": "bar", "other": "value"})
        otherFakeStorageService = FakeSecretStorage()
        otherFakeStorageService.reconfigService(secretdict={"foo2": "bar", "other2": "value"})
        secret_service_manager.services = [fakeStorageService, otherFakeStorageService]
        secret_result = await secret_service_manager.get("foo3")
        self.assertEqual(secret_result, None)
