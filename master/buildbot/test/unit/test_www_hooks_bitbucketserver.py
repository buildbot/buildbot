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
# Copyright Mamba Team

from io import BytesIO

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.fake.web import FakeRequest
from buildbot.test.fake.web import fakeMasterForHooks
from buildbot.test.util.misc import TestReactorMixin
from buildbot.util import unicode2bytes
from buildbot.www import change_hook
from buildbot.www.hooks.bitbucketserver import _HEADER_EVENT

_CT_JSON = b'application/json'

pushJsonPayload = """
{
    "actor": {
        "username": "John",
        "displayName": "John Smith"
    },
    "repository": {
        "scmId": "git",
        "project": {
            "key": "CI",
            "name": "Continuous Integration"
        },
        "slug": "py-repo",
        "links": {
            "self": [
                {
                    "href": "http://localhost:7990/projects/CI/repos/py-repo/browse"
                }
            ]
        },
        "public": false,
        "ownerName": "CI",
        "owner": {
            "username": "CI",
            "displayName": "CI"
        },
        "fullName": "CI/py-repo"
    },
    "push": {
        "changes": [
            {
                "created": false,
                "closed": false,
                "new": {
                    "type": "branch",
                    "name": "branch_1496411680",
                    "target": {
                        "type": "commit",
                        "hash": "793d4754230023d85532f9a38dba3290f959beb4"
                    }
                },
                "old": {
                    "type": "branch",
                    "name": "branch_1496411680",
                    "target": {
                        "type": "commit",
                        "hash": "a87e21f7433d8c16ac7be7413483fbb76c72a8ba"
                    }
                }
            }
        ]
    }
}
"""

pullRequestCreatedJsonPayload = """
{
    "actor": {
        "username": "John",
        "displayName": "John Smith"
    },
    "pullrequest": {
        "id": "21",
        "title": "dot 1496311906",
        "link": "http://localhost:7990/projects/CI/repos/py-repo/pull-requests/21",
        "authorLogin": "John Smith",
        "fromRef": {
            "repository": {
                "scmId": "git",
                "project": {
                    "key": "CI",
                    "name": "Continuous Integration"
                },
                "slug": "py-repo",
                "links": {
                    "self": [
                        {
                            "href": "http://localhost:7990/projects/CI/repos/py-repo/browse"
                        }
                    ]
                },
                "public": false,
                "ownerName": "CI",
                "owner": {
                    "username": "CI",
                    "displayName": "CI"
                },
                "fullName": "CI/py-repo"
            },
            "commit": {
                "message": null,
                "date": null,
                "hash": "a87e21f7433d8c16ac7be7413483fbb76c72a8ba",
                "authorTimestamp": 0
            },
            "branch": {
                "rawNode": "a87e21f7433d8c16ac7be7413483fbb76c72a8ba",
                "name": "branch_1496411680"
            }
        },
        "toRef": {
            "repository": {
                "scmId": "git",
                "project": {
                    "key": "CI",
                    "name": "Continuous Integration"
                },
                "slug": "py-repo",
                "links": {
                    "self": [
                        {
                            "href": "http://localhost:7990/projects/CI/repos/py-repo/browse"
                        }
                    ]
                },
                "public": false,
                "ownerName": "CI",
                "owner": {
                    "username": "CI",
                    "displayName": "CI"
                },
                "fullName": "CI/py-repo"
            },
            "commit": {
                "message": null,
                "date": null,
                "hash": "7aebbb0089c40fce138a6d0b36d2281ea34f37f5",
                "authorTimestamp": 0
            },
            "branch": {
                "rawNode": "7aebbb0089c40fce138a6d0b36d2281ea34f37f5",
                "name": "master"
            }
        }
    },
    "repository": {
        "scmId": "git",
        "project": {
            "key": "CI",
            "name": "Continuous Integration"
        },
        "slug": "py-repo",
        "links": {
            "self": [
                {
                    "href": "http://localhost:7990/projects/CI/repos/py-repo/browse"
                }
            ]
        },
        "public": false,
        "ownerName": "CI",
        "owner": {
            "username": "CI",
            "displayName": "CI"
        },
        "fullName": "CI/py-repo"
    }
}
"""

