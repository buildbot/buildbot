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

from twisted.spread import pb
from twisted.internet import defer
from twisted.python import log

(ATTACHING, # slave attached, still checking hostinfo/etc
 IDLE, # idle, available for use
 PINGING, # build about to start, making sure it is still alive
 BUILDING, # build is running
 LATENT, # latent slave is not substantiated; similar to idle
 SUBSTANTIATING,
 ) = range(6)

class AbstractSlaveBuilder(pb.Referenceable):
    def __init__(self):
        self.ping_watchers = []
        self.state = None # set in subclass
        self.conn = None
        self.slave = None
        self.builder_name = None
        self.locks = None

    def __repr__(self):
        r = ["<", self.__class__.__name__]
        if self.builder_name:
            r.extend([" builder=", repr(self.builder_name)])
        if self.slave:
            r.extend([" slave=", repr(self.slave.slavename)])
        r.append(">")
        return ''.join(r)

    def setBuilder(self, b):
        self.builder = b
        self.builder_name = b.name

    def getSlaveCommandVersion(self, command, oldversion=None):
        if self.remoteCommands is None:
            # the slave is 0.5.0 or earlier
            return oldversion
        return self.remoteCommands.get(command)

    def isAvailable(self):
        # if this SlaveBuilder is busy, then it's definitely not available
        if self.isBusy():
            return False

        # otherwise, check in with the BuildSlave
        if self.slave:
            return self.slave.canStartBuild()

        # no slave? not very available.
        return False

    def isBusy(self):
        return self.state not in (IDLE, LATENT)

    def buildStarted(self):
        self.state = BUILDING

    def buildFinished(self):
        self.state = IDLE
        if self.slave:
            self.slave.buildFinished(self)

    def attached(self, slave, commands):
        """
        @type  slave: L{buildbot.buildslave.BuildSlave}
        @param slave: the BuildSlave that represents the buildslave as a
                      whole
        @type  commands: dict: string -> string, or None
        @param commands: provides the slave's version of each RemoteCommand
        """
        self.state = ATTACHING
        self.conn = slave.conn
        self.remoteCommands = commands # maps command name to version
        if self.slave is None:
            self.slave = slave
            self.slave.addSlaveBuilder(self)
        else:
            assert self.slave == slave
        log.msg("Buildslave %s attached to %s" % (slave.slavename,
                                                  self.builder_name))
        d = defer.succeed(None)

        d.addCallback(lambda _:
            self.conn.remotePrint(message="attached"))

        def setIdle(res):
            self.state = IDLE
            return self
        d.addCallback(setIdle)

        return d

    def prepare(self, builder_status, build):
        if not self.slave.acquireLocks():
            return defer.succeed(False)
        return defer.succeed(True)

    def ping(self, status=None):
        """Ping the slave to make sure it is still there. Returns a Deferred
        that fires with True if it is.

        @param status: if you point this at a BuilderStatus, a 'pinging'
                       event will be pushed.
        """
        oldstate = self.state
        self.state = PINGING
        newping = not self.ping_watchers
        d = defer.Deferred()
        self.ping_watchers.append(d)
        if newping:
            if status:
                event = status.addEvent(["pinging"])
                d2 = defer.Deferred()
                d2.addCallback(self._pong_status, event)
                self.ping_watchers.insert(0, d2)
                # I think it will make the tests run smoother if the status
                # is updated before the ping completes
            Ping().ping(self.conn).addCallback(self._pong)

        def reset_state(res):
            if self.state == PINGING:
                self.state = oldstate
            return res
        d.addCallback(reset_state)
        return d

    def _pong(self, res):
        watchers, self.ping_watchers = self.ping_watchers, []
        for d in watchers:
            d.callback(res)

    def _pong_status(self, res, event):
        if res:
            event.text = ["ping", "success"]
        else:
            event.text = ["ping", "failed"]
        event.finish()

    def detached(self):
        log.msg("Buildslave %s detached from %s" % (self.slave.slavename,
                                                    self.builder_name))
        if self.slave:
            self.slave.removeSlaveBuilder(self)
        self.slave = None
        self.conn = None
        self.remoteCommands = None


