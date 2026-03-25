from __future__ import annotations

from typing import TYPE_CHECKING

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process.properties import Interpolate
from buildbot.secrets.manager import SecretManager
from buildbot.test.fake import fakemaster
from buildbot.test.fake.fakebuild import FakeBuild
from buildbot.test.fake.secrets import FakeSecretStorage
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util.config import ConfigErrorsMixin

if TYPE_CHECKING:
    from buildbot.test.fake.fakemaster import FakeMaster
    from buildbot.util.twisted import InlineCallbacksType


class FakeBuildWithMaster(FakeBuild):
    master: FakeMaster

    def __init__(self, master: FakeMaster) -> None:
        super().__init__()
        self.master = master


class TestInterpolateSecrets(TestReactorMixin, ConfigErrorsMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self)
        fakeStorageService = FakeSecretStorage()
        fakeStorageService.reconfigService(secretdict={"foo": "bar", "other": "value"})
        self.secretsrv = SecretManager()
        self.secretsrv.services = [fakeStorageService]
        yield self.secretsrv.setServiceParent(self.master)
        self.build = FakeBuildWithMaster(self.master)

    @defer.inlineCallbacks
    def test_secret(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo %(secret:foo)s")
        rendered = yield self.build.render(command)
        self.assertEqual(rendered, "echo bar")

    @defer.inlineCallbacks
    def test_secret_not_found(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo %(secret:fuo)s")
        with self.assertRaises(defer.FirstError):
            yield self.build.render(command)


class TestInterpolateSecretsNoService(TestReactorMixin, ConfigErrorsMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self)
        self.build = FakeBuildWithMaster(self.master)

    @defer.inlineCallbacks
    def test_secret(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo %(secret:fuo)s")
        with self.assertRaises(defer.FirstError):
            yield self.build.render(command)


class TestInterpolateSecretsHiddenSecrets(TestReactorMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self)
        fakeStorageService = FakeSecretStorage()
        password = "bar"
        fakeStorageService.reconfigService(
            secretdict={"foo": password, "other": password + "random", "empty": ""}
        )
        self.secretsrv = SecretManager()
        self.secretsrv.services = [fakeStorageService]
        yield self.secretsrv.setServiceParent(self.master)
        self.build = FakeBuildWithMaster(self.master)

    @defer.inlineCallbacks
    def test_secret(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo %(secret:foo)s")
        rendered = yield self.build.render(command)
        cleantext = self.build.properties.cleanupTextFromSecrets(rendered)
        self.assertEqual(cleantext, "echo <foo>")

    @defer.inlineCallbacks
    def test_secret_replace(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo %(secret:foo)s %(secret:other)s")
        rendered = yield self.build.render(command)
        cleantext = self.build.properties.cleanupTextFromSecrets(rendered)
        self.assertEqual(cleantext, "echo <foo> <other>")

    @defer.inlineCallbacks
    def test_secret_replace_with_empty_secret(self) -> InlineCallbacksType[None]:
        command = Interpolate("echo %(secret:empty)s %(secret:other)s")
        rendered = yield self.build.render(command)
        cleantext = self.build.properties.cleanupTextFromSecrets(rendered)
        self.assertEqual(cleantext, "echo  <other>")
