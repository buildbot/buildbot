# coding: utf-8
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

from __future__ import absolute_import
from __future__ import print_function
from future.utils import PY3

import hmac
from calendar import timegm
from copy import deepcopy
from hashlib import sha1
from io import BytesIO

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.fake.web import FakeRequest
from buildbot.test.fake.web import fakeMasterForHooks
from buildbot.util import unicode2bytes
from buildbot.www.change_hook import ChangeHookResource
from buildbot.www.hooks.github import _HEADER_EVENT
from buildbot.www.hooks.github import _HEADER_SIGNATURE
from buildbot.www.hooks.github import GitHubEventHandler

# Sample GITHUB commit payload from http://help.github.com/post-receive-hooks/
# Added "modified" and "removed", and change email
# Added "head_commit"
#   https://developer.github.com/v3/activity/events/types/#webhook-payload-example-26
gitJsonPayload = b"""
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
  "head_commit": {
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
  },
  "after": "de8251ff97ee194a289832576287d6f8ad74e3d0",
  "ref": "refs/heads/master"
}
"""

gitJsonPayloadCiSkipTemplate = u"""
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
      "message": "update pricing a tad %(skip)s",
      "timestamp": "2008-02-15T14:36:34-08:00",
      "modified": ["modfile"],
      "removed": ["removedFile"]
    }
  ],
  "head_commit": {
    "id": "de8251ff97ee194a289832576287d6f8ad74e3d0",
    "url": "http://github.com/defunkt/github/commit/de8251ff97ee194a289832576287d6f8ad74e3d0",
    "author": {
      "email": "fred@flinstone.org",
      "name": "Fred Flinstone"
    },
    "message": "update pricing a tad %(skip)s",
    "timestamp": "2008-02-15T14:36:34-08:00",
    "modified": ["modfile"],
    "removed": ["removedFile"]
  },
  "after": "de8251ff97ee194a289832576287d6f8ad74e3d0",
  "ref": "refs/heads/master"
}
"""

gitJsonPayloadTag = b"""
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
  "head_commit": {
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
  },
  "after": "de8251ff97ee194a289832576287d6f8ad74e3d0",
  "ref": "refs/tags/v1.0.0"
}
"""

gitJsonPayloadNonBranch = b"""
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

gitJsonPayloadPullRequest = b"""
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

gitJsonPayloadCommit = {
    "sha": "de8251ff97ee194a289832576287d6f8ad74e3d0",
    "commit": {
        "author": {
            "name": "defunkt",
            "email": "fred@flinstone.org",
            "date": "2017-02-12T14:39:33Z"
        },
        "committer": {
            "name": "defunkt",
            "email": "fred@flinstone.org",
            "date": "2017-02-12T14:51:05Z"
        },
        "message": "black magic",
        "tree": {
        },
        "url": "...",
        "comment_count": 0
    },
    "url": "...",
    "html_url": "...",
    "comments_url": "...",
    "author": {},
    "committer": {},
    "parents": [],
    "stats": {},
    "files": []
}

gitPRproperties = {
    'github.head.sha': '05c588ba8cd510ecbe112d020f215facb17817a7',
    'github.state': 'open',
    'github.base.repo.full_name': 'defunkt/github',
    'github.number': 50,
    'github.base.ref': 'master',
    'github.base.sha': '69a8b72e2d3d955075d47f03d902929dcaf74034',
    'github.head.repo.full_name': 'defunkt/github',
    'github.merged_at': None,
    'github.head.ref': 'changes',
    'github.closed_at': None,
    'github.title': 'Update the README with new information',
    'event': 'pull_request'
}

