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

import pprint
from twisted.python import log
from buildbot.mq import base
from buildbot import config
from buildbot.util import topicmatch

class SimpleMQ(config.ReconfigurableServiceMixin, base.MQBase):

    def __init__(self, master):
        base.MQBase.__init__(self, master)
        self.qrefs = []
        self.persistent_qrefs = {}
        self.debug = False

    def reconfigService(self, new_config):
        self.debug = new_config.mq.get('debug', False)
        return config.ReconfigurableServiceMixin.reconfigService(self,
                                                            new_config)

    def produce(self, **data):
        if self.debug:
            log.msg("MSG: %s.%s\n%s" % (data['_type'], data['_event'], pprint.pformat(data)))
        for qref in self.qrefs:
            if qref.matcher.matches(data):
                qref.invoke(data)

    def startConsuming(self, callback, *topics, **kwargs):
        persistent_name = kwargs.get('persistent_name', None)
        if persistent_name:
            if persistent_name in self.persistent_qrefs:
                qref = self.persistent_qrefs[persistent_name]
                qref.startConsuming(callback)
            else:
                qref = PersistentQueueRef(self, callback, topics)
                self.qrefs.append(qref)
                self.persistent_qrefs[persistent_name] = qref
        else:
            qref = QueueRef(self, callback, topics)
            self.qrefs.append(qref)
        return qref

class QueueRef(base.QueueRef):

    __slots__ = [ 'mq', 'matcher' ]

    def __init__(self, mq, callback, topics):
        base.QueueRef.__init__(self, callback)
        self.mq = mq
        self.matcher = topicmatch.TopicMatcher(topics)

    def stopConsuming(self):
        self.callback = None
        try:
            self.mq.qrefs.remove(self)
        except ValueError:
            pass

class PersistentQueueRef(QueueRef):

    __slots__ = [ 'active', 'queue' ]

    def __init__(self, mq, callback, topics):
        QueueRef.__init__(self, mq, callback, topics)
        self.queue = []

    def startConsuming(self, callback):
        self.callback = callback
        self.active = True

        # invoke for every message that was missed
        queue, self.queue = self.queue, []
        for data in queue:
            self.invoke(data)

    def stopConsuming(self):
        self.callback = self.addToQueue
        self.active = False

    def addToQueue(self, data):
        self.queue.append(data)
