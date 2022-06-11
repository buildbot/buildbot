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

from twisted.internet import defer
from twisted.trial import unittest
from twisted.web.error import Error

from buildbot.changes.bitbucket import BitbucketPullrequestPoller
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import changesource
from buildbot.test.util.logging import LoggingMixin


class SourceRest():
    """https://api.bitbucket.org/2.0/repositories/{owner}/{slug}"""
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
                "href": "https://api.bitbucket.org/2.0/repositories/%(owner)s/%(slug)s"
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

    def response(self):
        return self.template % {
            "owner": self.owner,
            "slug": self.slug,
            "hash": self.hash,
            "short_hash": self.hash[0:12],
            "date": self.date,
        }

    def repo_response(self):
        return self.repo_template % {
            "owner": self.owner,
            "slug": self.slug,
        }


class PullRequestRest():
    """https://api.bitbucket.org/2.0/repositories/{owner}/{slug}/pullrequests/{pull_request_id}"""
    template = """\
{

    "description": "%(description)s",
    "title": "%(title)s",
    "source": {
        "commit": {
            "hash": "%(hash)s",
            "links": {
                "self": {
                    "href": "https://api.bitbucket.org/2.0/repositories/%(owner)s/%(slug)s/commit/%(hash)s"
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
"""  # noqa pylint: disable=line-too-long

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

    def response(self):
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
    """https://api.bitbucket.org/2.0/repositories/{owner}/{slug}/pullrequests"""
    template = """\
        {
            "description": "%(description)s",
            "links": {
                "self": {
                    "href": "https://api.bitbucket.org/2.0/repositories/%(owner)s/%(slug)s/pullrequests/%(id)d"
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
                            "href": "https://api.bitbucket.org/2.0/repositories/%(src_owner)s/%(src_slug)s/commit/%(short_hash)s"
                        }
                    }
                },
                "repository": {
                    "links": {
                        "self": {
                            "href": "https://api.bitbucket.org/2.0/repositories/%(src_owner)s/%(src_slug)s"
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
"""  # noqa pylint: disable=line-too-long

    def __init__(self, owner, slug, prs):
        self.owner = owner
        self.slug = slug
        self.prs = prs

        self.pr_by_id = {}
        self.src_by_url = {}
        for pr in prs:
            self.pr_by_id[pr.nr] = pr
            self.src_by_url[f"{pr.source.owner}/{pr.source.slug}"] = pr.source

    def response(self):

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
        return f"""\
{{

    "pagelen": 10,
    "values": [{s}],
    "page": 1

}}
"""

    def getPage(self, url, timeout=None, headers=None):
        list_url_re = re.compile(
            f"https://api.bitbucket.org/2.0/repositories/{self.owner}/{self.slug}/pullrequests")
        pr_url_re = re.compile(
            fr"https://api.bitbucket.org/2.0/repositories/{self.owner}/{self.slug}/pullrequests/(?P<id>\d+)")  # noqa pylint: disable=line-too-long
        source_commit_url_re = re.compile(
            r"https://api.bitbucket.org/2.0/repositories/(?P<src_owner>.*)/(?P<src_slug>.*)/commit/(?P<hash>\d+)")  # noqa pylint: disable=line-too-long
        source_url_re = re.compile(
            r"https://api.bitbucket.org/2.0/repositories/(?P<src_owner>.*)/(?P<src_slug>.*)")

        if list_url_re.match(url):
            return defer.succeed(self.request())

        m = pr_url_re.match(url)
        if m:
            return self.pr_by_id[int(m.group("id"))].request()

        m = source_commit_url_re.match(url)
        if m:
            return self.src_by_url[f'{m.group("src_owner")}/{m.group("src_slug")}'].request()

        m = source_url_re.match(url)
        if m:
            return self.src_by_url[f'{m.group("src_owner")}/{m.group("src_slug")}'].repo_request()

        raise Error(code=404)


