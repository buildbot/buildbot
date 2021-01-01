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

from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.reporters.base import ReporterBase
from buildbot.reporters.message import MessageFormatter
from buildbot.reporters.message import MessageFormatterMissingWorker
from buildbot.util import httpclientservice

from .utils import merge_reports_prop
from .utils import merge_reports_prop_take_first

ENCODING = 'utf8'

LEVELS = {
    CANCELLED: 'cancelled',
    EXCEPTION: 'exception',
    FAILURE: 'failing',
    SUCCESS: 'passing',
    WARNINGS: 'warnings'
}

DEFAULT_MSG_TEMPLATE = \
    ('The Buildbot has detected a <a href="{{ build_url }}">{{ status_detected }}</a>' +
     'of <i>{{ buildername }}</i> while building {{ projects }} on {{ workername }}.')

DEFAULT_MSG_TEMPLATE_MISSING_WORKER = \
    ('The Buildbot \'{{buildbot_title}}\' has noticed that the worker named ' +
     '{{worker.name}} went away. It last disconnected at {{worker.last_connection}}.')


class PushjetNotifier(ReporterBase):

    def checkConfig(self, secret,
                    mode=("failing", "passing", "warnings"),
                    tags=None, builders=None,
                    buildSetSummary=False, messageFormatter=None,
                    subject="Buildbot %(result)s in %(title)s on %(builder)s",
                    schedulers=None, branches=None,
                    levels=None, base_url='https://api.pushjet.io',
                    watchedWorkers=None, messageFormatterMissingWorker=None,
                    generators=None):
        super().checkConfig(mode, tags, builders,
                            buildSetSummary, messageFormatter,
                            subject, False, False,
                            schedulers,
                            branches, watchedWorkers,
                            messageFormatterMissingWorker,
                            generators=generators)

        httpclientservice.HTTPClientService.checkAvailable(self.__class__.__name__)

    @defer.inlineCallbacks
    def reconfigService(self, secret,
                        mode=("failing", "passing", "warnings"),
                        tags=None, builders=None,
                        buildSetSummary=False, messageFormatter=None,
                        subject="Buildbot %(result)s in %(title)s on %(builder)s",
                        schedulers=None, branches=None,
                        levels=None, base_url='https://api.pushjet.io',
                        watchedWorkers=None, messageFormatterMissingWorker=None,
                        generators=None):
        secret = yield self.renderSecrets(secret)
        if messageFormatter is None:
            messageFormatter = MessageFormatter(template_type='html', template=DEFAULT_MSG_TEMPLATE)
        if messageFormatterMissingWorker is None:
            messageFormatterMissingWorker = \
                MessageFormatterMissingWorker(template=DEFAULT_MSG_TEMPLATE_MISSING_WORKER)
        yield super().reconfigService(mode, tags, builders,
                                      buildSetSummary, messageFormatter,
                                      subject, False, False,
                                      schedulers, branches,
                                      watchedWorkers, messageFormatterMissingWorker,
                                      generators=generators)
        self.secret = secret
        if levels is None:
            self.levels = {}
        else:
            self.levels = levels
        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, base_url)

    def sendMessage(self, reports):
        body = merge_reports_prop(reports, 'body')
        subject = merge_reports_prop_take_first(reports, 'subject')
        results = merge_reports_prop(reports, 'results')
        worker = merge_reports_prop_take_first(reports, 'worker')

        msg = {
            'message': body,
            'title': subject
        }

        level = self.levels.get(LEVELS[results] if worker is None else 'worker_missing')
        if level is not None:
            msg['level'] = level

        return self.sendNotification(msg)

    def sendNotification(self, params):
        twlog.msg("sending pushjet notification")
        params.update(dict(secret=self.secret))
        return self._http.post('/message', data=params)
