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
        self._event_consumers = {}
        self._pending_got_event_calls = {}

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
        self.generators = generators

        wanted_event_keys = set()
        for g in self.generators:
            wanted_event_keys.update(g.wanted_event_keys)

        # Remove consumers for keys that are no longer wanted
        for key in list(self._event_consumers.keys()):
            if key not in wanted_event_keys:
                yield self._event_consumers[key].stopConsuming()
                del self._event_consumers[key]

        # Add consumers for new keys
        for key in sorted(list(wanted_event_keys)):
            if key not in self._event_consumers:
                self._event_consumers[key] = \
                    yield self.master.mq.startConsuming(self._got_event, key)

    @defer.inlineCallbacks
    def stopService(self):
        for consumer in self._event_consumers.values():
            yield consumer.stopConsuming()
        self._event_consumers = {}

        for pending_call in list(self._pending_got_event_calls.values()):
            yield pending_call
        self._pending_got_event_calls = {}

        yield super().stopService()

    def _does_generator_want_key(self, generator, key):
        for filter in generator.wanted_event_keys:
            if tuplematch.matchTuple(key, filter):
                return True
        return False

    def _get_chain_key_for_event(self, key, msg):
        if key[0] in ["builds", "buildrequests"]:
            return ("buildrequestid", msg["buildrequestid"])
        return None

    @defer.inlineCallbacks
    def _got_event(self, key, msg):
        chain_key = self._get_chain_key_for_event(key, msg)
        if chain_key is not None:
            d = defer.Deferred()
            pending_call = self._pending_got_event_calls.get(chain_key)
            self._pending_got_event_calls[chain_key] = d
            # Wait for previously pending call, if any, to ensure
            # reports are sent out in the order events were queued.
            if pending_call is not None:
                yield pending_call

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

        if chain_key is not None:
            if self._pending_got_event_calls.get(chain_key) == d:
                del self._pending_got_event_calls[chain_key]
            d.callback(None)  # This event is now fully handled

    def getResponsibleUsersForBuild(self, master, buildid):
        # Use library method but subclassers may want to override that
        return utils.getResponsibleUsersForBuild(master, buildid)

    @abc.abstractmethod
    def sendMessage(self, reports):
        pass
