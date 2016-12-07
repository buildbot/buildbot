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
# Copyright Manba Team
import calendar
from StringIO import StringIO

from dateutil.parser import parse as dateparse

from twisted.internet.defer import inlineCallbacks
from twisted.trial import unittest

import buildbot.www.change_hook as change_hook
from buildbot.test.fake.web import FakeRequest
from buildbot.test.fake.web import fakeMasterForHooks
from buildbot.www.hooks.bitbucket import _HEADER_CT
from buildbot.www.hooks.bitbucket import _HEADER_EVENT


gitJsonPayload = """{
    "canon_url": "https://bitbucket.org",
    "commits": [
        {
            "author": "marcus",
            "branch": "master",
            "files": [
                {
                    "file": "somefile.py",
                    "type": "modified"
                }
            ],
            "message": "Added some more things to somefile.py",
            "node": "620ade18607a",
            "parents": [
                "702c70160afc"
            ],
            "raw_author": "Marcus Bertrand <marcus@somedomain.com>",
            "raw_node": "620ade18607ac42d872b568bb92acaa9a28620e9",
            "revision": null,
            "size": -1,
            "timestamp": "2012-05-30 05:58:56",
            "utctimestamp": "2012-05-30 03:58:56+00:00"
        }
    ],
    "repository": {
        "absolute_url": "/marcus/project-x/",
        "fork": false,
        "is_private": true,
        "name": "Project X",
        "owner": "marcus",
        "scm": "git",
        "slug": "project-x",
        "website": "https://atlassian.com/"
    },
    "user": "marcus"
}"""

mercurialJsonPayload = """{
    "canon_url": "https://bitbucket.org",
    "commits": [
        {
            "author": "marcus",
            "branch": "master",
            "files": [
                {
                    "file": "somefile.py",
                    "type": "modified"
                }
            ],
            "message": "Added some more things to somefile.py",
            "node": "620ade18607a",
            "parents": [
                "702c70160afc"
            ],
            "raw_author": "Marcus Bertrand <marcus@somedomain.com>",
            "raw_node": "620ade18607ac42d872b568bb92acaa9a28620e9",
            "revision": null,
            "size": -1,
            "timestamp": "2012-05-30 05:58:56",
            "utctimestamp": "2012-05-30 03:58:56+00:00"
        }
    ],
    "repository": {
        "absolute_url": "/marcus/project-x/",
        "fork": false,
        "is_private": true,
        "name": "Project X",
        "owner": "marcus",
        "scm": "hg",
        "slug": "project-x",
        "website": "https://atlassian.com/"
    },
    "user": "marcus"
}"""

gitJsonNoCommitsPayload = """{
    "canon_url": "https://bitbucket.org",
    "commits": [
    ],
    "repository": {
        "absolute_url": "/marcus/project-x/",
        "fork": false,
        "is_private": true,
        "name": "Project X",
        "owner": "marcus",
        "scm": "git",
        "slug": "project-x",
        "website": "https://atlassian.com/"
    },
    "user": "marcus"
}"""

mercurialJsonNoCommitsPayload = """{
    "canon_url": "https://bitbucket.org",
    "commits": [
    ],
    "repository": {
        "absolute_url": "/marcus/project-x/",
        "fork": false,
        "is_private": true,
        "name": "Project X",
        "owner": "marcus",
        "scm": "hg",
        "slug": "project-x",
        "website": "https://atlassian.com/"
    },
    "user": "marcus"
}"""


_CT_ENCODED = 'application/x-www-form-urlencoded'
_CT_JSON = 'application/json'


#
# Bitbucket POST service sends content header as 'application/x-www-form-urlencoded':
# https://confluence.atlassian.com/bitbucket/post-service-management-223216518.html
#
# POST service is deprecated and replaced by Bitbucket webook events
#
def _prepare_request(payload, headers=None, change_dict=None):
    headers = {} if headers is None else headers
    request = FakeRequest(change_dict)
    request.uri = "/change_hook/bitbucket"
    request.method = "POST"

    if isinstance(payload, str):
        request.content = StringIO(payload)
        request.received_headers[_HEADER_CT] = _CT_JSON
    else:
        request.args['payload'] = payload
        request.received_headers[_HEADER_CT] = _CT_ENCODED

    request.received_headers.update(headers)
    return request


