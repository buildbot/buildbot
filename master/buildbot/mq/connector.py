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

from twisted.python.reflect import namedObject

from buildbot.util import service


class MQConnector(service.ReconfigurableServiceMixin, service.AsyncMultiService):

    classes = {
        'simple': {
            'class': "buildbot.mq.simple.SimpleMQ",
            'keys': set(['debug']),
        },
        'wamp': {
            'class': "buildbot.mq.wamp.WampMQ",
            'keys': set(["router_url", "realm", "wamp_debug_level"]),
        },
    }
    name = 'mq'

    def __init__(self):
        service.AsyncMultiService.__init__(self)
        self.impl = None  # set in setup
        self.impl_type = None  # set in setup

    def setup(self):
        assert not self.impl

        # imports are done locally so that we don't try to import
        # implementation-specific modules unless they're required.
        typ = self.master.config.mq['type']
        assert typ in self.classes  # this is checked by MasterConfig
        self.impl_type = typ
        cls = namedObject(self.classes[typ]['class'])
        self.impl = cls()

        # set up the impl as a child service
        self.impl.setServiceParent(self)

        # configure it (early)
        self.impl.reconfigServiceWithBuildbotConfig(self.master.config)

        # copy the methods onto this object for ease of access
        self.produce = self.impl.produce
        self.startConsuming = self.impl.startConsuming
        self.waitUntilEvent = self.impl.waitUntilEvent

    def reconfigServiceWithBuildbotConfig(self, new_config):
        # double-check -- the master ensures this in config checks
        assert self.impl_type == new_config.mq['type']

        return service.ReconfigurableServiceMixin.reconfigServiceWithBuildbotConfig(self,
                                                                                    new_config)

    def produce(self, routing_key, data):
        # will be patched after configuration to point to the running
        # implementation's method
        raise NotImplementedError

    def startConsuming(self, callback, filter, persistent_name=None):
        # will be patched after configuration to point to the running
        # implementation's method
        raise NotImplementedError