pullRequestUpdatedJsonPayload = """
{
    "actor": {
        "username": "John",
        "displayName": "John Smith"
    },
    "pullrequest": {
        "id": "21",
        "title": "dot 1496311906",
        "link": "http://localhost:7990/projects/CI/repos/py-repo/pull-requests/21",
        "authorLogin": "Buildbot",
        "fromRef": {
            "repository": {
                "scmId": "git",
                "project": {
                    "key": "CI",
                    "name": "Continuous Integration"
                },
                "slug": "py-repo",
                "links": {
                    "self": [
                        {
                            "href": "http://localhost:7990/projects/CI/repos/py-repo/browse"
                        }
                    ]
                },
                "public": false,
                "ownerName": "CI",
                "owner": {
                    "username": "CI",
                    "displayName": "CI"
                },
                "fullName": "CI/py-repo"
            },
            "commit": {
                "message": null,
                "date": null,
                "hash": "a87e21f7433d8c16ac7be7413483fbb76c72a8ba",
                "authorTimestamp": 0
            },
            "branch": {
                "rawNode": "a87e21f7433d8c16ac7be7413483fbb76c72a8ba",
                "name": "branch_1496411680"
            }
        },
        "toRef": {
            "repository": {
                "scmId": "git",
                "project": {
                    "key": "CI",
                    "name": "Continuous Integration"
                },
                "slug": "py-repo",
                "links": {
                    "self": [
                        {
                            "href": "http://localhost:7990/projects/CI/repos/py-repo/browse"
                        }
                    ]
                },
                "public": false,
                "ownerName": "CI",
                "owner": {
                    "username": "CI",
                    "displayName": "CI"
                },
                "fullName": "CI/py-repo"
            },
            "commit": {
                "message": null,
                "date": null,
                "hash": "7aebbb0089c40fce138a6d0b36d2281ea34f37f5",
                "authorTimestamp": 0
            },
            "branch": {
                "rawNode": "7aebbb0089c40fce138a6d0b36d2281ea34f37f5",
                "name": "master"
            }
        }
    },
    "repository": {
        "scmId": "git",
        "project": {
            "key": "CI",
            "name": "Continuous Integration"
        },
        "slug": "py-repo",
        "links": {
            "self": [
                {
                    "href": "http://localhost:7990/projects/CI/repos/py-repo/browse"
                }
            ]
        },
        "public": false,
        "ownerName": "CI",
        "owner": {
            "username": "CI",
            "displayName": "CI"
        },
        "fullName": "CI/py-repo"
    }
}
"""

pullRequestRejectedJsonPayload = """
{
    "actor": {
        "username": "John",
        "displayName": "John Smith"
    },
    "pullrequest": {
        "id": "21",
        "title": "dot 1496311906",
        "link": "http://localhost:7990/projects/CI/repos/py-repo/pull-requests/21",
        "authorLogin": "Buildbot",
        "fromRef": {
            "repository": {
                "scmId": "git",
                "project": {
                    "key": "CI",
                    "name": "Continuous Integration"
                },
                "slug": "py-repo",
                "links": {
                    "self": [
                        {
                            "href": "http://localhost:7990/projects/CI/repos/py-repo/browse"
                        }
                    ]
                },
                "public": false,
                "ownerName": "CI",
                "owner": {
                    "username": "CI",
                    "displayName": "CI"
                },
                "fullName": "CI/py-repo"
            },
            "commit": {
                "message": null,
                "date": null,
                "hash": "a87e21f7433d8c16ac7be7413483fbb76c72a8ba",
                "authorTimestamp": 0
            },
            "branch": {
                "rawNode": "a87e21f7433d8c16ac7be7413483fbb76c72a8ba",
                "name": "branch_1496411680"
            }
        },
        "toRef": {
            "repository": {
                "scmId": "git",
                "project": {
                    "key": "CI",
                    "name": "Continuous Integration"
                },
                "slug": "py-repo",
                "links": {
                    "self": [
                        {
                            "href": "http://localhost:7990/projects/CI/repos/py-repo/browse"
                        }
                    ]
                },
                "public": false,
                "ownerName": "CI",
                "owner": {
                    "username": "CI",
                    "displayName": "CI"
                },
                "fullName": "CI/py-repo"
            },
            "commit": {
                "message": null,
                "date": null,
                "hash": "7aebbb0089c40fce138a6d0b36d2281ea34f37f5",
                "authorTimestamp": 0
            },
            "branch": {
                "rawNode": "7aebbb0089c40fce138a6d0b36d2281ea34f37f5",
                "name": "master"
            }
        }
    },
    "repository": {
        "scmId": "git",
        "project": {
            "key": "CI",
            "name": "Continuous Integration"
        },
        "slug": "py-repo",
        "links": {
            "self": [
                {
                    "href": "http://localhost:7990/projects/CI/repos/py-repo/browse"
                }
            ]
        },
        "public": false,
        "ownerName": "CI",
        "owner": {
            "username": "CI",
            "displayName": "CI"
        },
        "fullName": "CI/py-repo"
    }
}
"""

