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

import json
import time
from datetime import datetime

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log
from twisted.web import client

from buildbot.changes import base
from buildbot.util import ascii2unicode
from buildbot.util import datetime2epoch
from buildbot.util import deferredLocked
from buildbot.util import epoch2datetime


class BitbucketPullrequestPoller(base.PollingChangeSource):

    compare_attrs = ("owner", "slug", "branch",
                     "pollInterval", "useTimestamps",
                     "category", "project", "pollAtLaunch")

    db_class_name = 'BitbucketPullrequestPoller'

    def __init__(self, owner, slug,
                 branch=None,
                 pollInterval=10 * 60,
                 useTimestamps=True,
                 category=None,
                 project='',
                 pullrequest_filter=True,
                 encoding='utf-8',
                 pollAtLaunch=False
                 ):

        self.owner = owner
        self.slug = slug
        self.branch = branch
        base.PollingChangeSource.__init__(
            self, name='/'.join([owner, slug]), pollInterval=pollInterval, pollAtLaunch=pollAtLaunch)
        self.encoding = encoding

        if hasattr(pullrequest_filter, '__call__'):
            self.pullrequest_filter = pullrequest_filter
        else:
            self.pullrequest_filter = (lambda _: pullrequest_filter)

        self.lastChange = time.time()
        self.lastPoll = time.time()
        self.useTimestamps = useTimestamps
        self.category = category if callable(
            category) else ascii2unicode(category)
        self.project = ascii2unicode(project)
        self.initLock = defer.DeferredLock()

    def describe(self):
        return "BitbucketPullrequestPoller watching the "\
            "Bitbucket repository %s/%s, branch: %s" % (
                self.owner, self.slug, self.branch)

    @deferredLocked('initLock')
    def poll(self):
        d = self._getChanges()
        d.addCallback(self._processChanges)
        d.addErrback(self._processChangesFailure)
        return d

    def _getChanges(self):
        self.lastPoll = time.time()
        log.msg("BitbucketPullrequestPoller: polling "
                "Bitbucket repository %s/%s, branch: %s" % (self.owner, self.slug, self.branch))
        url = "https://bitbucket.org/api/2.0/repositories/%s/%s/pullrequests" % (
            self.owner, self.slug)
        return client.getPage(url, timeout=self.pollInterval)

    @defer.inlineCallbacks
    def _processChanges(self, page):
        result = json.loads(page, encoding=self.encoding)
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
                    page = yield client.getPage(str(pr['links']['self']['href']))
                    pr_json = json.loads(page, encoding=self.encoding)

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
                        updated = epoch2datetime(reactor.seconds())
                    title = pr['title']
                    # parse commit api page
                    page = yield client.getPage(str(pr['source']['commit']['links']['self']['href']))
                    commit_json = json.loads(page, encoding=self.encoding)
                    # use the full-length hash from now on
                    revision = commit_json['hash']
                    revlink = commit_json['links']['html']['href']
                    # parse repo api page
                    page = yield client.getPage(str(pr['source']['repository']['links']['self']['href']))
                    repo_json = json.loads(page, encoding=self.encoding)
                    repo = repo_json['links']['html']['href']

                    # update database
                    yield self._setCurrentRev(nr, revision)
                    # emit the change
                    yield self.master.data.updates.addChange(
                        author=ascii2unicode(author),
                        revision=ascii2unicode(revision),
                        revlink=ascii2unicode(revlink),
                        comments=u'pull-request #%d: %s\n%s' % (
                            nr, title, prlink),
                        when_timestamp=datetime2epoch(updated),
                        branch=self.branch,
                        category=self.category,
                        project=self.project,
                        repository=ascii2unicode(repo),
                        src=u'bitbucket',
                    )

    def _processChangesFailure(self, f):
        log.msg('BitbucketPullrequestPoller: json api poll failed')
        log.err(f)
        # eat the failure to continue along the deferred chain - we still want
        # to catch up
        return None

    def _getCurrentRev(self, pr_id):
        # Return a deferred datetime object for the given pull request number
        # or None.
        d = self._getStateObjectId()

        @d.addCallback
        def oid_callback(oid):
            current = self.master.db.state.getState(
                oid, 'pull_request%d' % pr_id, None)

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
            return self.master.db.state.setState(oid, 'pull_request%d' % pr_id, rev)

        return d

    def _getStateObjectId(self):
        # Return a deferred for object id in state db.
        return self.master.db.state.getObjectId(
            '%s/%s#%s' % (self.owner, self.slug, self.branch), self.db_class_name)
