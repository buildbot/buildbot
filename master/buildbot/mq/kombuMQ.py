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
import kombu
import kombu.async
import amqp.exceptions
import multiprocessing

from buildbot import config
from twisted.internet import defer
from buildbot.mq import base
from buildbot.util import datetime2epoch
from buildbot.util import json
from datetime import datetime
from kombu.transport.base import Message
from twisted.python import log



class KombuMQ(config.ReconfigurableServiceMixin, base.MQBase):

    def __init__(self, master, conn='librabbitmq://guest:guest@localhost//'):
        # connection is a string and its default value:
        base.MQBase.__init__(self, master)
        self.debug = False
        self.conn = kombu.Connection(conn)
        self.channel = self.conn.channel()
        self.setupExchange()
        self.queues = {}
        self.producer = kombu.Producer(
            self.channel, exchange=self.exchange, auto_declare=False)
        # NOTE(damon) auto_declrae often causes redeclare and will cause error
        self.consumers = {}
        self.message_hub = KombuHub(self.conn)
        self.message_hub.start()

    def setupExchange(self):
        self.exchange = kombu.Exchange(
            'buildbot', 'topic', channel=self.channel, durable=True)
        # NOTE(damon) if durable = false, durable queue won't bind to this
        # exchange
        self.exchange.declare()
        log.msg("MSG: Exchange start successfully")

    def reconfigService(self, new_config):
        self.debug = new_config.mq.get('debug', True)
        return config.ReconfigurableServiceMixin.reconfigService(self,  new_config)

    def registerQueue(self, key, name=None, durable=False):
        if name is None:
            name = key
        if self._checkKey(key):
            # NOTE(damon) check for if called by other class
            self.queues[name] = kombu.Queue(
                name, self.exchange, channel=self.channel, routing_key=key,
                durable=durable)
            self.queues[name].declare()
        else:
            log.msg(
                "ERR: Routing Key %s has been used, register queue failed" % key)
            # raise Exception("ERROR: Routing Key %s has been used" % key)
            # NOTE(damon) should raise an exception here?

    def _checkKey(self, key):
        # check whether key already in queues
        for queue in self.queues.values():
            if queue.routing_key == key:
                return False
        return not any(queue.routing_key == key for queue in self.queues.values())

    def produce(self, routingKey, data):
        self.debug = True
        if self.debug:
            log.msg("MSG: %s\n%s" % (routingKey, pprint.pformat(data)))
        key = self.formatKey(routingKey)
        data = json.dumps(data, default=self._toJson,
                          sort_keys=True, separators=(',', ':'))
        message = Message(self.channel, body=data)
        ensurePublish = self.conn.ensure(self.producer,
                                             self.producer.publish, max_retries=5)
        ensurePublish(message.body, routing_key=key)

    def registerConsumer(self, queues_name, callback, name=None, durable=False):
        # queues_name can be a list of queues' names or one queue's name
        # (list of strings or one string)
        if name is None:
            name = queues_name

        if isinstance(queues_name, list):
            queues = self.getQueues(queues_name)
        else:
            queues = self.queues.get(queues_name)
        if not name in self.consumers:
            self.consumers[name] = kombu.Consumer(
                self.channel, queues, auto_declare=False)
            self.consumers[name].register_callback(callback)

    def getQueues(self, queues_name):
        return [self.queues[name] for name in queues_name]

    def startConsuming(self, callback, routingKey, persistent_name=None):
        key = self.formatKey(routingKey)

        if key not in self.queues:
            ensureRegister = self.conn.ensure(None,
                                              self.registerQueue,
                                              max_retries=5)
            ensureRegister(key)
        queue = self.queues.get(key)

        if key in self.consumers.keys():
            log.msg(
                "WARNNING: Consumer's Routing Key %s has been used by, " % key +
                "register failed")
            if callback in self.consumers[key].callbacks:
                log.msg(
                    "WARNNING: Consumer %s has been register to callback %s "
                    % (key, callback))
            else:
                self.consumers[key].register_callback(callback)
        else:
            self.registerConsumer(key, callback)

        # return DeferConsumer(self.consumers[key])
        qref = QueueRef(self.consumers[key], callback)
        return defer.succeed(qref)

    def formatKey(self, key):
        # transform key from a tuple to a string with standard routing key's
        # format
        result = [item for item in key]

        return ".".join(result)

    def _toJson(self, obj):
        if isinstance(obj, datetime.datetime):
            return datetime2epoch(obj)


class KombuHub(multiprocessing.Process):

    """Message hub to handle message asynchronously by start a another process"""

    def __init__(self, conn):
        multiprocessing.Process.__init__(self)
        self.conn = conn
        self.hub = kombu.async.Hub()
        self.lock = multiprocessing.Lock()

        self.conn.register_with_event_loop(self.hub)
        self.attempts = 5

    def run(self):
        if self.attempts == 0:
            raise "Attempts run kombu hub 5 times and all fail"
        try:
            self.hub.run_forever()
        except:
            self.attempts = self.attempts - 1
            self.run()

    def __exit__(self):
        self.hub.stop()


class DeferConsumer(object):

    "Use for simulating defer's addCallback"

    def __init__(self, consumer):
        self.consumer = consumer

    def addCallback(self, callback):
        self.consumer.register_callback(callback)

    def addErrback(self, callback, msg):
        self.consumer.register_callback(callback)
        log.msg(msg)

    def stopConsuming(self):
        pass

class QueueRef(base.QueueRef):

    __slots__ = ['mq', 'filter']

    def __init__(self, consumer, callback):
        base.QueueRef.__init__(self, callback)
        self.consumer = consumer

    def stopConsuming(self):
        self.callback = None
        self.consumer.cancel()