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
from future.utils import string_types

from twisted.internet import defer

from buildbot import config
from datetime import datetime
from humanize import naturaltime
from buildbot.status.builder import SUCCESS
from buildbot.util import httpclientservice
from buildbot.reporters.http import HttpStatusPushBase

SLACK_BASE_URL = "https://hooks.slack.com"


class SlackStatusPush(HttpStatusPushBase):
    """
    Sends messages to a Slack.io channel when each build finishes with a handy
    link to the build results.
    """

    name = "SlackStatusPush"

    def checkConfig(self, endpoint, username="buildbot",
                    icon="https://buildbot.net/img/nut.png",
                    notify_on_success=True, notify_on_failure=True,
                    **kwargs):
        if not isinstance(endpoint, string_types):
            config.error('endpoint must be a string')
        if not isinstance(username, string_types):
            config.error('username must be a string')
        if not isinstance(icon, string_types):
            config.error('icon must be a string')
        if not isinstance(notify_on_success, bool):
            config.error('notify_on_success must be a bool')
        if not isinstance(notify_on_failure, bool):
            config.error('notify_on_failure must be a bool')

    @defer.inlineCallbacks
    def reconfigService(self, endpoint, username="buildbot",
                        icon="https://buildbot.net/img/nut.png",
                        notify_on_success=True, notify_on_failure=True,
                        **kwargs):
        """
        Creates a SlackStatusPush status service.
        :param endpoint: Your Slack endpoint.
        :param username: The user name of the "user" positing the messages on
            Slack.
        :param icon: The icon of the user posting the messages on Slack.
        :param notify_on_success: Set this to False if you don't want
            messages when a build was successful.
        :param notify_on_failure: Set this to False if you don't want
            messages when a build failed.
        """
        yield HttpStatusPushBase.reconfigService(self, **kwargs)
        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, SLACK_BASE_URL,
            debug=self.debug, verify=self.verify)

        self.endpoint = endpoint
        self.username = username
        self.icon = icon
        self.notify_on_success = notify_on_success
        self.notify_on_failure = notify_on_failure

    @defer.inlineCallbacks
    def buildFinished(self, key, build):
        if not self.notify_on_success and build['result'] == SUCCESS:
            return

        if not self.notify_on_failure and build['result'] != SUCCESS:
            return

        url = "%s#/builders/%d/builds/%d" % (self.master.config.buildbotURL,
                                             build['builderid'],
                                             build['buildid'])
        naive_startedAt = build['started_at'].replace(tzinfo=None)
        humantime = naturaltime(datetime.now() - naive_startedAt)
        ss = yield self.master.db.sourcestamps.getSourceStamp(build['buildid'])
        br = yield self.master.db.buildrequests.getBuildRequest(build['buildrequestid'])

        if ss:
            message = """
Build {name} {result} | {author} | {humantime}
Upstream at {repository}
Details at {url}""".format(name=br['buildername'], result=build['state_string'],
                           author=ss['patch_author'], humantime=humantime,
                           repository=ss['repository'], url=url)
        else:
            message = """
Build {name} {result} | {humantime}
Details at {url}""".format(name=br['buildername'], result=build['state_string'],
                           humantime=humantime, url=url)

        payload = {
            "text": message
        }

        if self.username:
            payload['username'] = self.username

        if self.icon:
            if self.icon.startswith(':'):
                payload['icon_emoji'] = self.icon
            else:
                payload['icon_url'] = self.icon

        response = yield self._http.post(self.endpoint, json=payload)
        if response.code != 200:
            content = yield response.content()
            log.error("{code}: unable to upload status: {content}",
                      code=response.code, content=content)
