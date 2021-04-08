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

import abc

from twisted.internet import defer
from twisted.python import log

from buildbot import config
from buildbot.reporters import utils
from buildbot.util import service
from buildbot.util import tuplematch

ENCODING = 'utf-8'


class ReporterBase(service.BuildbotService):
    name = None
    __meta__ = abc.ABCMeta

    compare_attrs = ['generators']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.generators = None
        self._event_consumers = []

    def checkConfig(self, generators):
        if not isinstance(generators, list):
            config.error('{}: generators argument must be a list')

        for g in generators:
            g.check()

        if self.name is None:
            self.name = self.__class__.__name__
            for g in generators:
                self.name += "_" + g.generate_name()

    @defer.inlineCallbacks
    def reconfigService(self, generators):

        for consumer in self._event_consumers:
            yield consumer.stopConsuming()
        self._event_consumers = []

        self.generators = generators

        wanted_event_keys = set()
        for g in self.generators:
            wanted_event_keys.update(g.wanted_event_keys)

        for key in sorted(list(wanted_event_keys)):
            consumer = yield self.master.mq.startConsuming(self._got_event, key)
            self._event_consumers.append(consumer)

    @defer.inlineCallbacks
    def stopService(self):
        for consumer in self._event_consumers:
            yield consumer.stopConsuming()
        self._event_consumers = []
        yield super().stopService()

    def _does_generator_want_key(self, generator, key):
        for filter in generator.wanted_event_keys:
            if tuplematch.matchTuple(key, filter):
                return True
        return False

    @defer.inlineCallbacks
    def _got_event(self, key, msg):
        try:
            reports = []
            for g in self.generators:
                if self._does_generator_want_key(g, key):
                    report = yield g.generate(self.master, self, key, msg)
                    if report is not None:
                        reports.append(report)

            if reports:
                yield self.sendMessage(reports)
        except Exception as e:
            log.err(e, 'Got exception when handling reporter events')

    def getResponsibleUsersForBuild(self, master, buildid):
        # Use library method but subclassers may want to override that
        return utils.getResponsibleUsersForBuild(master, buildid)

    @abc.abstractmethod
    def sendMessage(self, reports):
        pass