class TestBitbucketPullrequestPoller(changesource.ChangeSourceMixin,
                                     TestReactorMixin, LoggingMixin,
                                     unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        self.setUpLogging()

        # create pull requests
        self.date = "2013-10-15T20:38:20.001797+00:00"
        self.date_epoch = datetime.strptime(self.date.split('.', maxsplit=1)[0],
                                            '%Y-%m-%dT%H:%M:%S')
        self.rest_src = SourceRest(
            owner="contributor",
            slug="slug",
            hash="1111111111111111111111111111111111111111",
            date=self.date,
        )
        self.rest_pr = PullRequestRest(
            nr=1,
            title="title",
            description="description",
            display_name="contributor",
            source=self.rest_src,
            created_on=self.date,
        )
        self.rest_pr_list = PullRequestListRest(
            owner="owner",
            slug="slug",
            prs=[self.rest_pr],
        )

        return self.setUpChangeSource()

    def tearDown(self):
        return self.tearDownChangeSource()

    def _fakeGetPage(self, result):
        # Install a fake getPage that puts the requested URL in self.getPage_got_url
        # and return result
        self.getPage_got_url = None

        def fake(url, timeout=None, headers=None):
            self.getPage_got_url = url
            return defer.succeed(result)
        self.patch(self.changesource, "getPage", fake)

    def _fakeGetPage403(self, expected_headers):

        def fail_unauthorized(url, timeout=None, headers=None):
            if headers != expected_headers:
                raise Error(code=403)
        self.patch(self.changesource, "getPage", fail_unauthorized)

    def _fakeGetPage404(self):

        def fail(url, timeout=None, headers=None):
            raise Error(code=404)
        self.patch(self.changesource, "getPage", fail)

    @defer.inlineCallbacks
    def _new_change_source(self, **kwargs):
        self._http = yield fakehttpclientservice.HTTPClientService.getService(
            self.master, self, 'https://api.bitbucket.org/2.0', auth=None)

        change_source = BitbucketPullrequestPoller(**kwargs)
        yield self.attachChangeSource(change_source)
        return change_source

    # tests
    @defer.inlineCallbacks
    def test_describe(self):
        yield self._new_change_source(owner='owner', slug='slug')
        assert re.search(r'owner/slug', self.changesource.describe())

    @defer.inlineCallbacks
    def test_poll_unknown_repo(self):
        # Polling a non-existent repository should result in a 404
        yield self._new_change_source(owner='owner', slug='slug')

        self._http.expect('get', '/repositories/owner/slug/pullrequests', content_json={}, code=404)

        yield self.changesource.poll()

        self.assertLogged('error 404 while loading')

    @defer.inlineCallbacks
    def test_poll_no_pull_requests(self):
        yield self._new_change_source(owner='owner', slug='slug')

        rest_pr_list = PullRequestListRest(
            owner="owner",
            slug="slug",
            prs=[],
        )

        self._http.expect(
            'get',
            '/repositories/owner/slug/pullrequests',
            content=rest_pr_list.response())

        yield self.changesource.poll()

        self.assertEqual(len(self.master.data.updates.changesAdded), 0)

    @defer.inlineCallbacks
    def test_poll_new_pull_requests(self):
        yield self._new_change_source(owner='owner', slug='slug')

        self._http.expect(
            'get',
            '/repositories/owner/slug/pullrequests',
            content=self.rest_pr_list.response())

        self._http.expect(
            'get',
            'https://api.bitbucket.org/2.0/repositories/owner/slug/pullrequests/1',
            content=self.rest_pr.response())

        self._http.expect(
            'get',
            'https://api.bitbucket.org/2.0/repositories/contributor/slug/commit/111111111111',
            content=self.rest_src.response())

        self._http.expect(
            'get',
            'https://api.bitbucket.org/2.0/repositories/contributor/slug',
            content=self.rest_src.repo_response())

        yield self.changesource.poll()

        self.assertEqual(self.master.data.updates.changesAdded, [{
            'author': 'contributor',
            'committer': None,
            'branch': 'default',
            'category': None,
            'codebase': None,
            'comments': 'pull-request #1: title\nhttps://bitbucket.org/owner/slug/pull-request/1',
            'files': None,
            'project': '',
            'properties': {'pullrequesturl': 'https://bitbucket.org/owner/slug/pull-request/1'},
            'repository': 'https://bitbucket.org/contributor/slug',
            'revision': '1111111111111111111111111111111111111111',
            'revlink': 'https://bitbucket.org/contributor/slug/commits/111111111111',
            'src': 'bitbucket',
            'when_timestamp': 1381869500,
        }])

    @defer.inlineCallbacks
    def test_poll_no_updated_pull_request(self):
        yield self._new_change_source(owner='owner', slug='slug')

        self._http.expect(
            'get',
            '/repositories/owner/slug/pullrequests',
            content=self.rest_pr_list.response())

        self._http.expect(
            'get',
            'https://api.bitbucket.org/2.0/repositories/owner/slug/pullrequests/1',
            content=self.rest_pr.response())

        self._http.expect(
            'get',
            'https://api.bitbucket.org/2.0/repositories/contributor/slug/commit/111111111111',
            content=self.rest_src.response())

        self._http.expect(
            'get',
            'https://api.bitbucket.org/2.0/repositories/contributor/slug',
            content=self.rest_src.repo_response())

        self._http.expect(
            'get',
            '/repositories/owner/slug/pullrequests',
            content=self.rest_pr_list.response())

        yield self.changesource.poll()

        self.assertEqual(self.master.data.updates.changesAdded, [{
            'author': 'contributor',
            'committer': None,
            'branch': 'default',
            'category': None,
            'codebase': None,
            'comments': 'pull-request #1: title\nhttps://bitbucket.org/owner/slug/pull-request/1',
            'files': None,
            'project': '',
            'properties': {'pullrequesturl': 'https://bitbucket.org/owner/slug/pull-request/1'},
            'repository': 'https://bitbucket.org/contributor/slug',
            'revision': '1111111111111111111111111111111111111111',
            'revlink': 'https://bitbucket.org/contributor/slug/commits/111111111111',
            'src': 'bitbucket',
            'when_timestamp': 1381869500,
        }])

        # repoll
        yield self.changesource.poll()
        self.assertEqual(len(self.master.data.updates.changesAdded), 1)

    @defer.inlineCallbacks
    def test_poll_updated_pull_request(self):
        yield self._new_change_source(owner='owner', slug='slug')

        rest_src2 = SourceRest(
            owner="contributor",
            slug="slug",
            hash="2222222222222222222222222222222222222222",
            date=self.date,
        )
        rest_pr2 = PullRequestRest(
            nr=1,
            title="title",
            description="description",
            display_name="contributor",
            source=rest_src2,
            created_on=self.date,
        )

        rest_pr_list2 = PullRequestListRest(
            owner="owner",
            slug="slug",
            prs=[rest_pr2],
        )

        self._http.expect(
            'get',
            '/repositories/owner/slug/pullrequests',
            content=self.rest_pr_list.response())

        self._http.expect(
            'get',
            'https://api.bitbucket.org/2.0/repositories/owner/slug/pullrequests/1',
            content=self.rest_pr.response())

        self._http.expect(
            'get',
            'https://api.bitbucket.org/2.0/repositories/contributor/slug/commit/111111111111',
            content=self.rest_src.response())

        self._http.expect(
            'get',
            'https://api.bitbucket.org/2.0/repositories/contributor/slug',
            content=self.rest_src.repo_response())

        self._http.expect(
            'get',
            '/repositories/owner/slug/pullrequests',
            content=rest_pr_list2.response())

        self._http.expect(
            'get',
            'https://api.bitbucket.org/2.0/repositories/owner/slug/pullrequests/1',
            content=rest_pr2.response())

        self._http.expect(
            'get',
            'https://api.bitbucket.org/2.0/repositories/contributor/slug/commit/222222222222',
            content=rest_src2.response())

        self._http.expect(
            'get',
            'https://api.bitbucket.org/2.0/repositories/contributor/slug',
            content=rest_src2.repo_response())

        yield self.changesource.poll()
        self.maxDiff = None
        self.assertEqual(self.master.data.updates.changesAdded, [{
            'author': 'contributor',
            'committer': None,
            'branch': 'default',
            'category': None,
            'codebase': None,
            'comments': 'pull-request #1: title\nhttps://bitbucket.org/owner/slug/pull-request/1',
            'files': None,
            'project': '',
            'properties': {'pullrequesturl': 'https://bitbucket.org/owner/slug/pull-request/1'},
            'repository': 'https://bitbucket.org/contributor/slug',

            'revision': '1111111111111111111111111111111111111111',
            'revlink': 'https://bitbucket.org/contributor/slug/commits/111111111111',
            'src': 'bitbucket',
            'when_timestamp': 1381869500,
        }])

        yield self.changesource.poll()

        self.assertEqual(self.master.data.updates.changesAdded, [
            {
                'author': 'contributor',
                'committer': None,
                'branch': 'default',
                'category': None,
                'codebase': None,
                'comments':
                    'pull-request #1: title\nhttps://bitbucket.org/owner/slug/pull-request/1',
                'files': None,
                'project': '',
                'properties': {'pullrequesturl': 'https://bitbucket.org/owner/slug/pull-request/1'},
                'repository': 'https://bitbucket.org/contributor/slug',
                'revision': '1111111111111111111111111111111111111111',
                'revlink': 'https://bitbucket.org/contributor/slug/commits/111111111111',
                'src': 'bitbucket',
                'when_timestamp': 1381869500,
            },
            {
                'author': 'contributor',
                'committer': None,
                'branch': 'default',
                'category': None,
                'codebase': None,
                'comments':
                    'pull-request #1: title\nhttps://bitbucket.org/owner/slug/pull-request/1',
                'files': None,
                'project': '',
                'properties': {'pullrequesturl': 'https://bitbucket.org/owner/slug/pull-request/1'},
                'repository': 'https://bitbucket.org/contributor/slug',
                'revision': '2222222222222222222222222222222222222222',
                'revlink': 'https://bitbucket.org/contributor/slug/commits/222222222222',
                'src': 'bitbucket',
                'when_timestamp': 1381869500,
            }
        ])

    @defer.inlineCallbacks
    def test_poll_pull_request_filter_False(self):
        yield self._new_change_source(owner='owner', slug='slug',
                                      pullrequest_filter=lambda x: False)

        self._http.expect(
            'get',
            '/repositories/owner/slug/pullrequests',
            content=self.rest_pr_list.response())

        self._http.expect(
            'get',
            'https://api.bitbucket.org/2.0/repositories/owner/slug/pullrequests/1',
            content=self.rest_pr.response())

        yield self.changesource.poll()

        self.assertEqual(len(self.master.data.updates.changesAdded), 0)

    @defer.inlineCallbacks
    def test_poll_pull_request_filter_True(self):
        yield self._new_change_source(owner='owner', slug='slug', pullrequest_filter=lambda x: True)

        self._http.expect(
            'get',
            '/repositories/owner/slug/pullrequests',
            content=self.rest_pr_list.response())

        self._http.expect(
            'get',
            'https://api.bitbucket.org/2.0/repositories/owner/slug/pullrequests/1',
            content=self.rest_pr.response())

        self._http.expect(
            'get',
            'https://api.bitbucket.org/2.0/repositories/contributor/slug/commit/111111111111',
            content=self.rest_src.response())

        self._http.expect(
            'get',
            'https://api.bitbucket.org/2.0/repositories/contributor/slug',
            content=self.rest_src.repo_response())

        yield self.changesource.poll()

        self.assertEqual(self.master.data.updates.changesAdded, [{
            'author': 'contributor',
            'committer': None,
            'branch': 'default',
            'category': None,
            'codebase': None,
            'comments': 'pull-request #1: title\nhttps://bitbucket.org/owner/slug/pull-request/1',
            'files': None,
            'project': '',
            'properties': {'pullrequesturl': 'https://bitbucket.org/owner/slug/pull-request/1'},
            'repository': 'https://bitbucket.org/contributor/slug',
            'revision': '1111111111111111111111111111111111111111',
            'revlink': 'https://bitbucket.org/contributor/slug/commits/111111111111',
            'src': 'bitbucket',
            'when_timestamp': 1381869500,
        }])

    @defer.inlineCallbacks
    def test_poll_pull_request_not_useTimestamps(self):
        yield self._new_change_source(owner='owner', slug='slug', useTimestamps=False)

        self._http.expect(
            'get',
            '/repositories/owner/slug/pullrequests',
            content=self.rest_pr_list.response())

        self._http.expect(
            'get',
            'https://api.bitbucket.org/2.0/repositories/owner/slug/pullrequests/1',
            content=self.rest_pr.response())

        self._http.expect(
            'get',
            'https://api.bitbucket.org/2.0/repositories/contributor/slug/commit/111111111111',
            content=self.rest_src.response())

        self._http.expect(
            'get',
            'https://api.bitbucket.org/2.0/repositories/contributor/slug',
            content=self.rest_src.repo_response())

        self.reactor.advance(1396825656)

        yield self.changesource.poll()
        self.assertEqual(self.master.data.updates.changesAdded, [{
            'author': 'contributor',
            'committer': None,
            'branch': 'default',
            'category': None,
            'codebase': None,
            'comments': 'pull-request #1: title\nhttps://bitbucket.org/owner/slug/pull-request/1',
            'files': None,
            'project': '',
            'properties': {'pullrequesturl': 'https://bitbucket.org/owner/slug/pull-request/1'},
            'repository': 'https://bitbucket.org/contributor/slug',
            'revision': '1111111111111111111111111111111111111111',
            'revlink': 'https://bitbucket.org/contributor/slug/commits/111111111111',
            'src': 'bitbucket',
            'when_timestamp': 1396825656,
        }])

    @defer.inlineCallbacks
    def test_poll_pull_request_properties(self):
        yield self._new_change_source(owner='owner', slug='slug',
                                      bitbucket_property_whitelist=["bitbucket.*"])

        self._http.expect(
            'get',
            '/repositories/owner/slug/pullrequests',
            content=self.rest_pr_list.response())

        self._http.expect(
            'get',
            'https://api.bitbucket.org/2.0/repositories/owner/slug/pullrequests/1',
            content=self.rest_pr.response())

        self._http.expect(
            'get',
            'https://api.bitbucket.org/2.0/repositories/contributor/slug/commit/111111111111',
            content=self.rest_src.response())

        self._http.expect(
            'get',
            'https://api.bitbucket.org/2.0/repositories/contributor/slug',
            content=self.rest_src.repo_response())

        yield self.changesource.poll()
        self.assertEqual(self.master.data.updates.changesAdded, [{
            'author': 'contributor',
            'committer': None,
            'branch': 'default',
            'category': None,
            'codebase': None,
            'comments': 'pull-request #1: title\nhttps://bitbucket.org/owner/slug/pull-request/1',
            'files': None,
            'project': '',
            'properties': {
                'pullrequesturl': 'https://bitbucket.org/owner/slug/pull-request/1',
                'bitbucket.author.display_name': 'contributor',
                'bitbucket.created_on': '2013-10-15T20:38:20.001797+00:00',
                'bitbucket.description': 'description',
                'bitbucket.id': 1,
                'bitbucket.links.html.href': 'https://bitbucket.org/owner/slug/pull-request/1',
                'bitbucket.links.self.href': 'https://api.bitbucket.org/2.0/'
                                             'repositories/owner/slug/pullrequests/1',
                'bitbucket.merge_commit': None,
                'bitbucket.source.branch.name': 'default',
                'bitbucket.source.commit.hash': '111111111111',
                'bitbucket.source.commit.links.self.href': 'https://api.bitbucket.org/2.0/'
                                                           'repositories/contributor/slug/'
                                                           'commit/111111111111',
                'bitbucket.source.repository.links.self.href': 'https://api.bitbucket.org/2.0/'
                                                               'repositories/contributor/slug',
                'bitbucket.state': 'OPEN',
                'bitbucket.title': 'title',
                'bitbucket.updated_on': '2013-10-15T20:38:20.001797+00:00'
            },
            'repository': 'https://bitbucket.org/contributor/slug',
            'revision': '1111111111111111111111111111111111111111',
            'revlink': 'https://bitbucket.org/contributor/slug/commits/111111111111',
            'src': 'bitbucket',
            'when_timestamp': 1381869500,
        }])
