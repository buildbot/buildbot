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

import os
import time
from datetime import datetime

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log
from twisted.web import client

from buildbot.changes import base
from buildbot.util.state import StateMixin
from buildbot.util import ascii2unicode
from buildbot.util import datetime2epoch
from buildbot.util import deferredLocked
from buildbot.util import epoch2datetime
from buildbot.util import json


class GitError(Exception):

    """Raised when git exits with code 128."""


class GitHubPullrequestPoller(base.PollingChangeSource, StateMixin):

    compare_attrs = ("owner", "repo", "branch",
                     "pollInterval", "useTimestamps",
                     "category", "project", "pollAtLaunch")

    db_class_name = 'GitHubPullrequestPoller'

    def __init__(self, token, owner, repo,
                 branch=None,
                 pollInterval=10 * 60,
                 useTimestamps=True,
                 category=None,
                 project='',
                 pullrequest_filter=True,
                 encoding='utf-8',
                 pollAtLaunch=False):

        self.token = token
        self.owner = owner
        self.repo = repo
        self.branch = branch
        self.repourl = "https://www.github.com/%s/%s.git" % (
                self.owner, self.repo)
        base.PollingChangeSource.__init__(
            self, name='/'.join([owner, repo]), pollInterval=pollInterval, pollAtLaunch=pollAtLaunch)
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
        return "GitHubPullrequestPoller watching the "\
            "GitHub repository %s/%s, branch: %s" % (
                self.owner, self.repo, self.branch)

    @deferredLocked('initLock')
    def poll(self):
        d = self._getChanges()
        d.addCallback(self._processChanges)
        d.addErrback(self._processChangesFailure)
        return d

    def _getChanges(self):
        self.lastPoll = time.time()
        log.msg("GitHubPullrequestPoller: polling "
                "GitHub repository %s/%s, branch: %s" % (self.owner, self.repo, self.branch))
        url = "https://api.github.com/repos/%s/%s/pulls" % (self.owner, self.repo)
        return client.getPage(url, headers={'Authorization': 'token ' + self.token},
                              timeout=self.pollInterval)

    @defer.inlineCallbacks
    def _processChanges(self, page):
        result = json.loads(page, encoding=self.encoding)
        for pr in result:
            branch = pr['head']['ref']
            prnumber = pr['number']
            revision = pr['head']['sha']

            # Check to see if the branch is set or matches
            if not self.branch or branch in self.branch:
                current = yield self._getCurrentRev(prnumber)

                if not current or current[0:12] != revision[0:12]:
                    # Access title, repo, html link, and comments
                    title = pr['title']
                    repo = pr['head']['repo']['name']
                    revlink = pr['html_url']
                    comments = pr['body']
                    if self.useTimestamps:
                        updated = datetime.strptime(
                            pr['updated_at'],
                            '%Y-%m-%dT%H:%M:%SZ')
                    else:
                        updated = epoch2datetime(reactor.seconds())

                    # update database
                    yield self._setCurrentRev(prnumber, revision)

                    # Grab author and e-mail
                    page = yield client.getPage(str(pr['user']['url']))
                    author = pr['user']['login']
                    user_json = json.loads(page, encoding=self.encoding)
                    email = user_json['email']
                    if email is not None or email is not "null":
                        author += " <" + str(email) + ">"

                    # emit the change
                    yield self.master.data.updates.addChange(
                        author=ascii2unicode(author),
                        revision=ascii2unicode(revision),
                        revlink=ascii2unicode(revlink),
                        comments=u'pull-request #%d: %s\n%s\n%s' % (
                            prnumber, title, revlink, comments),
                        when_timestamp=datetime2epoch(updated),
                        branch=branch,
                        category=self.category,
                        project=self.project,
                        repository=ascii2unicode(repo),
                        src=u'git')

    def _processChangesFailure(self, f):
        log.msg('GitHubPullrequestPoller: json api poll failed')
        log.err(f)
        # eat the failure to continue along the defered chain - we still want
        # to catch up
        return None

    def _getCurrentRev(self, prnumber):
        # Return a deferred datetime object for the given pull request number
        # or None.
        d = self._getStateObjectId()

        @d.addCallback
        def oid_callback(oid):
            current = self.master.db.state.getState(
                oid, 'pull_request%d' % prnumber, None)

            @current.addCallback
            def result_callback(result):
                return result
            return current
        return d

    def _setCurrentRev(self, prnumber, rev):
        # Set the datetime entry for a specifed pull request.
        d = self._getStateObjectId()

        @d.addCallback
        def oid_callback(oid):
            return self.master.db.state.setState(oid, 'pull_request%d' % prnumber, rev)
        return d

    def _getStateObjectId(self):
        # Return a deferred for object id in state db.
        return self.master.db.state.getObjectId(
            '%s/%s#%s' % (self.owner, self.repo, self.branch), self.db_class_name)
