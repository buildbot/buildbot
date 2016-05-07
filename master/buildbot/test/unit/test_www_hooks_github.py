# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members
import hmac
from calendar import timegm
from hashlib import sha1
from StringIO import StringIO

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.fake.web import FakeRequest
from buildbot.test.fake.web import fakeMasterForHooks
from buildbot.www.change_hook import ChangeHookResource
from buildbot.www.hooks.github import _HEADER_CT
from buildbot.www.hooks.github import _HEADER_EVENT
from buildbot.www.hooks.github import _HEADER_SIGNATURE

# Sample GITHUB commit payload from http://help.github.com/post-receive-hooks/
# Added "modfied" and "removed", and change email
gitJsonPayload = """
{
  "before": "5aef35982fb2d34e9d9d4502f6ede1072793222d",
  "repository": {
    "url": "http://github.com/defunkt/github",
    "html_url": "http://github.com/defunkt/github",
    "name": "github",
    "full_name": "defunkt/github",
    "description": "You're lookin' at it.",
    "watchers": 5,
    "forks": 2,
    "private": 1,
    "owner": {
      "email": "fred@flinstone.org",
      "name": "defunkt"
    }
  },
  "commits": [
    {
      "id": "41a212ee83ca127e3c8cf465891ab7216a705f59",
      "distinct": true,
      "url": "http://github.com/defunkt/github/commit/41a212ee83ca127e3c8cf465891ab7216a705f59",
      "author": {
        "email": "fred@flinstone.org",
        "name": "Fred Flinstone"
      },
      "message": "okay i give in",
      "timestamp": "2008-02-15T14:57:17-08:00",
      "added": ["filepath.rb"]
    },
    {
      "id": "de8251ff97ee194a289832576287d6f8ad74e3d0",
      "url": "http://github.com/defunkt/github/commit/de8251ff97ee194a289832576287d6f8ad74e3d0",
      "author": {
        "email": "fred@flinstone.org",
        "name": "Fred Flinstone"
      },
      "message": "update pricing a tad",
      "timestamp": "2008-02-15T14:36:34-08:00",
      "modified": ["modfile"],
      "removed": ["removedFile"]
    }
  ],
  "after": "de8251ff97ee194a289832576287d6f8ad74e3d0",
  "ref": "refs/heads/master"
}
"""

gitJsonPayloadNonBranch = """
{
  "before": "5aef35982fb2d34e9d9d4502f6ede1072793222d",
  "repository": {
    "url": "http://github.com/defunkt/github",
    "html_url": "http://github.com/defunkt/github",
    "name": "github",
    "full_name": "defunkt/github",
    "description": "You're lookin' at it.",
    "watchers": 5,
    "forks": 2,
    "private": 1,
    "owner": {
      "email": "fred@flinstone.org",
      "name": "defunkt"
    }
  },
  "commits": [
    {
      "id": "41a212ee83ca127e3c8cf465891ab7216a705f59",
      "distinct": true,
      "url": "http://github.com/defunkt/github/commit/41a212ee83ca127e3c8cf465891ab7216a705f59",
      "author": {
        "email": "fred@flinstone.org",
        "name": "Fred Flinstone"
      },
      "message": "okay i give in",
      "timestamp": "2008-02-15T14:57:17-08:00",
      "added": ["filepath.rb"]
    }
  ],
  "after": "de8251ff97ee194a289832576287d6f8ad74e3d0",
  "ref": "refs/garbage/master"
}
"""

