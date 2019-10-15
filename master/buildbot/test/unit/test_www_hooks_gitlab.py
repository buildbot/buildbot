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

import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.plugins import util
from buildbot.secrets.manager import SecretManager
from buildbot.test.fake.secrets import FakeSecretStorage
from buildbot.test.fake.web import FakeRequest
from buildbot.test.fake.web import fakeMasterForHooks
from buildbot.test.util.misc import TestReactorMixin
from buildbot.www import change_hook
from buildbot.www.hooks.gitlab import _HEADER_EVENT
from buildbot.www.hooks.gitlab import _HEADER_GITLAB_TOKEN

# Sample GITLAB commit payload from https://docs.gitlab.com/ce/user/project/integrations/webhooks.html
# Added "modified" and "removed", and change email
gitJsonPayload = b"""
{
  "before": "95790bf891e76fee5e1747ab589903a6a1f80f22",
  "after": "da1560886d4f094c3e6c9ef40349f7d38b5d27d7",
  "ref": "refs/heads/master",
  "user_id": 4,
  "user_name": "John Smith",
  "repository": {
    "name": "Diaspora",
    "url": "git@localhost:diaspora.git",
    "description": "",
    "homepage": "http://localhost/diaspora"
  },
  "commits": [
    {
      "id": "b6568db1bc1dcd7f8b4d5a946b0b91f9dacd7327",
      "message": "Update Catalan translation to e38cb41.",
      "timestamp": "2011-12-12T14:27:31+02:00",
      "url": "http://localhost/diaspora/commits/b6568db1bc1dcd7f8b4d5a946b0b91f9dacd7327",
      "author": {
        "name": "Jordi Mallach",
        "email": "jordi@softcatala.org"
      }
    },
    {
      "id": "da1560886d4f094c3e6c9ef40349f7d38b5d27d7",
      "message": "fixed readme",
      "timestamp": "2012-01-03T23:36:29+02:00",
      "url": "http://localhost/diaspora/commits/da1560886d4f094c3e6c9ef40349f7d38b5d27d7",
      "author": {
        "name": "GitLab dev user",
        "email": "gitlabdev@dv6700.(none)"
      }
    }
  ],
  "total_commits_count": 2
}
"""
gitJsonPayloadTag = b"""
{
  "object_kind": "tag_push",
  "before": "0000000000000000000000000000000000000000",
  "after": "82b3d5ae55f7080f1e6022629cdb57bfae7cccc7",
  "ref": "refs/tags/v1.0.0",
  "checkout_sha": "82b3d5ae55f7080f1e6022629cdb57bfae7cccc7",
  "user_id": 1,
  "user_name": "John Smith",
  "repository":{
    "name": "Example",
    "url": "git@localhost:diaspora.git",
    "description": "",
    "homepage": "http://example.com/jsmith/example",
    "git_http_url":"http://example.com/jsmith/example.git",
    "git_ssh_url":"git@example.com:jsmith/example.git",
    "visibility_level":0
  },
   "commits": [
     {
       "id": "b6568db1bc1dcd7f8b4d5a946b0b91f9dacd7327",
       "message": "Update Catalan translation to e38cb41.",
       "timestamp": "2011-12-12T14:27:31+02:00",
       "url": "http://localhost/diaspora/commits/b6568db1bc1dcd7f8b4d5a946b0b91f9dacd7327",
       "author": {
         "name": "Jordi Mallach",
         "email": "jordi@softcatala.org"
       }
     },
     {
       "id": "da1560886d4f094c3e6c9ef40349f7d38b5d27d7",
       "message": "fixed readme",
       "timestamp": "2012-01-03T23:36:29+02:00",
       "url": "http://localhost/diaspora/commits/da1560886d4f094c3e6c9ef40349f7d38b5d27d7",
       "author": {
         "name": "GitLab dev user",
         "email": "gitlabdev@dv6700.(none)"
       }
     }
   ],
   "total_commits_count": 2
}
"""