class TestChangeHookConfiguredWithBitbucketChange(unittest.TestCase):

    """Unit tests for BitBucket Change Hook
    """

    def setUp(self):
        self.change_hook = change_hook.ChangeHookResource(
            dialects={'bitbucket': True}, master=fakeMasterForHooks())

    @inlineCallbacks
    def testGitWithChange(self):
        request = _prepare_request([gitJsonPayload])

        yield request.test_render(self.change_hook)

        self.assertEqual(len(self.change_hook.master.addedChanges), 1)
        commit = self.change_hook.master.addedChanges[0]

        self.assertEqual(commit['files'], ['somefile.py'])
        self.assertEqual(
            commit['repository'], 'https://bitbucket.org/marcus/project-x/')
        self.assertEqual(
            calendar.timegm(commit['when_timestamp'].utctimetuple()),
            1338350336
        )
        self.assertEqual(
            commit['author'], 'Marcus Bertrand <marcus@somedomain.com>')
        self.assertEqual(
            commit['revision'], '620ade18607ac42d872b568bb92acaa9a28620e9')
        self.assertEqual(
            commit['comments'], 'Added some more things to somefile.py')
        self.assertEqual(commit['branch'], 'master')
        self.assertEqual(
            commit['revlink'],
            'https://bitbucket.org/marcus/project-x/commits/'
            '620ade18607ac42d872b568bb92acaa9a28620e9'
        )

    @inlineCallbacks
    def testGitWithNoCommitsPayload(self):
        request = _prepare_request([gitJsonNoCommitsPayload])

        yield request.test_render(self.change_hook)

        self.assertEqual(len(self.change_hook.master.addedChanges), 0)
        self.assertEqual(request.written, 'no changes found')

    @inlineCallbacks
    def testMercurialWithChange(self):
        request = _prepare_request([mercurialJsonPayload])

        yield request.test_render(self.change_hook)

        self.assertEqual(len(self.change_hook.master.addedChanges), 1)
        commit = self.change_hook.master.addedChanges[0]

        self.assertEqual(commit['files'], ['somefile.py'])
        self.assertEqual(
            commit['repository'], 'https://bitbucket.org/marcus/project-x/')
        self.assertEqual(
            calendar.timegm(commit['when_timestamp'].utctimetuple()),
            1338350336
        )
        self.assertEqual(
            commit['author'], 'Marcus Bertrand <marcus@somedomain.com>')
        self.assertEqual(
            commit['revision'], '620ade18607ac42d872b568bb92acaa9a28620e9')
        self.assertEqual(
            commit['comments'], 'Added some more things to somefile.py')
        self.assertEqual(commit['branch'], 'master')
        self.assertEqual(
            commit['revlink'],
            'https://bitbucket.org/marcus/project-x/commits/'
            '620ade18607ac42d872b568bb92acaa9a28620e9'
        )

    @inlineCallbacks
    def testMercurialWithNoCommitsPayload(self):
        request = _prepare_request([mercurialJsonNoCommitsPayload])

        yield request.test_render(self.change_hook)

        self.assertEqual(len(self.change_hook.master.addedChanges), 0)
        self.assertEqual(request.written, 'no changes found')

    @inlineCallbacks
    def testWithNoJson(self):
        request = _prepare_request([])

        yield request.test_render(self.change_hook)
        self.assertEqual(len(self.change_hook.master.addedChanges), 0)
        self.assertEqual(request.written, 'Error processing changes.')
        request.setResponseCode.assert_called_with(
            500, 'Error processing changes.')
        self.assertEqual(len(self.flushLoggedErrors()), 1)

    @inlineCallbacks
    def testGitWithChangeAndProject(self):
        change_dict = {'project': ['project-name']}
        request = _prepare_request([gitJsonPayload], change_dict=change_dict)

        yield request.test_render(self.change_hook)

        self.assertEqual(len(self.change_hook.master.addedChanges), 1)
        commit = self.change_hook.master.addedChanges[0]

        self.assertEqual(commit['project'], 'project-name')


