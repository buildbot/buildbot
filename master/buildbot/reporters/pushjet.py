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

LEVELS = {
    CANCELLED: 'cancelled',
    EXCEPTION: 'exception',
    FAILURE: 'failing',
    SUCCESS: 'passing',
    WARNINGS: 'warnings'
}


class PushjetNotifier(NotifierBase):

    def checkConfig(self, secret,
                    mode=("failing", "passing", "warnings"),
                    tags=None, builders=None,
                    buildSetSummary=False, messageFormatter=None,
                    subject="Buildbot %(result)s in %(title)s on %(builder)s",
                    name=None, schedulers=None, branches=None,
                    levels=None, base_url='https://api.pushjet.io',
                    watchedWorkers=None, messageFormatterMissingWorker=None):

        super(PushjetNotifier, self).checkConfig(mode, tags, builders,
                                                 buildSetSummary, messageFormatter,
                                                 subject, False, False,
                                                 name, schedulers,
                                                 branches, watchedWorkers)

        httpclientservice.HTTPClientService.checkAvailable(self.__class__.__name__)

    @defer.inlineCallbacks
    def reconfigService(self, secret,
                        mode=("failing", "passing", "warnings"),
                        tags=None, builders=None,
                        buildSetSummary=False, messageFormatter=None,
                        subject="Buildbot %(result)s in %(title)s on %(builder)s",
                        name=None, schedulers=None, branches=None,
                        levels=None, base_url='https://api.pushjet.io',
                        watchedWorkers=None, messageFormatterMissingWorker=None):

        if messageFormatter is None:
            messageFormatter = DefaultMessageFormatter(template_type='html',
                template_filename='default_notification.txt')
        if messageFormatterMissingWorker is None:
            messageFormatterMissingWorker = MessageFormatterMissingWorker(
                template_filename='missing_notification.txt')
        super(PushjetNotifier, self).reconfigService(mode, tags, builders,
                                                     buildSetSummary, messageFormatter,
                                                     subject, False, False,
                                                     name, schedulers, branches,
                                                     watchedWorkers, messageFormatterMissingWorker)
        self.secret = secret
        if levels is None:
            self.levels = {}
        else:
            self.levels = levels
        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, base_url)

    def sendMessage(self, body, subject=None, type=None, builderName=None,
                    results=None, builds=None, users=None, patches=None,
                    logs=None, worker=None):

        if worker is not None and worker not in self.watchedWorkers:
            return

        msg = {'message': body}
        level = self.levels.get(LEVELS[results] if worker is None else 'worker_missing')
        if level is not None:
            msg['level'] = level
        if subject is not None:
            msg['title'] = subject
        else:
            msg['title'] = self.subject % {'result': Results[results],
                                           'projectName': self.master.config.title,
                                           'title': self.master.config.title,
                                           'builder': builderName}
        return self.sendNotification(msg)

    def sendNotification(self, params):
        twlog.msg("sending pushjet notification")
        params.update(dict(secret=self.secret))
        return self._http.post('/message', data=params)
