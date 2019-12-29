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

import json

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.changes.bitbucket import BitbucketPullrequestPoller
from buildbot.config import ConfigErrors
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.util import changesource
from buildbot.test.util.logging import LoggingMixin
from buildbot.test.util.misc import TestReactorMixin

gitJsonPayloadSinglePullrequest = """
{
  "rendered": {
    "description": {
      "raw": "PR 1 description",
      "markup": "markdown",
      "html": "<p>PR 1 description</p>",
      "type": "rendered"
    },
    "title": {
      "raw": "Pull request 1",
      "markup": "markdown",
      "html": "<p>Pull request 1</p>",
      "type": "rendered"
    }
  },
  "type": "pullrequest",
  "description": "PR 1 description",
  "links": {
    "decline": {
      "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/pullrequests/1/decline"
    },
    "diffstat": {
      "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/diffstat/defunkt/defunkt:99999999999999999999999999?from_pullrequest_id=1"
    },
    "commits": {
      "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/pullrequests/1/commits"
    },
    "self": {
      "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/pullrequests/1"
    },
    "comments": {
      "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/pullrequests/1/comments"
    },
    "merge": {
      "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/pullrequests/1/merge"
    },
    "html": {
      "href": "https://bitbucket.org/defunkt/defunkt/pull-requests/1"
    },
    "activity": {
      "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/pullrequests/1/activity"
    },
    "diff": {
      "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/diff/defunkt/defunkt:99999999999999999999999999?from_pullrequest_id=1"
    },
    "approve": {
      "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/pullrequests/1/approve"
    },
    "statuses": {
      "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/pullrequests/1/statuses"
    }
  },
  "title": "Pull request 1",
  "close_source_branch": false,
  "reviewers": [],
  "id": 1,
  "destination": {
    "commit": {
      "hash": "999999999999",
      "type": "commit",
      "links": {
        "self": {
          "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/commit/999999999999"
        },
        "html": {
          "href": "https://bitbucket.org/defunkt/defunkt/commits/999999999999"
        }
      }
    },
    "repository": {
      "links": {
        "self": {
          "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt"
        },
        "html": {
          "href": "https://bitbucket.org/defunkt/defunkt"
        },
        "avatar": {
          "href": "avatar_repo_href"
        }
      },
      "type": "repository",
      "name": "defunkt",
      "full_name": "defunkt/defunkt",
      "uuid": "repo_uuid"
    },
    "branch": {
      "name": "master"
    }
  },
  "created_on": "2020-01-01T00:00:00.000000+00:00",
  "summary": {
    "raw": "PR 1",
    "markup": "markdown",
    "html" : "PR 1",
    "type": "rendered"
  },
  "source": {
    "commit": {
      "hash": "111111111111",
      "type": "commit",
      "links": {
        "self": {
          "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/commit/111111111111"
        },
        "html": {
          "href": "https://bitbucket.org/defunkt/defunkt/commits/111111111111"
        }
      }
    },
    "repository": {
      "links": {
        "self": {
          "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt"
        },
        "html": {
          "href": "https://bitbucket.org/defunkt/defunkt"
        },
        "avatar": {
          "href": "avatar_repo_href"
        }
      },
      "type": "repository",
      "name": "defunkt",
      "full_name": "defunkt/defunkt",
      "uuid": "repo_uuid"
    },
    "branch": {
      "name": "pr1-branch"
    }
  },
  "comment_count": 0,
  "state": "OPEN",
  "task_count": 0,
  "participants": [],
  "reason": "",
  "updated_on": "2020-01-01T00:00:00.000000+00:00",
  "author": {
    "display_name": "author_name",
    "uuid": "author_uuid",
    "links": {
      "self": {
        "href": "author_href"
      },
      "html": {
        "href": "author_html"
      },
      "avatar": {
        "href": "author_avatar_url"
      }
    },
    "nickname": "nickname-pr1",
    "type": "user",
    "account_id": "account_id"
  },
  "merge_commit": null,
  "closed_by": null
}
"""