pullRequestFulfilledJsonPayload = """
{
    "actor": {
        "username": "John",
        "displayName": "John Smith"
    },
    "pullrequest": {
        "id": "21",
        "title": "Branch 1496411680",
        "link": "http://localhost:7990/projects/CI/repos/py-repo/pull-requests/21",
        "authorLogin": "Buildbot",
        "fromRef": {
            "repository": {
                "scmId": "git",
                "project": {
                    "key": "CI",
                    "name": "Continuous Integration"
                },
                "slug": "py-repo",
                "links": {
                    "self": [
                        {
                            "href": "http://localhost:7990/projects/CI/repos/py-repo/browse"
                        }
                    ]
                },
                "public": false,
                "ownerName": "CI",
                "owner": {
                    "username": "CI",
                    "displayName": "CI"
                },
                "fullName": "CI/py-repo"
            },
            "commit": {
                "message": null,
                "date": null,
                "hash": "a87e21f7433d8c16ac7be7413483fbb76c72a8ba",
                "authorTimestamp": 0
            },
            "branch": {
                "rawNode": "a87e21f7433d8c16ac7be7413483fbb76c72a8ba",
                "name": "branch_1496411680"
            }
        },
        "toRef": {
            "repository": {
                "scmId": "git",
                "project": {
                    "key": "CI",
                    "name": "Continuous Integration"
                },
                "slug": "py-repo",
                "links": {
                    "self": [
                        {
                            "href": "http://localhost:7990/projects/CI/repos/py-repo/browse"
                        }
                    ]
                },
                "public": false,
                "ownerName": "CI",
                "owner": {
                    "username": "CI",
                    "displayName": "CI"
                },
                "fullName": "CI/py-repo"
            },
            "commit": {
                "message": null,
                "date": null,
                "hash": "7aebbb0089c40fce138a6d0b36d2281ea34f37f5",
                "authorTimestamp": 0
            },
            "branch": {
                "rawNode": "7aebbb0089c40fce138a6d0b36d2281ea34f37f5",
                "name": "master"
            }
        }
    },
    "repository": {
        "scmId": "git",
        "project": {
            "key": "CI",
            "name": "Continuous Integration"
        },
        "slug": "py-repo",
        "links": {
            "self": [
                {
                    "href": "http://localhost:7990/projects/CI/repos/py-repo/browse"
                }
            ]
        },
        "public": false,
        "ownerName": "CI",
        "owner": {
            "username": "CI",
            "displayName": "CI"
        },
        "fullName": "CI/py-repo"
    }
}
"""