gitJsonPayloadPullRequest = """
{
  "action": "opened",
  "number": 50,
  "pull_request": {
    "url": "https://api.github.com/repos/defunkt/github/pulls/50",
    "html_url": "https://github.com/defunkt/github/pull/50",
    "number": 50,
    "state": "open",
    "title": "Update the README with new information",
    "user": {
      "login": "defunkt",
      "id": 42,
      "type": "User"
    },
    "body": "This is a pretty simple change that we need to pull into master.",
    "created_at": "2014-10-10T00:09:50Z",
    "updated_at": "2014-10-10T00:09:50Z",
    "closed_at": null,
    "merged_at": null,
    "merge_commit_sha": "cd3ff078a350901f91f4c4036be74f91d0b0d5d6",
    "head": {
      "label": "defunkt:changes",
      "ref": "changes",
      "sha": "05c588ba8cd510ecbe112d020f215facb17817a7",
      "user": {
        "login": "defunkt",
        "id": 42,
        "type": "User"
      },
      "repo": {
        "id": 43,
        "name": "github",
        "full_name": "defunkt/github",
        "owner": {
          "login": "defunkt",
          "id": 42,
          "type": "User"
        },
        "html_url": "https://github.com/defunkt/github",
        "description": "",
        "url": "https://api.github.com/repos/defunkt/github",
        "created_at": "2014-05-20T22:39:43Z",
        "updated_at": "2014-07-25T16:37:51Z",
        "pushed_at": "2014-10-10T00:09:49Z",
        "git_url": "git://github.com/defunkt/github.git",
        "ssh_url": "git@github.com:defunkt/github.git",
        "clone_url": "https://github.com/defunkt/github.git",
        "default_branch": "master"
      }
    },
    "base": {
      "label": "defunkt:master",
      "ref": "master",
      "sha": "69a8b72e2d3d955075d47f03d902929dcaf74034",
      "user": {
        "login": "defunkt",
        "id": 42,
        "type": "User"
      },
      "repo": {
        "id": 43,
        "name": "github",
        "full_name": "defunkt/github",
        "owner": {
          "login": "defunkt",
          "id": 42,
          "type": "User"
        },
        "html_url": "https://github.com/defunkt/github",
        "description": "",
        "url": "https://api.github.com/repos/defunkt/github",
        "created_at": "2014-05-20T22:39:43Z",
        "updated_at": "2014-07-25T16:37:51Z",
        "pushed_at": "2014-10-10T00:09:49Z",
        "git_url": "git://github.com/defunkt/github.git",
        "ssh_url": "git@github.com:defunkt/github.git",
        "clone_url": "https://github.com/defunkt/github.git",
        "default_branch": "master"
      }
    },
    "_links": {
      "self": {
        "href": "https://api.github.com/repos/defunkt/github/pulls/50"
      },
      "html": {
        "href": "https://github.com/defunkt/github/pull/50"
      },
      "commits": {
        "href": "https://api.github.com/repos/defunkt/github/pulls/50/commits"
      }
    },
    "commits": 1,
    "additions": 2,
    "deletions": 0,
    "changed_files": 1
  },
  "repository": {
    "id": 43,
    "name": "github",
    "full_name": "defunkt/github",
    "owner": {
      "login": "defunkt",
      "id": 42,
      "type": "User"
    },
    "html_url": "https://github.com/defunkt/github",
    "description": "",
    "url": "https://api.github.com/repos/defunkt/github",
    "created_at": "2014-05-20T22:39:43Z",
    "updated_at": "2014-07-25T16:37:51Z",
    "pushed_at": "2014-10-10T00:09:49Z",
    "git_url": "git://github.com/defunkt/github.git",
    "ssh_url": "git@github.com:defunkt/github.git",
    "clone_url": "https://github.com/defunkt/github.git",
    "default_branch": "master"
  },
  "sender": {
    "login": "defunkt",
    "id": 42,
    "type": "User"
  }
}
"""

gitJsonPayloadEmpty = """
{
  "before": "5aef35982fb2d34e9d9d4502f6ede1072793222d",
  "repository": {
    "url": "http://github.com/defunkt/github",
    "html_url": "http://github.com/defunkt/github",
    "name": "github",
    "full_name": "defunkt/github",
    "description": "You're lookin' at it.",
    "watchers": 5,
    "forks": 2,
    "private": 1,
    "owner": {
      "email": "fred@flinstone.org",
      "name": "defunkt"
    }
  },
  "commits": [
  ],
  "after": "de8251ff97ee194a289832576287d6f8ad74e3d0",
  "ref": "refs/heads/master"
}
"""

_CT_ENCODED = 'application/x-www-form-urlencoded'
_CT_JSON = 'application/json'


def _prepare_github_change_hook(**params):
    return ChangeHookResource(dialects={
        'github': params
    }, master=fakeMasterForHooks())


def _prepare_request(event, payload, _secret=None, headers=None):
    if headers is None:
        headers = dict()

    request = FakeRequest()

    request.uri = "/change_hook/github"
    request.method = "GET"
    request.received_headers = {
        _HEADER_EVENT: event
    }

    if isinstance(payload, str):
        request.content = StringIO(payload)
        request.received_headers[_HEADER_CT] = _CT_JSON

        if _secret is not None:
            signature = hmac.new(_secret, msg=payload, digestmod=sha1)
            request.received_headers[_HEADER_SIGNATURE] = \
                'sha1=%s' % (signature.hexdigest(),)
    else:
        request.args['payload'] = payload
        request.received_headers[_HEADER_CT] = _CT_ENCODED

    request.received_headers.update(headers)

    # print request.received_headers

    return request


