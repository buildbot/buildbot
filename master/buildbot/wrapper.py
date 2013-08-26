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
# Portions Copyright Buildbot Team Members
# Portions Copyright Canonical Ltd. 2009

from twisted.application import service
from twisted.python import log
from twisted.internet import defer

from buildbot import config


class Wrapper(service.MultiService):

    def __init__(self, master):
        service.MultiService.__init__(self)
        self.master = master
        self.ampManager = master.ampManager
        self.pbmanager = master.pbmanager

    @defer.inlineCallbacks
    def maybeUpdateRegistration(self, bs, new_bs, config):
        """
        Check slave connection status. Might disconnect and re-register slave
        if necessary

        @param bs: buildbot.buildslave.base.BuildSlave instance
        @param new_bs: buildbot.buildslave.base.BuildSlave instance
        @param config: buildbot.config.MasterConfig instance
        """
        def portChanged():
            if bs.proto == "AMP":
                return True if bs.registered_port != config.AMPPortnum else False
            if bs.proto == "PB":
                return True if bs.registered_port != config.PBPortnum else False

        def protoChanged():
            return True if bs.proto != new_bs.proto else False

        # do we need to re-register?
        if (not bs.registration or bs.password != new_bs.password or portChanged()
            or protoChanged()):
            # remove old registration if exists
            if bs.registration:
                yield bs.registration.unregister()
                bs.registration = None
            bs.password = new_bs.password
            # Update port
            if new_bs.proto == "AMP":
                bs.registered_port = config.AMPPortnum
            elif new_bs.proto == "PB":
                bs.registered_port = config.PBPortnum
            # Register slave accordance with its protocol
            if new_bs.proto == "AMP":
                bs.registration = self.ampManager.register(
                        bs.registered_port, bs.slavename,
                        bs.password, bs.getPerspective)
            elif new_bs.proto == "PB":
                bs.registration = self.pbmanager.register(
                        bs.registered_port, bs.slavename,
                        bs.password, bs.getPerspective)
