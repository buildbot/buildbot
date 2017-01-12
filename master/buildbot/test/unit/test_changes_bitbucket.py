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

import re
from datetime import datetime

from twisted.internet import defer
from twisted.internet import reactor
from twisted.trial import unittest
from twisted.web import client
from twisted.web.error import Error

from buildbot.changes.bitbucket import BitbucketPullrequestPoller
from buildbot.test.util import changesource


class SourceRest():
    """https://bitbucket.org/!api/2.0/repositories/{owner}/{slug}"""
    template = """\
{

    "hash": "%(hash)s",
    "links": {
        "html": {
            "href": "https://bitbucket.org/%(owner)s/%(slug)s/commits/%(short_hash)s"
        }
    },
    "repository": {
        "links": {
            "self": {
                "href": "https://bitbucket.org/!api/2.0/repositories/%(owner)s/%(slug)s"
            }
        }
    },
    "date": "%(date)s"

}
"""
    repo_template = """\
{
    "links": {
        "html": {
            "href": "https://bitbucket.org/%(owner)s/%(slug)s"
        }
    }
}
"""

    def __init__(self, owner, slug, hash, date):
        self.owner = owner
        self.slug = slug
        self.hash = hash
        self.date = date

    def request(self):
        return self.template % {
            "owner": self.owner,
            "slug": self.slug,
            "hash": self.hash,
            "short_hash": self.hash[0:12],
            "date": self.date,
        }

    def repo_request(self):
        return self.repo_template % {
            "owner": self.owner,
            "slug": self.slug,
        }


class PullRequestRest():
    """https://bitbucket.org/!api/2.0/repositories/{owner}/{slug}/pullrequests/{pull_request_id}"""
    template = """\
{

    "description": "%(description)s",
    "title": "%(title)s",
    "source": {
        "commit": {
            "hash": "%(hash)s",
            "links": {
                "self": {
                    "href": "https://bitbucket.org/!api/2.0/repositories/%(owner)s/%(slug)s/commit/%(hash)s"
                }
            }
        }
    },
    "state": "OPEN",
    "author": {
        "display_name": "%(display_name)s"
    },
    "created_on": "%(created_on)s",
    "participants": [
    ],
    "updated_on": "%(updated_on)s",
    "merge_commit": null,
    "id": %(id)d

}
"""

    def __init__(self, nr, title, description, display_name, source, created_on, updated_on=None):
        self.nr = nr
        self.title = title
        self.description = description
        self.display_name = display_name
        self.source = source
        self.created_on = created_on
        if updated_on:
            self.updated_on = updated_on
        else:
            self.updated_on = self.created_on

    def request(self):
        return self.template % {
            "description": self.description,
            "title": self.title,
            "hash": self.source.hash,
            "short_hash": self.source.hash[0:12],
            "owner": self.source.owner,
            "slug": self.source.slug,
            "display_name": self.display_name,
            "created_on": self.created_on,
            "updated_on": self.updated_on,
            "id": self.nr,
        }