class TestChangeHookConfiguredWithGitChange(unittest.TestCase):

    def setUp(self):
        self.changeHook = _prepare_github_change_hook(strict=False)

    @defer.inlineCallbacks
    def test_unknown_event(self):
        bad_event = 'whatever'
        self.request = _prepare_request(bad_event, gitJsonPayload)
        yield self.request.test_render(self.changeHook)
        expected = 'Unknown event: %r' % (bad_event,)
        self.assertEqual(len(self.changeHook.master.addedChanges), 0)
        self.assertEqual(self.request.written, expected)

    @defer.inlineCallbacks
    def test_unknown_content_type(self):
        bad_content_type = 'application/x-useful'
        self.request = _prepare_request('push', gitJsonPayload, headers={
            _HEADER_CT: bad_content_type
        })
        yield self.request.test_render(self.changeHook)
        expected = 'Unknown content type: %r' % (bad_content_type,)
        self.assertEqual(len(self.changeHook.master.addedChanges), 0)
        self.assertEqual(self.request.written, expected)

    @defer.inlineCallbacks
    def _check_ping(self, payload):
        self.request = _prepare_request('ping', payload)
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.addedChanges), 0)

    def test_ping_encoded(self):
        self._check_ping(['{}'])

    def test_ping_json(self):
        self._check_ping('{}')

    # Test 'base' hook with attributes. We should get a json string
    # representing a Change object as a dictionary. All values show be set.
    @defer.inlineCallbacks
    def _check_git_with_change(self, payload):
        self.request = _prepare_request('push', payload)
        yield self.request.test_render(self.changeHook)
        self.assertEquals(len(self.changeHook.master.addedChanges), 2)
        change = self.changeHook.master.addedChanges[0]

        self.assertEquals(change['files'], ['filepath.rb'])
        self.assertEquals(change["repository"],
                          "http://github.com/defunkt/github")
        self.assertEquals(timegm(change["when_timestamp"].utctimetuple()),
                          1203116237)
        self.assertEquals(change["author"],
                          "Fred Flinstone <fred@flinstone.org>")
        self.assertEquals(change["revision"],
                          '41a212ee83ca127e3c8cf465891ab7216a705f59')
        self.assertEquals(change["comments"],
                          "okay i give in")
        self.assertEquals(change["branch"], "master")
        self.assertEquals(change["revlink"],
                          "http://github.com/defunkt/github/commit/"
                          "41a212ee83ca127e3c8cf465891ab7216a705f59")

        change = self.changeHook.master.addedChanges[1]
        self.assertEquals(change['files'], ['modfile', 'removedFile'])
        self.assertEquals(change["repository"],
                          "http://github.com/defunkt/github")
        self.assertEquals(timegm(change["when_timestamp"].utctimetuple()),
                          1203114994)
        self.assertEquals(change["author"],
                          "Fred Flinstone <fred@flinstone.org>")
        self.assertEquals(change["src"], "git")
        self.assertEquals(change["revision"],
                          'de8251ff97ee194a289832576287d6f8ad74e3d0')
        self.assertEquals(change["comments"], "update pricing a tad")
        self.assertEquals(change["branch"], "master")
        self.assertEquals(change["revlink"],
                          "http://github.com/defunkt/github/commit/"
                          "de8251ff97ee194a289832576287d6f8ad74e3d0")

    def test_git_with_change_encoded(self):
        self._check_git_with_change([gitJsonPayload])

    def test_git_with_change_json(self):
        self._check_git_with_change(gitJsonPayload)

    @defer.inlineCallbacks
    def testGitWithDistinctFalse(self):
        self.request = _prepare_request('push', [gitJsonPayload.replace('"distinct": true,',
                                                                        '"distinct": false,')])

        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.addedChanges), 1)
        change = self.changeHook.master.addedChanges[0]

        self.assertEqual(change['files'],
                         ['modfile', 'removedFile'])
        self.assertEqual(change["repository"],
                         "http://github.com/defunkt/github")
        self.assertEqual(timegm(change["when_timestamp"].utctimetuple()),
                         1203114994)
        self.assertEqual(change["author"],
                         "Fred Flinstone <fred@flinstone.org>")
        self.assertEqual(change["src"], "git")
        self.assertEqual(change["revision"],
                         'de8251ff97ee194a289832576287d6f8ad74e3d0')
        self.assertEqual(change["comments"], "update pricing a tad")
        self.assertEqual(change["branch"], "master")
        self.assertEqual(change["revlink"],
                         "http://github.com/defunkt/github/commit/"
                         "de8251ff97ee194a289832576287d6f8ad74e3d0")

    @defer.inlineCallbacks
    def testGitWithNoJson(self):
        self.request = _prepare_request('push', '')

        yield self.request.test_render(self.changeHook)
        expected = "No JSON object could be decoded"
        self.assertEquals(len(self.changeHook.master.addedChanges), 0)
        self.assertEqual(self.request.written, expected)
        self.request.setResponseCode.assert_called_with(400, expected)

    @defer.inlineCallbacks
    def _check_git_with_no_changes(self, payload):
        self.request = _prepare_request('push', payload)
        yield self.request.test_render(self.changeHook)
        expected = "no changes found"
        self.assertEquals(len(self.changeHook.master.addedChanges), 0)
        self.assertEqual(self.request.written, expected)

    def test_git_with_no_changes_encoded(self):
        self._check_git_with_no_changes([gitJsonPayloadEmpty])

    def test_git_with_no_changes_json(self):
        self._check_git_with_no_changes(gitJsonPayloadEmpty)

    @defer.inlineCallbacks
    def _check_git_with_non_branch_changes(self, payload):
        self.request = _prepare_request('push', payload)
        yield self.request.test_render(self.changeHook)
        expected = "no changes found"
        self.assertEquals(len(self.changeHook.master.addedChanges), 0)
        self.assertEqual(self.request.written, expected)

    def test_git_with_non_branch_changes_encoded(self):
        self._check_git_with_non_branch_changes([gitJsonPayloadNonBranch])

    def test_git_with_non_branch_changes_json(self):
        self._check_git_with_non_branch_changes(gitJsonPayloadNonBranch)

    @defer.inlineCallbacks
    def _check_git_with_pull(self, payload):
        self.request = _prepare_request('pull_request', payload)
        yield self.request.test_render(self.changeHook)
        self.assertEquals(len(self.changeHook.master.addedChanges), 1)
        change = self.changeHook.master.addedChanges[0]
        self.assertEquals(change["repository"],
                          "https://github.com/defunkt/github")
        self.assertEquals(timegm(change["when_timestamp"].utctimetuple()),
                          1412899790)
        self.assertEquals(change["author"],
                          "defunkt")
        self.assertEquals(change["revision"],
                          '05c588ba8cd510ecbe112d020f215facb17817a7')
        self.assertEquals(change["comments"],
                          "GitHub Pull Request #50 (1 commit)")
        self.assertEquals(change["branch"], "refs/pull/50/head")
        self.assertEquals(change["revlink"],
                          "https://github.com/defunkt/github/pull/50")

    def test_git_with_pull_encoded(self):
        self._check_git_with_pull([gitJsonPayloadPullRequest])

    def test_git_with_pull_json(self):
        self._check_git_with_pull(gitJsonPayloadPullRequest)


