from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType

import json

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.fake.web import FakeRequest
from buildbot.test.fake.web import fakeMasterForHooks
from buildbot.test.reactor import TestReactorMixin
from buildbot.util import bytes2unicode
from buildbot.www.change_hook import ChangeHookResource
from buildbot.www.hooks.base import BaseHookHandler


@defer.inlineCallbacks
def _prepare_base_change_hook(
    testcase: TestReactorMixin, **options: Any
) -> InlineCallbacksType[ChangeHookResource]:
    master = yield fakeMasterForHooks(testcase)
    return ChangeHookResource(dialects={'base': options}, master=master)


def _prepare_request(
    payload: dict[bytes, Any], headers: dict[bytes, bytes] | None = None
) -> FakeRequest:
    if headers is None:
        headers = {b"Content-type": b"application/x-www-form-urlencoded", b"Accept": b"text/plain"}
    else:
        headers = {}

    if b'comments' not in payload:
        payload[b'comments'] = b'test_www_hook_base submission'  # Required field

    request = FakeRequest()

    request.uri = b"/change_hook/base"
    request.method = b"POST"
    request.args = payload
    request.received_headers.update(headers)  # type: ignore[arg-type]

    return request


class TestChangeHookConfiguredWithBase(TestReactorMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.changeHook = yield _prepare_base_change_hook(self)

    @defer.inlineCallbacks
    def _check_base_with_change(self, payload: dict[bytes, Any]) -> InlineCallbacksType[None]:
        self.request = _prepare_request(payload)
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.data.updates.changesAdded), 1)
        change = self.changeHook.master.data.updates.changesAdded[0]

        def _first_or_nothing(val: Any) -> str | None:
            if isinstance(val, type([])):
                val = val[0]
            return bytes2unicode(val)

        if payload.get(b'files'):
            files = json.loads(_first_or_nothing(payload.get(b'files')))  # type: ignore[arg-type]
        else:
            files = []
        self.assertEqual(change['files'], files)

        if payload.get(b'properties'):
            props = json.loads(_first_or_nothing(payload.get(b'properties')))  # type: ignore[arg-type]
        else:
            props = {}
        self.assertEqual(change['properties'], props)

        self.assertEqual(
            change['author'], _first_or_nothing(payload.get(b'author', payload.get(b'who')))
        )

        for field in ('revision', 'committer', 'comments', 'branch', 'category', 'revlink'):
            self.assertEqual(change[field], _first_or_nothing(payload.get(field.encode())))

        for field in ('repository', 'project'):
            self.assertEqual(change[field], _first_or_nothing(payload.get(field.encode())) or '')

    def test_base_with_no_change(self) -> None:
        return self._check_base_with_change({})  # type: ignore[return-value]

    def test_base_with_changes(self) -> None:
        return self._check_base_with_change({  # type: ignore[return-value]
            b'revision': [b'1234badcaca5678'],
            b'branch': [b'master'],
            b'comments': [b'Fix foo bar'],
            b'category': [b'bug'],
            b'revlink': [b'https://git.myproject.org/commit/1234badcaca5678'],
            b'repository': [b'myproject'],
            b'project': [b'myproject'],
            b'author': [b'me <me@myself.org>'],
            b'committer': [b'me <me@myself.org>'],
            b'files': [b'["src/main.c", "src/foo.c"]'],
            b'properties': [b'{"color": "blue", "important": true, "size": 2}'],
        })


class TestChangeHookConfiguredWithCustomBase(TestReactorMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()

        class CustomBase(BaseHookHandler):
            def getChanges(self, request: Any) -> tuple[list[dict[str, Any]], None]:  # type: ignore[override]
                args = request.args
                chdict = {
                    "revision": args.get(b'revision'),
                    "repository": args.get(b'_repository') or '',
                    "project": args.get(b'project') or '',
                    "codebase": args.get(b'codebase'),
                }
                return ([chdict], None)

        self.changeHook = yield _prepare_base_change_hook(self, custom_class=CustomBase)

    @defer.inlineCallbacks
    def _check_base_with_change(self, payload: dict[bytes, Any]) -> InlineCallbacksType[None]:
        self.request = _prepare_request(payload)
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.data.updates.changesAdded), 1)
        change = self.changeHook.master.data.updates.changesAdded[0]
        self.assertEqual(change['repository'], payload.get(b'_repository') or '')

    def test_base_with_no_change(self) -> None:
        return self._check_base_with_change({b'repository': b'foo'})  # type: ignore[return-value]
