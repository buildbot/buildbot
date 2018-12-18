from __future__ import absolute_import
from __future__ import print_function

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.fake.web import FakeRequest
from buildbot.test.fake.web import fakeMasterForHooks
from buildbot.util import bytes2NativeString
from buildbot.www.change_hook import ChangeHookResource
from buildbot.www.hooks.base import BaseHookHandler


def _prepare_base_change_hook(**options):
    return ChangeHookResource(dialects={
        'base': options
    }, master=fakeMasterForHooks())


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


class TestChangeHookConfiguredWithBase(unittest.TestCase):
    def setUp(self):
        self.changeHook = _prepare_base_change_hook()

    @defer.inlineCallbacks
    def _check_base_with_change(self, payload):
        self.request = _prepare_request(payload)
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.addedChanges), 1)
        change = self.changeHook.master.addedChanges[0]
        self.assertEqual(change['files'], payload.get(b'files', []))
        self.assertEqual(change['properties'], payload.get(b'properties', {}))
        self.assertEqual(change['revision'], bytes2NativeString(payload.get(b'revision')))
        self.assertEqual(change['author'],
                         payload.get('author', bytes2NativeString(payload.get(b'who'))))
        self.assertEqual(change['comments'], bytes2NativeString(payload[b'comments']))
        self.assertEqual(change['branch'], bytes2NativeString(payload.get(b'branch')))
        self.assertEqual(change['category'], bytes2NativeString(payload.get(b'category')))
        self.assertEqual(change['revlink'], bytes2NativeString(payload.get(b'revlink')))
        self.assertEqual(change['repository'], bytes2NativeString(payload.get(b'repository')))
        self.assertEqual(change['project'], bytes2NativeString(payload.get(b'project')))

    def test_base_with_no_change(self):
        self._check_base_with_change({})


class TestChangeHookConfiguredWithCustomBase(unittest.TestCase):
    def setUp(self):
        class CustomBase(BaseHookHandler):
            def getChanges(self, request):
                args = request.args
                chdict = dict(
                              revision=args.get(b'revision'),
                              repository=args.get(b'_repository'),
                              project=args.get(b'project'),
                              codebase=args.get(b'codebase'))
                return ([chdict], None)
        self.changeHook = _prepare_base_change_hook(custom_class=CustomBase)

    @defer.inlineCallbacks
    def _check_base_with_change(self, payload):
        self.request = _prepare_request(payload)
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.addedChanges), 1)
        change = self.changeHook.master.addedChanges[0]
        self.assertEqual(change['repository'], payload.get(b'_repository'))

    def test_base_with_no_change(self):
        self._check_base_with_change({b'repository': b'foo'})