class TestChangeHookConfiguredWithStrict(unittest.TestCase):

    _SECRET = 'somethingreallysecret'

    def setUp(self):
        self.changeHook = _prepare_github_change_hook(strict=True,
                                                      secret=self._SECRET)

    @defer.inlineCallbacks
    def test_signature_ok(self):
        self.request = _prepare_request('push', gitJsonPayload,
                                        _secret=self._SECRET)
        yield self.request.test_render(self.changeHook)
        # Can it somehow be merged w/ the same code above in a different class?
        self.assertEquals(len(self.changeHook.master.addedChanges), 2)
        change = self.changeHook.master.addedChanges[0]

        self.assertEquals(change['files'], ['filepath.rb'])
        self.assertEquals(change["repository"],
                          "http://github.com/defunkt/github")
        self.assertEquals(timegm(change["when_timestamp"].utctimetuple()),
                          1203116237)
        self.assertEquals(change["author"],
                          "Fred Flinstone <fred@flinstone.org>")
        self.assertEquals(change["revision"],
                          '41a212ee83ca127e3c8cf465891ab7216a705f59')
        self.assertEquals(change["comments"],
                          "okay i give in")
        self.assertEquals(change["branch"], "master")
        self.assertEquals(change["revlink"],
                          "http://github.com/defunkt/github/commit/"
                          "41a212ee83ca127e3c8cf465891ab7216a705f59")

        change = self.changeHook.master.addedChanges[1]
        self.assertEquals(change['files'], ['modfile', 'removedFile'])
        self.assertEquals(change["repository"],
                          "http://github.com/defunkt/github")
        self.assertEquals(timegm(change["when_timestamp"].utctimetuple()),
                          1203114994)
        self.assertEquals(change["author"],
                          "Fred Flinstone <fred@flinstone.org>")
        self.assertEquals(change["src"], "git")
        self.assertEquals(change["revision"],
                          'de8251ff97ee194a289832576287d6f8ad74e3d0')
        self.assertEquals(change["comments"], "update pricing a tad")
        self.assertEquals(change["branch"], "master")
        self.assertEquals(change["revlink"],
                          "http://github.com/defunkt/github/commit/"
                          "de8251ff97ee194a289832576287d6f8ad74e3d0")

    @defer.inlineCallbacks
    def test_unknown_hash(self):
        bad_hash_type = 'blah'
        self.request = _prepare_request('push', gitJsonPayload, headers={
            _HEADER_SIGNATURE: '%s=doesnotmatter' % (bad_hash_type,)
        })
        yield self.request.test_render(self.changeHook)
        expected = 'Unknown hash type: %s' % (bad_hash_type,)
        self.assertEqual(len(self.changeHook.master.addedChanges), 0)
        self.assertEqual(self.request.written, expected)

    @defer.inlineCallbacks
    def test_signature_nok(self):
        bad_signature = 'sha1=wrongstuff'
        self.request = _prepare_request('push', gitJsonPayload, headers={
            _HEADER_SIGNATURE: bad_signature
        })
        yield self.request.test_render(self.changeHook)
        expected = 'Hash mismatch'
        self.assertEqual(len(self.changeHook.master.addedChanges), 0)
        self.assertEqual(self.request.written, expected)

    @defer.inlineCallbacks
    def test_missing_secret(self):
        # override the value assigned in setUp
        self.changeHook = _prepare_github_change_hook(strict=True)
        self.request = _prepare_request('push', gitJsonPayload)
        yield self.request.test_render(self.changeHook)
        expected = 'Strict mode is requested while no secret is provided'
        self.assertEqual(len(self.changeHook.master.addedChanges), 0)
        self.assertEqual(self.request.written, expected)

    @defer.inlineCallbacks
    def test_wrong_signature_format(self):
        bad_signature = 'hash=value=something'
        self.request = _prepare_request('push', gitJsonPayload, headers={
            _HEADER_SIGNATURE: bad_signature
        })
        yield self.request.test_render(self.changeHook)
        expected = 'Wrong signature format: %r' % (bad_signature,)
        self.assertEqual(len(self.changeHook.master.addedChanges), 0)
        self.assertEqual(self.request.written, expected)

    @defer.inlineCallbacks
    def test_signature_missing(self):
        self.request = _prepare_request('push', gitJsonPayload)
        yield self.request.test_render(self.changeHook)
        expected = 'Request has no required signature'
        self.assertEqual(len(self.changeHook.master.addedChanges), 0)
        self.assertEqual(self.request.written, expected)