gitJsonPayloadEmpty = b"""
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
  "head_commit": {
  },
  "after": "de8251ff97ee194a289832576287d6f8ad74e3d0",
  "ref": "refs/heads/master"
}
"""
gitJsonPayloadCreateTag = b"""
{
  "ref": "refs/tags/v0.9.15.post1",
  "before": "0000000000000000000000000000000000000000",
  "after": "ffe1e9affb2b5399369443194c02068032f9295e",
  "created": true,
  "deleted": false,
  "forced": false,
  "base_ref": null,
  "compare": "https://github.com/buildbot/buildbot/compare/v0.9.15.post1",
  "commits": [

  ],
  "head_commit": {
    "id": "57df618a4a450410c1dee440c7827ee105f5a226",
    "tree_id": "f9768673dc968b5c8fcbb15f119ce237b50b3252",
    "distinct": true,
    "message": "...",
    "timestamp": "2018-01-07T16:30:52+01:00",
    "url": "https://github.com/buildbot/buildbot/commit/...",
    "author": {
      "name": "User",
      "email": "userid@example.com",
      "username": "userid"
    },
    "committer": {
      "name": "GitHub",
      "email": "noreply@github.com",
      "username": "web-flow"
    },
    "added": [

    ],
    "removed": [
      "master/buildbot/newsfragments/bit_length.bugfix",
      "master/buildbot/newsfragments/localworker_umask.bugfix",
      "master/buildbot/newsfragments/svn-utf8.bugfix"
    ],
    "modified": [
      ".bbtravis.yml",
      "circle.yml",
      "master/docs/relnotes/index.rst"
    ]
  },
  "repository": {
    "html_url": "https://github.com/buildbot/buildbot",
    "name": "buildbot",
    "full_name": "buildbot"
  },
  "pusher": {
    "name": "userid",
    "email": "userid@example.com"
  },
  "organization": {
    "login": "buildbot",
    "url": "https://api.github.com/orgs/buildbot",
    "description": "Continous integration and delivery framework"
  },
  "sender": {
    "login": "userid",
    "gravatar_id": "",
    "type": "User",
    "site_admin": false
  },
  "ref_name": "v0.9.15.post1",
  "distinct_commits": [

  ]
}"""
_HEADER_CT = b'Content-Type'
_CT_ENCODED = b'application/x-www-form-urlencoded'
_CT_JSON = b'application/json'


def _prepare_github_change_hook(**params):
    return ChangeHookResource(dialects={
        'github': params
    }, master=fakeMasterForHooks())


def _prepare_request(event, payload, _secret=None, headers=None):
    if headers is None:
        headers = dict()

    request = FakeRequest()

    request.uri = b"/change_hook/github"
    request.method = b"GET"
    request.received_headers = {
        _HEADER_EVENT: event
    }

    assert isinstance(payload, (bytes, list)), \
        "payload can only be bytes or list, not {}".format(type(payload))

    if isinstance(payload, bytes):
        request.content = BytesIO(payload)
        request.received_headers[_HEADER_CT] = _CT_JSON

        if _secret is not None:
            signature = hmac.new(unicode2bytes(_secret),
                                 msg=unicode2bytes(payload),
                                 digestmod=sha1)
            request.received_headers[_HEADER_SIGNATURE] = \
                'sha1={}'.format(signature.hexdigest())
    else:
        request.args[b'payload'] = payload
        request.received_headers[_HEADER_CT] = _CT_ENCODED

    request.received_headers.update(headers)

    # print request.received_headers

    return request


