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
from twisted.python import log
from twisted.python.constants import NamedConstant
from twisted.python.constants import Names


class States(Names):
    # The worker isn't attached, or is in the process of attaching.
    DETACHED = NamedConstant()
    # The worker is available to build: either attached, or a latent worker.
    AVAILABLE = NamedConstant()
    # The worker is building.
    BUILDING = NamedConstant()


class AbstractWorkerForBuilder:

    def __init__(self):
        self.ping_watchers = []
        self.state = None  # set in subclass
        self.worker = None
        self.builder_name = None
        self.locks = None

    def __repr__(self):
        r = ["<", self.__class__.__name__]
        if self.builder_name:
            r.extend([" builder=", repr(self.builder_name)])
        if self.worker:
            r.extend([" worker=", repr(self.worker.workername)])
        r.extend([" state=", self.state.name, ">"])
        return ''.join(r)

    def setBuilder(self, b):
        self.builder = b
        self.builder_name = b.name

    def getWorkerCommandVersion(self, command, oldversion=None):
        if self.remoteCommands is None:
            # the worker is 0.5.0 or earlier
            return oldversion
        return self.remoteCommands.get(command)

    def isAvailable(self):
        # if this WorkerForBuilder is busy, then it's definitely not available
        if self.isBusy():
            return False

        # otherwise, check in with the Worker
        if self.worker:
            return self.worker.canStartBuild()

        # no worker? not very available.
        return False

    def isBusy(self):
        return self.state != States.AVAILABLE

    def buildStarted(self):
        self.state = States.BUILDING
        # AbstractWorker doesn't always have a buildStarted method
        # so only call it if it is available.
        try:
            worker_buildStarted = self.worker.buildStarted
        except AttributeError:
            pass
        else:
            worker_buildStarted(self)

    def buildFinished(self):
        self.state = States.AVAILABLE
        if self.worker:
            self.worker.buildFinished(self)

    @defer.inlineCallbacks
    def attached(self, worker, commands):
        """
        @type  worker: L{buildbot.worker.Worker}
        @param worker: the Worker that represents the worker as a whole
        @type  commands: dict: string -> string, or None
        @param commands: provides the worker's version of each RemoteCommand
        """
        self.remoteCommands = commands  # maps command name to version
        if self.worker is None:
            self.worker = worker
            self.worker.addWorkerForBuilder(self)
        else:
            assert self.worker == worker
        log.msg("Worker {} attached to {}".format(worker.workername, self.builder_name))

        yield self.worker.conn.remotePrint(message="attached")

    def substantiate_if_needed(self, build):
        return defer.succeed(True)

    def insubstantiate_if_needed(self):
        pass

    def ping(self):
        """Ping the worker to make sure it is still there. Returns a Deferred
        that fires with True if it is.
        """
        newping = not self.ping_watchers
        d = defer.Deferred()
        self.ping_watchers.append(d)
        if newping:
            Ping().ping(self.worker.conn).addBoth(self._pong)

        return d

    def abortPingIfAny(self):
        watchers, self.ping_watchers = self.ping_watchers, []
        for d in watchers:
            d.errback(PingException('aborted ping'))

    def _pong(self, res):
        watchers, self.ping_watchers = self.ping_watchers, []
        for d in watchers:
            d.callback(res)

    def detached(self):
        log.msg("Worker {} detached from {}".format(self.worker.workername, self.builder_name))
        if self.worker:
            self.worker.removeWorkerForBuilder(self)
        self.worker = None
        self.remoteCommands = None


class PingException(Exception):
    pass


class Ping:
    running = False

    def ping(self, conn):
        assert not self.running
        if not conn:
            # clearly the ping must fail
            return defer.fail(PingException("Worker not connected?"))
        self.running = True
        log.msg("sending ping")
        self.d = defer.Deferred()
        # TODO: add a distinct 'ping' command on the worker.. using 'print'
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
        # the worker has some sort of internal error, disconnect them. If we
        # don't, we'll requeue a build and ping them again right away,
        # creating a nasty loop.
        conn.loseConnection()
        self.d.errback(res)


class WorkerForBuilder(AbstractWorkerForBuilder):

    def __init__(self):
        super().__init__()
        self.state = States.DETACHED

    @defer.inlineCallbacks
    def attached(self, worker, commands):
        yield super().attached(worker, commands)

        # Only set available on non-latent workers, since latent workers
        # only attach while a build is in progress.
        self.state = States.AVAILABLE

    def detached(self):
        super().detached()
        if self.worker:
            self.worker.removeWorkerForBuilder(self)
        self.worker = None
        self.state = States.DETACHED


class LatentWorkerForBuilder(AbstractWorkerForBuilder):

    def __init__(self, worker, builder):
        super().__init__()
        self.worker = worker
        self.state = States.AVAILABLE
        self.setBuilder(builder)
        self.worker.addWorkerForBuilder(self)
        log.msg("Latent worker {} attached to {}".format(worker.workername, self.builder_name))

    def substantiate_if_needed(self, build):
        self.state = States.DETACHED
        d = self.substantiate(build)
        return d

    def insubstantiate_if_needed(self):
        self.worker.insubstantiate()

    def attached(self, worker, commands):
        # When a latent worker is attached, it is actually because it prepared for a build
        # thus building and not available like for normal worker
        if self.state == States.DETACHED:
            self.state = States.BUILDING
        return super().attached(worker, commands)

    def substantiate(self, build):
        return self.worker.substantiate(self, build)

    def ping(self):
        if not self.worker.substantiated:
            return defer.fail(PingException("worker is not substantiated"))
        return super().ping()