gitRepoPushJsonPayload = """{
  "actor": {
    "type": "user",
    "username": "emmap1",
    "display_name": "Emma",
    "uuid": "{a54f16da-24e9-4d7f-a3a7-b1ba2cd98aa3}",
    "links": {
      "self": {
        "href": "https://api.bitbucket.org/api/2.0/users/emmap1"
      },
      "html": {
        "href": "https://api.bitbucket.org/emmap1"
      },
      "avatar": {
        "href": "https://bitbucket-api-assetroot.s3.amazonaws.com/c/photos/2015/Feb/26/3613917261-0-emmap1-avatar_avatar.png"
      }
    }
  },
  "repository": {
    "type": "repository",
    "links": {
      "self": {
        "href": "https://api.bitbucket.org/api/2.0/repositories/bitbucket/bitbucket"
      },
      "html": {
        "href": "https://api.bitbucket.org/bitbucket/bitbucket"
      },
      "avatar": {
        "href": "https://api-staging-assetroot.s3.amazonaws.com/c/photos/2014/Aug/01/bitbucket-logo-2629490769-3_avatar.png"
      }
    },
    "uuid": "{673a6070-3421-46c9-9d48-90745f7bfe8e}",
    "project": {
      "type": "project",
      "project": "Untitled project",
      "uuid": "{3b7898dc-6891-4225-ae60-24613bb83080}",
      "links": {
        "html": {
          "href": "https://bitbucket.org/account/user/teamawesome/projects/proj"
        },
        "avatar": {
          "href": "https://bitbucket.org/account/user/teamawesome/projects/proj/avatar/32"
        }
      },
      "key": "proj"
    },
    "full_name": "team_name/repo_name",
    "name": "repo_name",
    "website": "https://mywebsite.com/",
    "owner": {
      "type": "user",
      "username": "emmap1",
      "display_name": "Emma",
      "uuid": "{a54f16da-24e9-4d7f-a3a7-b1ba2cd98aa3}",
      "links": {
        "self": {
          "href": "https://api.bitbucket.org/api/2.0/users/emmap1"
        },
        "html": {
          "href": "https://api.bitbucket.org/emmap1"
        },
        "avatar": {
          "href": "https://bitbucket-api-assetroot.s3.amazonaws.com/c/photos/2015/Feb/26/3613917261-0-emmap1-avatar_avatar.png"
        }
      }
    },
    "scm": "git",
    "is_private": true
  },
  "push": {
    "changes": [
      {
        "new": {
          "type": "branch",
          "name": "master",
          "target": {
            "type": "commit",
            "hash": "709d658dc5b6d6afcd46049c2f332ee3f515a67d",
            "author": {
              "raw": "Emma <emmap1@bitbucket.com>",
              "user": {
                "type": "user",
                "username": "emmap1",
                "display_name": "Emma",
                "uuid": "{a54f16da-24e9-4d7f-a3a7-b1ba2cd98aa3}",
                "links": {
                  "self": {
                    "href": "https://api.bitbucket.org/api/2.0/users/emmap1"
                  },
                  "html": {
                    "href": "https://api.bitbucket.org/emmap1"
                  },
                  "avatar": {
                    "href": "https://bitbucket-api-assetroot.s3.amazonaws.com/c/photos/2015/Feb/26/3613917261-0-emmap1-avatar_avatar.png"
                  }
                }
              }
            },
            "message": "new commit message",
            "date": "2015-06-09T03:34:49+00:00",
            "parents": [
              {
                "type": "commit",
                "hash": "1e65c05c1d5171631d92438a13901ca7dae9618c",
                "links": {
                  "self": {
                    "href": "https://api.bitbucket.org/2.0/repositories/user_name/repo_name/commit/8cbbd65829c7ad834a97841e0defc965718036a0"
                  },
                  "html": {
                    "href": "https://bitbucket.org/user_name/repo_name/commits/8cbbd65829c7ad834a97841e0defc965718036a0"
                  }
                }
              }
            ],
            "links": {
              "self": {
                "href": "https://api.bitbucket.org/2.0/repositories/user_name/repo_name/commit/c4b2b7914156a878aa7c9da452a09fb50c2091f2"
              },
              "html": {
                "href": "https://bitbucket.org/user_name/repo_name/commits/c4b2b7914156a878aa7c9da452a09fb50c2091f2"
              }
            }
          },
          "links": {
            "self": {
              "href": "https://api.bitbucket.org/2.0/repositories/user_name/repo_name/refs/branches/master"
            },
            "commits": {
              "href": "https://api.bitbucket.org/2.0/repositories/user_name/repo_name/commits/master"
            },
            "html": {
              "href": "https://bitbucket.org/user_name/repo_name/branch/master"
            }
          }
        },
        "old": {
          "type": "branch",
          "name": "master",
          "target": {
            "type": "commit",
            "hash": "1e65c05c1d5171631d92438a13901ca7dae9618c",
            "author": {
              "raw": "Emma <emmap1@bitbucket.com>",
              "user": {
                "type": "user",
                "username": "emmap1",
                "display_name": "Emma",
                "uuid": "{a54f16da-24e9-4d7f-a3a7-b1ba2cd98aa3}",
                "links": {
                  "self": {
                    "href": "https://api.bitbucket.org/api/2.0/users/emmap1"
                  },
                  "html": {
                    "href": "https://api.bitbucket.org/emmap1"
                  },
                  "avatar": {
                    "href": "https://bitbucket-api-assetroot.s3.amazonaws.com/c/photos/2015/Feb/26/3613917261-0-emmap1-avatar_avatar.png"
                  }
                }
              }
            },
            "message": "old commit message",
            "date": "2015-06-08T21:34:56+00:00",
            "parents": [
              {
                "type": "commit",
                "hash": "e0d0c2041e09746be5ce4b55067d5a8e3098c843",
                "links": {
                  "self": {
                    "href": "https://api.bitbucket.org/2.0/repositories/user_name/repo_name/commit/9c4a3452da3bc4f37af5a6bb9c784246f44406f7"
                  },
                  "html": {
                    "href": "https://bitbucket.org/user_name/repo_name/commits/9c4a3452da3bc4f37af5a6bb9c784246f44406f7"
                  }
                }
              }
            ],
            "links": {
              "self": {
                "href": "https://api.bitbucket.org/2.0/repositories/user_name/repo_name/commit/b99ea6dad8f416e57c5ca78c1ccef590600d841b"
              },
              "html": {
                "href": "https://bitbucket.org/user_name/repo_name/commits/b99ea6dad8f416e57c5ca78c1ccef590600d841b"
              }
            }
          },
          "links": {
            "self": {
              "href": "https://api.bitbucket.org/2.0/repositories/user_name/repo_name/refs/branches/master"
            },
            "commits": {
              "href": "https://api.bitbucket.org/2.0/repositories/user_name/repo_name/commits/master"
            },
            "html": {
              "href": "https://bitbucket.org/user_name/repo_name/branch/master"
            }
          }
        },
        "links": {
          "html": {
            "href": "https://bitbucket.org/user_name/repo_name/branches/compare/c4b2b7914156a878aa7c9da452a09fb50c2091f2..b99ea6dad8f416e57c5ca78c1ccef590600d841b"
          },
          "diff": {
            "href": "https://api.bitbucket.org/2.0/repositories/user_name/repo_name/diff/c4b2b7914156a878aa7c9da452a09fb50c2091f2..b99ea6dad8f416e57c5ca78c1ccef590600d841b"
          },
          "commits": {
            "href": "https://api.bitbucket.org/2.0/repositories/user_name/repo_name/commits?include=c4b2b7914156a878aa7c9da452a09fb50c2091f2&exclude=b99ea6dad8f416e57c5ca78c1ccef590600d841b"
          }
        },
        "created": false,
        "forced": false,
        "closed": false,
        "commits": [
          {
            "hash": "03f4a7270240708834de475bcf21532d6134777e",
            "type": "commit",
            "message": "commit message",
            "author": {
              "raw": "Emma <emmap1@bitbucket.com>",
              "user": {
                "type": "user",
                "username": "emmap1",
                "display_name": "Emma",
                "uuid": "{a54f16da-24e9-4d7f-a3a7-b1ba2cd98aa3}",
                "links": {
                  "self": {
                    "href": "https://api.bitbucket.org/api/2.0/users/emmap1"
                  },
                  "html": {
                    "href": "https://api.bitbucket.org/emmap1"
                  },
                  "avatar": {
                    "href": "https://bitbucket-api-assetroot.s3.amazonaws.com/c/photos/2015/Feb/26/3613917261-0-emmap1-avatar_avatar.png"
                  }
                }
              }
            },
            "links": {
              "self": {
                "href": "https://api.bitbucket.org/2.0/repositories/user/repo/commit/03f4a7270240708834de475bcf21532d6134777e"
              },
              "html": {
                "href": "https://bitbucket.org/user/repo/commits/03f4a7270240708834de475bcf21532d6134777e"
              }
            }
          }
        ],
        "truncated": false
      }
    ]
  }
}
"""


