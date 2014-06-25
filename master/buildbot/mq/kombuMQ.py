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
import threading
import thread

from buildbot import config
from buildbot.mq import base
from twisted.python import log
from kombu.transport.base import Message
from datetime import datetime


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
        # NOTE(damon) auto_declrae often cause redeclare and will cause error
        self.consumers = {}
        self.message_hub = KombuHub(self.conn)
        self.message_hub.start()

    def setupExchange(self):
        self.exchange = kombu.Exchange(
            'buildbot', 'topic', channel=self.channel, durable=True)
        # NOTE(damon) if durable = false, durable queue will cant bind to this
        # exchange
        try:
            self.exchange.declare()
        except amqp.exceptions.PreconditionFailed, e:
            log.msg(
                "WARNNING: exchange buildbot already exist, " +
                "this maybe casued by anomaly exit last time")
            # NOTE(damon) should we raise Exception here?
        except:
            log.msg("ERR: Unexpected error")
            raise
        finally:
            log.msg("MSG: Exchange start successfully")

    def reconfigService(self, new_config):
        self.debug = new_config.mq.get('debug', True)
        return config.ReconfigurableServiceMixin.reconfigService(self,
                                                                 new_config)

    def registerQueue(self, key, name=None, durable=False):
        if name == None:
            name = key
        if self._checkKey(key) == True:
            # NOTE(damon) check for if called by other class
            self.queues[name] = kombu.Queue(
                name, self.exchange, channel=self.channel, routing_key=key,
                durable=durable)
            self.queues[name].declare()
        else:
            log.msg(
                "ERROR: Routing Key %s has been used by, register queue failed" % key)
            raise Exception("ERROR: Routing Key %s has been used" % key)
            # NOTE(damon) should raise an exception here?

    def _checkKey(self, key):
        # check whether key already in queues
        for queue in self.queues.values():
            if queue.routing_key == key:
                return False
        return True

    def produce(self, routingKey, data):
        self.debug = True
        if self.debug:
            log.msg("MSG: %s\n%s" % (routingKey, pprint.pformat(data)))
        key = self.formatKey(routingKey)
        data = self.formatData(data)
        message = Message(self.channel, body=data)
        self.producer.publish(message.body, routing_key=key)
        # TODO(damon) default serializer is JSON, it doesn't support python's
        # datetime

    def registerConsumer(self, queues_name, callback, name=None, durable=False):
        # queues_name can be a list of queues' names or one queue's name
        # (list of strings or one string)
        if name == None:
            name = queues_name

        if type(queues_name) == list:
            queues = self.getQueues(queues_name)
        else:
            queues = self.queues.get(queues_name)
        if not name in self.consumers:
            self.consumers[name] = kombu.Consumer(
                self.channel, queues, auto_declare=False)
            self.consumers[name].register_callback(callback)

    def getQueues(self, queues_name):
        queues = []
        for name in queues_name:
            queues.append(self.queues[name])
        return queues

    def startConsuming(self, callback, routingKey, persistent_name=None):
        key = self.formatKey(routingKey)

        log.msg(str(key) + str(self.queues))
        try:
            queue = self.queues[key]
        except:
            self.registerQueue(key)
            try:
                queue = self.queues.get(key)
            except:
                raise

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

        self.consumers[key].addCallback = self.consumers[key].register_callback

        return self.consumers[key]

    def formatKey(self, key):
        # transform key from a tuple to a string with standard routing key's
        # format
        result = ""
        for item in key:
            if item == None:
                result += "*."
            else:
                result += item + "."

        return result[:-1]

    def formatData(self, data):
        from buildbot.util import datetime2epoch
        for item in data:
            data[item] = datetime2epoch(data[item])

        return data

    def __exit__(self):
        self.message_hub.__exit__()
        for queue in self.queues:
            queue.delete(nowait=True)
        self.exchange.delete(nowait=True)
        self.conn.release()


class KombuHub(threading.Thread):

    """Message hub to handle message asynchronously by start a another thread"""

    def __init__(self, conn):
        threading.Thread.__init__(self)
        self.conn = conn
        self.hub = kombu.async.Hub()

        self.conn.register_with_event_loop(self.hub)

    def run(self):
        self.hub.run_forever()

    def __exit__(self):
        self.hub.stop()