# == Merge requests from a different branch of the same project
# GITLAB commit payload from an actual version 10.7.1-ee gitlab instance
# chronicling the lives and times of a trivial MR through the operations
# open, edit description, add commit, close, and reopen, in that order.
# (Tidied with json_pp --json_opt=canonical,pretty and an editor.)
# FIXME: only show diffs here to keep file smaller and increase clarity
gitJsonPayloadMR_open = b"""
{
   "event_type" : "merge_request",
   "object_attributes" : {
      "action" : "open",
      "assignee_id" : null,
      "author_id" : 15,
      "created_at" : "2018-05-15 07:45:37 -0700",
      "description" : "This to both gitlab gateways!",
      "head_pipeline_id" : 29931,
      "human_time_estimate" : null,
      "human_total_time_spent" : null,
      "id" : 10850,
      "iid" : 6,
      "last_commit" : {
         "author" : {
            "email" : "mmusterman@example.com",
            "name" : "Max Mustermann"
         },
         "id" : "92268bc781b24f0a61b907da062950e9e5252a69",
         "message" : "Remove the dummy line again",
         "timestamp" : "2018-05-14T07:54:04-07:00",
         "url" : "https://gitlab.example.com/mmusterman/awesome_project/commit/92268bc781b24f0a61b907da062950e9e5252a69"
      },
      "last_edited_at" : null,
      "last_edited_by_id" : null,
      "merge_commit_sha" : null,
      "merge_error" : null,
      "merge_params" : {
         "force_remove_source_branch" : 0
      },
      "merge_status" : "unchecked",
      "merge_user_id" : null,
      "merge_when_pipeline_succeeds" : false,
      "milestone_id" : null,
      "source" : {
         "avatar_url" : null,
         "ci_config_path" : null,
         "default_branch" : "master",
         "description" : "Trivial project for testing build machinery quickly",
         "git_http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
         "git_ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "homepage" : "https://gitlab.example.com/mmusterman/awesome_project",
         "http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
         "id" : 239,
         "name" : "awesome_project",
         "namespace" : "mmusterman",
         "path_with_namespace" : "mmusterman/awesome_project",
         "ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "visibility_level" : 0,
         "web_url" : "https://gitlab.example.com/mmusterman/awesome_project"
      },
      "source_branch" : "ms-viewport",
      "source_project_id" : 239,
      "state" : "opened",
      "target" : {
         "avatar_url" : null,
         "ci_config_path" : null,
         "default_branch" : "master",
         "description" : "Trivial project for testing build machinery quickly",
         "git_http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
         "git_ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "homepage" : "https://gitlab.example.com/mmusterman/awesome_project",
         "http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
         "id" : 239,
         "name" : "awesome_project",
         "namespace" : "mmusterman",
         "path_with_namespace" : "mmusterman/awesome_project",
         "ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "visibility_level" : 0,
         "web_url" : "https://gitlab.example.com/mmusterman/awesome_project"
      },
      "target_branch" : "master",
      "target_project_id" : 239,
      "time_estimate" : 0,
      "title" : "Remove the dummy line again",
      "total_time_spent" : 0,
      "updated_at" : "2018-05-15 07:45:37 -0700",
      "updated_by_id" : null,
      "url" : "https://gitlab.example.com/mmusterman/awesome_project/merge_requests/6",
      "work_in_progress" : false
   },
   "object_kind" : "merge_request",
   "project" : {
      "avatar_url" : null,
      "ci_config_path" : null,
      "default_branch" : "master",
      "description" : "Trivial project for testing build machinery quickly",
      "git_http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
      "git_ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
      "homepage" : "https://gitlab.example.com/mmusterman/awesome_project",
      "http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
      "id" : 239,
      "name" : "awesome_project",
      "namespace" : "mmusterman",
      "path_with_namespace" : "mmusterman/awesome_project",
      "ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
      "url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
      "visibility_level" : 0,
      "web_url" : "https://gitlab.example.com/mmusterman/awesome_project"
   },
   "user" : {
      "avatar_url" : "http://www.gravatar.com/avatar/e64c7d89f26bd1972efa854d13d7dd61?s=40&d=identicon",
      "name" : "Max Mustermann",
      "username" : "mmusterman"
   }
}
"""
gitJsonPayloadMR_editdesc = b"""
{
   "event_type" : "merge_request",
   "object_attributes" : {
      "action" : "update",
      "assignee_id" : null,
      "author_id" : 15,
      "created_at" : "2018-05-15 07:45:37 -0700",
      "description" : "Edited description.",
      "head_pipeline_id" : 29931,
      "human_time_estimate" : null,
      "human_total_time_spent" : null,
      "id" : 10850,
      "iid" : 6,
      "last_commit" : {
         "author" : {
            "email" : "mmusterman@example.com",
            "name" : "Max Mustermann"
         },
         "id" : "92268bc781b24f0a61b907da062950e9e5252a69",
         "message" : "Remove the dummy line again",
         "timestamp" : "2018-05-14T07:54:04-07:00",
         "url" : "https://gitlab.example.com/mmusterman/awesome_project/commit/92268bc781b24f0a61b907da062950e9e5252a69"
      },
      "last_edited_at" : "2018-05-15 07:49:55 -0700",
      "last_edited_by_id" : 15,
      "merge_commit_sha" : null,
      "merge_error" : null,
      "merge_params" : {
         "force_remove_source_branch" : 0
      },
      "merge_status" : "can_be_merged",
      "merge_user_id" : null,
      "merge_when_pipeline_succeeds" : false,
      "milestone_id" : null,
      "source" : {
         "avatar_url" : null,
         "ci_config_path" : null,
         "default_branch" : "master",
         "description" : "Trivial project for testing build machinery quickly",
         "git_http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
         "git_ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "homepage" : "https://gitlab.example.com/mmusterman/awesome_project",
         "http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
         "id" : 239,
         "name" : "awesome_project",
         "namespace" : "mmusterman",
         "path_with_namespace" : "mmusterman/awesome_project",
         "ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "visibility_level" : 0,
         "web_url" : "https://gitlab.example.com/mmusterman/awesome_project"
      },
      "source_branch" : "ms-viewport",
      "source_project_id" : 239,
      "state" : "opened",
      "target" : {
         "avatar_url" : null,
         "ci_config_path" : null,
         "default_branch" : "master",
         "description" : "Trivial project for testing build machinery quickly",
         "git_http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
         "git_ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "homepage" : "https://gitlab.example.com/mmusterman/awesome_project",
         "http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
         "id" : 239,
         "name" : "awesome_project",
         "namespace" : "mmusterman",
         "path_with_namespace" : "mmusterman/awesome_project",
         "ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "visibility_level" : 0,
         "web_url" : "https://gitlab.example.com/mmusterman/awesome_project"
      },
      "target_branch" : "master",
      "target_project_id" : 239,
      "time_estimate" : 0,
      "title" : "Remove the dummy line again",
      "total_time_spent" : 0,
      "updated_at" : "2018-05-15 07:49:55 -0700",
      "updated_by_id" : 15,
      "url" : "https://gitlab.example.com/mmusterman/awesome_project/merge_requests/6",
      "work_in_progress" : false
   },
   "object_kind" : "merge_request",
   "project" : {
      "avatar_url" : null,
      "ci_config_path" : null,
      "default_branch" : "master",
      "description" : "Trivial project for testing build machinery quickly",
      "git_http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
      "git_ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
      "homepage" : "https://gitlab.example.com/mmusterman/awesome_project",
      "http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
      "id" : 239,
      "name" : "awesome_project",
      "namespace" : "mmusterman",
      "path_with_namespace" : "mmusterman/awesome_project",
      "ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
      "url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
      "visibility_level" : 0,
      "web_url" : "https://gitlab.example.com/mmusterman/awesome_project"
   },
   "user" : {
      "avatar_url" : "http://www.gravatar.com/avatar/e64c7d89f26bd1972efa854d13d7dd61?s=40&d=identicon",
      "name" : "Max Mustermann",
      "username" : "mmusterman"
   }
}
"""
gitJsonPayloadMR_addcommit = b"""
{
   "event_type" : "merge_request",
   "object_attributes" : {
      "action" : "update",
      "assignee_id" : null,
      "author_id" : 15,
      "created_at" : "2018-05-15 07:45:37 -0700",
      "description" : "Edited description.",
      "head_pipeline_id" : 29931,
      "human_time_estimate" : null,
      "human_total_time_spent" : null,
      "id" : 10850,
      "iid" : 6,
      "last_commit" : {
         "author" : {
            "email" : "mmusterman@example.com",
            "name" : "Max Mustermann"
         },
         "id" : "cee8b01dcbaeed89563c2822f7c59a93c813eb6b",
         "message" : "debian/compat: update to 9",
         "timestamp" : "2018-05-15T07:51:11-07:00",
         "url" : "https://gitlab.example.com/mmusterman/awesome_project/commit/cee8b01dcbaeed89563c2822f7c59a93c813eb6b"
      },
      "last_edited_at" : "2018-05-15 14:49:55 UTC",
      "last_edited_by_id" : 15,
      "merge_commit_sha" : null,
      "merge_error" : null,
      "merge_params" : {
         "force_remove_source_branch" : 0
      },
      "merge_status" : "unchecked",
      "merge_user_id" : null,
      "merge_when_pipeline_succeeds" : false,
      "milestone_id" : null,
      "oldrev" : "92268bc781b24f0a61b907da062950e9e5252a69",
      "source" : {
         "avatar_url" : null,
         "ci_config_path" : null,
         "default_branch" : "master",
         "description" : "Trivial project for testing build machinery quickly",
         "git_http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
         "git_ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "homepage" : "https://gitlab.example.com/mmusterman/awesome_project",
         "http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
         "id" : 239,
         "name" : "awesome_project",
         "namespace" : "mmusterman",
         "path_with_namespace" : "mmusterman/awesome_project",
         "ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "visibility_level" : 0,
         "web_url" : "https://gitlab.example.com/mmusterman/awesome_project"
      },
      "source_branch" : "ms-viewport",
      "source_project_id" : 239,
      "state" : "opened",
      "target" : {
         "avatar_url" : null,
         "ci_config_path" : null,
         "default_branch" : "master",
         "description" : "Trivial project for testing build machinery quickly",
         "git_http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
         "git_ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "homepage" : "https://gitlab.example.com/mmusterman/awesome_project",
         "http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
         "id" : 239,
         "name" : "awesome_project",
         "namespace" : "mmusterman",
         "path_with_namespace" : "mmusterman/awesome_project",
         "ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "visibility_level" : 0,
         "web_url" : "https://gitlab.example.com/mmusterman/awesome_project"
      },
      "target_branch" : "master",
      "target_project_id" : 239,
      "time_estimate" : 0,
      "title" : "Remove the dummy line again",
      "total_time_spent" : 0,
      "updated_at" : "2018-05-15 14:51:27 UTC",
      "updated_by_id" : 15,
      "url" : "https://gitlab.example.com/mmusterman/awesome_project/merge_requests/6",
      "work_in_progress" : false
   },
   "object_kind" : "merge_request",
   "project" : {
      "avatar_url" : null,
      "ci_config_path" : null,
      "default_branch" : "master",
      "description" : "Trivial project for testing build machinery quickly",
      "git_http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
      "git_ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
      "homepage" : "https://gitlab.example.com/mmusterman/awesome_project",
      "http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
      "id" : 239,
      "name" : "awesome_project",
      "namespace" : "mmusterman",
      "path_with_namespace" : "mmusterman/awesome_project",
      "ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
      "url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
      "visibility_level" : 0,
      "web_url" : "https://gitlab.example.com/mmusterman/awesome_project"
   },
   "user" : {
      "avatar_url" : "http://www.gravatar.com/avatar/e64c7d89f26bd1972efa854d13d7dd61?s=40&d=identicon",
      "name" : "Max Mustermann",
      "username" : "mmusterman"
   }
}
"""
gitJsonPayloadMR_close = b"""
{
   "event_type" : "merge_request",
   "object_attributes" : {
      "action" : "close",
      "assignee_id" : null,
      "author_id" : 15,
      "created_at" : "2018-05-15 07:45:37 -0700",
      "description" : "Edited description.",
      "head_pipeline_id" : 29958,
      "human_time_estimate" : null,
      "human_total_time_spent" : null,
      "id" : 10850,
      "iid" : 6,
      "last_commit" : {
         "author" : {
            "email" : "mmusterman@example.com",
            "name" : "Max Mustermann"
         },
         "id" : "cee8b01dcbaeed89563c2822f7c59a93c813eb6b",
         "message" : "debian/compat: update to 9",
         "timestamp" : "2018-05-15T07:51:11-07:00",
         "url" : "https://gitlab.example.com/mmusterman/awesome_project/commit/cee8b01dcbaeed89563c2822f7c59a93c813eb6b"
      },
      "last_edited_at" : "2018-05-15 07:49:55 -0700",
      "last_edited_by_id" : 15,
      "merge_commit_sha" : null,
      "merge_error" : null,
      "merge_params" : {
         "force_remove_source_branch" : 0
      },
      "merge_status" : "can_be_merged",
      "merge_user_id" : null,
      "merge_when_pipeline_succeeds" : false,
      "milestone_id" : null,
      "source" : {
         "avatar_url" : null,
         "ci_config_path" : null,
         "default_branch" : "master",
         "description" : "Trivial project for testing build machinery quickly",
         "git_http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
         "git_ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "homepage" : "https://gitlab.example.com/mmusterman/awesome_project",
         "http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
         "id" : 239,
         "name" : "awesome_project",
         "namespace" : "mmusterman",
         "path_with_namespace" : "mmusterman/awesome_project",
         "ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "visibility_level" : 0,
         "web_url" : "https://gitlab.example.com/mmusterman/awesome_project"
      },
      "source_branch" : "ms-viewport",
      "source_project_id" : 239,
      "state" : "closed",
      "target" : {
         "avatar_url" : null,
         "ci_config_path" : null,
         "default_branch" : "master",
         "description" : "Trivial project for testing build machinery quickly",
         "git_http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
         "git_ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "homepage" : "https://gitlab.example.com/mmusterman/awesome_project",
         "http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
         "id" : 239,
         "name" : "awesome_project",
         "namespace" : "mmusterman",
         "path_with_namespace" : "mmusterman/awesome_project",
         "ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "visibility_level" : 0,
         "web_url" : "https://gitlab.example.com/mmusterman/awesome_project"
      },
      "target_branch" : "master",
      "target_project_id" : 239,
      "time_estimate" : 0,
      "title" : "Remove the dummy line again",
      "total_time_spent" : 0,
      "updated_at" : "2018-05-15 07:52:01 -0700",
      "updated_by_id" : 15,
      "url" : "https://gitlab.example.com/mmusterman/awesome_project/merge_requests/6",
      "work_in_progress" : false
   },
   "object_kind" : "merge_request",
   "project" : {
      "avatar_url" : null,
      "ci_config_path" : null,
      "default_branch" : "master",
      "description" : "Trivial project for testing build machinery quickly",
      "git_http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
      "git_ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
      "homepage" : "https://gitlab.example.com/mmusterman/awesome_project",
      "http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
      "id" : 239,
      "name" : "awesome_project",
      "namespace" : "mmusterman",
      "path_with_namespace" : "mmusterman/awesome_project",
      "ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
      "url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
      "visibility_level" : 0,
      "web_url" : "https://gitlab.example.com/mmusterman/awesome_project"
   },
   "user" : {
      "avatar_url" : "http://www.gravatar.com/avatar/e64c7d89f26bd1972efa854d13d7dd61?s=40&d=identicon",
      "name" : "Max Mustermann",
      "username" : "mmusterman"
   }
}
"""
gitJsonPayloadMR_reopen = b"""
{
   "event_type" : "merge_request",
   "object_attributes" : {
      "action" : "reopen",
      "assignee_id" : null,
      "author_id" : 15,
      "created_at" : "2018-05-15 07:45:37 -0700",
      "description" : "Edited description.",
      "head_pipeline_id" : 29958,
      "human_time_estimate" : null,
      "human_total_time_spent" : null,
      "id" : 10850,
      "iid" : 6,
      "last_commit" : {
         "author" : {
            "email" : "mmusterman@example.com",
            "name" : "Max Mustermann"
         },
         "id" : "cee8b01dcbaeed89563c2822f7c59a93c813eb6b",
         "message" : "debian/compat: update to 9",
         "timestamp" : "2018-05-15T07:51:11-07:00",
         "url" : "https://gitlab.example.com/mmusterman/awesome_project/commit/cee8b01dcbaeed89563c2822f7c59a93c813eb6b"
      },
      "last_edited_at" : "2018-05-15 07:49:55 -0700",
      "last_edited_by_id" : 15,
      "merge_commit_sha" : null,
      "merge_error" : null,
      "merge_params" : {
         "force_remove_source_branch" : 0
      },
      "merge_status" : "can_be_merged",
      "merge_user_id" : null,
      "merge_when_pipeline_succeeds" : false,
      "milestone_id" : null,
      "source" : {
         "avatar_url" : null,
         "ci_config_path" : null,
         "default_branch" : "master",
         "description" : "Trivial project for testing build machinery quickly",
         "git_http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
         "git_ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "homepage" : "https://gitlab.example.com/mmusterman/awesome_project",
         "http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
         "id" : 239,
         "name" : "awesome_project",
         "namespace" : "mmusterman",
         "path_with_namespace" : "mmusterman/awesome_project",
         "ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "visibility_level" : 0,
         "web_url" : "https://gitlab.example.com/mmusterman/awesome_project"
      },
      "source_branch" : "ms-viewport",
      "source_project_id" : 239,
      "state" : "opened",
      "target" : {
         "avatar_url" : null,
         "ci_config_path" : null,
         "default_branch" : "master",
         "description" : "Trivial project for testing build machinery quickly",
         "git_http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
         "git_ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "homepage" : "https://gitlab.example.com/mmusterman/awesome_project",
         "http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
         "id" : 239,
         "name" : "awesome_project",
         "namespace" : "mmusterman",
         "path_with_namespace" : "mmusterman/awesome_project",
         "ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "visibility_level" : 0,
         "web_url" : "https://gitlab.example.com/mmusterman/awesome_project"
      },
      "target_branch" : "master",
      "target_project_id" : 239,
      "time_estimate" : 0,
      "title" : "Remove the dummy line again",
      "total_time_spent" : 0,
      "updated_at" : "2018-05-15 07:53:27 -0700",
      "updated_by_id" : 15,
      "url" : "https://gitlab.example.com/mmusterman/awesome_project/merge_requests/6",
      "work_in_progress" : false
   },
   "object_kind" : "merge_request",
   "project" : {
      "avatar_url" : null,
      "ci_config_path" : null,
      "default_branch" : "master",
      "description" : "Trivial project for testing build machinery quickly",
      "git_http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
      "git_ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
      "homepage" : "https://gitlab.example.com/mmusterman/awesome_project",
      "http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
      "id" : 239,
      "name" : "awesome_project",
      "namespace" : "mmusterman",
      "path_with_namespace" : "mmusterman/awesome_project",
      "ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
      "url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
      "visibility_level" : 0,
      "web_url" : "https://gitlab.example.com/mmusterman/awesome_project"
   },
   "user" : {
      "avatar_url" : "http://www.gravatar.com/avatar/e64c7d89f26bd1972efa854d13d7dd61?s=40&d=identicon",
      "name" : "Max Mustermann",
      "username" : "mmusterman"
   }
}
"""

