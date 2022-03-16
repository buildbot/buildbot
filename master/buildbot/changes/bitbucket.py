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


import time
from datetime import datetime

from twisted.internet import defer
from twisted.python import log

from buildbot.changes import base
from buildbot.util import bytes2unicode
from buildbot.util import datetime2epoch
from buildbot.util import deferredLocked
from buildbot.util import epoch2datetime
from buildbot.util import httpclientservice
from buildbot.util.pullrequest import PullRequestMixin


class BitbucketPullrequestPoller(base.ReconfigurablePollingChangeSource, PullRequestMixin):

    compare_attrs = ("owner", "slug", "branch",
                     "pollInterval", "useTimestamps",
                     "category", "project", "pollAtLaunch")

    db_class_name = 'BitbucketPullrequestPoller'
    property_basename = "bitbucket"

    def __init__(self, owner, slug, **kwargs):
        kwargs['name'] = self.build_name(owner, slug)

        self.initLock = defer.DeferredLock()

        super().__init__(owner, slug, **kwargs)

    def checkConfig(self, owner, slug,
                    branch=None, pollInterval=10 * 60, useTimestamps=True,
                    category=None, project='', pullrequest_filter=True,
                    pollAtLaunch=False, auth=None, bitbucket_property_whitelist=None):
        super().checkConfig(name=self.build_name(owner, slug),
                            pollInterval=pollInterval, pollAtLaunch=pollAtLaunch)

    @defer.inlineCallbacks
    def reconfigService(self, owner, slug,
                        branch=None, pollInterval=10 * 60, useTimestamps=True,
                        category=None, project='', pullrequest_filter=True,
                        pollAtLaunch=False, auth=None, bitbucket_property_whitelist=None):
        self.owner = owner
        self.slug = slug
        self.branch = branch
        if bitbucket_property_whitelist is None:
            bitbucket_property_whitelist = []

        if hasattr(pullrequest_filter, '__call__'):
            self.pullrequest_filter = pullrequest_filter
        else:
            self.pullrequest_filter = (lambda _: pullrequest_filter)

        self.lastChange = time.time()
        self.lastPoll = time.time()
        self.useTimestamps = useTimestamps
        self.category = category if callable(category) else bytes2unicode(category)
        self.project = bytes2unicode(project)
        self.external_property_whitelist = bitbucket_property_whitelist

        base_url = "https://api.bitbucket.org/2.0"
        self._http = yield httpclientservice.HTTPClientService.getService(self.master, base_url,
                                                                          auth=auth)

        yield super().reconfigService(self.build_name(owner, slug),
                                      pollInterval=pollInterval, pollAtLaunch=pollAtLaunch)

    def build_name(self, owner, slug):
        return '/'.join([owner, slug])

    def describe(self):
        return "BitbucketPullrequestPoller watching the "\
            f"Bitbucket repository {self.owner}/{self.slug}, branch: {self.branch}"

    @deferredLocked('initLock')
    @defer.inlineCallbacks
    def poll(self):
        response = yield self._getChanges()
        if response.code != 200:
            log.err(f"{self.__class__.__name__}: error {response.code} "
                    f"while loading {response.url}")
            return

        json_result = yield response.json()
        yield self._processChanges(json_result)

    def _getChanges(self):
        self.lastPoll = time.time()
        log.msg("BitbucketPullrequestPoller: polling "
                f"Bitbucket repository {self.owner}/{self.slug}, branch: {self.branch}")
        url = f"/repositories/{self.owner}/{self.slug}/pullrequests"
        return self._http.get(url, timeout=self.pollInterval)

    @defer.inlineCallbacks
    def _processChanges(self, result):
        for pr in result['values']:
            branch = pr['source']['branch']['name']
            nr = int(pr['id'])
            # Note that this is a short hash. The full length hash can be accessed via the
            # commit api resource but we want to avoid requesting multiple pages as long as
            # we are not sure that the pull request is new or updated.
            revision = pr['source']['commit']['hash']

            # check branch
            if not self.branch or branch in self.branch:
                current = yield self._getCurrentRev(nr)

                # compare _short_ hashes to check if the PR has been updated
                if not current or current[0:12] != revision[0:12]:
                    # parse pull request api page (required for the filter)
                    response = yield self._http.get(
                        str(pr['links']['self']['href'])
                    )
                    pr_json = yield response.json()

                    # filter pull requests by user function
                    if not self.pullrequest_filter(pr_json):
                        log.msg('pull request does not match filter')
                        continue

                    # access additional information
                    author = pr['author']['display_name']
                    prlink = pr['links']['html']['href']

                    # Get time updated time. Note that the timezone offset is
                    # ignored.
                    if self.useTimestamps:
                        updated = datetime.strptime(
                            pr['updated_on'].split('.')[0],
                            '%Y-%m-%dT%H:%M:%S')
                    else:
                        updated = epoch2datetime(self.master.reactor.seconds())
                    title = pr['title']

                    # parse commit api page
                    response = yield self._http.get(
                        str(pr['source']['commit']['links']['self']['href'])
                    )
                    commit_json = yield response.json()

                    # use the full-length hash from now on
                    revision = commit_json['hash']
                    revlink = commit_json['links']['html']['href']

                    # parse repo api page
                    response = yield self._http.get(
                        str(pr['source']['repository']['links']['self']['href'])
                    )
                    repo_json = yield response.json()
                    repo = repo_json['links']['html']['href']

                    # update database
                    yield self._setCurrentRev(nr, revision)

                    # emit the change
                    yield self.master.data.updates.addChange(
                        author=bytes2unicode(author),
                        committer=None,
                        revision=bytes2unicode(revision),
                        revlink=bytes2unicode(revlink),
                        comments=f'pull-request #{nr}: {title}\n{prlink}',
                        when_timestamp=datetime2epoch(updated),
                        branch=bytes2unicode(branch),
                        category=self.category,
                        project=self.project,
                        repository=bytes2unicode(repo),
                        properties={'pullrequesturl': prlink,
                                    **self.extractProperties(pr),
                                    },
                        src='bitbucket',
                    )

    def _getCurrentRev(self, pr_id):
        # Return a deferred datetime object for the given pull request number
        # or None.
        d = self._getStateObjectId()

        @d.addCallback
        def oid_callback(oid):
            current = self.master.db.state.getState(oid, f'pull_request{pr_id}', None)

            @current.addCallback
            def result_callback(result):
                return result
            return current
        return d

    def _setCurrentRev(self, pr_id, rev):
        # Set the datetime entry for a specified pull request.
        d = self._getStateObjectId()

        @d.addCallback
        def oid_callback(oid):
            return self.master.db.state.setState(oid, f'pull_request{pr_id}', rev)

        return d

    def _getStateObjectId(self):
        # Return a deferred for object id in state db.
        return self.master.db.state.getObjectId(
            f'{self.owner}/{self.slug}#{self.branch}', self.db_class_name)
