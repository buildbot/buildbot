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
"""
Push build statuses to Slack
"""
from twisted.internet import defer

from buildbot import config
from buildbot.process.results import SUCCESS
from buildbot.reporters.http import HttpStatusPushBase
from buildbot.util.httpclientservice import HTTPClientService
from buildbot.util.logger import Logger


_LOG = Logger()


class _Default(object):
    # pylint: disable=too-few-public-methods
    """
    this is a sentinel value for the default_channels parameter below
    """


class SlackReporter(HttpStatusPushBase):
    # pylint: disable=invalid-name, too-many-ancestors
    """
    minimal slack integration
    """
    def checkConfig(self,
                    username,   # pylint: disable=unused-argument
                    url,        # pylint: disable=unused-argument
                    mapping,
                    default_channels=_Default,
                    *args, **kwargs):
        """
        check if the provided configuration is OK
        """
        if not isinstance(mapping, dict):
            config.error('mapping parameter must be a dictionary')
        if not (default_channels is _Default or
                isinstance(default_channels, (list, tuple))):
            config.error('default_channels parameter must be a list or a tuple')

        super(SlackReporter).checkConfig(*args, **kwargs)

    @defer.inlineCallbacks
    def reconfigService(self, username, url, mapping, default_channels,
                        *args, **kwargs):
        """
        reconfigure the service based on the new parameters
        """
        yield super(SlackReporter).reconfigService(self, *args, **kwargs)

        # pylint: disable=attribute-defined-outside-init

        self._username = username

        # TODO: this goes to the documentation
        # mapping is expected to have the following structure
        # mapping = {
        #     'builder1': {
        #         'kinds': ('start',),
        #         'channels': ('#channel1', '#channel2')
        #     },
        #     'builder2': {
        #         'kinds': ('finish',),
        #     },
        #     'builder3': {
        #         'kinds': ('start', 'finish')
        #     },
        # }
        self._mapping = mapping
        # TODO: this goes to the documentation
        # list of channels to post a message to if none are specified in the
        # mapping.  the default behaviour is to use the channel configured for
        # the webhook
        self._default_channels = default_channels

        self._http = yield HTTPClientService.getService(self.master, url)

    def _filter_builds(self, build):
        """
        check if we should post a message for the given build:

        * the builder is present in the map
        * 'kinds' has the value for the kind of this notification (start/finish)
        """
        not_interested = None, None

        props = self._mapping.get(build['builder'], dict())
        if not props:
            return not_interested

        kind = 'finish' if build['complete'] else 'start'
        if kind not in props['kinds']:
            return not_interested

        if self._default_channels is not _Default:
            channels = props.get('channels', self._default_channels)
            if not channels:
                return not_interested
        else:
            channels = None

        return props, channels

    @staticmethod
    def _prepare_attachment(build):
        """
        prepare an attachment based on the build information
        """
        if build['complete']:
            result = build['results']

            title = 'Build #{} has finished: {}'.format(build['buildid'],
                                                        result)
            # NOTE: we might want to include links to the logs of failed
            # step(s) to 'text' => update neededDetails for the class
            text = ' '.join(build.getText())
            timestamp = build['complete_at']
            color = 'good' if result == SUCCESS else 'danger'
        else:
            title = 'Build #{} has started'.format(build['buildid'])
            text = None
            timestamp = build['started_at']
            color = 'warning'

        attachment = dict(
            title_name=title,
            title_url=build['url'],
            fallback='{}: <{}>'.format(title, build['url']),
            color=color,
            ts=timestamp
        )

        if text:
            attachment['text'] = text

        return attachment

    @defer.inlineCallbacks
    def send(self, build):
        """
        check the build and post a message to all configured channels
        """
        props, channels = self._filter_builds(build)
        if not props:
            defer.returnValue(SUCCESS)
        else:
            payload = dict(
                username=self._username,
                attachments=[self._prepare_attachment(build)])

            posts = []

            if channels is None:
                posts.append(self._http.post("", json=payload))
            else:
                for channel in channels:
                    payload['channel'] = channel

                    posts.append(self._http("", json=payload))

            return defer.gatherResults(posts)
