from __future__ import absolute_import
from __future__ import print_function

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.secrets.manager import SecretManager
from buildbot.secrets.secret import SecretDetails
from buildbot.test.fake import fakemaster
from buildbot.test.fake.secrets import FakeSecretStorage


class OtherFakeSecretStorage(FakeSecretStorage):

    def __init__(self, allsecretsInADict, props=None):
        self.properties = props
        super(OtherFakeSecretStorage, self).__init__(allsecretsInADict)


class TestSecretsManager(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master()
        self.master.config.secretsProviders = [FakeSecretStorage({"foo": "bar",
                                                                  "other": "value"})]

    @defer.inlineCallbacks
    def testGetManagerService(self):
        secret_service_manager = SecretManager()
        secret_service_manager.services = [FakeSecretStorage({"foo": "bar",
                                                              "other": "value"})]
        expectedClassName = FakeSecretStorage.__name__
        expectedSecretDetail = SecretDetails(expectedClassName, "foo", "bar")
        secret_result = yield secret_service_manager.get("foo")
        strExpectedSecretDetail = str(secret_result)
        self.assertEqual(secret_result, expectedSecretDetail)
        self.assertEqual(secret_result.key, "foo")
        self.assertEqual(secret_result.value, "bar")
        self.assertEqual(secret_result.source, expectedClassName)
        self.assertEqual(strExpectedSecretDetail,
                         "FakeSecretStorage foo: 'bar'")

    @defer.inlineCallbacks
    def testGetNoDataManagerService(self):
        secret_service_manager = SecretManager()
        secret_service_manager.services = [FakeSecretStorage({"foo": "bar",
                                                              "other": "value"})]
        secret_result = yield secret_service_manager.get("foo2")
        self.assertEqual(secret_result, None)

    @defer.inlineCallbacks
    def testGetDataMultipleManagerService(self):
        secret_service_manager = SecretManager()
        secret_service_manager.services = [FakeSecretStorage({"foo": "bar",
                                                              "other": "value"}),
                                           OtherFakeSecretStorage({"foo2": "bar",
                                                                   "other2": "value"},
                                                                  props={"property": "value_prop"})
                                           ]
        expectedSecretDetail = SecretDetails(OtherFakeSecretStorage.__name__,
                                             "foo2",
                                             "bar")
        secret_result = yield secret_service_manager.get(
            "foo2")
        self.assertEqual(secret_result, expectedSecretDetail)

    @defer.inlineCallbacks
    def testGetDataMultipleManagerValues(self):
        secret_service_manager = SecretManager()
        secret_service_manager.services = [FakeSecretStorage({"foo": "bar",
                                                              "other": ""}),
                                           OtherFakeSecretStorage({"foo2": "bar2",
                                                                   "other": ""},
                                                                  props={"property": "value_prop"})
                                           ]
        expectedSecretDetail = SecretDetails(FakeSecretStorage.__name__,
                                             "other",
                                             "")
        secret_result = yield secret_service_manager.get("other")
        self.assertEqual(secret_result, expectedSecretDetail)

    @defer.inlineCallbacks
    def testGetDataMultipleManagerServiceNoDatas(self):
        secret_service_manager = SecretManager()
        self.master.config.secretsProviders = [FakeSecretStorage({"foo": "bar",
                                                                 "other": "value"}),
                                               FakeSecretStorage({"foo2": "bar",
                                                                 "other2": "value"})
                                               ]
        SecretManager.master = self.master
        secret_result = yield secret_service_manager.get("foo3")
        self.assertEqual(secret_result, None)
