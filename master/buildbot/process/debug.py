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

from twisted.python import log
from twisted.internet import defer
from twisted.application import service
from buildbot.pbutil import NewCredPerspective
from buildbot.sourcestamp import SourceStamp
from buildbot import interfaces, config
from buildbot.process.properties import Properties

class DebugServices(config.ReconfigurableServiceMixin, service.MultiService):

    def __init__(self, master):
        service.MultiService.__init__(self)
        self.setName('debug_services')
        self.master = master

        self.debug_port = None
        self.debug_password = None
        self.debug_registration = None
        self.manhole = None


    @defer.inlineCallbacks
    def reconfigService(self, new_config):

        # debug client
        config_changed = (self.debug_port != new_config.slavePortnum or
                          self.debug_password != new_config.debugPassword)

        if not new_config.debugPassword or config_changed:
            if self.debug_registration:
                yield self.debug_registration.unregister()
                self.debug_registration = None

        if new_config.debugPassword and config_changed:
            factory = lambda mind, user : DebugPerspective(self.master)
            self.debug_registration = self.master.pbmanager.register(
                    new_config.slavePortnum, "debug", new_config.debugPassword,
                    factory)

        self.debug_password = new_config.debugPassword
        if self.debug_password:
            self.debug_port = new_config.slavePortnum
        else:
            self.debug_port = None

        # manhole
        if new_config.manhole != self.manhole:
            if self.manhole:
                yield defer.maybeDeferred(lambda :
                        self.manhole.disownServiceParent())
                self.manhole.master = None
                self.manhole = None

            if new_config.manhole:
                self.manhole = new_config.manhole
                self.manhole.master = self.master
                self.manhole.setServiceParent(self)

        # chain up
        yield config.ReconfigurableServiceMixin.reconfigService(self,
                                                    new_config)


    @defer.inlineCallbacks
    def stopService(self):
        if self.debug_registration:
            yield self.debug_registration.unregister()
            self.debug_registration = None

        # manhole will get stopped as a sub-service

        yield defer.maybeDeferred(lambda :
                service.MultiService.stopService(self))

        # clean up
        if self.manhole:
            self.manhole.master = None
            self.manhole = None


class DebugPerspective(NewCredPerspective):

    def __init__(self, master):
        self.master = master

    def attached(self, mind):
        return self

    def detached(self, mind):
        pass

    def perspective_requestBuild(self, buildername, reason, branch,
                            revision, properties={}):
        c = interfaces.IControl(self.master)
        bc = c.getBuilder(buildername)
        ss = SourceStamp(branch, revision)
        bpr = Properties()
        bpr.update(properties, "remote requestBuild")
        return bc.submitBuildRequest(ss, reason, bpr)

    def perspective_pingBuilder(self, buildername):
        c = interfaces.IControl(self.master)
        bc = c.getBuilder(buildername)
        bc.ping()

    def perspective_reload(self):
        log.msg("debug client - triggering master reconfig")
        self.master.reconfig()

    def perspective_pokeIRC(self):
        log.msg("saying something on IRC")
        from buildbot.status import words
        for s in self.master:
            if isinstance(s, words.IRC):
                bot = s.f
                for channel in bot.channels:
                    print " channel", channel
                    bot.p.msg(channel, "Ow, quit it")

    def perspective_print(self, msg):
        log.msg("debug %s" % msg)