deleteTagJsonPayload = """
{
    "actor": {
        "username": "John",
        "displayName": "John Smith"
    },
    "repository": {
        "scmId": "git",
        "project": {
            "key": "CI",
            "name": "Continuous Integration"
        },
        "slug": "py-repo",
        "links": {
            "self": [
                {
                    "href": "http://localhost:7990/projects/CI/repos/py-repo/browse"
                }
            ]
        },
        "ownerName": "BUIL",
        "public": false,
        "owner": {
            "username": "CI",
            "displayName": "CI"
        },
        "fullName": "CI/py-repo"
    },
    "push": {
        "changes": [
            {
                "created": false,
                "closed": true,
                "old": {
                    "type": "tag",
                    "name": "1.0.0",
                    "target": {
                        "type": "commit",
                        "hash": "793d4754230023d85532f9a38dba3290f959beb4"
                    }
                },
                "new": null
            }
        ]
    }
}
"""

deleteBranchJsonPayload = """
{
    "actor": {
        "username": "John",
        "displayName": "John Smith"
    },
    "repository": {
        "scmId": "git",
        "project": {
            "key": "CI",
            "name": "Continuous Integration"
        },
        "slug": "py-repo",
        "links": {
            "self": [
                {
                    "href": "http://localhost:7990/projects/CI/repos/py-repo/browse"
                }
            ]
        },
        "ownerName": "CI",
        "public": false,
        "owner": {
            "username": "CI",
            "displayName": "CI"
        },
        "fullName": "CI/py-repo"
    },
    "push": {
        "changes": [
            {
                "created": false,
                "closed": true,
                "old": {
                    "type": "branch",
                    "name": "branch_1496758965",
                    "target": {
                        "type": "commit",
                        "hash": "793d4754230023d85532f9a38dba3290f959beb4"
                    }
                },
                "new": null
            }
        ]
    }
}
"""

newTagJsonPayload = """
{
    "actor": {
        "username": "John",
        "displayName": "John Smith"
    },
    "repository": {
        "scmId": "git",
        "project": {
            "key": "CI",
            "name": "Continuous Integration"
        },
        "slug": "py-repo",
        "links": {
            "self": [
                {
                    "href": "http://localhost:7990/projects/CI/repos/py-repo/browse"
                }
            ]
        },
        "public": false,
        "ownerName": "CI",
        "owner": {
            "username": "CI",
            "displayName": "CI"
        },
        "fullName": "CI/py-repo"
    },
    "push": {
        "changes": [
            {
                "created": true,
                "closed": false,
                "old": null,
                "new": {
                    "type": "tag",
                    "name": "1.0.0",
                    "target": {
                        "type": "commit",
                        "hash": "793d4754230023d85532f9a38dba3290f959beb4"
                    }
                }
            }
        ]
    }
}
"""


def _prepare_request(payload, headers=None, change_dict=None):
    headers = headers or {}
    request = FakeRequest(change_dict)
    request.uri = b"/change_hook/bitbucketserver"
    request.method = b"POST"
    if isinstance(payload, str):
        payload = unicode2bytes(payload)
    request.content = BytesIO(payload)
    request.received_headers[b'Content-Type'] = _CT_JSON
    request.received_headers.update(headers)
    return request


