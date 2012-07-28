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

from zope.interface import implements

from twisted.spread import pb
from twisted.python import log
from twisted.internet import reactor, defer

from buildbot.process import metrics, botmaster
from buildbot.interfaces import IMasterProtocol

class PBSlaveProto(pb.Avatar):
    implements(IMasterProtocol)
    keepalive_timer = None
    keepalive_interval = None


    def __init__(self, buildslave, name, password, missing_timeout=3600,
                 keepalive_interval=3600):

        self.slavename = name
        self.password = password

        self.registration = None
        self.registered_port = None

        self.bot = None
        self.slave = None # a RemoteReference to the accepted Bot, when connected

        self.buildslave= buildslave# a local reference to BuildSlave

        self.missing_timeout = missing_timeout
        self.missing_timer = None

        self.keepalive_interval = keepalive_interval

    def setBuilderList(self, builders):
        """
        set BuilderList for a BuildSlave
        """
        return self.slave.callRemote("setBuilderList", builders)

    def startBuild(self, builder, args):
        """
        start Build on a SlaveBuilder
        """
        pass

    def getSlaveStatus(self):
        """
        send SlaveStatus to Master
        """

        # This is not used at the moment.
        pass

    def getSlaveInfo(self):
        """
        send SlaveInfo to Master on request
        """

        # we accumulate slave information in this 'state' dictionary, then
        # set it atomically if we make it far enough through the process
        state = {}

        d = defer.succeed(None)

        def _get_info(res):
            d1 = self.bot.callRemote("getSlaveInfo")
            def _got_info(info):
                log.msg("Got slaveinfo from '%s'" % self.slavename)
                # TODO: info{} might have other keys
                state["admin"] = info.get("admin")
                state["host"] = info.get("host")
                state["access_uri"] = info.get("access_uri", None)
                state["slave_environ"] = info.get("environ", {})
                state["slave_basedir"] = info.get("basedir", None)
                state["slave_system"] = info.get("system", None)
            def _info_unavailable(why):
                why.trap(pb.NoSuchMethod)
                # maybe an old slave, doesn't implement remote_getSlaveInfo
                log.msg("BuildSlave.info_unavailable")
                log.err(why)
            d1.addCallbacks(_got_info, _info_unavailable)
            return d1
        d.addCallback(_get_info)
        self.startKeepaliveTimer()

        def _get_version(res):
            d = self.bot.callRemote("getVersion")
            def _got_version(version):
                state["version"] = version
            def _version_unavailable(why):
                why.trap(pb.NoSuchMethod)
                # probably an old slave
                state["version"] = '(unknown)'
            d.addCallbacks(_got_version, _version_unavailable)
            return d
        d.addCallback(_get_version)

        def _get_commands(res):
            d1 = self.bot.callRemote("getCommands")
            def _got_commands(commands):
                state["slave_commands"] = commands
            def _commands_unavailable(why):
                # probably an old slave
                log.msg("BuildSlave._commands_unavailable")
                if why.check(AttributeError):
                    return
                log.err(why)
            d1.addCallbacks(_got_commands, _commands_unavailable)
            return d1
        d.addCallback(_get_commands)
        d.addCallback(lambda _: state)

        return d

    def startCommand(self, builder, args):
        """
        start a command on a SlaveBuilder
        """
        pass

    def interruptCommmand(self, builder, args):
        """
        interrupt a command on a SlaveBuilder
        """
        pass

    @defer.inlineCallbacks
    def shutdown(self):
        """
        shutdown slave
        """

        if not self.bot:
            log.msg("no remote; slave is already shut down")
            return

        # First, try the "new" way - calling our own remote's shutdown
        # method.  The method was only added in 0.8.3, so ignore NoSuchMethod
        # failures.

        def new_way():
            d = self.slave.callRemote('shutdown')
            d.addCallback(lambda _ : True) # successful shutdown request
            def check_nsm(f):
                f.trap(pb.NoSuchMethod)
                return False # fall through to the old way
            d.addErrback(check_nsm)
            def check_connlost(f):
                f.trap(pb.PBConnectionLost)
                return True # the slave is gone, so call it finished
            d.addErrback(check_connlost)
            return d

        if (yield new_way()):
            return # done!

        def old_way():
            d = None
            for b in self.slavebuilders.values():
                if b.remote:
                    d = b.remote.callRemote("shutdown")
                    break

            if d:
                log.msg("Shutting down (old) slave: %s" % self.slavename)
                # The remote shutdown call will not complete successfully since the
                # buildbot process exits almost immediately after getting the
                # shutdown request.
                # Here we look at the reason why the remote call failed, and if
                # it's because the connection was lost, that means the slave
                # shutdown as expected.
                def _errback(why):
                    if why.check(pb.PBConnectionLost):
                        log.msg("Lost connection to %s" % self.slavename)
                    else:
                        log.err("Unexpected error when trying to shutdown %s" % self.slavename)
                d.addErrback(_errback)
                return d
            log.err("Couldn't find remote builder to shut down slave")
            return defer.succeed(None)
        yield old_way()


    def sendMessage(self, message):
        """
        Sending a message to be printed to the slave. Also use for sending keepalives.
        """
        d = self.bot.callRemote("print", message)
        return d

    def getPerspective(self, mind, slavename):
        assert slavename == self.slavename
        metrics.MetricCountEvent.log("attached_slaves", 1)

        # record when this connection attempt occurred
        if self.buildslave.slave_status:
            self.buildslave.slave_status.recordConnectTime()

        if self.isConnected():
            # duplicate slave - send it to arbitration
            arb = botmaster.DuplicateSlaveArbitrator(self)
            return arb.getPerspective(mind, slavename)
        else:
            log.msg("slave '%s' attaching from %s" % (slavename, mind.broker.transport.getPeer()))
            return self

    def attached(self, bot):
        self.bot = bot

        # Log attachment on slave
        d = self.bot.callRemote("print", "attached")
        d.addErrback(lambda why: None)
        def _getSlaveInfo(res):
            return self.getSlaveInfo()
        d.addCallback(_getSlaveInfo)
        d.addCallback(self.buildslave.attached)
        return d

    def acceptSlave(self):
        self.slave = self.bot

    def detached(self, mind):
        self.bot = self.slave = None
        self.buildslave.detached()
        self.stopKeepaliveTimer()

    # TODO: Use SlaveStatus for this.
    def isConnected(self):
        return self.slave

    def _disconnect(self):
        # all kinds of teardown will happen as a result of
        # loseConnection(), but it happens after a reactor iteration or
        # two. Hook the actual disconnect so we can know when it is safe
        # to connect the new slave. We have to wait one additional
        # iteration (with callLater(0)) to make sure the *other*
        # notifyOnDisconnect handlers have had a chance to run.
        d = defer.Deferred()

        # notifyOnDisconnect runs the callback with one argument, the
        # RemoteReference being disconnected.
        def _disconnected(rref):
            reactor.callLater(0, d.callback, None)
        self.slave.notifyOnDisconnect(_disconnected)
        tport = self.slave.broker.transport
        # this is the polite way to request that a socket be closed
        tport.loseConnection()
        try:
            # but really we don't want to wait for the transmit queue to
            # drain. The remote end is unlikely to ACK the data, so we'd
            # probably have to wait for a (20-minute) TCP timeout.
            #tport._closeSocket()
            # however, doing _closeSocket (whether before or after
            # loseConnection) somehow prevents the notifyOnDisconnect
            # handlers from being run. Bummer.
            tport.offset = 0
            tport.dataBuffer = ""
        except:
            # however, these hacks are pretty internal, so don't blow up if
            # they fail or are unavailable
            log.msg("failed to accelerate the shutdown process")
        log.msg("waiting for slave to finish disconnecting")

        return d


    def perspective_keepalive(self):
        self.buildslave.messageReceivedFromSlave()

    def perspective_shutdown(self):
        log.msg("slave %s wants to shut down" % self.slavename)
        self.buildslave.slave_status.setGraceful(True)

    def register(self, new, new_config, master):
        # replace old variables of AbstractBuildSlave to those of slaveproto.pb
        if (not self.registration or
            self.password != new.password or
            new_config.slavePortnum != self.registered_port):
            if self.registration:
                self.registration.unregister()
            self.password = new.password
            self.registered_port = new_config.slavePortnum
            self.registration = master.pbmanager.register(
                    self.registered_port, self.slavename,
                    self.password, self.getPerspective)
            return self.registration

    def doKeepalive(self):
        self.keepalive_timer = reactor.callLater(self.keepalive_interval,
                                                self.doKeepalive)
        if not self.bot:
            return
        d = self.sendMessage("Received keepalive from master")
        d.addErrback(log.msg, "Keepalive failed for '%s'" % (self.slavename, ))

    def stopKeepaliveTimer(self):
        if self.keepalive_timer:
            self.keepalive_timer.cancel()

    def startKeepaliveTimer(self):
        assert self.keepalive_interval
        log.msg("Starting buildslave keepalive timer for '%s'" % \
                                        (self.slavename, ))
        self.doKeepalive()