gitRepoPullRequestCreatedJsonPayload = """{
   "repository": {
      "full_name": "team_name/repo_name",
      "owner": {
         "display_name": "Team_Name",
         "type": "team",
         "username": "team_name",
         "uuid": "{1a6c626d-8394-4b11-b256-a51f3401aec1}",
         "links": {
            "self": {
               "href": "https://api.bitbucket.org/2.0/teams/team_name"
            },
            "avatar": {
               "href": "https://bitbucket.org/account/team_name/avatar/32/"
            },
            "html": {
               "href": "https://bitbucket.org/team_name/"
            }
         }
      },
      "uuid": "{c7ba4614-f171-1310-10cf-a4b72aeebd31}",
      "scm": "git",
      "website": "",
      "name": "repo_name",
      "is_private": true,
      "type": "repository",
      "links": {
         "self": {
            "href": "https://api.bitbucket.org/2.0/repositories/team_name/repo_name"
         },
         "avatar": {
            "href": "https://bitbucket.org/team_name/repo_name/avatar/32/"
         },
         "html": {
            "href": "https://bitbucket.org/team_name/repo_name"
         }
      },
      "project": {
         "name": "repo_name",
         "type": "project",
         "links": {
            "self": {
               "href": "https://api.bitbucket.org/2.0/teams/team_name/projects/PKEY"
            },
            "avatar": {
               "href": "https://bitbucket.org/account/user/team_name/projects/PKEY/avatar/32"
            },
            "html": {
               "href": "https://bitbucket.org/account/user/team_name/projects/PKEY"
            }
         },
         "uuid": "{b8de53c2-3361-233a-1c61-aea422adcb61}",
         "key": "PKEY"
      }
   },
   "actor": {
      "display_name": "Emma",
      "type": "user",
      "username": "emmap1",
      "uuid": "{a54f16da-24e9-4d7f-a3a7-b1ba2cd98aa3}",
      "links": {
         "self": {
            "href": "https://api.bitbucket.org/2.0/users/emmap1"
         },
         "avatar": {
            "href": "https://bitbucket.org/account/emmap1/avatar/32/"
         },
         "html": {
            "href": "https://bitbucket.org/emmap1/"
         }
      }
   },
   "pullrequest": {
      "id": 2,
      "task_count": 0,
      "reason": "",
      "title": "Master buildbot test",
      "comment_count": 0,
      "destination": {
         "repository": {
            "name": "repo_name",
            "links": {
               "self": {
                  "href": "https://api.bitbucket.org/2.0/repositories/team_name/repo_name"
               },
               "avatar": {
                  "href": "https://bitbucket.org/team_name/repo_name/avatar/32/"
               },
               "html": {
                  "href": "https://bitbucket.org/team_name/repo_name"
               }
            },
            "full_name": "team_name/repo_name",
            "uuid": "{c7ba4614-f171-1310-10cf-a4b72aeebd31}",
            "type": "repository"
         },
         "branch": {
            "name": "master-buildbot-test2"
         },
         "commit": {
            "hash": "e715de0a3ec1",
            "links": {
               "self": {
                  "href": "https://api.bitbucket.org/2.0/repositories/team_name/repo_name/commit/e7259e0d3ec5"
               }
            }
         }
      },
      "state": "OPEN",
      "type": "pullrequest",
      "author": {
         "display_name": "Emma",
         "type": "user",
         "username": "emmap1",
         "uuid": "{a54f16da-24e9-4d7f-a3a7-b1ba2cd98aa3}",
         "links": {
            "self": {
               "href": "https://api.bitbucket.org/2.0/users/emmap1"
            },
            "avatar": {
               "href": "https://bitbucket.org/account/emmap1/avatar/32/"
            },
            "html": {
               "href": "https://bitbucket.org/emmap1/"
            }
         }
      },
      "reviewers": [

      ],
      "created_on": "2016-12-06T15:34:56.496384+00:00",
      "close_source_branch": false,
      "merge_commit": null,
      "description": "* Trigger Webhook\\r\\n\\r\\n* Trigger Webhook\\r\\n\\r\\n* Trigger Webhook\\r\\n\\r\\n* Trigger Webhook\\r\\n\\r\\n* Trigger Webhook",
      "participants": [

      ],
      "links": {
         "merge": {
            "href": "https://api.bitbucket.org/2.0/repositories/team_name/repo_name/pullrequests/2/merge"
         },
         "activity": {
            "href": "https://api.bitbucket.org/2.0/repositories/team_name/repo_name/pullrequests/2/activity"
         },
         "decline": {
            "href": "https://api.bitbucket.org/2.0/repositories/team_name/repo_name/pullrequests/2/decline"
         },
         "statuses": {
            "href": "https://api.bitbucket.org/2.0/repositories/team_name/repo_name/pullrequests/2/statuses"
         },
         "diff": {
            "href": "https://api.bitbucket.org/2.0/repositories/team_name/repo_name/pullrequests/2/diff"
         },
         "self": {
            "href": "https://api.bitbucket.org/2.0/repositories/team_name/repo_name/pullrequests/2"
         },
         "approve": {
            "href": "https://api.bitbucket.org/2.0/repositories/team_name/repo_name/pullrequests/2/approve"
         },
         "comments": {
            "href": "https://api.bitbucket.org/2.0/repositories/team_name/repo_name/pullrequests/2/comments"
         },
         "commits": {
            "href": "https://api.bitbucket.org/2.0/repositories/team_name/repo_name/pullrequests/2/commits"
         },
         "html": {
            "href": "https://bitbucket.org/team_name/repo_name/pull-requests/2"
         }
      },
      "closed_by": null,
      "source": {
         "repository": {
            "name": "repo_name",
            "links": {
               "self": {
                  "href": "https://api.bitbucket.org/2.0/repositories/team_name/repo_name"
               },
               "avatar": {
                  "href": "https://bitbucket.org/team_name/repo_name/avatar/32/"
               },
               "html": {
                  "href": "https://bitbucket.org/team_name/repo_name"
               }
            },
            "full_name": "team_name/repo_name",
            "uuid": "{c7ba4614-f171-1310-10cf-a4b72aeebd31}",
            "type": "repository"
         },
         "branch": {
            "name": "master-buildbot-test"
         },
         "commit": {
            "hash": "af319f4c0f50",
            "links": {
               "self": {
                  "href": "https://api.bitbucket.org/2.0/repositories/team_name/repo_name/commit/df98dc8f0f53"
               }
            }
         }
      },
      "updated_on": "2016-12-06T15:34:56.517784+00:00"
   }
}
"""

