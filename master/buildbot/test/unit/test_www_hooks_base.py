from __future__ import absolute_import
from __future__ import print_function

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.fake.web import FakeRequest
from buildbot.test.fake.web import fakeMasterForHooks
from buildbot.www.change_hook import ChangeHookResource


def _prepare_base_change_hook():
    return ChangeHookResource(dialects={
        'base': True
    }, master=fakeMasterForHooks())


def _prepare_request(payload, headers=None):
    if headers is None:
        headers = {
            "Content-type": "application/x-www-form-urlencoded",
            "Accept": "text/plain"}
    else:
        headers = {}

    if 'comments' not in payload:
        payload['comments'] = 'test_www_hook_base submission'  # Required field

    request = FakeRequest()

    request.uri = "/change_hook/base"
    request.method = "POST"
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
        self.assertEqual(change['files'], payload.get('files', []))
        self.assertEqual(change['properties'], payload.get('properties', {}))
        self.assertEqual(change['revision'], payload.get('revision'))
        self.assertEqual(change['author'],
                         payload.get('author', payload.get('who')))
        self.assertEqual(change['comments'], payload['comments'])
        self.assertEqual(change['branch'], payload.get('branch'))
        self.assertEqual(change['category'], payload.get('category'))
        self.assertEqual(change['revlink'], payload.get('revlink'))
        self.assertEqual(change['repository'], payload.get('repository'))
        self.assertEqual(change['project'], payload.get('project'))

    def test_base_with_no_change(self):
        self._check_base_with_change({})