class PullRequestListRest():
    """https://bitbucket.org/api/2.0/repositories/{owner}/{slug}/pullrequests"""
    template = """\
        {
            "description": "%(description)s",
            "links": {
                "self": {
                    "href": "https://bitbucket.org/!api/2.0/repositories/%(owner)s/%(slug)s/pullrequests/%(id)d"
                },
                "html": {
                    "href": "https://bitbucket.org/%(owner)s/%(slug)s/pull-request/%(id)d"
                }
            },
            "author": {
                "display_name": "%(display_name)s"
            },
            "title": "%(title)s",
            "source": {
                "commit": {
                    "hash": "%(short_hash)s",
                    "links": {
                        "self": {
                            "href": "https://bitbucket.org/!api/2.0/repositories/%(src_owner)s/%(src_slug)s/commit/%(short_hash)s"
                        }
                    }
                },
                "repository": {
                    "links": {
                        "self": {
                            "href": "https://bitbucket.org/!api/2.0/repositories/%(src_owner)s/%(src_slug)s"
                        }
                    }
                },
                "branch": {
                    "name": "default"
                }
            },
            "state": "OPEN",
            "created_on": "%(created_on)s",
            "updated_on": "%(updated_on)s",
            "merge_commit": null,
            "id": %(id)s
        }
"""

    def __init__(self, owner, slug, prs):
        self.owner = owner
        self.slug = slug
        self.prs = prs

        self.pr_by_id = {}
        self.src_by_url = {}
        for pr in prs:
            self.pr_by_id[pr.nr] = pr
            self.src_by_url["%s/%s"
                            % (pr.source.owner, pr.source.slug)] = pr.source

    def request(self):

        s = ""
        for pr in self.prs:
            s += self.template % {
                "description": pr.description,
                "owner": self.owner,
                "slug": self.slug,
                "display_name": pr.display_name,
                "title": pr.title,
                "hash": pr.source.hash,
                "short_hash": pr.source.hash[0:12],
                "src_owner": pr.source.owner,
                "src_slug": pr.source.slug,
                "created_on": pr.created_on,
                "updated_on": pr.updated_on,
                "id": pr.nr,
            }
        return """\
{

    "pagelen": 10,
    "values": [%s
    ],
    "page": 1

}
""" % s

    def getPage(self, url, timeout=None):

        list_url_re = re.compile(
            r"https://bitbucket.org/api/2.0/repositories/%s/%s/pullrequests"
            % (self.owner, self.slug))
        pr_url_re = re.compile(
            r"https://bitbucket.org/!api/2.0/repositories/%s/%s/pullrequests/(?P<id>\d+)"
            % (self.owner, self.slug))
        source_commit_url_re = re.compile(
            r"https://bitbucket.org/!api/2.0/repositories/(?P<src_owner>.*)/(?P<src_slug>.*)/commit/(?P<hash>\d+)")
        source_url_re = re.compile(
            r"https://bitbucket.org/!api/2.0/repositories/(?P<src_owner>.*)/(?P<src_slug>.*)")

        if list_url_re.match(url):
            return defer.succeed(self.request())

        m = pr_url_re.match(url)
        if m:
            return self.pr_by_id[int(m.group("id"))].request()

        m = source_commit_url_re.match(url)
        if m:
            return self.src_by_url["%s/%s"
                                   % (m.group("src_owner"), m.group("src_slug"))].request()

        m = source_url_re.match(url)
        if m:
            return self.src_by_url["%s/%s"
                                   % (m.group("src_owner"), m.group("src_slug"))].repo_request()

        raise Error(code=404)


