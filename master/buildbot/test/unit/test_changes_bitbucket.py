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

import re

from datetime import datetime

from buildbot.changes.bitbucket import BitbucketPullrequestPoller
from buildbot.test.util import changesource
from twisted.internet import defer
from twisted.trial import unittest
from twisted.web import client
from twisted.web.error import Error


class SourceRest():
    template = """\
{

    "hash": "%(hash)s",
    "links": {
        "html": {
            "href": "https://bitbucket.org/%(owner)s/%(slug)s/commits/%(hash)s"
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
            "date": self.date,
        }

    def repo_request(self):
        return self.repo_template % {
            "owner": self.owner,
            "slug": self.slug,
        }


class PullRequestRest():
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
            "owner": self.source.owner,
            "slug": self.source.slug,
            "display_name": self.display_name,
            "created_on": self.created_on,
            "updated_on": self.updated_on,
            "id": self.nr,
        }


class PullRequestListRest():
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
                    "hash": "%(hash)s",
                    "links": {
                        "self": {
                            "href": "https://bitbucket.org/!api/2.0/repositories/%(src_owner)s/%(src_slug)s/commit/%(hash)s"
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
            hash="000000000000000000000000000001",
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
            hash="000000000000000000000000000002",
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

        d = self.setUpChangeSource()

        def create_poller(_):
            self.attachChangeSource(BitbucketPullrequestPoller(
                owner='owner',
                slug='slug',
            ))

        d.addCallback(create_poller)
        return d

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

    # tests

    def test_describe(self):
        assert re.search(r'owner/slug', self.changesource.describe())

    def test_poll_unknown_repo(self):
        # Polling a non-existent repository should result in a 404
        self._fakeGetPage404()
        d = self.changesource.poll()

        def check(_):
            self.fail('Polling a non-existent repository should result in a 404.')

        def err(e):
            self.assertEqual(e.getErrorMessage(), '404 Not Found')

        d.addCallback(check)
        d.addErrback(err)
        return d

    def test_poll_no_pull_requests(self):
        rest = PullRequestListRest(owner="owner", slug="slug", prs=[])
        self._fakeGetPage(rest.request())
        d = self.changesource.poll()

        def check(_):
            self.assertEqual(len(self.changes_added), 0)

        d.addCallback(check)
        return d

    def test_poll_new_pull_requests(self):

        # patch client.getPage()
        self.patch(client, "getPage", self.pr_list.getPage)

        d = self.changesource.poll()

        def check(_):
            self.assertEqual(len(self.changes_added), 1)
            self.assertEqual(self.changes_added[0]['author'], "contributor")
            self.assertEqual(int(self.changes_added[0]['revision']), 1)
            self.assertEqual(self.changes_added[0]['when_timestamp'],
                             self.date_epoch)

        d.addCallback(check)
        return d

    def test_poll_no_updated_pull_request(self):

        # patch client.getPage()
        self.patch(client, "getPage", self.pr_list.getPage)

        d = self.changesource.poll()

        def check(_):
            self.assertEqual(len(self.changes_added), 1)
            self.assertEqual(self.changes_added[0]['author'], "contributor")
            self.assertEqual(int(self.changes_added[0]['revision']), 1)
            self.assertEqual(self.changes_added[0]['when_timestamp'],
                             self.date_epoch)

            # repoll
            d = self.changesource.poll()

            def check2(_):
                self.assertEqual(len(self.changes_added), 1)

            d.addCallback(check2)

        d.addCallback(check)
        return d

    def test_poll_updated_pull_request(self):

        # patch client.getPage()
        self.patch(client, "getPage", self.pr_list.getPage)

        d = self.changesource.poll()

        def check(_):
            self.assertEqual(len(self.changes_added), 1)
            self.assertEqual(self.changes_added[0]['author'], "contributor")
            self.assertEqual(int(self.changes_added[0]['revision']), 1)
            self.assertEqual(self.changes_added[0]['when_timestamp'],
                             self.date_epoch)

            self.patch(client, "getPage", self.pr_list2.getPage)
            d = self.changesource.poll()

            def check2(_):
                self.assertEqual(len(self.changes_added), 2)
                self.assertEqual(self.changes_added[1]['author'], "contributor")
                self.assertEqual(int(self.changes_added[1]['revision']), 2)
                self.assertEqual(self.changes_added[1]['when_timestamp'],
                                 self.date_epoch)

            d.addCallback(check2)
            return d

        d.addCallback(check)
        return d

    def test_poll_pull_request_filter_False(self):
        self.attachChangeSource(BitbucketPullrequestPoller(
            owner='owner',
            slug='slug',
            pullrequest_filter=lambda x: False
        ))

        # patch client.getPage()
        self.patch(client, "getPage", self.pr_list.getPage)

        d = self.changesource.poll()

        def check(_):
            self.assertEqual(len(self.changes_added), 0)

        d.addCallback(check)
        return d

    def test_poll_pull_request_filter_True(self):
        self.attachChangeSource(BitbucketPullrequestPoller(
            owner='owner',
            slug='slug',
            pullrequest_filter=lambda x: True
        ))

        # patch client.getPage()
        self.patch(client, "getPage", self.pr_list.getPage)

        d = self.changesource.poll()

        def check(_):
            self.assertEqual(len(self.changes_added), 1)
            self.assertEqual(self.changes_added[0]['author'], "contributor")
            self.assertEqual(int(self.changes_added[0]['revision']), 1)
            self.assertEqual(self.changes_added[0]['when_timestamp'],
                             self.date_epoch)

        d.addCallback(check)
        return d

    def test_poll_pull_request_not_useTimestamps(self):
        self.attachChangeSource(BitbucketPullrequestPoller(
            owner='owner',
            slug='slug',
            useTimestamps=False,
        ))

        # patch client.getPage()
        self.patch(client, "getPage", self.pr_list.getPage)

        d = self.changesource.poll()

        def check(_):
            self.assertEqual(len(self.changes_added), 1)
            self.assertEqual(self.changes_added[0]['author'], "contributor")
            self.assertEqual(int(self.changes_added[0]['revision']), 1)
            self.assertNotEqual(self.changes_added[0]['when_timestamp'],
                                self.date_epoch)

        d.addCallback(check)
        return d
