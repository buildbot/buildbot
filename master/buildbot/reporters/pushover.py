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


from twisted.internet import defer
from twisted.python import log as twlog

from buildbot import config
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.reporters.base import ReporterBase
from buildbot.reporters.generators.build import BuildStatusGenerator
from buildbot.reporters.message import MessageFormatter
from buildbot.util import httpclientservice

from .utils import merge_reports_prop
from .utils import merge_reports_prop_take_first

ENCODING = 'utf8'

VALID_PARAMS = {"sound", "callback", "timestamp", "url",
                "url_title", "device", "retry", "expire", "html"}

PRIORITIES = {
    CANCELLED: 'cancelled',
    EXCEPTION: 'exception',
    FAILURE: 'failing',
    SUCCESS: 'passing',
    WARNINGS: 'warnings'
}

DEFAULT_MSG_TEMPLATE = \
    ('The Buildbot has detected a <a href="{{ build_url }}">{{ status_detected }}</a>' +
     'of <i>{{ buildername }}</i> while building {{ projects }} on {{ workername }}.')


class PushoverNotifier(ReporterBase):

    def checkConfig(self, user_key, api_token, priorities=None, otherParams=None,
                    generators=None):

        if generators is None:
            generators = self._create_default_generators()

        super().checkConfig(generators=generators)

        httpclientservice.HTTPClientService.checkAvailable(self.__class__.__name__)

        if otherParams is not None and set(otherParams.keys()) - VALID_PARAMS:
            config.error("otherParams can be only 'sound', 'callback', 'timestamp', "
                         "'url', 'url_title', 'device', 'retry', 'expire', or 'html'")

    @defer.inlineCallbacks
    def reconfigService(self, user_key, api_token, priorities=None, otherParams=None,
                        generators=None):
        user_key, api_token = yield self.renderSecrets(user_key, api_token)

        if generators is None:
            generators = self._create_default_generators()

        yield super().reconfigService(generators=generators)
        self.user_key = user_key
        self.api_token = api_token
        if priorities is None:
            self.priorities = {}
        else:
            self.priorities = priorities
        if otherParams is None:
            self.otherParams = {}
        else:
            self.otherParams = otherParams
        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, 'https://api.pushover.net')

    def _create_default_generators(self):
        formatter = MessageFormatter(template_type='html', template=DEFAULT_MSG_TEMPLATE)
        return [BuildStatusGenerator(message_formatter=formatter)]

    def sendMessage(self, reports):
        body = merge_reports_prop(reports, 'body')
        subject = merge_reports_prop_take_first(reports, 'subject')
        type = merge_reports_prop_take_first(reports, 'type')
        results = merge_reports_prop(reports, 'results')
        worker = merge_reports_prop_take_first(reports, 'worker')

        msg = {
            'message': body,
            'title': subject
        }
        if type == 'html':
            msg['html'] = '1'
        try:
            priority_name = PRIORITIES[results] if worker is None else 'worker_missing'
            msg['priority'] = self.priorities[priority_name]
        except KeyError:
            pass
        return self.sendNotification(msg)

    def sendNotification(self, params):
        twlog.msg("sending pushover notification")
        params.update(dict(user=self.user_key, token=self.api_token))
        params.update(self.otherParams)
        return self._http.post('/1/messages.json', params=params)
