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
from buildbot.util import service
from twisted.internet import defer


class DebugServices(config.ReconfigurableServiceMixin, service.AsyncMultiService):

    def __init__(self, master):
        service.AsyncMultiService.__init__(self)
        self.setName('debug_services')
        self.master = master

        self.debug_port = None
        self.debug_password = None
        self.debug_registration = None
        self.manhole = None

    @defer.inlineCallbacks
    def reconfigService(self, new_config):
        if new_config.manhole != self.manhole:
            if self.manhole:
                yield self.manhole.disownServiceParent()
                self.manhole.master = None
                self.manhole = None

            if new_config.manhole:
                self.manhole = new_config.manhole
                self.manhole.master = self.master
                yield self.manhole.setServiceParent(self)

        # chain up
        yield config.ReconfigurableServiceMixin.reconfigService(self,
                                                                new_config)

    @defer.inlineCallbacks
    def stopService(self):
        # manhole will get stopped as a sub-service
        yield service.AsyncMultiService.stopService(self)

        # clean up
        if self.manhole:
            self.manhole.master = None
            self.manhole = None