class TestChangeHookConfiguredWithCodebaseValue(unittest.TestCase):

    def setUp(self):
        self.changeHook = _prepare_github_change_hook(codebase='foobar')

    @defer.inlineCallbacks
    def _check_git_with_change(self, payload):
        self.request = _prepare_request('push', payload)
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.addedChanges), 2)
        change = self.changeHook.master.addedChanges[0]
        self.assertEquals(change['codebase'], 'foobar')

    def test_git_with_change_encoded(self):
        return self._check_git_with_change([gitJsonPayload])

    def test_git_with_change_json(self):
        return self._check_git_with_change(gitJsonPayload)


def _codebase_function(payload):
    return 'foobar-' + payload['repository']['name']


class TestChangeHookConfiguredWithCodebaseFunction(unittest.TestCase):

    def setUp(self):
        self.changeHook = _prepare_github_change_hook(
            codebase=_codebase_function)

    @defer.inlineCallbacks
    def _check_git_with_change(self, payload):
        self.request = _prepare_request('push', payload)
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.addedChanges), 2)
        change = self.changeHook.master.addedChanges[0]
        self.assertEquals(change['codebase'], 'foobar-github')

    def test_git_with_change_encoded(self):
        return self._check_git_with_change([gitJsonPayload])

    def test_git_with_change_json(self):
        return self._check_git_with_change(gitJsonPayload)