class TestChangeHookConfiguredWithGitChange(unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self.changeHook = _prepare_github_change_hook(
            strict=False, github_property_whitelist=["github.*"])
        self.master = self.changeHook.master
        fake_headers = {'User-Agent': 'Buildbot'}
        self._http = yield fakehttpclientservice.HTTPClientService.getFakeService(
            self.master, self, 'https://api.github.com', headers=fake_headers,
            debug=False, verify=False)
        yield self.master.startService()

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.master.stopService()

    def assertDictSubset(self, expected_dict, response_dict):
        expected = {}
        for key in expected_dict.keys():
            self.assertIn(key, set(response_dict.keys()))
            expected[key] = response_dict[key]
        self.assertDictEqual(expected_dict, expected)

    @defer.inlineCallbacks
    def test_unknown_event(self):
        bad_event = b'whatever'
        self.request = _prepare_request(bad_event, gitJsonPayload)
        yield self.request.test_render(self.changeHook)
        expected = b'Unknown event: ' + bad_event
        self.assertEqual(len(self.changeHook.master.addedChanges), 0)
        self.assertEqual(self.request.written, expected)

    @defer.inlineCallbacks
    def test_unknown_content_type(self):
        bad_content_type = b'application/x-useful'
        self.request = _prepare_request(b'push', gitJsonPayload, headers={
            _HEADER_CT: bad_content_type
        })
        yield self.request.test_render(self.changeHook)
        expected = b'Unknown content type: '
        self.assertEqual(len(self.changeHook.master.addedChanges), 0)
        self.assertIn(expected, self.request.written)

    @defer.inlineCallbacks
    def _check_ping(self, payload):
        self.request = _prepare_request(b'ping', payload)
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.addedChanges), 0)

    def test_ping_encoded(self):
        self._check_ping([b'{}'])

    def test_ping_json(self):
        self._check_ping(b'{}')

    @defer.inlineCallbacks
    def test_git_with_push_tag(self):
        self.request = _prepare_request(b'push', gitJsonPayloadTag)
        yield self.request.test_render(self.changeHook)

        self.assertEqual(len(self.changeHook.master.addedChanges), 2)
        change = self.changeHook.master.addedChanges[0]
        self.assertEqual(change["author"],
                         "Fred Flinstone <fred@flinstone.org>")
        self.assertEqual(change["branch"], "v1.0.0")
        self.assertEqual(change["category"], "tag")

    @defer.inlineCallbacks
    def test_git_with_push_newtag(self):
        self.request = _prepare_request(b'push', gitJsonPayloadCreateTag)
        yield self.request.test_render(self.changeHook)

        self.assertEqual(len(self.changeHook.master.addedChanges), 1)
        change = self.changeHook.master.addedChanges[0]
        self.assertEqual(change["author"],
                         "User <userid@example.com>")
        self.assertEqual(change["branch"], "v0.9.15.post1")
        self.assertEqual(change["category"], "tag")

    # Test 'base' hook with attributes. We should get a json string
    # representing a Change object as a dictionary. All values show be set.
    @defer.inlineCallbacks
    def _check_git_with_change(self, payload):
        self.request = _prepare_request(b'push', payload)
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.addedChanges), 2)
        change = self.changeHook.master.addedChanges[0]

        self.assertEqual(change['files'], ['filepath.rb'])
        self.assertEqual(change["repository"],
                         "http://github.com/defunkt/github")
        self.assertEqual(timegm(change["when_timestamp"].utctimetuple()),
                         1203116237)
        self.assertEqual(change["author"],
                         "Fred Flinstone <fred@flinstone.org>")
        self.assertEqual(change["revision"],
                         '41a212ee83ca127e3c8cf465891ab7216a705f59')
        self.assertEqual(change["comments"],
                         "okay i give in")
        self.assertEqual(change["branch"], "master")
        self.assertEqual(change["revlink"],
                         "http://github.com/defunkt/github/commit/"
                         "41a212ee83ca127e3c8cf465891ab7216a705f59")

        change = self.changeHook.master.addedChanges[1]
        self.assertEqual(change['files'], ['modfile', 'removedFile'])
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
        self.assertEqual(change["properties"]["event"], "push")

    def test_git_with_change_encoded(self):
        self._check_git_with_change([gitJsonPayload])

    def test_git_with_change_json(self):
        self._check_git_with_change(gitJsonPayload)

    # Test that, even with commits not marked as distinct, the changes get
    # recorded each time we receive the payload. This is important because
    # without it, commits can get pushed to a non-scheduled branch, get
    # recorded and associated with that branch, and then later get pushed to a
    # scheduled branch and not trigger a build.
    #
    # For example, if a commit is pushed to a dev branch, it then gets recorded
    # as a change associated with that dev branch. If that change is later
    # pushed to master, we still need to trigger a build even though we've seen
    # the commit before.
    @defer.inlineCallbacks
    def testGitWithDistinctFalse(self):
        self.request = _prepare_request(b'push', [gitJsonPayload.replace(b'"distinct": true,',
                                                                        b'"distinct": false,')])

        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.addedChanges), 2)

        change = self.changeHook.master.addedChanges[0]
        self.assertEqual(change['files'], ['filepath.rb'])
        self.assertEqual(change["repository"],
                         "http://github.com/defunkt/github")
        self.assertEqual(timegm(change["when_timestamp"].utctimetuple()),
                         1203116237)
        self.assertEqual(change["author"],
                         "Fred Flinstone <fred@flinstone.org>")
        self.assertEqual(change["revision"],
                         '41a212ee83ca127e3c8cf465891ab7216a705f59')
        self.assertEqual(change["comments"],
                         "okay i give in")
        self.assertEqual(change["branch"], "master")
        self.assertEqual(change["revlink"],
                         "http://github.com/defunkt/github/commit/"
                         "41a212ee83ca127e3c8cf465891ab7216a705f59")
        self.assertEqual(change["properties"]["github_distinct"],
                         False)

        change = self.changeHook.master.addedChanges[1]
        self.assertEqual(change['files'], ['modfile', 'removedFile'])
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
        self.request = _prepare_request(b'push', b'')

        yield self.request.test_render(self.changeHook)
        if PY3:
            expected = b"Expecting value: line 1 column 1 (char 0)"
        else:
            expected = b"No JSON object could be decoded"
        self.assertEqual(len(self.changeHook.master.addedChanges), 0)
        self.assertEqual(self.request.written, expected)
        self.request.setResponseCode.assert_called_with(400, expected)

    @defer.inlineCallbacks
    def _check_git_with_no_changes(self, payload):
        self.request = _prepare_request(b'push', payload)
        yield self.request.test_render(self.changeHook)
        expected = b"no change found"
        self.assertEqual(len(self.changeHook.master.addedChanges), 0)
        self.assertEqual(self.request.written, expected)

    def test_git_with_no_changes_encoded(self):
        self._check_git_with_no_changes([gitJsonPayloadEmpty])

    def test_git_with_no_changes_json(self):
        self._check_git_with_no_changes(gitJsonPayloadEmpty)

    @defer.inlineCallbacks
    def _check_git_with_non_branch_changes(self, payload):
        self.request = _prepare_request(b'push', payload)
        yield self.request.test_render(self.changeHook)
        expected = b"no change found"
        self.assertEqual(len(self.changeHook.master.addedChanges), 0)
        self.assertEqual(self.request.written, expected)

    def test_git_with_non_branch_changes_encoded(self):
        self._check_git_with_non_branch_changes([gitJsonPayloadNonBranch])

    def test_git_with_non_branch_changes_json(self):
        self._check_git_with_non_branch_changes(gitJsonPayloadNonBranch)

    @defer.inlineCallbacks
    def _check_git_with_pull(self, payload):
        self.request = _prepare_request('pull_request', payload)
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.addedChanges), 1)
        change = self.changeHook.master.addedChanges[0]
        self.assertEqual(change["repository"],
                         "https://github.com/defunkt/github")
        self.assertEqual(timegm(change["when_timestamp"].utctimetuple()),
                         1412899790)
        self.assertEqual(change["author"],
                         "defunkt")
        self.assertEqual(change["revision"],
                         '05c588ba8cd510ecbe112d020f215facb17817a7')
        self.assertEqual(change["comments"],
                         "GitHub Pull Request #50 (1 commit)\n"
                         "Update the README with new information\n"
                         "This is a pretty simple change that we need to pull into master.")
        self.assertEqual(change["branch"], "refs/pull/50/merge")
        self.assertEqual(change["revlink"],
                         "https://github.com/defunkt/github/pull/50")
        self.assertDictSubset(gitPRproperties, change["properties"])

    def test_git_with_pull_encoded(self):
        api_endpoint = '/repos/defunkt/github/commits/05c588ba8cd510ecbe112d020f215facb17817a7'
        self._http.expect('get', api_endpoint, content_json=gitJsonPayloadCommit)
        self._check_git_with_pull([gitJsonPayloadPullRequest])

    def test_git_with_pull_json(self):
        api_endpoint = '/repos/defunkt/github/commits/05c588ba8cd510ecbe112d020f215facb17817a7'
        self._http.expect('get', api_endpoint, content_json=gitJsonPayloadCommit)
        self._check_git_with_pull(gitJsonPayloadPullRequest)

    @defer.inlineCallbacks
    def _check_git_push_with_skip_message(self, payload):
        self.request = _prepare_request(b'push', payload)
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.addedChanges), 0)

    def test_git_push_with_skip_message(self):
        gitJsonPayloadCiSkips = [
            unicode2bytes(gitJsonPayloadCiSkipTemplate % {'skip': '[ci skip]'}),
            unicode2bytes(gitJsonPayloadCiSkipTemplate % {'skip': '[skip ci]'}),
            unicode2bytes(gitJsonPayloadCiSkipTemplate % {'skip': '[  ci skip   ]'}),
        ]

        for payload in gitJsonPayloadCiSkips:
            self._check_git_push_with_skip_message(payload)

    @defer.inlineCallbacks
    def _check_git_pull_request_with_skip_message(self, payload):
        self.request = _prepare_request(b'pull_request', payload)
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.addedChanges), 0)

    def test_git_pull_request_with_skip_message(self):
        api_endpoint = '/repos/defunkt/github/commits/05c588ba8cd510ecbe112d020f215facb17817a7'
        commit = deepcopy(gitJsonPayloadCommit)
        msgs = (
            'black magic [ci skip]',
            'black magic [skip ci]',
            'black magic [  ci skip   ]',
        )
        for msg in msgs:
            commit['commit']['message'] = msg
            self._http.expect('get', api_endpoint, content_json=commit)
            self._check_git_pull_request_with_skip_message(
                gitJsonPayloadPullRequest)


