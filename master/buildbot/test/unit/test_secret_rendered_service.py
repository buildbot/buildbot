from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process.properties import Secret
from buildbot.secrets.manager import SecretManager
from buildbot.test.fake import fakemaster
from buildbot.test.fake.secrets import FakeSecretStorage
from buildbot.test.reactor import TestReactorMixin
from buildbot.util.service import BuildbotService

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class FakeServiceUsingSecrets(BuildbotService):
    name = "FakeServiceUsingSecrets"
    secrets = ["foo", "bar", "secret"]

    def reconfigService(  # type: ignore[return]
        self, foo: Any = None, bar: Any = None, secret: Any = None, other: Any = None
    ) -> defer.Deferred[None]:
        self.foo = foo
        self.bar = bar
        self.secret = secret

    def returnRenderedSecrets(self, secretKey: str) -> Any:
        return getattr(self, secretKey)


class TestRenderSecrets(TestReactorMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self)
        fakeStorageService = FakeSecretStorage(secretdict={"foo": "bar", "other": "value"})
        self.secretsrv = SecretManager()
        self.secretsrv.services = [fakeStorageService]
        yield self.secretsrv.setServiceParent(self.master)
        self.srvtest = FakeServiceUsingSecrets()
        yield self.srvtest.setServiceParent(self.master)
        yield self.master.startService()
        self.addCleanup(self.master.stopService)

    @defer.inlineCallbacks
    def test_secret_rendered(self) -> InlineCallbacksType[None]:
        yield self.srvtest.configureService()
        new = FakeServiceUsingSecrets(foo=Secret("foo"), other=Secret("other"))
        yield self.srvtest.reconfigServiceWithSibling(new)
        self.assertEqual("bar", self.srvtest.returnRenderedSecrets("foo"))

    @defer.inlineCallbacks
    def test_secret_rendered_not_found(self) -> InlineCallbacksType[None]:
        new = FakeServiceUsingSecrets(foo=Secret("foo"))
        yield self.srvtest.reconfigServiceWithSibling(new)
        with self.assertRaises(AttributeError):
            self.srvtest.returnRenderedSecrets("more")
