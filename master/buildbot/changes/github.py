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
from future.utils import iteritems

from datetime import datetime
from fnmatch import fnmatch

from twisted.internet import defer

from buildbot import config
from buildbot.changes import base
from buildbot.util import ascii2unicode
from buildbot.util import datetime2epoch
from buildbot.util import httpclientservice
from buildbot.util.logger import Logger
from buildbot.util.state import StateMixin

log = Logger()

HOSTED_BASE_URL = "https://api.github.com"
link_urls = {
    "https": "clone_url",
    "svn": "svn_url",
    "git": "git_url",
    "ssh": "ssh_url"
}


class PullRequestMixin(object):
    def extractProperties(self, pr_info):
        def flatten(properties, base, info_dict):
            for k, v in iteritems(info_dict):
                name = ".".join([base, k])
                if isinstance(v, dict):
                    flatten(properties, name, v)
                elif any([fnmatch(name, expr)
                          for expr in self.github_property_whitelist]):
                    properties[name] = v

        properties = {}
        flatten(properties, "github", pr_info)
        return properties


class GitHubPullrequestPoller(base.ReconfigurablePollingChangeSource,
                              StateMixin, PullRequestMixin):
    compare_attrs = ("owner", "repo", "token", "branches", "pollInterval",
                     "category", "pollAtLaunch", "name")
    db_class_name = 'GitHubPullrequestPoller'

    def __init__(self, owner, repo, **kwargs):
        name = kwargs.get("name")
        if not name:
            kwargs["name"] = "GitHubPullrequestPoller:" + owner + "/" + repo
        super(GitHubPullrequestPoller, self).__init__(owner, repo, **kwargs)

    def checkConfig(self,
                    owner,
                    repo,
                    branches=None,
                    category='pull',
                    baseURL=None,
                    pullrequest_filter=True,
                    token=None,
                    magic_link=False,
                    repository_type="https",
                    github_property_whitelist=None,
                    **kwargs):
        if repository_type not in ["https", "svn", "git", "ssh"]:
            config.error(
                "repository_type must be one of {https, svn, git, ssh}")
        base.ReconfigurablePollingChangeSource.checkConfig(
            self, name=self.name, **kwargs)

    @defer.inlineCallbacks
    def reconfigService(self,
                        owner,
                        repo,
                        branches=None,
                        pollInterval=10 * 60,
                        category=None,
                        baseURL=None,
                        pullrequest_filter=True,
                        token=None,
                        pollAtLaunch=False,
                        magic_link=False,
                        repository_type="https",
                        github_property_whitelist=None,
                        **kwargs):
        yield base.ReconfigurablePollingChangeSource.reconfigService(
            self, name=self.name, **kwargs)

        if baseURL is None:
            baseURL = HOSTED_BASE_URL
        if baseURL.endswith('/'):
            baseURL = baseURL[:-1]

        http_headers = {'User-Agent': 'Buildbot'}
        if token is not None:
            http_headers.update({'Authorization': 'token ' + token})

        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, baseURL, headers=http_headers)

        self.token = token
        self.owner = owner
        self.repo = repo
        self.branches = branches
        self.github_property_whitelist = github_property_whitelist
        self.pollInterval = pollInterval
        self.pollAtLaunch = pollAtLaunch
        self.repository_type = link_urls[repository_type]
        self.magic_link = magic_link

        if github_property_whitelist is None:
            self.github_property_whitelist = []

        if callable(pullrequest_filter):
            self.pullrequest_filter = pullrequest_filter
        else:
            self.pullrequest_filter = (lambda _: pullrequest_filter)

        self.category = category if callable(category) else ascii2unicode(
            category)

    def describe(self):
        return "GitHubPullrequestPoller watching the "\
            "GitHub repository %s/%s" % (
                self.owner, self.repo)

    @defer.inlineCallbacks
    def _getPullInformation(self, pull_number):
        result = yield self._http.get('/'.join(
            ['/repos', self.owner, self.repo, 'pulls', str(pull_number)]))
        my_json = yield result.json()
        defer.returnValue(my_json)

    @defer.inlineCallbacks
    def _getPulls(self):
        log.debug("GitHubPullrequestPoller: polling "
                  "GitHub repository %s/%s, branches: %s" %
                  (self.owner, self.repo, self.branches))
        result = yield self._http.get('/'.join(
            ['/repos', self.owner, self.repo, 'pulls']))
        my_json = yield result.json()
        defer.returnValue(my_json)

    @defer.inlineCallbacks
    def _getEmail(self, user):
        result = yield self._http.get("/".join(['/users', user]))
        my_json = yield result.json()
        defer.returnValue(my_json["email"])

    @defer.inlineCallbacks
    def _getFiles(self, prnumber):
        result = yield self._http.get("/".join([
            '/repos', self.owner, self.repo, 'pulls', str(prnumber), 'files'
        ]))
        my_json = yield result.json()

        defer.returnValue([f["filename"] for f in my_json])

    @defer.inlineCallbacks
    def _getCurrentRev(self, prnumber):
        # Get currently assigned revision of PR number

        result = yield self._getStateObjectId()
        rev = yield self.master.db.state.getState(result, 'pull_request%d' %
                                                  prnumber, None)
        defer.returnValue(rev)

    @defer.inlineCallbacks
    def _setCurrentRev(self, prnumber, rev):
        # Set the updated revision for PR number.

        result = yield self._getStateObjectId()
        yield self.master.db.state.setState(result,
                                            'pull_request%d' % prnumber, rev)

    @defer.inlineCallbacks
    def _getStateObjectId(self):
        # Return a deferred for object id in state db.
        result = yield self.master.db.state.getObjectId(
            '%s/%s' % (self.owner, self.repo), self.db_class_name)
        defer.returnValue(result)

    @defer.inlineCallbacks
    def _processChanges(self, github_result):
        for pr in github_result:
            # Track PRs for specified branches
            base_branch = pr['base']['ref']
            prnumber = pr['number']
            revision = pr['head']['sha']

            # Check to see if the branch is set or matches
            if self.branches is not None and base_branch not in self.branches:
                continue
            if (self.pullrequest_filter is not None and
                    not self.pullrequest_filter(pr)):
                continue
            current = yield self._getCurrentRev(prnumber)
            if not current or current[0:12] != revision[0:12]:
                # Access title, repo, html link, and comments
                pr = yield self._getPullInformation(prnumber)
                title = pr['title']
                if self.magic_link:
                    branch = 'refs/pull/{:d}/merge'.format(prnumber)
                    repo = pr['base']['repo'][self.repository_type]
                else:
                    branch = pr['head']['ref']
                    repo = pr['head']['repo'][self.repository_type]
                revlink = pr['html_url']
                comments = pr['body']
                updated = datetime.strptime(pr['updated_at'],
                                            '%Y-%m-%dT%H:%M:%SZ')
                # update database
                yield self._setCurrentRev(prnumber, revision)

                author = pr['user']['login']
                project = pr['base']['repo']['full_name']
                commits = pr['commits']

                dl = defer.DeferredList(
                    [self._getFiles(prnumber), self._getEmail(author)],
                    consumeErrors=True)

                results = yield dl
                failures = [r[1] for r in results if not r[0]]
                if failures:
                    for failure in failures:
                        log.error("while processing changes for "
                                  "Pullrequest {} revision {}".format(
                                      prnumber, revision))
                        # Fail on the first error!
                        failures[0].raiseException()
                [files, email] = [r[1] for r in results]

                if email is not None and email != "null":
                    author += " <" + str(email) + ">"

                properties = self.extractProperties(pr)

                # emit the change
                yield self.master.data.updates.addChange(
                    author=ascii2unicode(author),
                    revision=ascii2unicode(revision),
                    revlink=ascii2unicode(revlink),
                    comments=u'GitHub Pull Request #{0} ({1} commit{2})\n{3}\n{4}'.
                    format(prnumber, commits, 's'
                           if commits > 0 else '', title, comments),
                    when_timestamp=datetime2epoch(updated),
                    branch=ascii2unicode(branch),
                    category=self.category,
                    project=project,
                    repository=ascii2unicode(repo),
                    files=files,
                    properties=properties,
                    src=u'git')

    @defer.inlineCallbacks
    def poll(self):
        result = yield self._getPulls()
        yield self._processChanges(result)