# == Merge requests from a fork of the project
# (Captured more accurately than above test data)
gitJsonPayloadMR_open_forked = b"""
{
   "changes" : {
      "total_time_spent" : {
         "current" : 0,
         "previous" : null
      }
   },
   "event_type" : "merge_request",
   "labels" : [],
   "object_attributes" : {
      "action" : "open",
      "assignee_id" : null,
      "author_id" : 15,
      "created_at" : "2018-05-19 06:57:12 -0700",
      "description" : "This is a merge request from a fork of the project.",
      "head_pipeline_id" : null,
      "human_time_estimate" : null,
      "human_total_time_spent" : null,
      "id" : 10914,
      "iid" : 7,
      "last_commit" : {
         "author" : {
            "email" : "mmusterman@example.com",
            "name" : "Max Mustermann"
         },
         "id" : "e46ee239f3d6d41ade4d1e610669dd71ed86ec80",
         "message" : "Add note to README",
         "timestamp" : "2018-05-19T06:35:26-07:00",
         "url" : "https://gitlab.example.com/mmusterman/awesome_project/commit/e46ee239f3d6d41ade4d1e610669dd71ed86ec80"
      },
      "last_edited_at" : null,
      "last_edited_by_id" : null,
      "merge_commit_sha" : null,
      "merge_error" : null,
      "merge_params" : {
         "force_remove_source_branch" : "0"
      },
      "merge_status" : "unchecked",
      "merge_user_id" : null,
      "merge_when_pipeline_succeeds" : false,
      "milestone_id" : null,
      "source" : {
         "avatar_url" : null,
         "ci_config_path" : null,
         "default_branch" : "master",
         "description" : "Trivial project for testing build machinery quickly",
         "git_http_url" : "https://gitlab.example.com/build/awesome_project.git",
         "git_ssh_url" : "git@gitlab.example.com:build/awesome_project.git",
         "homepage" : "https://gitlab.example.com/build/awesome_project",
         "http_url" : "https://gitlab.example.com/build/awesome_project.git",
         "id" : 2337,
         "name" : "awesome_project",
         "namespace" : "build",
         "path_with_namespace" : "build/awesome_project",
         "ssh_url" : "git@gitlab.example.com:build/awesome_project.git",
         "url" : "git@gitlab.example.com:build/awesome_project.git",
         "visibility_level" : 0,
         "web_url" : "https://gitlab.example.com/build/awesome_project"
      },
      "source_branch" : "ms-viewport",
      "source_project_id" : 2337,
      "state" : "opened",
      "target" : {
         "avatar_url" : null,
         "ci_config_path" : null,
         "default_branch" : "master",
         "description" : "Trivial project for testing build machinery quickly",
         "git_http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
         "git_ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "homepage" : "https://gitlab.example.com/mmusterman/awesome_project",
         "http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
         "id" : 239,
         "name" : "awesome_project",
         "namespace" : "mmusterman",
         "path_with_namespace" : "mmusterman/awesome_project",
         "ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
         "visibility_level" : 0,
         "web_url" : "https://gitlab.example.com/mmusterman/awesome_project"
      },
      "target_branch" : "master",
      "target_project_id" : 239,
      "time_estimate" : 0,
      "title" : "Add note to README",
      "total_time_spent" : 0,
      "updated_at" : "2018-05-19 06:57:12 -0700",
      "updated_by_id" : null,
      "url" : "https://gitlab.example.com/mmusterman/awesome_project/merge_requests/7",
      "work_in_progress" : false
   },
   "object_kind" : "merge_request",
   "project" : {
      "avatar_url" : null,
      "ci_config_path" : null,
      "default_branch" : "master",
      "description" : "Trivial project for testing build machinery quickly",
      "git_http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
      "git_ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
      "homepage" : "https://gitlab.example.com/mmusterman/awesome_project",
      "http_url" : "https://gitlab.example.com/mmusterman/awesome_project.git",
      "id" : 239,
      "name" : "awesome_project",
      "namespace" : "mmusterman",
      "path_with_namespace" : "mmusterman/awesome_project",
      "ssh_url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
      "url" : "git@gitlab.example.com:mmusterman/awesome_project.git",
      "visibility_level" : 0,
      "web_url" : "https://gitlab.example.com/mmusterman/awesome_project"
   },
   "repository" : {
      "description" : "Trivial project for testing build machinery quickly",
      "homepage" : "https://gitlab.example.com/mmusterman/awesome_project",
      "name" : "awesome_project",
      "url" : "git@gitlab.example.com:mmusterman/awesome_project.git"
   },
   "user" : {
      "avatar_url" : "http://www.gravatar.com/avatar/e64c7d89f26bd1972efa854d13d7dd61?s=40&d=identicon",
      "name" : "Max Mustermann",
      "username" : "mmusterman"
   }
}
"""


