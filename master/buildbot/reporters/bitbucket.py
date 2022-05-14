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

from urllib.parse import urlparse

from twisted.internet import defer
from twisted.python import log

from buildbot import config
from buildbot.process.properties import Properties
from buildbot.process.properties import Property
from buildbot.process.results import SUCCESS
from buildbot.reporters.base import ReporterBase
from buildbot.reporters.generators.build import BuildStartEndStatusGenerator
from buildbot.reporters.message import MessageFormatter
from buildbot.util import httpclientservice

# Magic words understood by Butbucket REST API
BITBUCKET_INPROGRESS = 'INPROGRESS'
BITBUCKET_SUCCESSFUL = 'SUCCESSFUL'
BITBUCKET_FAILED = 'FAILED'

_BASE_URL = 'https://api.bitbucket.org/2.0/repositories'
_OAUTH_URL = 'https://bitbucket.org/site/oauth2/access_token'
_GET_TOKEN_DATA = {
    'grant_type': 'client_credentials'
}


class BitbucketStatusPush(ReporterBase):
    name = "BitbucketStatusPush"

    def checkConfig(self, oauth_key=None, oauth_secret=None, auth=None, base_url=_BASE_URL,
                    oauth_url=_OAUTH_URL, debug=None, verify=None, status_key=None,
                    status_name=None, generators=None, **kwargs):
        if auth is not None and (oauth_key is not None or oauth_secret is not None):
            config.error('Either App Passwords or OAuth can be specified, not both')

        if generators is None:
            generators = self._create_default_generators()

        super().checkConfig(generators=generators, **kwargs)
        httpclientservice.HTTPClientService.checkAvailable(self.__class__.__name__)

    @defer.inlineCallbacks
    def reconfigService(self, oauth_key=None, oauth_secret=None, auth=None, base_url=_BASE_URL,
                        oauth_url=_OAUTH_URL, debug=None, verify=None, status_key=None,
                        status_name=None, generators=None, **kwargs):
        oauth_key, oauth_secret = yield self.renderSecrets(oauth_key, oauth_secret)
        self.auth = yield self.renderSecrets(auth)
        self.base_url = base_url
        self.debug = debug
        self.verify = verify
        self.status_key = status_key or Property('buildername')
        self.status_name = status_name or Property('buildername')

        if generators is None:
            generators = self._create_default_generators()

        yield super().reconfigService(generators=generators, **kwargs)

        base_url = base_url.rstrip('/')

        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, base_url,
            debug=self.debug, verify=self.verify, auth=self.auth)

        self.oauthhttp = None
        if self.auth is None:
            self.oauthhttp = yield httpclientservice.HTTPClientService.getService(
                self.master, oauth_url, auth=(oauth_key, oauth_secret),
                debug=self.debug, verify=self.verify)

    def _create_default_generators(self):
        return [
            BuildStartEndStatusGenerator(
                start_formatter=MessageFormatter(subject="", template=''),
                end_formatter=MessageFormatter(subject="", template='')
            )
        ]

    @defer.inlineCallbacks
    def sendMessage(self, reports):
        # Only use OAuth if basic auth has not been specified
        if not self.auth:
            request = yield self.oauthhttp.post("", data=_GET_TOKEN_DATA)
            if request.code != 200:
                content = yield request.content()
                log.msg(f"{request.code}: unable to authenticate to Bitbucket {content}")
                return
            token = (yield request.json())['access_token']
            self._http.updateHeaders({'Authorization': f'Bearer {token}'})

        build = reports[0]['builds'][0]
        if build['complete']:
            status = BITBUCKET_SUCCESSFUL if build['results'] == SUCCESS else BITBUCKET_FAILED
        else:
            status = BITBUCKET_INPROGRESS

        props = Properties.fromDict(build['properties'])
        props.master = self.master

        body = {
            'state': status,
            'key': (yield props.render(self.status_key)),
            'name': (yield props.render(self.status_name)),
            'description': reports[0]['subject'],
            'url': build['url']
        }

        for sourcestamp in build['buildset']['sourcestamps']:
            if not sourcestamp['repository']:
                log.msg(f"Empty repository URL for Bitbucket status {body}")
                continue
            owner, repo = self.get_owner_and_repo(sourcestamp['repository'])

            endpoint = (owner, repo, 'commit', sourcestamp['revision'], 'statuses', 'build')
            bitbucket_uri = f"/{'/'.join(endpoint)}"

            if self.debug:
                log.msg(f"Bitbucket status {bitbucket_uri} {body}")

            response = yield self._http.post(bitbucket_uri, json=body)
            if response.code not in (200, 201):
                content = yield response.content()
                log.msg(f"{response.code}: unable to upload Bitbucket status {content}")

    def get_owner_and_repo(self, repourl):
        """
        Takes a git repository URL from Bitbucket and tries to determine the owner and repository
        name
        :param repourl: Bitbucket git repo in the form of
                    git@bitbucket.org:OWNER/REPONAME.git
                    https://bitbucket.org/OWNER/REPONAME.git
                    ssh://git@bitbucket.org/OWNER/REPONAME.git
                    https://api.bitbucket.org/2.0/repositories/OWNER/REPONAME
        :return: owner, repo: The owner of the repository and the repository name
        """
        parsed = urlparse(repourl)

        base_parsed = urlparse(self.base_url)
        if parsed.path.startswith(base_parsed.path):
            path = parsed.path.replace(base_parsed.path, "")
        elif parsed.scheme:
            path = parsed.path
        else:
            # we assume git@host:owner/repo.git here
            path = parsed.path.split(':', 1)[-1]

        path = path.lstrip('/')
        if path.endswith('.git'):
            path = path[:-4]
        path = path.rstrip('/')

        parts = path.split('/')

        assert len(parts) == 2, 'OWNER/REPONAME is expected'

        return parts
