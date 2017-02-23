from __future__ import absolute_import
from __future__ import print_function

import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.config import MasterConfig
from buildbot.process.properties import Interpolate
from buildbot.secrets.provider.base import SecretProviderBase
from buildbot.secrets.secret import SecretDetails
from buildbot.test.fake import fakemaster
from buildbot.test.fake.fakebuild import FakeBuild
from buildbot.test.util.config import ConfigErrorsMixin


class FakeSecretStorage(SecretProviderBase):

    def __init__(self, allsecretsInADict):
        self.allsecrets = allsecretsInADict

    def get(self, key):
        if key in self.allsecrets:
            return self.allsecrets[key], None
        else:
            return None, None


class FakeBuildWithMaster(FakeBuild):

    def __init__(self, master):
        super(FakeBuildWithMaster, self).__init__()
        self.master = master


class FakeService(object):

    def __init__(self, dictprop):
        self.dict = dictprop

    def get(self, key):
        if key in self.dict:
            return SecretDetails("FakeService", key, self.dict[key])
        else:
            return SecretDetails("FakeService", key, None)


class FakeServiceManager(object):

    def __init__(self, dictionary):
        self.dictionary = dictionary

    def __getitem__(self, dictionary):
        return FakeService(self.dictionary)

class TestInterpolateSecrets(unittest.TestCase, ConfigErrorsMixin):

    def setUp(self):
        self.master = fakemaster.make_master()
        self.master.config.secretsManagers = [FakeSecretStorage({"foo": "bar",
                                                                 "other": "value"})]
        self.master.namedServices = FakeServiceManager({"foo": "bar",
                                                        "other": "value"})
        self.build = FakeBuildWithMaster(self.master)

    @defer.inlineCallbacks
    def test_secret(self):
        command = Interpolate("echo %(secrets:foo)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo bar")

    @defer.inlineCallbacks
    def test_secret_not_found(self):
        command = Interpolate("echo %(secrets:fuo)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo ")
