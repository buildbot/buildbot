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

from twisted.internet import defer
from twisted.application import service
from buildbot.buildslave.protocols import pb as bbpb, amp as bbamp
from buildbot import config

class BuildslaveRegistration(object):

    __slots__ = [ 'master', 'buildslave' ]

    def __init__(self, master, buildslave):
        self.master = master
        self.buildslave = buildslave

    def __repr__(self):
        return "<%s for %r>" % (self.__class__.__name__, self.slavename)

    @defer.inlineCallbacks
    def unregister(self):
        bs = self.buildslave
        # update with portStr=None to remove any registration in place
        yield self.master.buildslaves.pb.updateRegistration(
            bs.slavename, bs.password, None, None)
        yield self.master.buildslaves._unregister(self)

    @defer.inlineCallbacks
    def update(self, slave_config, global_config):
        # For most protocols, there's nothing to do, but for PB we must
        # update the registration in case the port or password has changed.
        yield self.master.buildslaves.pb.updateRegistration(
                slave_config.slavename, slave_config.password,
                global_config.PBPortnum, # TOOD: use new config
                self.getPerspective)

    def getPerspective(self, mind, slavename):
        return self.buildslave.getPerspective(mind, slavename)


class BuildslaveManager(config.ReconfigurableServiceMixin,
                        service.MultiService):

    name = "buildslaves"

    def __init__(self, master):
        service.MultiService.__init__(self)
        self.setName('buildslaves')
        self.master = master

        self.amp = bbamp.Listener(self.master)
        self.amp.setServiceParent(self)
        self.pb = bbpb.Listener(self.master)
        self.pb.setServiceParent(self)

        # BuildslaveRegistration instances keyed by buildslave name
        self.registrations = {}

    @defer.inlineCallbacks
    def reconfigService(self, new_config):

        # TODO: make buildslaves child services to this object instead of
        # BotMaster, so they no longer need to register

        # reconfig any newly-added change sources, as well as existing
        yield config.ReconfigurableServiceMixin.reconfigService(self,
                                                        new_config)

    def register(self, buildslave):
        # TODO: doc that update must be called, too
        buildslaveName = buildslave.slavename
        reg = BuildslaveRegistration(self.master, buildslave)
        self.registrations[buildslaveName] = reg
        return defer.succeed(reg)

    def _unregister(self, registration):
        del self.registrations[registration.buildslave.slavename]