gitRepoPullRequestUpdatedJsonPayload = """{
   "actor":{
      "username":"emmap1",
      "display_name":"Emma",
      "uuid":"{a54f16da-24e9-4d7f-a3a7-b1ba2cd98aa3}",
      "type":"user",
      "links":{
         "avatar":{
            "href":"https://bitbucket.org/account/emmap1/avatar/32/"
         },
         "html":{
            "href":"https://bitbucket.org/emmap1/"
         },
         "self":{
            "href":"https://api.bitbucket.org/2.0/users/emmap1"
         }
      }
   },
   "repository":{
      "full_name":"team_name/repo_name",
      "website":"",
      "type":"repository",
      "project":{
         "key":"PKEY",
         "uuid":"{c7de53c5-8333-436a-9c64-ceb970accb82}",
         "type":"project",
         "name":"Project name",
         "links":{
            "avatar":{
               "href":"https://bitbucket.org/account/user/team_name/projects/PKEY/avatar/32"
            },
            "html":{
               "href":"https://bitbucket.org/account/user/team_name/projects/PKEY"
            },
            "self":{
               "href":"https://api.bitbucket.org/2.0/teams/team_name/projects/PKEY"
            }
         }
      },
      "links":{
         "avatar":{
            "href":"https://bitbucket.org/team_name/repo_name/avatar/32/"
         },
         "html":{
            "href":"https://bitbucket.org/team_name/repo_name"
         },
         "self":{
            "href":"https://api.bitbucket.org/2.0/repositories/team_name/repo_name"
         }
      },
      "scm":"git",
      "is_private":true,
      "owner":{
         "username":"team_name",
         "display_name":"Team_Name",
         "uuid":"{1a6c626d-8390-4b19-b216-b51f3401aec5}",
         "type":"team",
         "links":{
            "avatar":{
               "href":"https://bitbucket.org/account/team_name/avatar/32/"
            },
            "html":{
               "href":"https://bitbucket.org/team_name/"
            },
            "self":{
               "href":"https://api.bitbucket.org/2.0/teams/team_name"
            }
         }
      },
      "uuid":"{47ab6377-f541-4710-80cf-e4b72aeebd35}",
      "name":"repo_name"
   },
   "pullrequest":{
      "comment_count":1,
      "reviewers":[

      ],
      "participants":[
         {
            "approved":false,
            "user":{
               "username":"emmap1",
               "display_name":"Emma",
               "uuid":"{a54f16da-24e9-4d7f-a3a7-b1ba2cd98aa3}",
               "type":"user",
               "links":{
                  "avatar":{
                     "href":"https://bitbucket.org/account/emmap1/avatar/32/"
                  },
                  "html":{
                     "href":"https://bitbucket.org/emmap1/"
                  },
                  "self":{
                     "href":"https://api.bitbucket.org/2.0/users/emmap1"
                  }
               }
            },
            "type":"participant",
            "role":"PARTICIPANT"
         }
      ],
      "task_count":0,
      "links":{
         "statuses":{
            "href":"https://api.bitbucket.org/2.0/repositories/team_name/repo_name/pullrequests/2/statuses"
         },
         "comments":{
            "href":"https://api.bitbucket.org/2.0/repositories/team_name/repo_name/pullrequests/2/comments"
         },
         "merge":{
            "href":"https://api.bitbucket.org/2.0/repositories/team_name/repo_name/pullrequests/2/merge"
         },
         "self":{
            "href":"https://api.bitbucket.org/2.0/repositories/team_name/repo_name/pullrequests/2"
         },
         "activity":{
            "href":"https://api.bitbucket.org/2.0/repositories/team_name/repo_name/pullrequests/2/activity"
         },
         "html":{
            "href":"https://bitbucket.org/team_name/repo_name/pull-requests/2"
         },
         "commits":{
            "href":"https://api.bitbucket.org/2.0/repositories/team_name/repo_name/pullrequests/2/commits"
         },
         "diff":{
            "href":"https://api.bitbucket.org/2.0/repositories/team_name/repo_name/pullrequests/2/diff"
         },
         "decline":{
            "href":"https://api.bitbucket.org/2.0/repositories/team_name/repo_name/pullrequests/2/decline"
         },
         "approve":{
            "href":"https://api.bitbucket.org/2.0/repositories/team_name/repo_name/pullrequests/2/approve"
         }
      },
      "close_source_branch":false,
      "state":"OPEN",
      "closed_by":null,
      "merge_commit":null,
      "source":{
         "commit":{
            "hash":"df98dc8f0f53",
            "links":{
               "self":{
                  "href":"https://api.bitbucket.org/2.0/repositories/team_name/repo_name/commit/df98dc8f0f53"
               }
            }
         },
         "branch":{
            "name":"master-buildbot-test"
         },
         "repository":{
            "full_name":"team_name/repo_name",
            "uuid":"{47ab6377-f541-4710-80cf-e4b72aeebd35}",
            "type":"repository",
            "name":"repo_name",
            "links":{
               "avatar":{
                  "href":"https://bitbucket.org/team_name/repo_name/avatar/32/"
               },
               "html":{
                  "href":"https://bitbucket.org/team_name/repo_name"
               },
               "self":{
                  "href":"https://api.bitbucket.org/2.0/repositories/team_name/repo_name"
               }
            }
         }
      },
      "id":2,
      "title":"Master buildbot test",
      "updated_on":"2016-12-06T16:51:28.027419+00:00",
      "destination":{
         "commit":{
            "hash":"e7259e0d3ec5",
            "links":{
               "self":{
                  "href":"https://api.bitbucket.org/2.0/repositories/team_name/repo_name/commit/e7259e0d3ec5"
               }
            }
         },
         "branch":{
            "name":"master-buildbot-test2"
         },
         "repository":{
            "full_name":"team_name/repo_name",
            "uuid":"{47ab6377-f541-4710-80cf-e4b72aeebd35}",
            "type":"repository",
            "name":"repo_name",
            "links":{
               "avatar":{
                  "href":"https://bitbucket.org/team_name/repo_name/avatar/32/"
               },
               "html":{
                  "href":"https://bitbucket.org/team_name/repo_name"
               },
               "self":{
                  "href":"https://api.bitbucket.org/2.0/repositories/team_name/repo_name"
               }
            }
         }
      },
      "created_on":"2016-12-06T15:34:56.496384+00:00",
      "description":"* Trigger Webhook\\r\\n\\r\\n* Trigger Webhook\\r\\n\\r\\n* Trigger Webhook",
      "reason":"",
      "author":{
         "username":"emmap1",
         "display_name":"Emma",
         "uuid":"{a54f16da-24e9-4d7f-a3a7-b1ba2cd98aa3}",
         "type":"user",
         "links":{
            "avatar":{
               "href":"https://bitbucket.org/account/emmap1/avatar/32/"
            },
            "html":{
               "href":"https://bitbucket.org/emmap1/"
            },
            "self":{
               "href":"https://api.bitbucket.org/2.0/users/emmap1"
            }
         }
      },
      "type":"pullrequest"
   }
}
"""