gitJsonPayloadPullRequests = """
{
  "pagelen": 10,
  "values": [
    {
      "description": "PR 1 description",
      "links": {
        "decline": {
          "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/pullrequests/1/decline"
        },
        "diffstat": {
          "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/defunkt/defunkt:99999999999999999999999999?from_pullrequest_id=1"
        },
        "commits": {
          "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/pullrequests/1/commits"
        },
        "self": {
          "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/pullrequests/1"
        },
        "comments": {
          "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/pullrequests/1/comments"
        },
        "merge": {
          "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/pullrequests/1/merge"
        },
        "html": {
          "href": "https://bitbucket.org/defunkt/defunkt/pull-requests/1"
        },
        "activity": {
          "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/pullrequests/1/activity"
        },
        "diff": {
          "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/diff/defunkt/defunkt:99999999999999999999999999?from_pullrequest_id=1"
        },
        "approve": {
          "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/pullrequests/1/approve"
        },
        "statuses": {
          "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/pullrequests/1/statuses"
        }
      },
      "title": "Pull request 1",
      "close_source_branch": false,
      "type": "pullrequest",
      "id": 1,
      "destination": {
        "commit": {
          "hash": "999999999999",
          "type": "commit",
          "links": {
            "self": {
              "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/commit/999999999999"
            },
            "html": {
              "href": "https://bitbucket.org/defunkt/defunkt/commits/999999999999"
            }
          }
        },
        "repository": {
          "links": {
            "self": {
              "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt"
            },
            "html": {
              "href": "https://bitbucket.org/defunkt/defunkt"
            },
            "avatar": {
              "href": "avatar_href"
            }
          },
          "type": "repository",
          "name": "defunkt",
          "full_name": "defunkt/defunkt",
          "uuid": "repo_uuid"
        },
        "branch": {
          "name": "master"
        }
      },
      "created_on": "2020-01-01T00:00:00.000000+00:00",
      "summary": {
        "raw": "PR 1",
        "markup": "markdown",
        "html" : "PR 1",
        "type": "rendered"
      },
      "source": {
        "commit": {
          "hash": "111111111111",
          "type": "commit",
          "links": {
            "self": {
              "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/commit/111111111111"
            },
            "html": {
              "href": "https://bitbucket.org/defunkt/defunkt/commits/111111111111"
            }
          }
        },
        "repository": {
          "links": {
            "self": {
              "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt"
            },
            "html": {
              "href": "https://bitbucket.org/defunkt/defunkt"
            },
            "avatar": {
              "href": "avator_repo_href"
            }
          },
          "type": "repository",
          "name": "defunkt",
          "full_name": "defunkt/defunkt",
          "uuid": "repo_uuid"
        },
        "branch": {
          "name": "pr1-branch"
        }
      },
      "comment_count": 0,
      "state": "OPEN",
      "task_count": 0,
      "reason": "",
      "updated_on": "2020-01-01T00:00:00.000000+00:00",
      "author": {
        "display_name": "author_name",
        "uuid": "author_uuid",
        "links": {
          "self": {
            "href": "author_href"
          },
          "html": {
            "href": "author_html"
          },
          "avatar": {
            "href": "author_avatar_url"
          }
        },
        "nickname": "nickname-pr1",
        "type": "user",
        "account_id": "account_id"
      },
      "merge_commit": null,
      "closed_by": null
    }
  ],
  "page": 1,
  "size": 2
}
"""

