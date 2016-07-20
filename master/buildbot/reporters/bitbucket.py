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

import json
from urlparse import urlparse

from twisted.internet import defer
from twisted.python import log

from buildbot.process.results import SUCCESS
from buildbot.reporters import http

# Magic words understood by Butbucket REST API
BITBUCKET_INPROGRESS = 'INPROGRESS'
BITBUCKET_SUCCESSFUL = 'SUCCESSFUL'
BITBUCKET_FAILED = 'FAILED'

_BASE_URL = 'https://api.bitbucket.org/2.0/repositories'
_OAUTH_URL = 'https://bitbucket.org/site/oauth2/access_token'
_GET_TOKEN_DATA = {
    'grant_type': 'client_credentials'
}


class BitbucketStatusPush(http.HttpStatusPushBase):
    name = "BitbucketStatusPush"

    @defer.inlineCallbacks
    def reconfigService(self, oauth_key, oauth_secret,
                        base_url=_BASE_URL,
                        oauth_url=_OAUTH_URL,
                        **kwargs):
        yield http.HttpStatusPushBase.reconfigService(self, **kwargs)

        if base_url.endswith('/'):
            base_url = base_url[:-1]

        self._base_url = base_url
        self._oauth_url = oauth_url
        self._auth = (oauth_key, oauth_secret)

    @defer.inlineCallbacks
    def send(self, build):
        results = build['results']

        if build['complete']:
            status = BITBUCKET_SUCCESSFUL if results == SUCCESS else BITBUCKET_FAILED
        else:
            status = BITBUCKET_INPROGRESS

        for sourcestamp in build['buildset']['sourcestamps']:
            sha = sourcestamp['revision']
            body = {
                'state': status,
                'key': build['builder']['name'],
                'name': build['builder']['name'],
                'url': build['url']
            }

            owner, repo = self.get_owner_and_repo(sourcestamp['repository'])

            oauth_request = yield self.session.post(self._oauth_url,
                                                    auth=self._auth,
                                                    data=_GET_TOKEN_DATA)
            if oauth_request.status_code == 200:
                token = json.loads(oauth_request.content)['access_token']
            else:
                token = ''

            self.session.headers.update({'Authorization': 'Bearer ' + token})

            bitbucket_uri = '/'.join([self._base_url, owner, repo, 'commit', sha, 'statuses', 'build'])

            response = yield self.session.post(bitbucket_uri, json=body)
            if response.status_code != 201:
                log.msg("%s: unable to upload Bitbucket status: %s" %
                        (response.status_code, response.content))
            else:
                log.msg("Unable to determine owner or repository name: (owner: %s, repo: %s)" %
                        (str(owner), str(repo)))

    @staticmethod
    def get_owner_and_repo(repourl):
        """
        Takes a git repository URL from Bitbucket and tries to determine the owner and repository name
        :param repourl: Bitbucket git repo in the form of
                    git@bitbucket.com:OWNER/REPONAME.git
                    https://bitbucket.com/OWNER/REPONAME.git
                    ssh://git@bitbucket.com/OWNER/REPONAME.git
        :return: owner, repo: The owner of the repository and the repository name
        """
        parsed = urlparse(repourl)

        if parsed.scheme:
            path = parsed.path[1:]
        else:
            # we assume git@host:owner/repo.git here
            path = parsed.path.split(':', 1)[-1]

        if path.endswith('.git'):
            path = path[:-4]

        parts = path.split('/')

        assert len(parts) == 2, 'OWNER/REPONAME is expected'

        return parts
