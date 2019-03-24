import json

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.fake.web import FakeRequest
from buildbot.test.fake.web import fakeMasterForHooks
from buildbot.test.util.misc import TestReactorMixin
from buildbot.util import bytes2unicode
from buildbot.www.change_hook import ChangeHookResource
from buildbot.www.hooks.base import BaseHookHandler


def _prepare_base_change_hook(testcase, **options):
    return ChangeHookResource(dialects={
        'base': options
    }, master=fakeMasterForHooks(testcase))


def _prepare_request(payload, headers=None):
    if headers is None:
        headers = {
            b"Content-type": b"application/x-www-form-urlencoded",
            b"Accept": b"text/plain"}
    else:
        headers = {}

    if b'comments' not in payload:
        payload[b'comments'] = b'test_www_hook_base submission'  # Required field

    request = FakeRequest()

    request.uri = b"/change_hook/base"
    request.method = b"POST"
    request.args = payload
    request.received_headers.update(headers)

    return request


class TestChangeHookConfiguredWithBase(unittest.TestCase, TestReactorMixin):
    def setUp(self):
        self.setUpTestReactor()
        self.changeHook = _prepare_base_change_hook(self)

    @defer.inlineCallbacks
    def _check_base_with_change(self, payload):
        self.request = _prepare_request(payload)
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.data.updates.changesAdded), 1)
        change = self.changeHook.master.data.updates.changesAdded[0]

        def _first_or_nothing(val):
            if isinstance(val, type([])):
                val = val[0]
            return bytes2unicode(val)

        if payload.get(b'files'):
            files = json.loads(_first_or_nothing(payload.get(b'files')))
        else:
            files = []
        self.assertEqual(change['files'], files)

        if payload.get(b'properties'):
            props = json.loads(_first_or_nothing(payload.get(b'properties')))
        else:
            props = {}
        self.assertEqual(change['properties'], props)

        self.assertEqual(
            change['author'],
            _first_or_nothing(payload.get(b'author', payload.get(b'who'))))

        for field in ('revision', 'comments', 'branch', 'category',
                      'revlink'):
            self.assertEqual(
                change[field], _first_or_nothing(payload.get(field.encode())))

        for field in ('repository', 'project'):
            self.assertEqual(
                change[field], _first_or_nothing(payload.get(field.encode())) or '')

    def test_base_with_no_change(self):
        return self._check_base_with_change({})

    def test_base_with_changes(self):
        self._check_base_with_change({
            b'revision': [b'1234badcaca5678'],
            b'branch': [b'master'],
            b'comments': [b'Fix foo bar'],
            b'category': [b'bug'],
            b'revlink': [b'https://git.myproject.org/commit/1234badcaca5678'],
            b'repository': [b'myproject'],
            b'project': [b'myproject'],
            b'author': [b'me <me@myself.org>'],
            b'files': [b'["src/main.c", "src/foo.c"]'],
            b'properties': [b'{"color": "blue", "important": true, "size": 2}'],
        })


class TestChangeHookConfiguredWithCustomBase(unittest.TestCase,
                                             TestReactorMixin):
    def setUp(self):
        self.setUpTestReactor()

        class CustomBase(BaseHookHandler):
            def getChanges(self, request):
                args = request.args
                chdict = dict(
                              revision=args.get(b'revision'),
                              repository=args.get(b'_repository') or '',
                              project=args.get(b'project') or '',
                              codebase=args.get(b'codebase'))
                return ([chdict], None)
        self.changeHook = _prepare_base_change_hook(self, custom_class=CustomBase)

    @defer.inlineCallbacks
    def _check_base_with_change(self, payload):
        self.request = _prepare_request(payload)
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.data.updates.changesAdded), 1)
        change = self.changeHook.master.data.updates.changesAdded[0]
        self.assertEqual(change['repository'], payload.get(b'_repository') or '')

    def test_base_with_no_change(self):
        return self._check_base_with_change({b'repository': b'foo'})