def FakeRequestMR(content):
    request = FakeRequest(content=content)
    request.uri = b"/change_hook/gitlab"
    request.args = {b'codebase': [b'MyCodebase']}
    request.received_headers[_HEADER_EVENT] = b"Merge Request Hook"
    request.method = b"POST"
    return request


class TestChangeHookConfiguredWithGitChange(unittest.TestCase,
                                            TestReactorMixin):

    def setUp(self):
        self.setUpTestReactor()
        self.changeHook = change_hook.ChangeHookResource(
            dialects={'gitlab': True}, master=fakeMasterForHooks(self))

    def check_changes_tag_event(self, r, project='', codebase=None):
        self.assertEqual(len(self.changeHook.master.data.updates.changesAdded), 2)
        change = self.changeHook.master.data.updates.changesAdded[0]

        self.assertEqual(change["repository"], "git@localhost:diaspora.git")
        self.assertEqual(
            change["when_timestamp"],
            1323692851
        )
        self.assertEqual(change["branch"], "v1.0.0")

    def check_changes_mr_event(self, r, project='awesome_project', codebase=None, timestamp=1526309644, source_repo=None):
        self.assertEqual(len(self.changeHook.master.data.updates.changesAdded), 1)
        change = self.changeHook.master.data.updates.changesAdded[0]

        self.assertEqual(change["repository"],
                         "https://gitlab.example.com/mmusterman/awesome_project.git")
        if source_repo is None:
            source_repo = "https://gitlab.example.com/mmusterman/awesome_project.git"
        self.assertEqual(change['properties']["source_repository"],
                         source_repo)
        self.assertEqual(change['properties']["target_repository"],
                         "https://gitlab.example.com/mmusterman/awesome_project.git")
        self.assertEqual(
            change["when_timestamp"],
            timestamp
        )
        self.assertEqual(change["branch"], "master")
        self.assertEqual(change['properties']["source_branch"], 'ms-viewport')
        self.assertEqual(change['properties']["target_branch"], 'master')
        self.assertEqual(change["category"], "merge_request")
        self.assertEqual(change.get("project"), project)

    def check_changes_push_event(self, r, project='diaspora', codebase=None):
        self.assertEqual(len(self.changeHook.master.data.updates.changesAdded), 2)
        change = self.changeHook.master.data.updates.changesAdded[0]

        self.assertEqual(change["repository"], "git@localhost:diaspora.git")
        self.assertEqual(
            change["when_timestamp"],
            1323692851
        )
        self.assertEqual(
            change["author"], "Jordi Mallach <jordi@softcatala.org>")
        self.assertEqual(
            change["revision"], 'b6568db1bc1dcd7f8b4d5a946b0b91f9dacd7327')
        self.assertEqual(
            change["comments"], "Update Catalan translation to e38cb41.")
        self.assertEqual(change["branch"], "master")
        self.assertEqual(change[
            "revlink"], "http://localhost/diaspora/commits/b6568db1bc1dcd7f8b4d5a946b0b91f9dacd7327")

        change = self.changeHook.master.data.updates.changesAdded[1]
        self.assertEqual(change["repository"], "git@localhost:diaspora.git")
        self.assertEqual(
            change["when_timestamp"],
            1325626589
        )
        self.assertEqual(
            change["author"], "GitLab dev user <gitlabdev@dv6700.(none)>")
        self.assertEqual(change["src"], "git")
        self.assertEqual(
            change["revision"], 'da1560886d4f094c3e6c9ef40349f7d38b5d27d7')
        self.assertEqual(change["comments"], "fixed readme")
        self.assertEqual(change["branch"], "master")
        self.assertEqual(change[
            "revlink"], "http://localhost/diaspora/commits/da1560886d4f094c3e6c9ef40349f7d38b5d27d7")

        # FIXME: should we convert project name to canonical case?
        # Or should change filter be case insensitive?
        self.assertEqual(change.get("project").lower(), project.lower())
        self.assertEqual(change.get("codebase"), codebase)

    # Test 'base' hook with attributes. We should get a json string representing
    # a Change object as a dictionary. All values show be set.
    @defer.inlineCallbacks
    def testGitWithChange(self):
        self.request = FakeRequest(content=gitJsonPayload)
        self.request.uri = b"/change_hook/gitlab"
        self.request.method = b"POST"
        self.request.received_headers[_HEADER_EVENT] = b"Push Hook"
        res = yield self.request.test_render(self.changeHook)
        self.check_changes_push_event(res)

    @defer.inlineCallbacks
    def testGitWithChange_WithProjectToo(self):
        self.request = FakeRequest(content=gitJsonPayload)
        self.request.uri = b"/change_hook/gitlab"
        self.request.args = {b'project': [b'Diaspora']}
        self.request.received_headers[_HEADER_EVENT] = b"Push Hook"
        self.request.method = b"POST"
        res = yield self.request.test_render(self.changeHook)
        self.check_changes_push_event(res, project="Diaspora")

    @defer.inlineCallbacks
    def testGitWithChange_WithCodebaseToo(self):
        self.request = FakeRequest(content=gitJsonPayload)
        self.request.uri = b"/change_hook/gitlab"
        self.request.args = {b'codebase': [b'MyCodebase']}
        self.request.received_headers[_HEADER_EVENT] = b"Push Hook"
        self.request.method = b"POST"
        res = yield self.request.test_render(self.changeHook)
        self.check_changes_push_event(res, codebase="MyCodebase")

    @defer.inlineCallbacks
    def testGitWithChange_WithPushTag(self):
        self.request = FakeRequest(content=gitJsonPayloadTag)
        self.request.uri = b"/change_hook/gitlab"
        self.request.args = {b'codebase': [b'MyCodebase']}
        self.request.received_headers[_HEADER_EVENT] = b"Push Hook"
        self.request.method = b"POST"
        res = yield self.request.test_render(self.changeHook)
        self.check_changes_tag_event(res, codebase="MyCodebase")

    @defer.inlineCallbacks
    def testGitWithNoJson(self):
        self.request = FakeRequest()
        self.request.uri = b"/change_hook/gitlab"
        self.request.method = b"POST"
        self.request.received_headers[_HEADER_EVENT] = b"Push Hook"
        yield self.request.test_render(self.changeHook)

        self.assertEqual(len(self.changeHook.master.data.updates.changesAdded), 0)
        self.assertIn(b"Error loading JSON:", self.request.written)
        self.request.setResponseCode.assert_called_with(400, mock.ANY)

    @defer.inlineCallbacks
    def test_event_property(self):
        self.request = FakeRequest(content=gitJsonPayload)
        self.request.received_headers[_HEADER_EVENT] = b"Push Hook"
        self.request.uri = b"/change_hook/gitlab"
        self.request.method = b"POST"
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.data.updates.changesAdded), 2)
        change = self.changeHook.master.data.updates.changesAdded[0]
        self.assertEqual(change["properties"]["event"], "Push Hook")
        self.assertEqual(change["category"], "Push Hook")

    @defer.inlineCallbacks
    def testGitWithChange_WithMR_open(self):
        self.request = FakeRequestMR(content=gitJsonPayloadMR_open)
        res = yield self.request.test_render(self.changeHook)
        self.check_changes_mr_event(res, codebase="MyCodebase")
        change = self.changeHook.master.data.updates.changesAdded[0]
        self.assertEqual(change["category"], "merge_request")

    @defer.inlineCallbacks
    def testGitWithChange_WithMR_editdesc(self):
        self.request = FakeRequestMR(content=gitJsonPayloadMR_editdesc)
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.data.updates.changesAdded), 0)

    @defer.inlineCallbacks
    def testGitWithChange_WithMR_addcommit(self):
        self.request = FakeRequestMR(content=gitJsonPayloadMR_addcommit)
        res = yield self.request.test_render(self.changeHook)
        self.check_changes_mr_event(res, codebase="MyCodebase", timestamp=1526395871)
        change = self.changeHook.master.data.updates.changesAdded[0]
        self.assertEqual(change["category"], "merge_request")

    @defer.inlineCallbacks
    def testGitWithChange_WithMR_close(self):
        self.request = FakeRequestMR(content=gitJsonPayloadMR_close)
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.data.updates.changesAdded), 0)

    @defer.inlineCallbacks
    def testGitWithChange_WithMR_reopen(self):
        self.request = FakeRequestMR(content=gitJsonPayloadMR_reopen)
        res = yield self.request.test_render(self.changeHook)
        self.check_changes_mr_event(res, codebase="MyCodebase", timestamp=1526395871)
        change = self.changeHook.master.data.updates.changesAdded[0]
        self.assertEqual(change["category"], "merge_request")

    @defer.inlineCallbacks
    def testGitWithChange_WithMR_open_forked(self):
        self.request = FakeRequestMR(content=gitJsonPayloadMR_open_forked)
        res = yield self.request.test_render(self.changeHook)
        self.check_changes_mr_event(
                res, codebase="MyCodebase", timestamp=1526736926,
                source_repo="https://gitlab.example.com/build/awesome_project.git")
        change = self.changeHook.master.data.updates.changesAdded[0]
        self.assertEqual(change["category"], "merge_request")


