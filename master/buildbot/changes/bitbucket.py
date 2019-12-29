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


from datetime import datetime

from twisted.internet import defer

from buildbot import config
from buildbot.changes import base
from buildbot.util import bytes2unicode
from buildbot.util import datetime2epoch
from buildbot.util import httpclientservice
from buildbot.util.logger import Logger
from buildbot.util.state import StateMixin

log = Logger()

BASE_URL = "https://api.bitbucket.org"
OAUTH_URL = 'https://bitbucket.org/site/oauth2/access_token'
_GET_TOKEN_DATA = {
    'grant_type': 'client_credentials'
}


class BitbucketPullrequestPoller(base.ReconfigurablePollingChangeSource,
                                 StateMixin):

    compare_attrs = ("owner", "slug", "branches", "pollInterval",
                     "category", "pollAtLaunch", "name")
    db_class_name = "BitBuckerPullrequestPoller"

    def __init__(self, owner, slug, **kwargs):
        name = kwargs.get("name")
        if not name:
            kwargs["name"] = "BitbucketPullrequestPoller:" + owner + "/" + slug
        super(BitbucketPullrequestPoller, self).__init__(owner, slug, **kwargs)
        self.debug = kwargs.get("debug")
        self.verify = None
        self.codebase = kwargs.get('codebase')

    def checkConfig(self,
                    owner,
                    slug,
                    branches=None,
                    pollInterval=10 * 60,
                    pollAtLaunch=False,
                    category='pull',
                    pullrequest_filter=True,
                    codebase='',
                    oauth_key=None,
                    oauth_secret=None,
                    repository_type="https",
                    debug=False,
                    **kwargs):
        if repository_type not in ["https", "ssh"]:
            config.error(
                "repository_type must be one of {https, svn, git, ssh}")
        super().checkConfig(name=self.name, **kwargs)

    @defer.inlineCallbacks
    def reconfigService(self,
                        owner,
                        slug,
                        branches=None,
                        pollInterval=10 * 60,
                        pollAtLaunch=False,
                        category='pull',
                        pullrequest_filter=True,
                        codebase='',
                        oauth_key=None,
                        oauth_secret=None,
                        debug=False,
                        repository_type="https",
                        **kwargs):

        yield super().reconfigService(name=self.name, **kwargs)

        http_headers = {'User-Agent': 'Buildbot'}

        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, BASE_URL, headers=http_headers)

        if oauth_key is not None:
            oauth_key, oauth_secret = yield self.renderSecrets(oauth_key, oauth_secret)

            self._oauthhttp = yield httpclientservice.HTTPClientService.getService(
                self.master, OAUTH_URL, auth=(oauth_key, oauth_secret),
                debug=self.debug, verify=self.verify, headers=http_headers)

        self.owner = owner
        self.slug = slug
        self.branches = branches
        self.pollInterval = pollInterval
        self.pollAtLaunch = pollAtLaunch
        self.repository_type = repository_type

        if callable(pullrequest_filter):
            self.pullrequest_filter = pullrequest_filter
        else:
            self.pullrequest_filter = (lambda _: pullrequest_filter)

        self.category = category if callable(category) else bytes2unicode(
            category)

    @defer.inlineCallbacks
    def _getAccessToken(self):
        oauth_request = yield self._oauthhttp.post("",
                                                  data=_GET_TOKEN_DATA)
        if oauth_request.code == 200:
            content_json = yield oauth_request.json()
            token = content_json['access_token']
            return token
        else:
            content = yield oauth_request.content()
            log.error("{code}: unable to authenticate to Bitbucket {content}",
                      code=oauth_request.code, content=content)
        return None

    def describe(self):
        return "BitbucketPullrequestPoller watching the "\
            "Bitbucket repository %s/%s" % (
                self.owner, self.slug)

    @defer.inlineCallbacks
    def _getRepoURL(self):
        result = yield self._http.get('/'.join(
            ['/2.0/repositories', self.owner, self.slug]))
        my_json = yield result.json()
        for url in my_json['links']['clone']:
            if url['name'] == self.repository_type:
                return url['href']

    @defer.inlineCallbacks
    def _getProject(self):
        result = yield self._http.get('/'.join(
            ['/2.0/repositories', self.owner, self.slug]))
        my_json = yield result.json()
        return my_json.get('project', {}).get('name', '')

    @defer.inlineCallbacks
    def _getPullInformation(self, pull_number):
        result = yield self._http.get('/'.join(
            ['/2.0/repositories', self.owner, self.slug, 'pullrequests', str(pull_number)]))
        my_json = yield result.json()
        return my_json

    @defer.inlineCallbacks
    def _getPulls(self):
        log.debug("BitbucketPullrequestPoller: polling "
                  "Bitbucket repository %s/%s, branches: %s" %
                  (self.owner, self.slug, self.branches))
        result = yield self._http.get('/'.join(
            ['/2.0/repositories', self.owner, self.slug, 'pullrequests']))
        my_json = yield result.json()
        return my_json

    @defer.inlineCallbacks
    def _getFiles(self, revision, prnumber):
        files = set()
        result = yield self._http.get('/'.join(
            ['/2.0/repositories', self.owner, self.slug, 'pullrequests',
                str(prnumber), 'diffstat'
        ]))
        my_json = yield result.json()

        for f in my_json['values']:
            if type(f.get('new')) is dict:
                files.add(f['new']['path'])

        for f in my_json['values']:
            if type(f.get('old')) is dict:
                files.add(f['old']['path'])

        return list(files)

    @defer.inlineCallbacks
    def _getAuthors(self, prnumber):
        result = yield self._http.get("/".join([
            '/2.0/repositories', self.owner, self.slug, 'pullrequests', str(prnumber), 'commits'
        ]))
        my_json = yield result.json()

        return [a['author']['raw'] for a in my_json['values']]

    @defer.inlineCallbacks
    def _getCurrentRev(self, prnumber):
        # Get currently assigned revision of PR number

        result = yield self._getStateObjectId()
        rev = yield self.master.db.state.getState(result, 'pull_request%d' %
                                                  prnumber, None)
        return rev

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
            '%s/%s' % (self.owner, self.slug), self.db_class_name)
        return result

    @defer.inlineCallbacks
    def _processChanges(self, bitbucket_result):
        for pr in bitbucket_result['values']:
            # Track PRs for specified branches
            base_branch = pr['destination']['branch']['name']
            prnumber = pr['id']
            revision = pr['source']['commit']['hash']

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
                branch = pr['source']['branch']['name']
                repo = yield self._getRepoURL()
                revlink = pr['links']['html']['href']
                comments = pr['description']
                updated = datetime.strptime(pr['updated_on'],
                                            '%Y-%m-%dT%H:%M:%S.%f%z')
                # update database
                yield self._setCurrentRev(prnumber, revision)

                project = yield self._getProject()

                dl = defer.DeferredList(
                    [self._getAuthors(prnumber), self._getFiles(revision, prnumber)],
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
                [authors, files] = [r[1] for r in results]

                author = authors[0]

                # emit the change
                yield self.master.data.updates.addChange(
                    author=author,
                    committer=None,
                    revision=bytes2unicode(revision),
                    revlink=bytes2unicode(revlink),
                    comments='Bitbucket Pull Request #{0} ({1})\n{2}\n{3}'.
                    format(prnumber, revision, title, comments),
                    when_timestamp=datetime2epoch(updated),
                    branch=bytes2unicode(branch),
                    category=self.category,
                    project=project,
                    repository=bytes2unicode(repo),
                    files=files,
                    codebase="willo32/naboo",
                    src='git')

    @defer.inlineCallbacks
    def poll(self):
        if self._oauthhttp is not None:
            token = yield self._getAccessToken()
            if token is None:
                return
            self._http.updateHeaders({'Authorization': 'Bearer ' + token})

        result = yield self._getPulls()
        yield self._processChanges(result)
