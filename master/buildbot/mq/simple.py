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

import re
import pprint
from twisted.python import log
from buildbot.mq import base
from buildbot import config

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

    def produce(self, routing_key, data):
        if self.debug:
            log.msg("MSG: %s\n%s" % (routing_key, pprint.pformat(data)))
        for qref in self.qrefs:
            if qref.matches(routing_key):
                qref.invoke(routing_key, data)

    def startConsuming(self, callback, *topics, **kwargs):
        persistent_name = kwargs.get('persistent_name', None)
        if persistent_name:
            if persistent_name in self.persistent_qrefs:
                qref = self.persistent_qrefs[persistent_name]
                qref.start_consuming(callback)
            else:
                qref = PersistentQueueRef(self, callback, topics)
                self.qrefs.append(qref)
                self.persistent_qrefs[persistent_name] = qref
        else:
            qref = QueueRef(self, callback, topics)
            self.qrefs.append(qref)
        return qref

_needsQuotesRegexp = re.compile(r'([\\.*?+{}\[\]|()])')
class QueueRef(base.QueueRef):

    __slots__ = [ 'mq', 'topics' ]

    def __init__(self, mq, callback, topics):
        base.QueueRef.__init__(self, callback)
        self.mq = mq
        self.topics = [ self.topicToRegexp(t) for t in topics ]

    def topicToRegexp(self, topic):
        subs = { '.' : r'\.', '*' : r'[^.]+', }

        parts = re.split(r'(\.)', topic)
        topic_re = []
        while parts:
            part = parts.pop(0)
            if part in subs:
                topic_re.append(subs[part])
            elif part == '#':
                if parts:
                    # pop the following '.', as it will not exist when
                    # matching zero words.
                    parts.pop(0)
                    topic_re.append(r'([^.]+\.)*')
                else:
                    # pop the previous '.' from the regexp, as it will not
                    # exist when matching zero words
                    if topic_re:
                        topic_re.pop()
                        topic_re.append(r'(\.[^.]+)*')
                    else:
                        # topic is just '#': degenerate case
                        topic_re.append(r'.+')
            else:
                topic_re.append(_needsQuotesRegexp.sub(r'\\\1', part))
        topic_re = ''.join(topic_re) + '$'
        return re.compile(topic_re)

    def matches(self, routing_key):
        for re in self.topics:
            if re.match(routing_key):
                return True
        return False

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

    def start_consuming(self, callback):
        self.callback = callback
        self.active = True

        # invoke for every message that was missed
        queue, self.queue = self.queue, []
        for routing_key, data in queue:
            self.invoke(routing_key, data)

    def stopConsuming(self):
        self.callback = self.addToQueue
        self.active = False

    def addToQueue(self, routing_key, data):
        self.queue.append((routing_key, data))
