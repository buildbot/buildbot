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


from buildbot.util import service


class DebugServices(service.ReconfigurableServiceMixin, service.AsyncMultiService):
    name = 'debug_services'

    def __init__(self):
        super().__init__()

        self.debug_port = None
        self.debug_password = None
        self.debug_registration = None
        self.manhole = None

    async def reconfigServiceWithBuildbotConfig(self, new_config):
        if new_config.manhole != self.manhole:
            if self.manhole:
                await self.manhole.disownServiceParent()
                self.manhole = None

            if new_config.manhole:
                self.manhole = new_config.manhole
                await self.manhole.setServiceParent(self)

        # chain up
        await super().reconfigServiceWithBuildbotConfig(new_config)

    async def stopService(self):
        # manhole will get stopped as a sub-service
        await super().stopService()

        # clean up
        if self.manhole:
            self.manhole = None
