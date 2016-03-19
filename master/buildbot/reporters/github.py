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


"""Push events to github

."""

from datetime import datetime

from buildbot import config
from buildbot.util import service
from buildbot.reporters import utils
from buildbot.process.properties import Properties
from buildbot.process.properties import Interpolate
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import Results
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS

from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet.protocol import ProcessProtocol
from twisted.python import log

try:
    from txgithub.api import GithubApi as GitHubAPI
except ImportError:
    GitHubAPI = None

class GitHubStatusPush(service.BuildbotService):

    name = "GitHubStatusPush"

    def reconfigService(self, token,
            startDescription=None, endDescription=None,
            context=None, baseURL=None, builders=None):
        self.builders = builders

        """
        Token for GitHub API.
        """
        if not GitHubAPI:
            config.error('GitHubStatus requires txgithub package installed')

        self.context = context or Interpolate('buildbot/%(prop:buildername)s')
        self.startDescription = startDescription or 'Build started.'
        self.endDescription = endDescription or 'Build done.'

        self.github = GitHubAPI(oauth2_token=token, baseURL=baseURL)

        self.handledBuildIds = set()

    @defer.inlineCallbacks
    def startService(self):
        yield service.BuildbotService.startService(self)
        startConsuming = self.master.mq.startConsuming

        self._buildUpdatedConsumer = yield startConsuming(
            self.sendGitHubStatus,
            ('builds', None, 'update'))

        self._buildCompleteConsumer = yield startConsuming(
            self.sendGitHubStatus,
            ('builds', None, 'finished'))

    def stopService(self):
        self._buildUpdatedConsumer.stopConsuming()
        self._buildCompleteConsumer.stopConsuming()

    @defer.inlineCallbacks
    def sendGitHubStatus(self, key, build):

        if not build['complete'] and build['buildid'] in self.handledBuildIds:
            return
        else:
            self.handledBuildIds.add(build['buildid'])

        buildrequest = yield self.master.data.get(("buildrequests", build['buildrequestid']))
        buildset = yield self.master.data.get(("buildsets", buildrequest['buildsetid']))
        yield utils.getDetailsForBuilds(self.master, buildset, [build])
        build['url'] = utils.getURLForBuild(self.master, build['builder']['builderid'], build['number'])

        status = {}

        props_dict = yield self.master.db.builds.getBuildProperties(build['buildid'])
        props = Properties.fromDict(props_dict)

        startTime = build['started_at'];
        endTime = build['complete_at'];
        status['startDateTime'] = startTime.isoformat(' ')

        if build['complete']:
            self.handledBuildIds.remove(build['buildid'])
            status['state'] = {
                    SUCCESS: 'success',
                    FAILURE: 'failure'
                }.get(build['results'], 'error')
            status['description'] = yield props.render(self.endDescription)
            status['endDateTime'] = endTime.isoformat(' ')
            status['duration'] = str(endTime - startTime)
        else:
            status['state'] = 'pending'
            status['description'] = yield props.render(self.startDescription)
            status['endDateTime'] = "In Progress"
            status['duration'] = "In Progress"

        status['context'] = yield props.render(self.context)

        sourcestamps = build['buildset']['sourcestamps']
        project = sourcestamps[0]['project']

        if project == '':
            repo = sourcestamps[0]['repository'].split('/')[-2:]
            repoOwner = repo[0]
            repoName = '.'.join(repo[1].split('.')[:-1])
        else:
            repoOwner, repoName = project.split('/')

        status['repoOwner'] = repoOwner
        status['repoName'] = repoName

        for sourcestamp in sourcestamps:
            _status = status.copy()
            _status['sha'] = sourcestamp['revision']
            d = self.github.repos.createStatus(
                repo_user = _status['repoOwner'].encode('utf-8'),
                repo_name = _status['repoName'].encode('utf-8'),
                sha = _status['sha'].encode('utf-8'),
                state = _status['state'].encode('utf-8'),
                target_url = build['url'].encode('utf-8'),
                context = _status['context'].encode('utf-8'),
                description = _status['description'].encode('utf-8')
            )
            success_message = (
                'Status "%(state)s" sent for '
                '%(repoOwner)s/%(repoName)s at %(sha)s.'
            ) % _status
            error_message = (
                'Fail to send status "%(state)s" for '
                '%(repoOwner)s/%(repoName)s at %(sha)s.'
            ) % _status
            d.addCallback(lambda _: log.msg(success_message))
            d.addErrback(lambda failure: log.err(failure, error_message))
