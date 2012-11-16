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

from buildbot import config
from twisted.application import service
from twisted.python.reflect import namedObject

class MQConnector(config.ReconfigurableServiceMixin, service.MultiService):

    classes = {
        'simple' : {
            'class' : "buildbot.mq.simple.SimpleMQ",
            'keys' : set(['debug']),
        },
    }

    def __init__(self, master):
        service.MultiService.__init__(self)
        self.setName('mq')
        self.master = master
        self.impl = None # set in setup
        self.impl_type = None # set in setup

    def setup(self):
        assert not self.impl

        # imports are done locally so that we don't try to import
        # implementation-specific modules unless they're required.
        typ = self.master.config.mq['type']
        assert typ in self.classes # this is checked by MasterConfig
        self.impl_type = typ
        cls = namedObject(self.classes[typ]['class'])
        self.impl = cls(self.master)

        # set up the impl as a child service
        self.impl.setServiceParent(self)

        # configure it (early)
        self.impl.reconfigService(self.master.config)

        # copy the methods onto this object for ease of access
        self.produce = self.impl.produce
        self.startConsuming = self.impl.startConsuming

    def reconfigService(self, new_config):
        # double-check -- the master ensures this in config checks
        assert self.impl_type == new_config.mq['type']

        return config.ReconfigurableServiceMixin.reconfigService(self,
                                                            new_config)

    def produce(self, routing_key, data):
        # will be patched after configuration to point to the running
        # implementation's method
        raise NotImplementedError

    def startConsuming(self, callback, filter, persistent_name=None):
        # will be patched after configuration to point to the running
        # implementation's method
        raise NotImplementedError