class TestChangeHookConfiguredWithGitChangeCustomPullrequestRef(unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self.changeHook = _prepare_github_change_hook(
            strict=False, github_property_whitelist=["github.*"], pullrequest_ref="head")
        self.master = self.changeHook.master
        fake_headers = {'User-Agent': 'Buildbot'}
        self._http = yield fakehttpclientservice.HTTPClientService.getFakeService(
            self.master, self, 'https://api.github.com', headers=fake_headers,
            debug=False, verify=False)
        yield self.master.startService()

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.master.stopService()

    @defer.inlineCallbacks
    def test_git_pull_request_with_custom_ref(self):
        commit = deepcopy([gitJsonPayloadPullRequest])
        api_endpoint = '/repos/defunkt/github/commits/05c588ba8cd510ecbe112d020f215facb17817a7'
        self._http.expect('get', api_endpoint, content_json=gitJsonPayloadCommit)
        self.request = _prepare_request('pull_request', commit)
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.addedChanges), 1)
        change = self.changeHook.master.addedChanges[0]
        self.assertEqual(change["branch"], "refs/pull/50/head")


class TestChangeHookConfiguredWithCustomSkips(unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self.changeHook = _prepare_github_change_hook(
            strict=False, skips=[r'\[ *bb *skip *\]'])
        self.master = self.changeHook.master
        fake_headers = {'User-Agent': 'Buildbot'}
        self._http = yield fakehttpclientservice.HTTPClientService.getFakeService(
            self.master, self, 'https://api.github.com', headers=fake_headers,
            debug=False, verify=False)
        yield self.master.startService()

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.master.stopService()

    @defer.inlineCallbacks
    def _check_push_with_skip_message(self, payload):
        self.request = _prepare_request(b'push', payload)
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.addedChanges), 0)

    def test_push_with_skip_message(self):
        gitJsonPayloadCiSkips = [
            unicode2bytes(gitJsonPayloadCiSkipTemplate % {'skip': '[bb skip]'}),
            unicode2bytes(gitJsonPayloadCiSkipTemplate % {'skip': '[  bb skip   ]'}),
        ]

        for payload in gitJsonPayloadCiSkips:
            self._check_push_with_skip_message(payload)

    @defer.inlineCallbacks
    def _check_push_no_ci_skip(self, payload):
        self.request = _prepare_request(b'push', payload)
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.addedChanges), 2)

    def test_push_no_ci_skip(self):
        # user overrode the skip pattern already,
        # so the default patterns should not work.
        payload = gitJsonPayloadCiSkipTemplate % {'skip': '[ci skip]'}
        payload = unicode2bytes(payload)
        self._check_push_no_ci_skip(payload)

    @defer.inlineCallbacks
    def _check_pull_request_with_skip_message(self, payload):
        self.request = _prepare_request(b'pull_request', payload)
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.addedChanges), 0)

    def test_pull_request_with_skip_message(self):
        api_endpoint = '/repos/defunkt/github/commits/05c588ba8cd510ecbe112d020f215facb17817a7'
        commit = deepcopy(gitJsonPayloadCommit)
        msgs = (
            'black magic [bb skip]',
            'black magic [  bb skip   ]',
        )
        for msg in msgs:
            commit['commit']['message'] = msg
            self._http.expect('get', api_endpoint, content_json=commit)
            self._check_pull_request_with_skip_message(
                gitJsonPayloadPullRequest)

    @defer.inlineCallbacks
    def _check_pull_request_no_skip(self, payload):
        self.request = _prepare_request(b'pull_request', payload)
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.addedChanges), 1)

    def test_pull_request_no_skip(self):
        api_endpoint = '/repos/defunkt/github/commits/05c588ba8cd510ecbe112d020f215facb17817a7'
        commit = deepcopy(gitJsonPayloadCommit)
        commit['commit']['message'] = 'black magic [skip bb]'  # pattern not matched

        self._http.expect('get', api_endpoint, content_json=commit)
        self._check_pull_request_no_skip(gitJsonPayloadPullRequest)


