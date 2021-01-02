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

from buildbot import config
from buildbot.process.results import SUCCESS
from buildbot.reporters.base import ReporterBase
from buildbot.reporters.generators.build import BuildStartEndStatusGenerator
from buildbot.util import httpclientservice
from buildbot.util.logger import Logger
from buildbot.warnings import warn_deprecated

log = Logger()

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

    def checkConfig(self, oauth_key, oauth_secret, base_url=_BASE_URL, oauth_url=_OAUTH_URL,
                    builders=None, debug=None, verify=None, wantProperties=False,
                    wantSteps=False, wantPreviousBuild=False, wantLogs=False, generators=None,
                    **kwargs):

        old_arg_names = {
            'wantProperties': wantProperties is not False,
            'builders': builders is not None,
            'wantSteps': wantSteps is not False,
            'wantPreviousBuild': wantPreviousBuild is not False,
            'wantLogs': wantLogs is not False,
        }

        passed_old_arg_names = [k for k, v in old_arg_names.items() if v]

        if passed_old_arg_names:

            old_arg_names_msg = ', '.join(passed_old_arg_names)
            if generators is not None:
                print(generators is not None)
                config.error(("can't specify generators and deprecated {} arguments ({}) at the "
                              "same time").format(self.__class__.__name__, old_arg_names_msg))
            warn_deprecated('2.10.0',
                            ('The arguments {} passed to {} have been deprecated. Use generators '
                             'instead').format(old_arg_names_msg, self.__class__.__name__))

        if generators is None:
            generators = self._create_generators_from_old_args(builders, wantProperties, wantSteps,
                                                               wantPreviousBuild, wantLogs)

        super().checkConfig(generators=generators, **kwargs)
        httpclientservice.HTTPClientService.checkAvailable(self.__class__.__name__)

    @defer.inlineCallbacks
    def reconfigService(self, oauth_key, oauth_secret, base_url=_BASE_URL, oauth_url=_OAUTH_URL,
                        builders=None, debug=None, verify=None, wantProperties=False,
                        wantSteps=False, wantPreviousBuild=False, wantLogs=False, generators=None,
                        **kwargs):
        oauth_key, oauth_secret = yield self.renderSecrets(oauth_key, oauth_secret)
        self.debug = debug
        self.verify = verify

        if generators is None:
            generators = self._create_generators_from_old_args(builders, wantProperties, wantSteps,
                                                               wantPreviousBuild, wantLogs)

        yield super().reconfigService(generators=generators, **kwargs)

        if base_url.endswith('/'):
            base_url = base_url[:-1]

        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, base_url,
            debug=self.debug, verify=self.verify)

        self.oauthhttp = yield httpclientservice.HTTPClientService.getService(
            self.master, oauth_url, auth=(oauth_key, oauth_secret),
            debug=self.debug, verify=self.verify)

    def _create_generators_from_old_args(self, builders, wantProperties, wantSteps,
                                         wantPreviousBuild, wantLogs):
        # wantProperties, wantLogs, wantSteps and wantPreviousBuild are ignored, because they are
        # not used in this reporter.
        return [BuildStartEndStatusGenerator(builders=builders)]

    @defer.inlineCallbacks
    def send(self, build):
        # the only case when this function is called is when the user derives this class, overrides
        # send() and calls super().send(build) from there.
        yield self._send_impl(build)

    @defer.inlineCallbacks
    def sendMessage(self, reports):
        build = reports[0]['builds'][0]
        if self.send.__func__ is not BitbucketStatusPush.send:
            warn_deprecated('2.9.0', 'send() in reporters has been deprecated. Use sendMessage()')
            yield self.send(build)
        else:
            yield self._send_impl(build)

    @defer.inlineCallbacks
    def _send_impl(self, build):
        results = build['results']
        oauth_request = yield self.oauthhttp.post("",
                                                  data=_GET_TOKEN_DATA)
        if oauth_request.code == 200:
            content_json = yield oauth_request.json()
            token = content_json['access_token']
        else:
            content = yield oauth_request.content()
            log.error("{code}: unable to authenticate to Bitbucket {content}",
                      code=oauth_request.code, content=content)
            return

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

            self._http.updateHeaders({'Authorization': 'Bearer ' + token})

            bitbucket_uri = '/' + \
                '/'.join([owner, repo, 'commit', sha, 'statuses', 'build'])

            response = yield self._http.post(bitbucket_uri, json=body)
            if response.code != 200 and response.code != 201:
                content = yield response.content()
                log.error("{code}: unable to upload Bitbucket status {content}",
                          code=response.code, content=content)

    @staticmethod
    def get_owner_and_repo(repourl):
        """
        Takes a git repository URL from Bitbucket and tries to determine the owner and repository
        name
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
        while path.endswith('/'):
            path = path[:-1]

        parts = path.split('/')

        assert len(parts) == 2, 'OWNER/REPONAME is expected'

        return parts
