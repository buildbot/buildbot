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
from zope.interface import implementer

from buildbot import config
from buildbot import interfaces
from buildbot import util
from buildbot.reporters.message import MessageFormatterMissingWorker

ENCODING = 'utf-8'


@implementer(interfaces.IReportGenerator)
class WorkerMissingGenerator(util.ComparableMixin):

    compare_attrs = ['workers', 'formatter']

    wanted_event_keys = [
        ('workers', None, 'missing'),
    ]

    def __init__(self, workers='all', message_formatter=None):
        self.workers = workers
        self.formatter = message_formatter
        if self.formatter is None:
            self.formatter = MessageFormatterMissingWorker()

    def check(self):
        if not (self.workers == 'all' or isinstance(self.workers, (list, tuple, set))):
            config.error("workers must be 'all', or list of worker names")

    @defer.inlineCallbacks
    def generate(self, master, reporter, key, worker):
        if not self._is_message_needed(worker):
            return None

        msg = yield self.formatter.formatMessageForMissingWorker(master, worker)
        body = msg['body'].encode(ENCODING)
        subject = msg['subject']
        if subject is None:
            subject = "Buildbot worker {name} missing".format(**worker)
        assert msg['type'] in ('plain', 'html'), \
            "'{}' message type must be 'plain' or 'html'.".format(msg['type'])

        return {
            'body': body,
            'subject': subject,
            'type': msg['type'],
            'builder_name': None,
            'results': None,
            'builds': None,
            'users': worker['notify'],
            'patches': None,
            'logs': None,
            'worker': worker['name']
        }

    def generate_name(self):
        name = self.__class__.__name__
        if self.workers is not None:
            name += "_workers_" + "+".join(self.workers)
        return name

    def _is_message_needed(self, worker):
        return (self.workers == 'all' or worker['name'] in self.workers) and worker['notify']