gitJsonPayloadRepository = """
{
  "scm": "git",
  "website": null,
  "has_wiki": false,
  "uuid": "repo_uuid",
  "links": {
    "watchers": {
      "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/watchers"
    },
    "branches": {
      "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/refs/branches"
    },
    "tags": {
      "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/refs/tags"
    },
    "commits": {
      "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/commits"
    },
    "clone": [
      {
        "href": "https://defunkt@bitbucket.org/defunkt/defunkt.git",
        "name": "https"
      },
      {
        "href": "git@bitbucket.org:defunkt/defunkt.git",
        "name": "ssh"
      }
    ],
    "self": {
      "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt"
    },
    "source": {
      "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/src"
    },
    "html": {
      "href": "https://bitbucket.org/defunkt/defunkt"
    },
    "avatar": {
      "href": "repo_avatar_href"
    },
    "hooks": {
      "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/hooks"
    },
    "forks": {
      "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/forks"
    },
    "downloads": {
      "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/downloads"
    },
    "pullrequests": {
      "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/pullrequests"
    }
  },
  "fork_policy": "no_forks",
  "name": "defunkt",
  "language": "Language",
  "created_on": "2020-01-01T00:00:00.000000+00:00",
  "mainbranch": {
    "type": "branch",
    "name": "master"
  },
  "full_name": "defunkt/defunkt",
  "has_issues": false,
  "owner": {
    "display_name": "defunkt",
    "uuid": "defunkt_uuid",
    "links": {
      "self": {
        "href": "https://api.bitbucket.org/2.0/users/%7B368a8ac8-9443-4489-ae9c-2ff392122e2d%7D"
      },
      "html": {
        "href": "https://bitbucket.org/%7B368a8ac8-9443-4489-ae9c-2ff392122e2d%7D/"
      },
      "avatar": {
        "href": "https://secure.gravatar.com/avatar/347c11a437c726ecd4294940f85097b6?d=https%3A%2F%2Favatar-management--avatars.us-west-2.prod.public.atl-paas.net%2Finitials%2FTM-2.png"
      }
    },
    "nickname": "user_name",
    "type": "user",
    "account_id": "account_id"
  },
  "updated_on": "2020-01-01T00:00:00.000000+00:00",
  "size": 1,
  "type": "repository",
  "slug": "defunkt",
  "is_private": true,
  "description": "Repository decsription"
}
"""

gitJsonPayloadCommits = """
{
  "pagelen": 10,
  "values": [
    {
      "hash": "11111111111111111111111111",
      "repository": {
        "links": {
          "self": {
            "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt"
          },
          "html": {
            "href": "https://bitbucket.org/defunkt/defunkt"
          },
          "avatar": {
            "href": "https://bytebucket.org/ravatar/%7B2f593a87-d3cb-4d07-82ee-72c10ed809af%7D?ts=c"
          }
        },
        "type": "repository",
        "name": "defunkt",
        "full_name": "defunkt/defunkt",
        "uuid": "user_uuid"
      },
      "links": {
        "self": {
          "href": "commit_href"
        },
        "comments": {
          "href": "comment_href"
        },
        "patch": {
          "href": "patch_href"
        },
        "html": {
          "href": "html_href"
        },
        "diff": {
          "href": "diff_href"
        },
        "approve": {
          "href": "approve_href"
        },
        "statuses": {
          "href": "statuses_href"
        }
      },
      "author": {
        "raw": "defunkt <defunkt@defunkt.null>",
        "type": "author",
        "user": {
          "display_name": "defunkt",
          "uuid": "user_uuid",
          "links": {
            "self": {
              "href": "user_href"
            },
            "html": {
              "href": "user_html"
            },
            "avatar": {
              "href": "user_avatar"
            }
          },
          "nickname": "defunkt",
          "type": "user",
          "account_id": "account_id"
        }
      },
      "summary": {
        "raw": "Update README.md",
        "markup": "markdown",
        "html": "<p>Update README.md</p>",
        "type": "rendered"
      },
      "parents": [
        {
          "hash": "99999999999999999999999999",
          "type": "commit",
          "links": {
            "self": {
              "href": "https://api.bitbucket.org/2.0/repositories/defunkt/defunkt/commit/99999999999999999999999999"
            },
            "html": {
              "href": "https://bitbucket.org/defunkt/defunkt/commits/99999999999999999999999999"
            }
          }
        }
      ],
      "date": "2020-01-01T00:00:00+00:00",
      "message": "Update README.md\\n",
      "type": "commit"
    }
  ],
  "page": 1
}
"""

gitJsonPayloadDiffstat = """
{
    "pagelen": 500,
    "values": [
        {
            "type": "diffstat",
            "status": "modified",
            "lines_removed": 1,
            "lines_added": 2,
            "old": {
                "path": "README.md",
                "type": "commit_file",
                "links": {
                    "self": {
                        "href": "hred_ref"
                    }
                }
            },
            "new": {
                "path": "README.md",
                "type": "commit_file",
                "links": {
                    "self": {
                        "href": "href_ref"
                     }
                }
            }
        }
    ],
    "page": 1,
    "size": 1
}
"""