class TestChangeHookConfiguredWithSecret(unittest.TestCase, TestReactorMixin):

    _SECRET = 'thesecret'

    def setUp(self):
        self.setUpTestReactor()
        self.master = fakeMasterForHooks(self)

        fakeStorageService = FakeSecretStorage()
        fakeStorageService.reconfigService(secretdict={"secret_key": self._SECRET})

        self.secretService = SecretManager()
        self.secretService.services = [fakeStorageService]
        self.master.addService(self.secretService)

        self.changeHook = change_hook.ChangeHookResource(
            dialects={'gitlab': {'secret': util.Secret("secret_key")}},
            master=self.master)

    @defer.inlineCallbacks
    def test_missing_secret(self):
        self.request = FakeRequest(content=gitJsonPayloadTag)
        self.request.uri = b"/change_hook/gitlab"
        self.request.args = {b'codebase': [b'MyCodebase']}
        self.request.method = b"POST"
        self.request.received_headers[_HEADER_EVENT] = b"Push Hook"
        yield self.request.test_render(self.changeHook)
        expected = b'Invalid secret'
        self.assertEqual(self.request.written, expected)
        self.assertEqual(len(self.changeHook.master.data.updates.changesAdded), 0)

    @defer.inlineCallbacks
    def test_valid_secret(self):
        self.request = FakeRequest(content=gitJsonPayload)
        self.request.received_headers[_HEADER_GITLAB_TOKEN] = self._SECRET
        self.request.received_headers[_HEADER_EVENT] = b"Push Hook"
        self.request.uri = b"/change_hook/gitlab"
        self.request.method = b"POST"
        yield self.request.test_render(self.changeHook)
        self.assertEqual(len(self.changeHook.master.data.updates.changesAdded), 2)
