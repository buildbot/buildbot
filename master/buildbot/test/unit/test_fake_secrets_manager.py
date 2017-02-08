from __future__ import absolute_import
from __future__ import print_function

from twisted.trial import unittest

from buildbot.plugins import util
from buildbot.secrets.manager import SecretManager
from buildbot.secrets.secret import SecretDetails
from buildbot.test.fake import fakemaster
from buildbot.secrets.provider.base import SecretProviderBase


class FakeSecretStorage(SecretProviderBase):

    def __init__(self, allsecretsInADict):
        self.allsecrets = allsecretsInADict

    def get(self, key):
        if key in self.allsecrets:
            return self.allsecrets[key], None
        else:
            return None, None


class OtherFakeSecretStorage(FakeSecretStorage):

    def __init__(self, allsecretsInADict, props=None):
        self.properties = props
        super(OtherFakeSecretStorage, self).__init__(allsecretsInADict)


class TestSecretsManager(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master()
        self.master.config.secretsManagers = [FakeSecretStorage({"foo": "bar",
                                                                 "other": "value"})]

    def testGetManagerService(self):
        secret_service_manager = SecretManager()
        SecretManager.master = self.master
        expectedSecretDetail = SecretDetails(
            FakeSecretStorage({"foo": "bar",
                               "other": "value"}).__class__.__name__, "foo",
            "bar")
        self.assertEqual(secret_service_manager.get(
            "foo"), expectedSecretDetail)

    def testGetNoDataManagerService(self):
        secret_service_manager = SecretManager()
        SecretManager.master = self.master
        expectedSecretDetail = SecretDetails(
            FakeSecretStorage({"foo": "bar",
                               "other": "value"}).__class__.__name__, "foo2",
            None)
        self.assertEqual(secret_service_manager.get(
            "foo2"), expectedSecretDetail)

    def testGetDataMultipleManagerService(self):
        secret_service_manager = SecretManager()
        self.master.config.secretsManagers = [FakeSecretStorage({"foo": "bar",
                                                                 "other": "value"}),
                                              OtherFakeSecretStorage({"foo2": "bar",
                                                                      "other2": "value"},
                                                                     props={"property": "value_prop"})
                                              ]
        SecretManager.master = self.master
        expectedSecretDetail = SecretDetails(
            OtherFakeSecretStorage({"foo2": "bar",
                                    "other2": "value"}).__class__.__name__, "foo2",
            "bar")
        self.assertEqual(secret_service_manager.get(
            "foo2"), expectedSecretDetail)

    def testGetDataMultipleManagerServiceNoDatas(self):
        secret_service_manager = SecretManager()
        self.master.config.secretsManagers = [FakeSecretStorage({"foo": "bar",
                                                                 "other": "value"}),
                                              FakeSecretStorage({"foo2": "bar",
                                                                 "other2": "value"})
                                              ]
        SecretManager.master = self.master
        expectedSecretDetail = SecretDetails(
            FakeSecretStorage({"foo2": "bar",
                               "other2": "value"}).__class__.__name__, "foo3",
            None)
        self.assertEqual(secret_service_manager.get(
            "foo3"), expectedSecretDetail)