bitbucketOauthToken = """
{
    "access_token": "token"
}
"""

class TestBitbucketPullrequestPoller(changesource.ChangeSourceMixin,
                                     TestReactorMixin,
                                     LoggingMixin,
                                     unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self):
        self.setUpTestReactor()
        yield self.setUpChangeSource()
        yield self.master.startService()

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.master.stopService()
        yield self.tearDownChangeSource()

    @defer.inlineCallbacks
    def newChangeSource(self,
                        owner,
                        slug,
                        endpoint='https://api.bitbucket.org',
                        oauth_key="foo",
                        oauth_secret="bar",
                        **kwargs):
        http_headers = {'User-Agent': 'Buildbot'}
        self._http = yield fakehttpclientservice.HTTPClientService.getFakeService(
            self.master, self, endpoint, headers=http_headers)
        self._oauthhttp = yield fakehttpclientservice.HTTPClientService.getFakeService(
                self.master, self, 'https://bitbucket.org/site/oauth2/access_token',
                auth=(oauth_key, oauth_secret), debug=None, verify=None, headers=http_headers)
        self.changesource = BitbucketPullrequestPoller(owner, slug, oauth_key=oauth_key,
                oauth_secret=oauth_secret, **kwargs)

    @defer.inlineCallbacks
    def startChangeSource(self):
        yield self.changesource.setServiceParent(self.master)
        yield self.attachChangeSource(self.changesource)

    def assertDictSubset(self, expected_dict, response_dict):
        expected = {}
        for key in expected_dict.keys():
            self.assertIn(key, set(response_dict.keys()))
            expected[key] = response_dict[key]
        self.assertDictEqual(expected_dict, expected)

    @defer.inlineCallbacks
    def test_describe(self):
        yield self.newChangeSource('defunkt', 'defunkt')
        yield self.startChangeSource()
        self.assertEqual(
            "BitbucketPullrequestPoller watching the Bitbucket repository {}/{}".
            format('defunkt', 'defunkt'), self.changesource.describe())

    @defer.inlineCallbacks
    def test_default_name(self):
        yield self.newChangeSource('defunkt', 'defunkt')
        yield self.startChangeSource()
        self.assertEqual("BitbucketPullrequestPoller:{}/{}".format(
            'defunkt', 'defunkt'), self.changesource.name)

    @defer.inlineCallbacks
    def test_custom_name(self):
        yield self.newChangeSource('defunkt', 'defunkt', name="MyName")
        yield self.startChangeSource()
        self.assertEqual("MyName", self.changesource.name)

    @defer.inlineCallbacks
    def test_SimplePR(self):
        yield self.newChangeSource(
            'defunkt', 'defunkt')
        self._oauthhttp.expect(
            method='post',
            ep='',
            data={'grant_type': 'client_credentials'},
            content_json=json.loads(bitbucketOauthToken))
        self._http.expect(
            method='get',
            ep='/2.0/repositories/defunkt/defunkt/pullrequests',
            content_json=json.loads(gitJsonPayloadPullRequests))
        self._http.expect(
            method='get',
            ep='/2.0/repositories/defunkt/defunkt/pullrequests/1',
            content_json=json.loads(gitJsonPayloadSinglePullrequest))
        self._http.expect(
            method='get',
            ep='/2.0/repositories/defunkt/defunkt',
            content_json=json.loads(gitJsonPayloadRepository))
        self._http.expect(
            method='get',
            ep='/2.0/repositories/defunkt/defunkt',
            content_json=json.loads(gitJsonPayloadRepository))
        self._http.expect(
            method='get',
            ep='/2.0/repositories/defunkt/defunkt/pullrequests/1/commits',
            content_json=json.loads(gitJsonPayloadCommits))
        self._http.expect(
            method='get',
            ep='/2.0/repositories/defunkt/defunkt/pullrequests/1/diffstat',
            content_json=json.loads(gitJsonPayloadDiffstat))
        yield self.startChangeSource()
        yield self.changesource.poll()

        self.assertEqual(len(self.master.data.updates.changesAdded), 1)
        change = self.master.data.updates.changesAdded[0]
        self.assertEqual(change['author'], 'defunkt <defunkt@defunkt.null>')
        self.assertEqual(change['revision'],
                         '111111111111')
        self.assertEqual(change['revlink'],
                         'https://bitbucket.org/defunkt/defunkt/pull-requests/1')
        self.assertEqual(change['branch'], 'pr1-branch')
        self.assertEqual(change['repository'],
                         'https://defunkt@bitbucket.org/defunkt/defunkt.git')
        self.assertEqual(change['files'], ['README.md'])
        self.assertEqual(change['committer'], None)

        self.assertEqual(change["comments"],
                         "Bitbucket Pull Request #1 (111111111111)\n"
                         "Pull request 1\n"
                         "PR 1 description")

    @defer.inlineCallbacks
    def test_failOauth(self):
        yield self.newChangeSource(
            'defunkt', 'defunkt')
        self._oauthhttp.expect(
            method='post',
            ep='',
            data={'grant_type': 'client_credentials'},
            code=400,
            content_json={
                "error_description": "Unsupported grant type: None",
                "error": "invalid_grant"})
        self.setUpLogging()
        yield self.startChangeSource()
        yield self.changesource.poll()
        self.assertLogged('400: unable to authenticate to Bitbucket')

    @defer.inlineCallbacks
    def test_wrongBranch(self):
        yield self.newChangeSource(
            'defunkt', 'defunkt', branches=['wrongBranch'])
        self._oauthhttp.expect(
            method='post',
            ep='',
            data={'grant_type': 'client_credentials'},
            content_json=json.loads(bitbucketOauthToken))
        self._http.expect(
            method='get',
            ep='/2.0/repositories/defunkt/defunkt/pullrequests',
            content_json=json.loads(gitJsonPayloadPullRequests))

        yield self.startChangeSource()
        yield self.changesource.poll()
        self.assertEqual(len(self.master.data.updates.changesAdded), 0)

    @defer.inlineCallbacks
    def test_PRfilter(self):
        yield self.newChangeSource(
            'defunkt',
            'defunkt',
            pullrequest_filter=lambda pr: pr['id'] == 1337
        )
        self._oauthhttp.expect(
            method='post',
            ep='',
            data={'grant_type': 'client_credentials'},
            content_json=json.loads(bitbucketOauthToken))
        self._http.expect(
            method='get',
            ep='/2.0/repositories/defunkt/defunkt/pullrequests',
            content_json=json.loads(gitJsonPayloadPullRequests))
        yield self.startChangeSource()
        yield self.changesource.poll()
        self.assertEqual(len(self.master.data.updates.changesAdded), 0)

    @defer.inlineCallbacks
    def test_failCommitters(self):
        yield self.newChangeSource('defunkt', 'defunkt')
        self._oauthhttp.expect(
            method='post',
            ep='',
            data={'grant_type': 'client_credentials'},
            content_json=json.loads(bitbucketOauthToken))
        self._http.expect(
            method='get',
            ep='/2.0/repositories/defunkt/defunkt/pullrequests',
            content_json=json.loads(gitJsonPayloadPullRequests))
        self._http.expect(
            method='get',
            ep='/2.0/repositories/defunkt/defunkt/pullrequests/1',
            content_json=json.loads(gitJsonPayloadSinglePullrequest))
        self._http.expect(
            method='get',
            ep='/2.0/repositories/defunkt/defunkt',
            content_json=json.loads(gitJsonPayloadRepository))
        self._http.expect(
            method='get',
            ep='/2.0/repositories/defunkt/defunkt',
            content_json=json.loads(gitJsonPayloadRepository))
        self._http.expect(
            method='get',
            ep='/2.0/repositories/defunkt/defunkt/pullrequests/1/commits',
            content_json=json.loads('{"values": [{}]}'))
        self._http.expect(
            method='get',
            ep='/2.0/repositories/defunkt/defunkt/pullrequests/1/diffstat',
            content_json=json.loads(gitJsonPayloadDiffstat))
        yield self.startChangeSource()
        yield self.assertFailure(self.changesource.poll(), KeyError)

    @defer.inlineCallbacks
    def test_wrongRepoLink(self):
        yield self.assertFailure(
            self.newChangeSource(
                'defunkt', 'defunkt', repository_type='defunkt'),
            ConfigErrors)