class TestChangeHookConfiguredWithAuth(unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        _token = '7e076f41-b73a-4045-a817'
        self.changeHook = _prepare_github_change_hook(
            strict=False, token=_token)
        self.master = self.changeHook.master
        fake_headers = {'User-Agent': 'Buildbot',
                'Authorization': 'token ' + _token}
        self._http = yield fakehttpclientservice.HTTPClientService.getFakeService(
            self.master, self, 'https://api.github.com', headers=fake_headers,
            debug=False, verify=False)
        yield self.master.startService()

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.master.stopService()

    @defer.inlineCallbacks
    def _check_pull_request(self, payload):
        self.request = _prepare_request(b'pull_request', payload)
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.addedChanges), 1)

    def test_pull_request(self):
        api_endpoint = '/repos/defunkt/github/commits/05c588ba8cd510ecbe112d020f215facb17817a7'

        self._http.expect('get', api_endpoint, content_json=gitJsonPayloadCommit)
        self._check_pull_request(gitJsonPayloadPullRequest)


class TestChangeHookConfiguredWithCustomApiRoot(unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self.changeHook = _prepare_github_change_hook(
            strict=False, github_api_endpoint='https://black.magic.io')
        self.master = self.changeHook.master
        fake_headers = {'User-Agent': 'Buildbot'}
        self._http = yield fakehttpclientservice.HTTPClientService.getFakeService(
            self.master, self, 'https://black.magic.io', headers=fake_headers,
            debug=False, verify=False)
        yield self.master.startService()

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.master.stopService()

    @defer.inlineCallbacks
    def _check_pull_request(self, payload):
        self.request = _prepare_request(b'pull_request', payload)
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.addedChanges), 1)

    def test_pull_request(self):
        api_endpoint = '/repos/defunkt/github/commits/05c588ba8cd510ecbe112d020f215facb17817a7'

        self._http.expect('get', api_endpoint, content_json=gitJsonPayloadCommit)
        self._check_pull_request(gitJsonPayloadPullRequest)


