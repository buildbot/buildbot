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

import pprint

from twisted.internet import defer
from twisted.python import log

from buildbot.mq import base
from buildbot.util import service
from buildbot.util import tuplematch


class SimpleMQ(service.ReconfigurableServiceMixin, base.MQBase):

    def __init__(self):
        base.MQBase.__init__(self)
        self.qrefs = []
        self.persistent_qrefs = {}
        self.debug = False

    def reconfigServiceWithBuildbotConfig(self, new_config):
        self.debug = new_config.mq.get('debug', False)
        return service.ReconfigurableServiceMixin.reconfigServiceWithBuildbotConfig(self,
                                                                                    new_config)

    def produce(self, routingKey, data):
        if self.debug:
            log.msg("MSG: %s\n%s" % (routingKey, pprint.pformat(data)))
        for qref in self.qrefs:
            if tuplematch.matchTuple(routingKey, qref.filter):
                qref.invoke(routingKey, data)

    def startConsuming(self, callback, filter, persistent_name=None):
        if any(not isinstance(k, str) and k is not None for k in filter):
            raise AssertionError("%s is not a filter" % (filter,))
        if persistent_name:
            if persistent_name in self.persistent_qrefs:
                qref = self.persistent_qrefs[persistent_name]
                qref.startConsuming(callback)
            else:
                qref = PersistentQueueRef(self, callback, filter)
                self.qrefs.append(qref)
                self.persistent_qrefs[persistent_name] = qref
        else:
            qref = QueueRef(self, callback, filter)
            self.qrefs.append(qref)
        return defer.succeed(qref)


class QueueRef(base.QueueRef):

    __slots__ = ['mq', 'filter']

    def __init__(self, mq, callback, filter):
        base.QueueRef.__init__(self, callback)
        self.mq = mq
        self.filter = filter

    def stopConsuming(self):
        self.callback = None
        try:
            self.mq.qrefs.remove(self)
        except ValueError:
            pass


class PersistentQueueRef(QueueRef):

    __slots__ = ['active', 'queue']

    def __init__(self, mq, callback, filter):
        QueueRef.__init__(self, mq, callback, filter)
        self.queue = []

    def startConsuming(self, callback):
        self.callback = callback
        self.active = True

        # invoke for every message that was missed
        queue, self.queue = self.queue, []
        for routingKey, data in queue:
            self.invoke(routingKey, data)

    def stopConsuming(self):
        self.callback = self.addToQueue
        self.active = False

    def addToQueue(self, routingKey, data):
        self.queue.append((routingKey, data))
