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

from twisted.internet import defer
from twisted.python import log

from buildbot.process.results import SUCCESS
from buildbot.reporters import http

# Magic words understood by Butbucket REST API
BITBUCKET_INPROGRESS = 'INPROGRESS'
BITBUCKET_SUCCESSFUL = 'SUCCESSFUL'
BITBUCKET_FAILED = 'FAILED'


class BitbucketStatusPush(http.HttpStatusPushBase):
    name = "BitbucketStatusPush"

    @defer.inlineCallbacks
    def reconfigService(self, oauth_key, oauth_secret, base_url='https://api.bitbucket.org/2.0/repositories',
                        oauth_url='https://bitbucket.org/site/oauth2/access_token', **kwargs):
        yield http.HttpStatusPushBase.reconfigService(self, **kwargs)
        if base_url.endswith('/'):
            base_url = base_url[:-1]
        self.base_url = base_url
        self.oauth_url = oauth_url
        self.auth = (oauth_key, oauth_secret)

    @defer.inlineCallbacks
    def send(self, build):
        results = build['results']
        if build['complete']:
            status = BITBUCKET_SUCCESSFUL if results == SUCCESS else BITBUCKET_FAILED
        else:
            status = BITBUCKET_INPROGRESS
        for sourcestamp in build['buildset']['sourcestamps']:
            sha = sourcestamp['revision']
            body = {'state': status,
                    'key': build['builder']['name'],
                    'name': build['builder']['name'],
                    'url': build['url']
                    }
            owner, repo = self.get_owner_and_repo(sourcestamp['repository'])
            if repo is not None and owner is not None:
                token = ''
                oauth_request = yield self.session.post(self.oauth_url, auth=self.auth,
                                                       data={'grant_type': 'client_credentials'})
                if oauth_request.status_code == 200:
                    token =  json.loads(oauth_request.content)['access_token']
                self.session.headers.update({'Authorization': 'Bearer ' + token})
                bitbucket_uri = '/'.join([self.base_url, owner, repo, 'commit', sha, 'statuses', 'build'])
                response = yield self.session.post(bitbucket_uri, json=body)
                if response.status_code != 201:
                    log.msg("%s: unable to upload Bitbucket status: %s" %
                            (response.status_code, response.content))
            else:
                log.msg("Unable to determine owner or repository name: (owner: %s, repo: %s)" %
                        (str(owner), str(repo)))

    def get_owner_and_repo(self, repourl):
        """
        Takes a git repository URL from Bitbucket and tries to determine the owner and repository name
        :param repourl: Bitbucket git repo in the form of
                    git@bitbucket.com/OWNER/REPONAME.git
                    https://bitbucket.com/OWNER/REPONAME.git
        :return: owner, repo: The owner of the repository and the repository name
        """
        owner = None
        repo = None
        if repourl.startswith('git@'):
            tail = repourl.split(':')[-1]
            owner = tail.split('/')[-2]
            repo = tail.split('/')[-1]
        elif repourl.startswith('http'):
            repo = repourl.split('/')[-1]
            owner = repourl.split('/')[-2]
        if repo is not None and repo.endswith('.git'):
            repo = repo[:-4]
        return owner, repo