class TestChangeHookConfiguredWithCustomApiRootWithAuth(unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        _token = '7e076f41-b73a-4045-a817'
        self.changeHook = _prepare_github_change_hook(
            strict=False, github_api_endpoint='https://black.magic.io',
            token=_token)
        self.master = self.changeHook.master
        fake_headers = {'User-Agent': 'Buildbot',
                'Authorization': 'token ' + _token}
        self._http = yield fakehttpclientservice.HTTPClientService.getFakeService(
            self.master, self, 'https://black.magic.io', headers=fake_headers,
            debug=False, verify=False)
        yield self.master.startService()

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.master.stopService()

    @defer.inlineCallbacks
    def _check_pull_request(self, payload):
        self.request = _prepare_request(b'pull_request', payload)
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.addedChanges), 1)

    def test_pull_request(self):
        api_endpoint = '/repos/defunkt/github/commits/05c588ba8cd510ecbe112d020f215facb17817a7'

        self._http.expect('get', api_endpoint, content_json=gitJsonPayloadCommit)
        self._check_pull_request(gitJsonPayloadPullRequest)


class TestChangeHookConfiguredWithStrict(unittest.TestCase):

    _SECRET = 'somethingreallysecret'

    def setUp(self):
        self.changeHook = _prepare_github_change_hook(strict=True,
                                                      secret=self._SECRET)

    @defer.inlineCallbacks
    def test_signature_ok(self):
        self.request = _prepare_request(b'push', gitJsonPayload,
                                        _secret=self._SECRET)
        yield self.request.test_render(self.changeHook)
        # Can it somehow be merged w/ the same code above in a different class?
        self.assertEqual(len(self.changeHook.master.addedChanges), 2)
        change = self.changeHook.master.addedChanges[0]

        self.assertEqual(change['files'], ['filepath.rb'])
        self.assertEqual(change["repository"],
                         "http://github.com/defunkt/github")
        self.assertEqual(timegm(change["when_timestamp"].utctimetuple()),
                         1203116237)
        self.assertEqual(change["author"],
                         "Fred Flinstone <fred@flinstone.org>")
        self.assertEqual(change["revision"],
                         '41a212ee83ca127e3c8cf465891ab7216a705f59')
        self.assertEqual(change["comments"],
                         "okay i give in")
        self.assertEqual(change["branch"], "master")
        self.assertEqual(change["revlink"],
                         "http://github.com/defunkt/github/commit/"
                         "41a212ee83ca127e3c8cf465891ab7216a705f59")

        change = self.changeHook.master.addedChanges[1]
        self.assertEqual(change['files'], ['modfile', 'removedFile'])
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
    def test_unknown_hash(self):
        bad_hash_type = b'blah'
        self.request = _prepare_request(b'push', gitJsonPayload, headers={
            _HEADER_SIGNATURE: bad_hash_type + b'=doesnotmatter'
        })
        yield self.request.test_render(self.changeHook)
        expected = b'Unknown hash type: ' + bad_hash_type
        self.assertEqual(len(self.changeHook.master.addedChanges), 0)
        self.assertEqual(self.request.written, expected)

    @defer.inlineCallbacks
    def test_signature_nok(self):
        bad_signature = b'sha1=wrongstuff'
        self.request = _prepare_request(b'push', gitJsonPayload, headers={
            _HEADER_SIGNATURE: bad_signature
        })
        yield self.request.test_render(self.changeHook)
        expected = b'Hash mismatch'
        self.assertEqual(len(self.changeHook.master.addedChanges), 0)
        self.assertEqual(self.request.written, expected)

    @defer.inlineCallbacks
    def test_missing_secret(self):
        # override the value assigned in setUp
        self.changeHook = _prepare_github_change_hook(strict=True)
        self.request = _prepare_request(b'push', gitJsonPayload)
        yield self.request.test_render(self.changeHook)
        expected = b'Strict mode is requested while no secret is provided'
        self.assertEqual(len(self.changeHook.master.addedChanges), 0)
        self.assertEqual(self.request.written, expected)

    @defer.inlineCallbacks
    def test_wrong_signature_format(self):
        bad_signature = b'hash=value=something'
        self.request = _prepare_request(b'push', gitJsonPayload, headers={
            _HEADER_SIGNATURE: bad_signature
        })
        yield self.request.test_render(self.changeHook)
        expected = b'Wrong signature format: ' + bad_signature
        self.assertEqual(len(self.changeHook.master.addedChanges), 0)
        self.assertEqual(self.request.written, expected)

    @defer.inlineCallbacks
    def test_signature_missing(self):
        self.request = _prepare_request(b'push', gitJsonPayload)
        yield self.request.test_render(self.changeHook)
        expected = b'Request has no required signature'
        self.assertEqual(len(self.changeHook.master.addedChanges), 0)
        self.assertEqual(self.request.written, expected)