class TestWebHookEvent(unittest.TestCase):

    """Unit tests for BitBucket webhook event
    """

    def setUp(self):
        self.change_hook = change_hook.ChangeHookResource(
            dialects={'bitbucket': True}, master=fakeMasterForHooks())

    @inlineCallbacks
    def testGitRepoPush(self):
        request = _prepare_request(gitRepoPushJsonPayload, headers={_HEADER_EVENT: "repo:push"})
        yield request.test_render(self.change_hook)

        self.assertEqual(len(self.change_hook.master.addedChanges), 1)
        commit = self.change_hook.master.addedChanges[0]

        self.assertEqual(commit['repository'], 'git@bitbucket.org:team_name/repo_name.git')
        self.assertEqual(commit['project'], 'repo_name')
        self.assertEqual(commit['when_timestamp'], dateparse("2015-06-09T03:34:49+00:00"))
        self.assertEqual(commit['author'], 'Emma <emmap1>')
        self.assertEqual(commit['revision'], '03f4a7270240708834de475bcf21532d6134777e')
        self.assertEqual(commit['comments'], 'commit message')
        self.assertEqual(commit['branch'], 'master')
        self.assertEqual(
            commit['revlink'],
            'https://bitbucket.org/user/repo/commits/03f4a7270240708834de475bcf21532d6134777e'
        )

    @inlineCallbacks
    def testGitPullRequestCreated(self):
        request = _prepare_request(gitRepoPullRequestCreatedJsonPayload, headers={_HEADER_EVENT: "pullrequest:created"})
        yield request.test_render(self.change_hook)

        self.assertEqual(len(self.change_hook.master.addedChanges), 1)
        commit = self.change_hook.master.addedChanges[0]

        self.assertEqual(commit['repository'], 'git@bitbucket.org:team_name/repo_name.git')
        self.assertEqual(commit['project'], 'repo_name')
        self.assertEqual(commit['when_timestamp'], dateparse("2016-12-06T15:34:56.496384+00:00"))
        self.assertEqual(commit['author'], 'Emma <emmap1>')
        self.assertEqual(commit['revision'], 'af319f4c0f50')
        self.assertEqual(commit['comments'], 'Bitbucket Pull Request #2')
        self.assertEqual(commit['branch'], 'refs/pull/2/merge')
        self.assertEqual(
            commit['revlink'],
            'https://api.bitbucket.org/2.0/repositories/team_name/repo_name/pullrequests/2/commits'
        )

    @inlineCallbacks
    def testGitPullRequestUpdated(self):
        request = _prepare_request(gitRepoPullRequestUpdatedJsonPayload, headers={_HEADER_EVENT: "pullrequest:updated"})
        yield request.test_render(self.change_hook)

        self.assertEqual(len(self.change_hook.master.addedChanges), 1)
        commit = self.change_hook.master.addedChanges[0]

        self.assertEqual(commit['repository'], 'git@bitbucket.org:team_name/repo_name.git')
        self.assertEqual(commit['project'], 'Project name')
        self.assertEqual(commit['when_timestamp'], dateparse("2016-12-06T16:51:28.027419+00:00"))
        self.assertEqual(commit['author'], 'Emma <emmap1>')
        self.assertEqual(commit['revision'], 'df98dc8f0f53')
        self.assertEqual(commit['comments'], 'Bitbucket Pull Request #2')
        self.assertEqual(commit['branch'], 'refs/pull/2/merge')
        self.assertEqual(
            commit['revlink'],
            'https://api.bitbucket.org/2.0/repositories/team_name/repo_name/pullrequests/2/commits'
        )
