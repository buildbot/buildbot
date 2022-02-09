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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot import config
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import www
from buildbot.www import auth
from buildbot.www import avatar


class TestAvatar(avatar.AvatarBase):

    def getUserAvatar(self, email, username, size, defaultAvatarUrl):
        user_avatar = f'{repr(email)} {repr(size)} {repr(defaultAvatarUrl)}'.encode('utf-8')
        return defer.succeed((b"image/png", user_avatar))


class AvatarResource(TestReactorMixin, www.WwwTestMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()

    @defer.inlineCallbacks
    def test_default(self):
        master = self.make_master(
            url='http://a/b/', auth=auth.NoAuth(), avatar_methods=[])
        rsrc = avatar.AvatarResource(master)
        rsrc.reconfigResource(master.config)

        res = yield self.render_resource(rsrc, b'/')
        self.assertEqual(
            res, dict(redirected=avatar.AvatarResource.defaultAvatarUrl))

    @defer.inlineCallbacks
    def test_gravatar(self):
        master = self.make_master(
            url='http://a/b/', auth=auth.NoAuth(), avatar_methods=[avatar.AvatarGravatar()])
        rsrc = avatar.AvatarResource(master)
        rsrc.reconfigResource(master.config)

        res = yield self.render_resource(rsrc, b'/?email=foo')
        self.assertEqual(res, dict(redirected=b'//www.gravatar.com/avatar/acbd18db4cc2f85ce'
                                   b'def654fccc4a4d8?d=retro&s=32'))

    @defer.inlineCallbacks
    def test_avatar_call(self):
        master = self.make_master(
            url='http://a/b/', auth=auth.NoAuth(), avatar_methods=[TestAvatar()])
        rsrc = avatar.AvatarResource(master)
        rsrc.reconfigResource(master.config)

        res = yield self.render_resource(rsrc, b'/?email=foo')
        self.assertEqual(res, b"b'foo' 32 b'http://a/b/img/nobody.png'")

    @defer.inlineCallbacks
    def test_custom_size(self):
        master = self.make_master(
            url='http://a/b/', auth=auth.NoAuth(), avatar_methods=[TestAvatar()])
        rsrc = avatar.AvatarResource(master)
        rsrc.reconfigResource(master.config)

        res = yield self.render_resource(rsrc, b'/?email=foo&size=64')
        self.assertEqual(res, b"b'foo' 64 b'http://a/b/img/nobody.png'")

    @defer.inlineCallbacks
    def test_invalid_size(self):
        master = self.make_master(
            url='http://a/b/', auth=auth.NoAuth(), avatar_methods=[TestAvatar()])
        rsrc = avatar.AvatarResource(master)
        rsrc.reconfigResource(master.config)

        res = yield self.render_resource(rsrc, b'/?email=foo&size=abcd')
        self.assertEqual(res, b"b'foo' 32 b'http://a/b/img/nobody.png'")

    @defer.inlineCallbacks
    def test_custom_not_found(self):
        # use gravatar if the custom avatar fail to return a response
        class CustomAvatar(avatar.AvatarBase):

            def getUserAvatar(self, email, username, size, defaultAvatarUrl):
                return defer.succeed(None)

        master = self.make_master(url=b'http://a/b/', auth=auth.NoAuth(),
                                  avatar_methods=[CustomAvatar(), avatar.AvatarGravatar()])
        rsrc = avatar.AvatarResource(master)
        rsrc.reconfigResource(master.config)

        res = yield self.render_resource(rsrc, b'/?email=foo')
        self.assertEqual(res, dict(redirected=b'//www.gravatar.com/avatar/acbd18db4cc2f85ce'
                         b'def654fccc4a4d8?d=retro&s=32'))


github_username_search_reply = {
    "login": "defunkt",
    "id": 42424242,
    "node_id": "MDQ6VXNlcjQyNDI0MjQy",
    "avatar_url": "https://avatars3.githubusercontent.com/u/42424242?v=4",
    "gravatar_id": "",
    "url": "https://api.github.com/users/defunkt",
    "html_url": "https://github.com/defunkt",
    "followers_url": "https://api.github.com/users/defunkt/followers",
    "following_url": "https://api.github.com/users/defunkt/following{/other_user}",
    "gists_url": "https://api.github.com/users/defunkt/gists{/gist_id}",
    "starred_url": "https://api.github.com/users/defunkt/starred{/owner}{/repo}",
    "subscriptions_url": "https://api.github.com/users/defunkt/subscriptions",
    "organizations_url": "https://api.github.com/users/defunkt/orgs",
    "repos_url": "https://api.github.com/users/defunkt/repos",
    "events_url": "https://api.github.com/users/defunkt/events{/privacy}",
    "received_events_url": "https://api.github.com/users/defunkt/received_events",
    "type": "User",
    "site_admin": False,
    "name": "Defunkt User",
    "company": None,
    "blog": "",
    "location": None,
    "email": None,
    "hireable": None,
    "bio": None,
    "twitter_username": None,
    "public_repos": 1,
    "public_gists": 1,
    "followers": 1,
    "following": 1,
    "created_at": "2000-01-01T00:00:00Z",
    "updated_at": "2021-01-01T00:00:00Z"
}

github_username_not_found_reply = {
    "message": "Not Found",
    "documentation_url": "https://docs.github.com/rest/reference/users#get-a-user"
}

github_email_search_reply = {
    "total_count": 1,
    "incomplete_results": False,
    "items": [
        {
            "login": "defunkt",
            "id": 42424242,
            "node_id": "MDQ6VXNlcjQyNDI0MjQy",
            "avatar_url": "https://avatars3.githubusercontent.com/u/42424242?v=4",
            "gravatar_id": "",
            "url": "https://api.github.com/users/defunkt",
            "html_url": "https://github.com/defunkt",
            "followers_url": "https://api.github.com/users/defunkt/followers",
            "following_url": "https://api.github.com/users/defunkt/following{/other_user}",
            "gists_url": "https://api.github.com/users/defunkt/gists{/gist_id}",
            "starred_url": "https://api.github.com/users/defunkt/starred{/owner}{/repo}",
            "subscriptions_url": "https://api.github.com/users/defunkt/subscriptions",
            "organizations_url": "https://api.github.com/users/defunkt/orgs",
            "repos_url": "https://api.github.com/users/defunkt/repos",
            "events_url": "https://api.github.com/users/defunkt/events{/privacy}",
            "received_events_url": "https://api.github.com/users/defunkt/received_events",
            "type": "User",
            "site_admin": False,
            "score": 1.0
        }
    ]
}

github_email_search_not_found_reply = {
    "total_count": 0,
    "incomplete_results": False,
    "items": [

    ]
}

github_commit_search_reply = {
    "total_count": 1,
    "incomplete_results": False,
    "items": [
        {
            "url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                   "commits/1111111111111111111111111111111111111111",
            "sha": "1111111111111111111111111111111111111111",
            "node_id":
                "MDY6Q29tbWl0NDM0MzQzNDM6MTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTEx",
            "html_url": "https://github.com/defunkt-org/defunkt-repo/"
                        "commit/1111111111111111111111111111111111111111",
            "comments_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                            "commits/1111111111111111111111111111111111111111/comments",
            "commit": {
                "url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                       "git/commits/1111111111111111111111111111111111111111",
                "author": {
                    "date": "2021-01-01T01:01:01.000-01:00",
                    "name": "Defunkt User",
                    "email": "defunkt@defunkt.com"
                },
                "committer": {
                    "date": "2021-01-01T01:01:01.000-01:00",
                    "name": "Defunkt User",
                    "email": "defunkt@defunkt.com"
                },
                "message": "defunkt message",
                "tree": {
                    "url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                           "git/trees/2222222222222222222222222222222222222222",
                    "sha": "2222222222222222222222222222222222222222"
                },
                "comment_count": 0
            },
            "author": {
                "login": "defunkt",
                "id": 42424242,
                "node_id": "MDQ6VXNlcjQyNDI0MjQy",
                "avatar_url": "https://avatars3.githubusercontent.com/u/42424242?v=4",
                "gravatar_id": "",
                "url": "https://api.github.com/users/defunkt",
                "html_url": "https://github.com/defunkt",
                "followers_url": "https://api.github.com/users/defunkt/followers",
                "following_url": "https://api.github.com/users/defunkt/following{/other_user}",
                "gists_url": "https://api.github.com/users/defunkt/gists{/gist_id}",
                "starred_url": "https://api.github.com/users/defunkt/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/defunkt/subscriptions",
                "organizations_url": "https://api.github.com/users/defunkt/orgs",
                "repos_url": "https://api.github.com/users/defunkt/repos",
                "events_url": "https://api.github.com/users/defunkt/events{/privacy}",
                "received_events_url": "https://api.github.com/users/defunkt/received_events",
                "type": "User",
                "site_admin": False
            },
            "committer": {
                "login": "defunkt",
                "id": 42424242,
                "node_id": "MDQ6VXNlcjQyNDI0MjQy",
                "avatar_url": "https://avatars3.githubusercontent.com/u/42424242?v=4",
                "gravatar_id": "",
                "url": "https://api.github.com/users/defunkt",
                "html_url": "https://github.com/defunkt",
                "followers_url": "https://api.github.com/users/defunkt/followers",
                "following_url": "https://api.github.com/users/defunkt/following{/other_user}",
                "gists_url": "https://api.github.com/users/defunkt/gists{/gist_id}",
                "starred_url": "https://api.github.com/users/defunkt/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/defunkt/subscriptions",
                "organizations_url": "https://api.github.com/users/defunkt/orgs",
                "repos_url": "https://api.github.com/users/defunkt/repos",
                "events_url": "https://api.github.com/users/defunkt/events{/privacy}",
                "received_events_url": "https://api.github.com/users/defunkt/received_events",
                "type": "User",
                "site_admin": False
            },
            "parents": [
                {
                    "url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                           "commits/3333333333333333333333333333333333333333",
                    "html_url": "https://github.com/defunkt-org/defunkt-repo/"
                                "commit/3333333333333333333333333333333333333333",
                    "sha": "3333333333333333333333333333333333333333"
                }
            ],
            "repository": {
                "id": 43434343,
                "node_id": "MDEwOlJlcG9zaXRvcnk0MzQzNDM0Mw==",
                "name": "defunkt-repo",
                "full_name": "defunkt-org/defunkt-repo",
                "private": False,
                "owner": {
                    "login": "defunkt-org",
                    "id": 44444444,
                    "node_id": "MDEyOk9yZ2FuaXphdGlvbjQ0NDQ0NDQ0",
                    "avatar_url": "https://avatars2.githubusercontent.com/u/44444444?v=4",
                    "gravatar_id": "",
                    "url": "https://api.github.com/users/defunkt-org",
                    "html_url": "https://github.com/defunkt-org",
                    "followers_url": "https://api.github.com/users/defunkt-org/followers",
                    "following_url": "https://api.github.com/users/defunkt-org/"
                                     "following{/other_user}",
                    "gists_url": "https://api.github.com/users/defunkt-org/gists{/gist_id}",
                    "starred_url": "https://api.github.com/users/defunkt-org/"
                                   "starred{/owner}{/repo}",
                    "subscriptions_url": "https://api.github.com/users/defunkt-org/subscriptions",
                    "organizations_url": "https://api.github.com/users/defunkt-org/orgs",
                    "repos_url": "https://api.github.com/users/defunkt-org/repos",
                    "events_url": "https://api.github.com/users/defunkt-org/events{/privacy}",
                    "received_events_url": "https://api.github.com/users/defunkt-org/"
                                           "received_events",
                    "type": "Organization",
                    "site_admin": False
                },
                "html_url": "https://github.com/defunkt-org/defunkt-repo",
                "description": "defunkt project",
                "fork": False,
                "url": "https://api.github.com/repos/defunkt-org/defunkt-repo",
                "forks_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/forks",
                "keys_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/keys{/key_id}",
                "collaborators_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                     "collaborators{/collaborator}",
                "teams_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/teams",
                "hooks_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/hooks",
                "issue_events_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                    "issues/events{/number}",
                "events_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/events",
                "assignees_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                 "assignees{/user}",
                "branches_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                "branches{/branch}",
                "tags_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/tags",
                "blobs_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                             "git/blobs{/sha}",
                "git_tags_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                "git/tags{/sha}",
                "git_refs_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                "git/refs{/sha}",
                "trees_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                             "git/trees{/sha}",
                "statuses_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                "statuses/{sha}",
                "languages_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                 "languages",
                "stargazers_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                  "stargazers",
                "contributors_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                    "contributors",
                "subscribers_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                   "subscribers",
                "subscription_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                    "subscription",
                "commits_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                               "commits{/sha}",
                "git_commits_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                   "git/commits{/sha}",
                "comments_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                "comments{/number}",
                "issue_comment_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                     "issues/comments{/number}",
                "contents_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                "contents/{+path}",
                "compare_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                               "compare/{base}...{head}",
                "merges_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/merges",
                "archive_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                               "{archive_format}{/ref}",
                "downloads_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                 "downloads",
                "issues_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                              "issues{/number}",
                "pulls_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                             "pulls{/number}",
                "milestones_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                  "milestones{/number}",
                "notifications_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                     "notifications{?since,all,participating}",
                "labels_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                              "labels{/name}",
                "releases_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                "releases{/id}",
                "deployments_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                   "deployments"
            },
            "score": 1.0
        }
    ]
}

github_commit_search_no_user_reply = {
    "total_count": 1,
    "incomplete_results": False,
    "items": [
        {
            "url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                   "commits/1111111111111111111111111111111111111111",
            "sha": "1111111111111111111111111111111111111111",
            "node_id":
                "MDY6Q29tbWl0NDM0MzQzNDM6MTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTEx",
            "html_url": "https://github.com/defunkt-org/defunkt-repo/"
                        "commit/1111111111111111111111111111111111111111",
            "comments_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                            "commits/1111111111111111111111111111111111111111/comments",
            "commit": {
                "url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                       "git/commits/1111111111111111111111111111111111111111",
                "author": {
                    "date": "2021-01-01T01:01:01.000-01:00",
                    "name": "Defunkt User",
                    "email": "defunkt@defunkt.com"
                },
                "committer": {
                    "date": "2021-01-01T01:01:01.000-01:00",
                    "name": "Defunkt User",
                    "email": "defunkt@defunkt.com"
                },
                "message": "defunkt message",
                "tree": {
                    "url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                           "git/trees/2222222222222222222222222222222222222222",
                    "sha": "2222222222222222222222222222222222222222"
                },
                "comment_count": 0
            },
            "author": None,
            "committer": None,
            "parents": [
                {
                    "url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                           "commits/3333333333333333333333333333333333333333",
                    "html_url": "https://github.com/defunkt-org/defunkt-repo/"
                                "commit/3333333333333333333333333333333333333333",
                    "sha": "3333333333333333333333333333333333333333"
                }
            ],
            "repository": {
                "id": 43434343,
                "node_id": "MDEwOlJlcG9zaXRvcnk0MzQzNDM0Mw==",
                "name": "defunkt-repo",
                "full_name": "defunkt-org/defunkt-repo",
                "private": False,
                "owner": {
                    "login": "defunkt-org",
                    "id": 44444444,
                    "node_id": "MDEyOk9yZ2FuaXphdGlvbjQ0NDQ0NDQ0",
                    "avatar_url": "https://avatars2.githubusercontent.com/u/44444444?v=4",
                    "gravatar_id": "",
                    "url": "https://api.github.com/users/defunkt-org",
                    "html_url": "https://github.com/defunkt-org",
                    "followers_url": "https://api.github.com/users/defunkt-org/followers",
                    "following_url": "https://api.github.com/users/defunkt-org/"
                                     "following{/other_user}",
                    "gists_url": "https://api.github.com/users/defunkt-org/gists{/gist_id}",
                    "starred_url": "https://api.github.com/users/defunkt-org/"
                                   "starred{/owner}{/repo}",
                    "subscriptions_url": "https://api.github.com/users/defunkt-org/subscriptions",
                    "organizations_url": "https://api.github.com/users/defunkt-org/orgs",
                    "repos_url": "https://api.github.com/users/defunkt-org/repos",
                    "events_url": "https://api.github.com/users/defunkt-org/events{/privacy}",
                    "received_events_url": "https://api.github.com/users/defunkt-org/"
                                           "received_events",
                    "type": "Organization",
                    "site_admin": False
                },
                "html_url": "https://github.com/defunkt-org/defunkt-repo",
                "description": "defunkt project",
                "fork": False,
                "url": "https://api.github.com/repos/defunkt-org/defunkt-repo",
                "forks_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/forks",
                "keys_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/keys{/key_id}",
                "collaborators_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                     "collaborators{/collaborator}",
                "teams_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/teams",
                "hooks_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/hooks",
                "issue_events_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                    "issues/events{/number}",
                "events_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/events",
                "assignees_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                 "assignees{/user}",
                "branches_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                "branches{/branch}",
                "tags_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/tags",
                "blobs_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                             "git/blobs{/sha}",
                "git_tags_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                "git/tags{/sha}",
                "git_refs_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                "git/refs{/sha}",
                "trees_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                             "git/trees{/sha}",
                "statuses_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                "statuses/{sha}",
                "languages_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                 "languages",
                "stargazers_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                  "stargazers",
                "contributors_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                    "contributors",
                "subscribers_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                   "subscribers",
                "subscription_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                    "subscription",
                "commits_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                               "commits{/sha}",
                "git_commits_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                   "git/commits{/sha}",
                "comments_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                "comments{/number}",
                "issue_comment_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                     "issues/comments{/number}",
                "contents_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                "contents/{+path}",
                "compare_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                               "compare/{base}...{head}",
                "merges_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/merges",
                "archive_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                               "{archive_format}{/ref}",
                "downloads_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                 "downloads",
                "issues_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                              "issues{/number}",
                "pulls_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                             "pulls{/number}",
                "milestones_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                  "milestones{/number}",
                "notifications_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                     "notifications{?since,all,participating}",
                "labels_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                              "labels{/name}",
                "releases_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                "releases{/id}",
                "deployments_url": "https://api.github.com/repos/defunkt-org/defunkt-repo/"
                                   "deployments"
            },
            "score": 1.0
        }
    ]
}

github_commit_search_not_found_reply = {
    "total_count": 0,
    "incomplete_results": False,
    "items": [

    ]
}


class GitHubAvatar(TestReactorMixin, www.WwwTestMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()

        master = self.make_master(
            url='http://a/b/', auth=auth.NoAuth(),
            avatar_methods=[avatar.AvatarGitHub(token="abcd")])

        self.rsrc = avatar.AvatarResource(master)
        self.rsrc.reconfigResource(master.config)

        headers = {
            'User-Agent': 'Buildbot',
            'Authorization': 'token abcd',
        }
        self._http = yield fakehttpclientservice.HTTPClientService.getService(
            master, self,
            avatar.AvatarGitHub.DEFAULT_GITHUB_API_URL,
            headers=headers,
            debug=False, verify=False)
        yield self.master.startService()

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.master.stopService()

    @defer.inlineCallbacks
    def test_username(self):
        username_search_endpoint = '/users/defunkt'
        self._http.expect('get', username_search_endpoint,
            content_json=github_username_search_reply,
            headers={'Accept': 'application/vnd.github.v3+json'})
        res = yield self.render_resource(self.rsrc, b'/?username=defunkt')
        self.assertEqual(res, dict(redirected=b'https://avatars3.githubusercontent.com/'
            b'u/42424242?v=4&s=32'))

    @defer.inlineCallbacks
    def test_username_not_found(self):
        username_search_endpoint = '/users/inexistent'
        self._http.expect('get', username_search_endpoint, code=404,
            content_json=github_username_not_found_reply,
            headers={'Accept': 'application/vnd.github.v3+json'})
        res = yield self.render_resource(self.rsrc, b'/?username=inexistent')
        self.assertEqual(res, dict(redirected=b'img/nobody.png'))

    @defer.inlineCallbacks
    def test_username_error(self):
        username_search_endpoint = '/users/error'
        self._http.expect('get', username_search_endpoint, code=500,
            headers={'Accept': 'application/vnd.github.v3+json'})
        res = yield self.render_resource(self.rsrc, b'/?username=error')
        self.assertEqual(res, dict(redirected=b'img/nobody.png'))

    @defer.inlineCallbacks
    def test_username_cached(self):
        username_search_endpoint = '/users/defunkt'
        self._http.expect('get', username_search_endpoint,
            content_json=github_username_search_reply,
            headers={'Accept': 'application/vnd.github.v3+json'})
        res = yield self.render_resource(self.rsrc, b'/?username=defunkt')
        self.assertEqual(res, dict(redirected=b'https://avatars3.githubusercontent.com/'
            b'u/42424242?v=4&s=32'))
        # Second request will give same result but without an HTTP request
        res = yield self.render_resource(self.rsrc, b'/?username=defunkt')
        self.assertEqual(res, dict(redirected=b'https://avatars3.githubusercontent.com/'
            b'u/42424242?v=4&s=32'))

    @defer.inlineCallbacks
    def test_email(self):
        email_search_endpoint = '/search/users?q=defunkt%40defunkt.com+in%3Aemail'
        self._http.expect('get', email_search_endpoint, content_json=github_email_search_reply,
            headers={'Accept': 'application/vnd.github.v3+json'})
        res = yield self.render_resource(self.rsrc, b'/?email=defunkt@defunkt.com')
        self.assertEqual(res, dict(redirected=b'https://avatars3.githubusercontent.com/'
            b'u/42424242?v=4&s=32'))

    @defer.inlineCallbacks
    def test_email_commit(self):
        email_search_endpoint = '/search/users?q=defunkt%40defunkt.com+in%3Aemail'
        self._http.expect('get', email_search_endpoint,
            content_json=github_email_search_not_found_reply,
            headers={'Accept': 'application/vnd.github.v3+json'})
        commit_search_endpoint = ('/search/commits?'
            'per_page=1&q=author-email%3Adefunkt%40defunkt.com&sort=committer-date')
        self._http.expect('get', commit_search_endpoint, content_json=github_commit_search_reply,
            headers={'Accept': 'application/vnd.github.v3+json,'
                'application/vnd.github.cloak-preview'})
        res = yield self.render_resource(self.rsrc, b'/?email=defunkt@defunkt.com')
        self.assertEqual(res, dict(redirected=b'https://avatars3.githubusercontent.com/'
            b'u/42424242?v=4&s=32'))

    @defer.inlineCallbacks
    def test_email_commit_no_user(self):
        email_search_endpoint = '/search/users?q=defunkt%40defunkt.com+in%3Aemail'
        self._http.expect('get', email_search_endpoint,
            content_json=github_email_search_not_found_reply,
            headers={'Accept': 'application/vnd.github.v3+json'})
        commit_search_endpoint = ('/search/commits?'
            'per_page=1&q=author-email%3Adefunkt%40defunkt.com&sort=committer-date')
        self._http.expect('get', commit_search_endpoint,
            content_json=github_commit_search_no_user_reply,
            headers={'Accept': 'application/vnd.github.v3+json,'
                'application/vnd.github.cloak-preview'})
        res = yield self.render_resource(self.rsrc, b'/?email=defunkt@defunkt.com')
        self.assertEqual(res, dict(redirected=b'img/nobody.png'))

    @defer.inlineCallbacks
    def test_email_not_found(self):
        email_search_endpoint = '/search/users?q=notfound%40defunkt.com+in%3Aemail'
        self._http.expect('get', email_search_endpoint,
            content_json=github_email_search_not_found_reply,
            headers={'Accept': 'application/vnd.github.v3+json'})
        commit_search_endpoint = ('/search/commits?'
            'per_page=1&q=author-email%3Anotfound%40defunkt.com&sort=committer-date')
        self._http.expect('get', commit_search_endpoint,
            content_json=github_commit_search_not_found_reply,
            headers={'Accept': 'application/vnd.github.v3+json,'
                'application/vnd.github.cloak-preview'})
        res = yield self.render_resource(self.rsrc, b'/?email=notfound@defunkt.com')
        self.assertEqual(res, dict(redirected=b'img/nobody.png'))

    @defer.inlineCallbacks
    def test_email_error(self):
        email_search_endpoint = '/search/users?q=error%40defunkt.com+in%3Aemail'
        self._http.expect('get', email_search_endpoint, code=500,
            headers={'Accept': 'application/vnd.github.v3+json'})
        commit_search_endpoint = ('/search/commits?'
            'per_page=1&q=author-email%3Aerror%40defunkt.com&sort=committer-date')
        self._http.expect('get', commit_search_endpoint, code=500,
            headers={'Accept': 'application/vnd.github.v3+json,'
                'application/vnd.github.cloak-preview'})
        res = yield self.render_resource(self.rsrc, b'/?email=error@defunkt.com')
        self.assertEqual(res, dict(redirected=b'img/nobody.png'))


class GitHubAvatarBasicAuth(TestReactorMixin, www.WwwTestMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()

        avatar_method = avatar.AvatarGitHub(client_id="oauth_id",
                                            client_secret="oauth_secret")
        master = self.make_master(url='http://a/b/', auth=auth.NoAuth(),
                                  avatar_methods=[avatar_method])

        self.rsrc = avatar.AvatarResource(master)
        self.rsrc.reconfigResource(master.config)

        headers = {
            'User-Agent': 'Buildbot',
            # oauth_id:oauth_secret in Base64
            'Authorization': 'basic b2F1dGhfaWQ6b2F1dGhfc2VjcmV0',
        }
        self._http = yield fakehttpclientservice.HTTPClientService.getService(
            master, self,
            avatar.AvatarGitHub.DEFAULT_GITHUB_API_URL,
            headers=headers,
            debug=False, verify=False)
        yield self.master.startService()

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.master.stopService()

    def test_incomplete_credentials(self):
        with self.assertRaises(config.ConfigErrors):
            avatar.AvatarGitHub(client_id="oauth_id")
        with self.assertRaises(config.ConfigErrors):
            avatar.AvatarGitHub(client_secret="oauth_secret")

    def test_token_and_client_credentials(self):
        with self.assertRaises(config.ConfigErrors):
            avatar.AvatarGitHub(client_id="oauth_id",
                                client_secret="oauth_secret",
                                token="token")

    @defer.inlineCallbacks
    def test_username(self):
        username_search_endpoint = '/users/defunkt'
        self._http.expect('get', username_search_endpoint,
                          content_json=github_username_search_reply,
                          headers={'Accept': 'application/vnd.github.v3+json'})
        res = yield self.render_resource(self.rsrc, b'/?username=defunkt')
        self.assertEqual(res, {'redirected': b'https://avatars3.githubusercontent.com/'
            b'u/42424242?v=4&s=32'})