class TestChangeHookConfiguredWithGitChange(unittest.TestCase,
                                            TestReactorMixin):

    def setUp(self):
        self.setUpTestReactor()
        self.change_hook = change_hook.ChangeHookResource(
            dialects={'bitbucketserver': {}}, master=fakeMasterForHooks(self))

    def _checkPush(self, change):
        self.assertEqual(
            change['repository'],
            'http://localhost:7990/projects/CI/repos/py-repo/')
        self.assertEqual(change['author'], 'John Smith <John>')
        self.assertEqual(change['project'], 'Continuous Integration')
        self.assertEqual(change['revision'],
                         '793d4754230023d85532f9a38dba3290f959beb4')
        self.assertEqual(
            change['comments'], 'Bitbucket Server commit '
                                '793d4754230023d85532f9a38dba3290f959beb4')
        self.assertEqual(
            change['revlink'],
            'http://localhost:7990/projects/CI/repos/py-repo/commits/'
            '793d4754230023d85532f9a38dba3290f959beb4')

    @defer.inlineCallbacks
    def testHookWithChangeOnPushEvent(self):

        request = _prepare_request(
            pushJsonPayload, headers={_HEADER_EVENT: 'repo:refs_changed'})

        yield request.test_render(self.change_hook)

        self.assertEqual(len(self.change_hook.master.data.updates.changesAdded), 1)
        change = self.change_hook.master.data.updates.changesAdded[0]
        self._checkPush(change)
        self.assertEqual(change['branch'], 'refs/heads/branch_1496411680')
        self.assertEqual(change['category'], 'push')

    @defer.inlineCallbacks
    def testHookWithNonDictOption(self):
        self.change_hook.dialects = {'bitbucketserver': True}
        yield self.testHookWithChangeOnPushEvent()

    def _checkPullRequest(self, change):
        self.assertEqual(
            change['repository'],
            'http://localhost:7990/projects/CI/repos/py-repo/')
        self.assertEqual(change['author'], 'John Smith <John>')
        self.assertEqual(change['project'], 'Continuous Integration')
        self.assertEqual(change['comments'],
                         'Bitbucket Server Pull Request #21')
        self.assertEqual(change['revlink'],
                         'http://localhost:7990/projects/'
                         'CI/repos/py-repo/pull-requests/21')
        self.assertEqual(change['revision'],
                         'a87e21f7433d8c16ac7be7413483fbb76c72a8ba')
        pr_url = change['properties'].get('pullrequesturl')
        self.assertNotEqual(pr_url, None)
        self.assertEqual(
            pr_url,
            "http://localhost:7990/projects/CI/repos/py-repo/pull-requests/21")

    @defer.inlineCallbacks
    def testHookWithChangeOnPullRequestCreated(self):
        request = _prepare_request(
            pullRequestCreatedJsonPayload,
            headers={_HEADER_EVENT: 'pullrequest:created'})

        yield request.test_render(self.change_hook)

        self.assertEqual(len(self.change_hook.master.data.updates.changesAdded), 1)
        change = self.change_hook.master.data.updates.changesAdded[0]
        self._checkPullRequest(change)
        self.assertEqual(change['branch'], 'refs/pull-requests/21/merge')
        self.assertEqual(change['category'], 'pull-created')

    @defer.inlineCallbacks
    def testHookWithChangeOnPullRequestUpdated(self):
        request = _prepare_request(
            pullRequestUpdatedJsonPayload,
            headers={_HEADER_EVENT: 'pullrequest:updated'})

        yield request.test_render(self.change_hook)

        self.assertEqual(len(self.change_hook.master.data.updates.changesAdded), 1)
        change = self.change_hook.master.data.updates.changesAdded[0]
        self._checkPullRequest(change)
        self.assertEqual(change['branch'], 'refs/pull-requests/21/merge')
        self.assertEqual(change['category'], 'pull-updated')

    @defer.inlineCallbacks
    def testHookWithChangeOnPullRequestRejected(self):
        request = _prepare_request(
            pullRequestRejectedJsonPayload,
            headers={_HEADER_EVENT: 'pullrequest:rejected'})

        yield request.test_render(self.change_hook)

        self.assertEqual(len(self.change_hook.master.data.updates.changesAdded), 1)
        change = self.change_hook.master.data.updates.changesAdded[0]
        self._checkPullRequest(change)
        self.assertEqual(change['branch'], 'refs/heads/branch_1496411680')
        self.assertEqual(change['category'], 'pull-rejected')

    @defer.inlineCallbacks
    def testHookWithChangeOnPullRequestFulfilled(self):
        request = _prepare_request(
            pullRequestFulfilledJsonPayload,
            headers={_HEADER_EVENT: 'pullrequest:fulfilled'})

        yield request.test_render(self.change_hook)

        self.assertEqual(len(self.change_hook.master.data.updates.changesAdded), 1)
        change = self.change_hook.master.data.updates.changesAdded[0]
        self._checkPullRequest(change)
        self.assertEqual(change['branch'], 'refs/heads/master')
        self.assertEqual(change['category'], 'pull-fulfilled')

    @defer.inlineCallbacks
    def _checkCodebase(self, event_type, expected_codebase):
        payloads = {
            'repo:refs_changed': pushJsonPayload,
            'pullrequest:updated': pullRequestUpdatedJsonPayload}
        request = _prepare_request(
            payloads[event_type], headers={_HEADER_EVENT: event_type})
        yield request.test_render(self.change_hook)
        self.assertEqual(len(self.change_hook.master.data.updates.changesAdded), 1)
        change = self.change_hook.master.data.updates.changesAdded[0]
        self.assertEqual(change['codebase'], expected_codebase)

    @defer.inlineCallbacks
    def testHookWithCodebaseValueOnPushEvent(self):
        self.change_hook.dialects = {
            'bitbucketserver': {'codebase': 'super-codebase'}}
        yield self._checkCodebase('repo:refs_changed', 'super-codebase')

    @defer.inlineCallbacks
    def testHookWithCodebaseFunctionOnPushEvent(self):
        self.change_hook.dialects = {
            'bitbucketserver': {
                'codebase':
                    lambda payload: payload['repository']['project']['key']}}
        yield self._checkCodebase('repo:refs_changed', 'CI')

    @defer.inlineCallbacks
    def testHookWithCodebaseValueOnPullEvent(self):
        self.change_hook.dialects = {
            'bitbucketserver': {'codebase': 'super-codebase'}}
        yield self._checkCodebase('pullrequest:updated', 'super-codebase')

    @defer.inlineCallbacks
    def testHookWithCodebaseFunctionOnPullEvent(self):
        self.change_hook.dialects = {
            'bitbucketserver': {
                'codebase':
                    lambda payload: payload['repository']['project']['key']}}
        yield self._checkCodebase('pullrequest:updated', 'CI')

    @defer.inlineCallbacks
    def testHookWithUnhandledEvent(self):
        request = _prepare_request(
            pushJsonPayload, headers={_HEADER_EVENT: 'invented:event'})
        yield request.test_render(self.change_hook)
        self.assertEqual(len(self.change_hook.master.data.updates.changesAdded), 0)
        self.assertEqual(request.written, b"Unknown event: invented_event")

    @defer.inlineCallbacks
    def testHookWithChangeOnCreateTag(self):
        request = _prepare_request(
            newTagJsonPayload, headers={_HEADER_EVENT: 'repo:refs_changed'})
        yield request.test_render(self.change_hook)
        self.assertEqual(len(self.change_hook.master.data.updates.changesAdded), 1)
        change = self.change_hook.master.data.updates.changesAdded[0]
        self._checkPush(change)
        self.assertEqual(change['branch'], 'refs/tags/1.0.0')
        self.assertEqual(change['category'], 'push')

    @defer.inlineCallbacks
    def testHookWithChangeOnDeleteTag(self):
        request = _prepare_request(
            deleteTagJsonPayload, headers={_HEADER_EVENT: 'repo:refs_changed'})
        yield request.test_render(self.change_hook)
        self.assertEqual(len(self.change_hook.master.data.updates.changesAdded), 1)
        change = self.change_hook.master.data.updates.changesAdded[0]
        self._checkPush(change)
        self.assertEqual(change['branch'], 'refs/tags/1.0.0')
        self.assertEqual(change['category'], 'ref-deleted')

    @defer.inlineCallbacks
    def testHookWithChangeOnDeleteBranch(self):
        request = _prepare_request(
            deleteBranchJsonPayload,
            headers={_HEADER_EVENT: 'repo:refs_changed'})
        yield request.test_render(self.change_hook)
        self.assertEqual(len(self.change_hook.master.data.updates.changesAdded), 1)
        change = self.change_hook.master.data.updates.changesAdded[0]
        self._checkPush(change)
        self.assertEqual(change['branch'], 'refs/heads/branch_1496758965')
        self.assertEqual(change['category'], 'ref-deleted')

    @defer.inlineCallbacks
    def testHookWithInvalidContentType(self):
        request = _prepare_request(
            pushJsonPayload, headers={_HEADER_EVENT: b'repo:refs_changed'})
        request.received_headers[b'Content-Type'] = b'invalid/content'
        yield request.test_render(self.change_hook)
        self.assertEqual(len(self.change_hook.master.data.updates.changesAdded), 0)
        self.assertEqual(request.written,
                         b"Unknown content type: invalid/content")
