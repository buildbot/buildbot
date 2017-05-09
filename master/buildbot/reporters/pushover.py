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

from twisted.internet import defer
from twisted.python import log as twlog

from buildbot import config
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.process.results import Results
from buildbot.reporters.message import MessageFormatter as DefaultMessageFormatter
from buildbot.reporters.message import MessageFormatterMissingWorker
from buildbot.reporters.notifier import NotifierBase
from buildbot.util import httpclientservice

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


class PushoverNotifier(NotifierBase):

    def checkConfig(self, user_key, api_token,
                    mode=("failing", "passing", "warnings"),
                    tags=None, builders=None,
                    buildSetSummary=False, messageFormatter=None,
                    subject="Buildbot %(result)s in %(title)s on %(builder)s",
                    name=None, schedulers=None, branches=None,
                    priorities=None, otherParams=None,
                    watchedWorkers=None, messageFormatterMissingWorker=None):

        super(PushoverNotifier, self).checkConfig(mode, tags, builders,
                                                  buildSetSummary, messageFormatter,
                                                  subject, False, False,
                                                  name, schedulers,
                                                  branches, watchedWorkers)

        httpclientservice.HTTPClientService.checkAvailable(self.__class__.__name__)

        if otherParams is not None and set(otherParams.keys()) - VALID_PARAMS:
            config.error("otherParams can be only 'sound', 'callback', 'timestamp', "
                         "'url', 'url_title', 'device', 'retry', 'expire', or 'html'")

    @defer.inlineCallbacks
    def reconfigService(self, user_key, api_token,
                        mode=("failing", "passing", "warnings"),
                        tags=None, builders=None,
                        buildSetSummary=False, messageFormatter=None,
                        subject="Buildbot %(result)s in %(title)s on %(builder)s",
                        name=None, schedulers=None, branches=None,
                        priorities=None, otherParams=None,
                        watchedWorkers=None, messageFormatterMissingWorker=None):

        if messageFormatter is None:
            messageFormatter = DefaultMessageFormatter(template_type='html',
                template_filename='default_notification.txt')
        if messageFormatterMissingWorker is None:
            messageFormatterMissingWorker = MessageFormatterMissingWorker(
                template_filename='missing_notification.txt')
        super(PushoverNotifier, self).reconfigService(mode, tags, builders,
                                                      buildSetSummary, messageFormatter,
                                                      subject, False, False,
                                                      name, schedulers, branches,
                                                      watchedWorkers, messageFormatterMissingWorker)
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

    def sendMessage(self, body, subject=None, type=None, builderName=None,
                    results=None, builds=None, users=None, patches=None,
                    logs=None, worker=None):

        if worker is not None and worker not in self.watchedWorkers:
            return

        msg = {'message': body}
        if type == 'html':
            msg['html'] = '1'
        try:
            msg['priority'] = self.priorities[PRIORITIES[results] if worker is None else 'worker_missing']
        except KeyError:
            pass
        if subject is not None:
            msg['title'] = subject
        else:
            msg['title'] = self.subject % {'result': Results[results],
                                           'projectName': self.master.config.title,
                                           'title': self.master.config.title,
                                           'builder': builderName}
        return self.sendNotification(msg)

    def sendNotification(self, params):
        twlog.msg("sending pushover notification")
        params.update(dict(user=self.user_key, token=self.api_token))
        params.update(self.otherParams)
        return self._http.post('/1/messages.json', params=params)
