
import time
from twisted.python import log
from twisted.internet import defer, reactor

from buildbot.pbutil import NewCredPerspective
from buildbot.status.builder import SlaveStatus

class BuildSlave(NewCredPerspective):
    """This is the master-side representative for a remote buildbot slave.
    There is exactly one for each slave described in the config file (the
    c['slaves'] list). When buildbots connect in (.attach), they get a
    reference to this instance. The BotMaster object is stashed as the
    .service attribute.

    I represent a build slave -- a remote machine capable of
    running builds.  I am instantiated by the configuration file, and can be
    subclassed to add extra functionality."""

    def __init__(self, name, password, max_builds=None):
        """
        @param name: botname this machine will supply when it connects
        @param password: password this machine will supply when
                         it connects
        @param max_builds: maximum number of simultaneous builds that will
                           be run concurrently on this buildslave (the
                           default is None for no limit)
        """

        self.slavename = name
        self.password = password
        self.botmaster = None # no buildmaster yet
        self.slave_status = SlaveStatus(name)
        self.slave = None # a RemoteReference to the Bot, when connected
        self.slave_commands = None
        self.slavebuilders = []
        self.max_builds = max_builds
        self.lastMessageReceived = 0

    def update(self, new):
        """
        Given a new BuildSlave, configure this one identically.  Because
        BuildSlave objects are remotely referenced, we can't replace them
        without disconnecting the slave, yet there's no reason to do that.
        """
        # the reconfiguration logic should guarantee this:
        assert self.slavename == new.slavename
        assert self.password == new.password
        assert self.__class__ == new.__class__
        self.max_builds = new.max_builds

    def __repr__(self):
        builders = self.botmaster.getBuildersForSlave(self.slavename)
        return "<BuildSlave '%s', current builders: %s>" % \
               (self.slavename, ','.join(map(lambda b: b.name, builders)))

    def setBotmaster(self, botmaster):
        assert not self.botmaster, "BuildSlave already has a botmaster"
        self.botmaster = botmaster

    def updateSlave(self):
        """Called to add or remove builders after the slave has connected.

        @return: a Deferred that indicates when an attached slave has
        accepted the new builders and/or released the old ones."""
        if self.slave:
            return self.sendBuilderList()
        return defer.succeed(None)

    def attached(self, bot):
        """This is called when the slave connects.

        @return: a Deferred that fires with a suitable pb.IPerspective to
                 give to the slave (i.e. 'self')"""

        if self.slave:
            # uh-oh, we've got a duplicate slave. The most likely
            # explanation is that the slave is behind a slow link, thinks we
            # went away, and has attempted to reconnect, so we've got two
            # "connections" from the same slave, but the previous one is
            # stale. Give the new one precedence.
            log.msg("duplicate slave %s replacing old one" % self.slavename)

            # just in case we've got two identically-configured slaves,
            # report the IP addresses of both so someone can resolve the
            # squabble
            tport = self.slave.broker.transport
            log.msg("old slave was connected from", tport.getPeer())
            log.msg("new slave is from", bot.broker.transport.getPeer())
            d = self.disconnect()
        else:
            d = defer.succeed(None)
        # now we go through a sequence of calls, gathering information, then
        # tell the Botmaster that it can finally give this slave to all the
        # Builders that care about it.

        # we accumulate slave information in this 'state' dictionary, then
        # set it atomically if we make it far enough through the process
        state = {}

        def _log_attachment_on_slave(res):
            d1 = bot.callRemote("print", "attached")
            d1.addErrback(lambda why: None)
            return d1
        d.addCallback(_log_attachment_on_slave)

        def _get_info(res):
            d1 = bot.callRemote("getSlaveInfo")
            def _got_info(info):
                log.msg("Got slaveinfo from '%s'" % self.slavename)
                # TODO: info{} might have other keys
                state["admin"] = info.get("admin")
                state["host"] = info.get("host")
            def _info_unavailable(why):
                # maybe an old slave, doesn't implement remote_getSlaveInfo
                log.msg("BuildSlave.info_unavailable")
                log.err(why)
            d1.addCallbacks(_got_info, _info_unavailable)
            return d1
        d.addCallback(_get_info)

        def _get_commands(res):
            d1 = bot.callRemote("getCommands")
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

        def _accept_slave(res):
            self.slave_status.setAdmin(state.get("admin"))
            self.slave_status.setHost(state.get("host"))
            self.slave_status.setConnected(True)
            self.slave_commands = state.get("slave_commands")
            self.slave = bot
            log.msg("bot attached")
            self.messageReceivedFromSlave()
            return self.updateSlave()
        d.addCallback(_accept_slave)

        # Finally, the slave gets a reference to this BuildSlave. They
        # receive this later, after we've started using them.
        d.addCallback(lambda res: self)
        return d

    def messageReceivedFromSlave(self):
        now = time.time()
        self.lastMessageReceived = now

    def detached(self, mind):
        self.slave = None
        self.slave_status.setConnected(False)
        self.botmaster.slaveLost(self)
        log.msg("BuildSlave.detached(%s)" % self.slavename)


    def disconnect(self):
        """Forcibly disconnect the slave.

        This severs the TCP connection and returns a Deferred that will fire
        (with None) when the connection is probably gone.

        If the slave is still alive, they will probably try to reconnect
        again in a moment.

        This is called in two circumstances. The first is when a slave is
        removed from the config file. In this case, when they try to
        reconnect, they will be rejected as an unknown slave. The second is
        when we wind up with two connections for the same slave, in which
        case we disconnect the older connection.
        """

        if not self.slave:
            return defer.succeed(None)
        log.msg("disconnecting old slave %s now" % self.slavename)

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
            pass
        except:
            # however, these hacks are pretty internal, so don't blow up if
            # they fail or are unavailable
            log.msg("failed to accelerate the shutdown process")
            pass
        log.msg("waiting for slave to finish disconnecting")

        # When this Deferred fires, we'll be ready to accept the new slave
        return d

    def sendBuilderList(self):
        our_builders = self.botmaster.getBuildersForSlave(self.slavename)
        blist = [(b.name, b.builddir) for b in our_builders]
        d = self.slave.callRemote("setBuilderList", blist)
        def _sent(slist):
            dl = []
            for name, remote in slist.items():
                # use get() since we might have changed our mind since then
                b = self.botmaster.builders.get(name)
                if b:
                    d1 = b.attached(self, remote, self.slave_commands)
                    dl.append(d1)
            return defer.DeferredList(dl)
        def _set_failed(why):
            log.msg("BuildSlave.sendBuilderList (%s) failed" % self)
            log.err(why)
            # TODO: hang up on them?, without setBuilderList we can't use
            # them
        d.addCallbacks(_sent, _set_failed)
        return d

    def perspective_keepalive(self):
        pass

    def addSlaveBuilder(self, sb):
        log.msg("%s adding %s" % (self, sb))
        self.slavebuilders.append(sb)

    def removeSlaveBuilder(self, sb):
        log.msg("%s removing %s" % (self, sb))
        if sb in self.slavebuilders:
            self.slavebuilders.remove(sb)

    def canStartBuild(self):
        """
        I am called when a build is requested to see if this buildslave
        can start a build.  This function can be used to limit overall
        concurrency on the buildslave.
        """
        if self.max_builds:
            active_builders = [sb for sb in self.slavebuilders if sb.isBusy()]
            if len(active_builders) >= self.max_builds:
                return False
        return True