class Ping:
    running = False

    def ping(self, conn):
        assert not self.running
        if not conn:
            # clearly the ping must fail
            return defer.succeed(False)
        self.running = True
        log.msg("sending ping")
        self.d = defer.Deferred()
        # TODO: add a distinct 'ping' command on the slave.. using 'print'
        # for this purpose is kind of silly.
        conn.remotePrint(message="ping").addCallbacks(self._pong,
                                                        self._ping_failed,
                                                        errbackArgs=(conn,))
        return self.d

    def _pong(self, res):
        log.msg("ping finished: success")
        self.d.callback(True)

    def _ping_failed(self, res, conn):
        log.msg("ping finished: failure")
        # the slave has some sort of internal error, disconnect them. If we
        # don't, we'll requeue a build and ping them again right away,
        # creating a nasty loop.
        conn.loseConnection()
        self.d.callback(False)


class SlaveBuilder(AbstractSlaveBuilder):

    def __init__(self):
        AbstractSlaveBuilder.__init__(self)
        self.state = ATTACHING

    def detached(self):
        AbstractSlaveBuilder.detached(self)
        if self.slave:
            self.slave.removeSlaveBuilder(self)
        self.slave = None
        self.state = ATTACHING

class LatentSlaveBuilder(AbstractSlaveBuilder):
    def __init__(self, slave, builder):
        AbstractSlaveBuilder.__init__(self)
        self.slave = slave
        self.state = LATENT
        self.setBuilder(builder)
        self.slave.addSlaveBuilder(self)
        log.msg("Latent buildslave %s attached to %s" % (slave.slavename,
                                                         self.builder_name))

    def prepare(self, builder_status, build):
        # If we can't lock, then don't bother trying to substantiate
        if not self.slave or not self.slave.acquireLocks():
            return defer.succeed(False)

        log.msg("substantiating slave %s" % (self,))
        d = self.substantiate(build)
        def substantiation_failed(f):
            builder_status.addPointEvent(['removing', 'latent',
                                          self.slave.slavename])
            self.slave.disconnect()
            # TODO: should failover to a new Build
            return f
        def substantiation_cancelled(res):
            # if res is False, latent slave cancelled subtantiation
            if not res:
                self.state = LATENT
            return res
        d.addCallback(substantiation_cancelled)
        d.addErrback(substantiation_failed)
        return d

    def substantiate(self, build):
        self.state = SUBSTANTIATING
        d = self.slave.substantiate(self, build)
        if not self.slave.substantiated:
            event = self.builder.builder_status.addEvent(
                ["substantiating"])
            def substantiated(res):
                msg = ["substantiate", "success"]
                if isinstance(res, basestring):
                    msg.append(res)
                elif isinstance(res, (tuple, list)):
                    msg.extend(res)
                event.text = msg
                event.finish()
                return res
            def substantiation_failed(res):
                event.text = ["substantiate", "failed"]
                # TODO add log of traceback to event
                event.finish()
                return res
            d.addCallbacks(substantiated, substantiation_failed)
        return d

    def detached(self):
        AbstractSlaveBuilder.detached(self)
        self.state = LATENT

    def buildStarted(self):
        AbstractSlaveBuilder.buildStarted(self)
        self.slave.buildStarted(self)

    def _attachFailure(self, why, where):
        self.state = LATENT
        return AbstractSlaveBuilder._attachFailure(self, why, where)

    def ping(self, status=None):
        if not self.slave.substantiated:
            if status:
                status.addEvent(["ping", "latent"]).finish()
            return defer.succeed(True)
        return AbstractSlaveBuilder.ping(self, status)