class TestChangeHookConfiguredWithCodebaseValue(unittest.TestCase):

    def setUp(self):
        self.changeHook = _prepare_github_change_hook(codebase='foobar')

    @defer.inlineCallbacks
    def _check_git_with_change(self, payload):
        self.request = _prepare_request(b'push', payload)
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.addedChanges), 2)
        change = self.changeHook.master.addedChanges[0]
        self.assertEqual(change['codebase'], 'foobar')

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
        self.request = _prepare_request(b'push', payload)
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.addedChanges), 2)
        change = self.changeHook.master.addedChanges[0]
        self.assertEqual(change['codebase'], 'foobar-github')

    def test_git_with_change_encoded(self):
        return self._check_git_with_change([gitJsonPayload])

    def test_git_with_change_json(self):
        return self._check_git_with_change(gitJsonPayload)


class TestChangeHookConfiguredWithCustomEventHandler(unittest.TestCase):

    def setUp(self):
        class CustomGitHubEventHandler(GitHubEventHandler):
            def handle_ping(self, _, __):
                self.master.hook_called = True
                return [], None

        self.changeHook = _prepare_github_change_hook(
            **{'class': CustomGitHubEventHandler})

    @defer.inlineCallbacks
    def test_ping(self):
        self.request = _prepare_request(b'ping', b'{}')
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.addedChanges), 0)
        self.assertTrue(self.changeHook.master.hook_called)