class TestBitbucketPullrequestPoller(changesource.ChangeSourceMixin, unittest.TestCase):

    def setUp(self):
        # create pull requests
        self.date = "2013-10-15T20:38:20.001797+00:00"
        self.date_epoch = datetime.strptime(self.date.split('.')[0],
                                            '%Y-%m-%dT%H:%M:%S')
        src = SourceRest(
            owner="contributor",
            slug="slug",
            hash="1111111111111111111111111111111111111111",
            date=self.date,
        )
        pr = PullRequestRest(
            nr=1,
            title="title",
            description="description",
            display_name="contributor",
            source=src,
            created_on=self.date,
        )
        self.pr_list = PullRequestListRest(
            owner="owner",
            slug="slug",
            prs=[pr],
        )
        # update
        src = SourceRest(
            owner="contributor",
            slug="slug",
            hash="2222222222222222222222222222222222222222",
            date=self.date,
        )
        pr = PullRequestRest(
            nr=1,
            title="title",
            description="description",
            display_name="contributor",
            source=src,
            created_on=self.date,
        )
        self.pr_list2 = PullRequestListRest(
            owner="owner",
            slug="slug",
            prs=[pr],
        )
        return self.setUpChangeSource()

    def tearDown(self):
        return self.tearDownChangeSource()

    def _fakeGetPage(self, result):
        # Install a fake getPage that puts the requested URL in self.getPage_got_url
        # and return result
        self.getPage_got_url = None

        def fake(url, timeout=None):
            self.getPage_got_url = url
            return defer.succeed(result)
        self.patch(client, "getPage", fake)

    def _fakeGetPage404(self):

        def fail(url, timeout=None):
            raise Error(code=404)
        self.patch(client, "getPage", fail)

    def attachDefaultChangeSource(self):
        return self.attachChangeSource(BitbucketPullrequestPoller(
            owner='owner',
            slug='slug'))

    # tests
    @defer.inlineCallbacks
    def test_describe(self):
        yield self.attachDefaultChangeSource()
        assert re.search(r'owner/slug', self.changesource.describe())

    @defer.inlineCallbacks
    def test_poll_unknown_repo(self):
        yield self.attachDefaultChangeSource()
        # Polling a non-existent repository should result in a 404
        self._fakeGetPage404()
        try:
            yield self.changesource.poll()
            self.fail(
                'Polling a non-existent repository should result in a 404.')
        except Exception as e:
            self.assertEqual(str(e), '404 Not Found')

    @defer.inlineCallbacks
    def test_poll_no_pull_requests(self):
        yield self.attachDefaultChangeSource()
        rest = PullRequestListRest(owner="owner", slug="slug", prs=[])
        self._fakeGetPage(rest.request())
        yield self.changesource.poll()

        self.assertEqual(len(self.master.data.updates.changesAdded), 0)

    @defer.inlineCallbacks
    def test_poll_new_pull_requests(self):
        yield self.attachDefaultChangeSource()
        # patch client.getPage()
        self.patch(client, "getPage", self.pr_list.getPage)

        yield self.changesource.poll()

        self.assertEqual(self.master.data.updates.changesAdded, [{
            'author': u'contributor',
            'branch': None,
            'category': None,
            'codebase': None,
            'comments': u'pull-request #1: title\nhttps://bitbucket.org/owner/slug/pull-request/1',
            'files': None,
            'project': u'',
            'properties': {},
            'repository': u'https://bitbucket.org/contributor/slug',
            'revision': u'1111111111111111111111111111111111111111',
            'revlink': u'https://bitbucket.org/contributor/slug/commits/111111111111',
            'src': u'bitbucket',
            'when_timestamp': 1381869500,
        }])

    @defer.inlineCallbacks
    def test_poll_no_updated_pull_request(self):
        yield self.attachDefaultChangeSource()

        # patch client.getPage()
        self.patch(client, "getPage", self.pr_list.getPage)

        yield self.changesource.poll()

        self.assertEqual(self.master.data.updates.changesAdded, [{
            'author': u'contributor',
            'branch': None,
            'category': None,
            'codebase': None,
            'comments': u'pull-request #1: title\nhttps://bitbucket.org/owner/slug/pull-request/1',
            'files': None,
            'project': u'',
            'properties': {},
            'repository': u'https://bitbucket.org/contributor/slug',
            'revision': u'1111111111111111111111111111111111111111',
            'revlink': u'https://bitbucket.org/contributor/slug/commits/111111111111',
            'src': u'bitbucket',
            'when_timestamp': 1381869500,
        }])

        # repoll
        yield self.changesource.poll()
        self.assertEqual(len(self.master.data.updates.changesAdded), 1)

    @defer.inlineCallbacks
    def test_poll_updated_pull_request(self):
        yield self.attachDefaultChangeSource()
        # patch client.getPage()
        self.patch(client, "getPage", self.pr_list.getPage)

        yield self.changesource.poll()

        self.assertEqual(self.master.data.updates.changesAdded, [{
            'author': u'contributor',
            'branch': None,
            'category': None,
            'codebase': None,
            'comments': u'pull-request #1: title\nhttps://bitbucket.org/owner/slug/pull-request/1',
            'files': None,
            'project': u'',
            'properties': {},
            'repository': u'https://bitbucket.org/contributor/slug',

            'revision': u'1111111111111111111111111111111111111111',
            'revlink': u'https://bitbucket.org/contributor/slug/commits/111111111111',
            'src': u'bitbucket',
            'when_timestamp': 1381869500,
        }])
        self.patch(client, "getPage", self.pr_list2.getPage)
        yield self.changesource.poll()

        self.assertEqual(self.master.data.updates.changesAdded, [
            {
                'author': u'contributor',
                'branch': None,
                'category': None,
                'codebase': None,
                'comments': u'pull-request #1: title\nhttps://bitbucket.org/owner/slug/pull-request/1',
                'files': None,
                'project': u'',
                'properties': {},
                'repository': u'https://bitbucket.org/contributor/slug',
                'revision': u'1111111111111111111111111111111111111111',
                'revlink': u'https://bitbucket.org/contributor/slug/commits/111111111111',
                'src': u'bitbucket',
                'when_timestamp': 1381869500,
            },
            {
                'author': u'contributor',
                'branch': None,
                'category': None,
                'codebase': None,
                'comments': u'pull-request #1: title\nhttps://bitbucket.org/owner/slug/pull-request/1',
                'files': None,
                'project': u'',
                'properties': {},
                'repository': u'https://bitbucket.org/contributor/slug',
                'revision': u'2222222222222222222222222222222222222222',
                'revlink': u'https://bitbucket.org/contributor/slug/commits/222222222222',
                'src': u'bitbucket',
                'when_timestamp': 1381869500,
            }
        ])

    @defer.inlineCallbacks
    def test_poll_pull_request_filter_False(self):
        yield self.attachChangeSource(BitbucketPullrequestPoller(
            owner='owner',
            slug='slug',
            pullrequest_filter=lambda x: False
        ))

        # patch client.getPage()
        self.patch(client, "getPage", self.pr_list.getPage)

        yield self.changesource.poll()

        self.assertEqual(len(self.master.data.updates.changesAdded), 0)

    @defer.inlineCallbacks
    def test_poll_pull_request_filter_True(self):
        yield self.attachChangeSource(BitbucketPullrequestPoller(
            owner='owner',
            slug='slug',
            pullrequest_filter=lambda x: True
        ))

        # patch client.getPage()
        self.patch(client, "getPage", self.pr_list.getPage)

        yield self.changesource.poll()

        self.assertEqual(self.master.data.updates.changesAdded, [{
            'author': u'contributor',
            'branch': None,
            'category': None,
            'codebase': None,
            'comments': u'pull-request #1: title\nhttps://bitbucket.org/owner/slug/pull-request/1',
            'files': None,
            'project': u'',
            'properties': {},
            'repository': u'https://bitbucket.org/contributor/slug',
            'revision': u'1111111111111111111111111111111111111111',
            'revlink': u'https://bitbucket.org/contributor/slug/commits/111111111111',
            'src': u'bitbucket',
            'when_timestamp': 1381869500,
        }])

    @defer.inlineCallbacks
    def test_poll_pull_request_not_useTimestamps(self):
        yield self.attachChangeSource(BitbucketPullrequestPoller(
            owner='owner',
            slug='slug',
            useTimestamps=False,
        ))

        # patch client.getPage()
        self.patch(client, "getPage", self.pr_list.getPage)
        self.patch(reactor, "seconds", lambda: 1396825656)

        yield self.changesource.poll()
        self.assertEqual(self.master.data.updates.changesAdded, [{
            'author': u'contributor',
            'branch': None,
            'category': None,
            'codebase': None,
            'comments': u'pull-request #1: title\nhttps://bitbucket.org/owner/slug/pull-request/1',
            'files': None,
            'project': u'',
            'properties': {},
            'repository': u'https://bitbucket.org/contributor/slug',
            'revision': u'1111111111111111111111111111111111111111',
            'revlink': u'https://bitbucket.org/contributor/slug/commits/111111111111',
            'src': u'bitbucket',
            'when_timestamp': 1396825656,
        }])
