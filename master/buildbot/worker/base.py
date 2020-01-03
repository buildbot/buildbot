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

import time

from twisted.internet import defer
from twisted.python import log
from twisted.python.reflect import namedModule
from zope.interface import implementer

from buildbot import config
from buildbot.interfaces import IWorker
from buildbot.process import metrics
from buildbot.process.properties import Properties
from buildbot.status.worker import WorkerStatus
from buildbot.util import Notifier
from buildbot.util import bytes2unicode
from buildbot.util import service
from buildbot.util.eventual import eventually


@implementer(IWorker)
class AbstractWorker(service.BuildbotService):

    """This is the master-side representative for a remote buildbot worker.
    There is exactly one for each worker described in the config file (the
    c['workers'] list). When buildbots connect in (.attach), they get a
    reference to this instance. The BotMaster object is stashed as the
    .botmaster attribute. The BotMaster is also our '.parent' Service.

    I represent a worker -- a remote machine capable of
    running builds.  I am instantiated by the configuration file, and can be
    subclassed to add extra functionality."""

    # reconfig workers after builders
    reconfig_priority = 64

    quarantine_timer = None
    quarantine_timeout = quarantine_initial_timeout = 10
    quarantine_max_timeout = 60 * 60
    start_missing_on_startup = True
    DEFAULT_MISSING_TIMEOUT = 3600
    DEFAULT_KEEPALIVE_INTERVAL = 3600

    # override to True if isCompatibleWithBuild may return False
    builds_may_be_incompatible = False

    def checkConfig(self, name, password, max_builds=None,
                    notify_on_missing=None,
                    missing_timeout=None,
                    properties=None, defaultProperties=None,
                    locks=None,
                    keepalive_interval=DEFAULT_KEEPALIVE_INTERVAL,
                    machine_name=None):
        """
        @param name: botname this machine will supply when it connects
        @param password: password this machine will supply when
                         it connects
        @param max_builds: maximum number of simultaneous builds that will
                           be run concurrently on this worker (the
                           default is None for no limit)
        @param properties: properties that will be applied to builds run on
                           this worker
        @type properties: dictionary
        @param defaultProperties: properties that will be applied to builds
                                  run on this worker only if the property
                                  has not been set by another source
        @type defaultProperties: dictionary
        @param locks: A list of locks that must be acquired before this worker
                      can be used
        @type locks: dictionary
        @param machine_name: The name of the machine to associate with the
                             worker.
        """
        self.name = name = bytes2unicode(name)
        self.machine_name = machine_name

        self.password = password

        # protocol registration
        self.registration = None

        self._graceful = False
        self._paused = False

        # these are set when the service is started
        self.manager = None
        self.workerid = None

        self.worker_status = WorkerStatus(name)
        self.worker_commands = None
        self.workerforbuilders = {}
        self.max_builds = max_builds
        self.access = []
        if locks:
            self.access = locks
        self.lock_subscriptions = []

        self.properties = Properties()
        self.properties.update(properties or {}, "Worker")
        self.properties.setProperty("workername", name, "Worker")
        self.defaultProperties = Properties()
        self.defaultProperties.update(defaultProperties or {}, "Worker")

        if self.machine_name is not None:
            self.properties.setProperty('machine_name', self.machine_name,
                                        'Worker')
        self.machine = None

        self.lastMessageReceived = 0

        if notify_on_missing is None:
            notify_on_missing = []
        if isinstance(notify_on_missing, str):
            notify_on_missing = [notify_on_missing]
        self.notify_on_missing = notify_on_missing
        for i in notify_on_missing:
            if not isinstance(i, str):
                config.error(
                    'notify_on_missing arg %r is not a string' % (i,))

        self.missing_timeout = missing_timeout
        self.missing_timer = None

        # a protocol connection, if we're currently connected
        self.conn = None

        # during disconnection self.conn will be set to None before all disconnection notifications
        # are delivered. During that period _pending_disconnection_delivery_notifier will be set to a
        # notifier and allows interested users to wait until all disconnection notifications are
        # delivered.
        self._pending_disconnection_delivery_notifier = None

        self._old_builder_list = None
        self._configured_builderid_list = None

    def __repr__(self):
        return "<%s %r>" % (self.__class__.__name__, self.name)

    @property
    def workername(self):
        # workername is now an alias to twisted.Service's name
        return self.name

    @property
    def botmaster(self):
        if self.master is None:
            return None
        return self.master.botmaster

    @defer.inlineCallbacks
    def updateLocks(self):
        """Convert the L{LockAccess} objects in C{self.locks} into real lock
        objects, while also maintaining the subscriptions to lock releases."""
        # unsubscribe from any old locks
        for s in self.lock_subscriptions:
            s.unsubscribe()

        # convert locks into their real form
        locks = yield self.botmaster.getLockFromLockAccesses(self.access, self.config_version)

        self.locks = [(l.getLockForWorker(self.workername), la)
                      for l, la in locks]
        self.lock_subscriptions = [l.subscribeToReleases(self._lockReleased)
                                   for l, la in self.locks]

    def locksAvailable(self):
        """
        I am called to see if all the locks I depend on are available,
        in which I return True, otherwise I return False
        """
        if not self.locks:
            return True
        for lock, access in self.locks:
            if not lock.isAvailable(self, access):
                return False
        return True

    def acquireLocks(self):
        """
        I am called when a build is preparing to run. I try to claim all
        the locks that are needed for a build to happen. If I can't, then
        my caller should give up the build and try to get another worker
        to look at it.
        """
        log.msg("acquireLocks(worker %s, locks %s)" % (self, self.locks))
        if not self.locksAvailable():
            log.msg("worker %s can't lock, giving up" % (self, ))
            return False
        # all locks are available, claim them all
        for lock, access in self.locks:
            lock.claim(self, access)
        return True

    def releaseLocks(self):
        """
        I am called to release any locks after a build has finished
        """
        log.msg("releaseLocks(%s): %s" % (self, self.locks))
        for lock, access in self.locks:
            lock.release(self, access)

    def _lockReleased(self):
        """One of the locks for this worker was released; try scheduling
        builds."""
        if not self.botmaster:
            return  # oh well..
        self.botmaster.maybeStartBuildsForWorker(self.name)

    def _applyWorkerInfo(self, info):
        if not info:
            return

        self.worker_status.setAdmin(info.get("admin"))
        self.worker_status.setHost(info.get("host"))
        self.worker_status.setAccessURI(info.get("access_uri", None))
        self.worker_status.setVersion(info.get("version", "(unknown)"))

        # store everything as Properties
        for k, v in info.items():
            if k in ('environ', 'worker_commands'):
                continue
            self.worker_status.info.setProperty(k, v, "Worker")

    @defer.inlineCallbacks
    def _getWorkerInfo(self):
        worker = yield self.master.data.get(
            ('workers', self.workerid))
        self._applyWorkerInfo(worker['workerinfo'])

    def setServiceParent(self, parent):
        # botmaster needs to set before setServiceParent which calls
        # startService

        self.manager = parent
        return super().setServiceParent(parent)

    @defer.inlineCallbacks
    def startService(self):
        # tracks config version for locks
        self.config_version = self.master.config_version

        self.updateLocks()
        self.workerid = yield self.master.data.updates.findWorkerId(
            self.name)

        self.workerActionConsumer = yield self.master.mq.startConsuming(self.controlWorker,
                                                                        ("control", "worker",
                                                                        str(self.workerid),
                                                                        None))

        yield self._getWorkerInfo()
        yield super().startService()

        # startMissingTimer wants the service to be running to really start
        if self.start_missing_on_startup:
            self.startMissingTimer()

    @defer.inlineCallbacks
    def reconfigService(self, name, password, max_builds=None,
                        notify_on_missing=None, missing_timeout=DEFAULT_MISSING_TIMEOUT,
                        properties=None, defaultProperties=None,
                        locks=None,
                        keepalive_interval=DEFAULT_KEEPALIVE_INTERVAL,
                        machine_name=None):
        # Given a Worker config arguments, configure this one identically.
        # Because Worker objects are remotely referenced, we can't replace them
        # without disconnecting the worker, yet there's no reason to do that.

        assert self.name == name
        self.password = password

        # adopt new instance's configuration parameters
        self.max_builds = max_builds
        self.access = []
        if locks:
            self.access = locks
        if notify_on_missing is None:
            notify_on_missing = []
        if isinstance(notify_on_missing, str):
            notify_on_missing = [notify_on_missing]
        self.notify_on_missing = notify_on_missing

        if self.missing_timeout != missing_timeout:
            running_missing_timer = self.missing_timer
            self.stopMissingTimer()
            self.missing_timeout = missing_timeout
            if running_missing_timer:
                self.startMissingTimer()

        self.properties = Properties()
        self.properties.update(properties or {}, "Worker")
        self.properties.setProperty("workername", name, "Worker")
        self.defaultProperties = Properties()
        self.defaultProperties.update(defaultProperties or {}, "Worker")

        # Note that before first reconfig self.machine will always be None and
        # out of sync with self.machine_name, thus more complex logic is needed.
        if self.machine is not None and self.machine_name != machine_name:
            self.machine.unregisterWorker(self)
            self.machine = None

        self.machine_name = machine_name
        if self.machine is None and self.machine_name is not None:
            self.machine = self.master.machine_manager.getMachineByName(self.machine_name)
            if self.machine is not None:
                self.machine.registerWorker(self)
                self.properties.setProperty("machine_name", self.machine_name,
                                            "Worker")
            else:
                log.err("Unknown machine '{}' for worker '{}'".format(
                    self.machine_name, self.name))

        # update our records with the worker manager
        if not self.registration:
            self.registration = yield self.master.workers.register(self)
        yield self.registration.update(self, self.master.config)

        # tracks config version for locks
        self.config_version = self.master.config_version
        self.updateLocks()

    @defer.inlineCallbacks
    def reconfigServiceWithSibling(self, sibling):
        # reconfigServiceWithSibling will only reconfigure the worker when it is configured differently.
        # However, the worker configuration depends on which builder it is configured
        yield super().reconfigServiceWithSibling(sibling)

        # update the attached worker's notion of which builders are attached.
        # This assumes that the relevant builders have already been configured,
        # which is why the reconfig_priority is set low in this class.
        bids = [
            b.getBuilderId() for b in self.botmaster.getBuildersForWorker(self.name)]
        bids = yield defer.gatherResults(bids, consumeErrors=True)
        if self._configured_builderid_list != bids:
            yield self.master.data.updates.workerConfigured(self.workerid, self.master.masterid, bids)
            yield self.updateWorker()
            self._configured_builderid_list = bids

    @defer.inlineCallbacks
    def stopService(self):
        if self.registration:
            yield self.registration.unregister()
            self.registration = None
        self.workerActionConsumer.stopConsuming()
        self.stopMissingTimer()
        self.stopQuarantineTimer()
        # mark this worker as configured for zero builders in this master
        yield self.master.data.updates.workerConfigured(self.workerid, self.master.masterid, [])

        # during master shutdown we need to wait until the disconnection notification deliveries
        # are completed, otherwise some of the events may still be firing long after the master
        # is completely shut down.
        yield self.disconnect()
        yield self.waitForCompleteShutdown()

        yield super().stopService()

    def isCompatibleWithBuild(self, build_props):
        # given a build properties object, determines whether the build is
        # compatible with the currently running worker or not. This is most
        # often useful for latent workers where it's possible to request
        # different kinds of workers.
        return defer.succeed(True)

    def startMissingTimer(self):
        if self.missing_timeout and self.parent and self.running:
            self.stopMissingTimer()  # in case it's already running
            self.missing_timer = self.master.reactor.callLater(self.missing_timeout,
                                                               self._missing_timer_fired)

    def stopMissingTimer(self):
        if self.missing_timer:
            if self.missing_timer.active():
                self.missing_timer.cancel()
            self.missing_timer = None

    def isConnected(self):
        return self.conn

    def _missing_timer_fired(self):
        self.missing_timer = None
        # notify people, but only if we're still in the config
        if not self.parent:
            return
        last_connection = time.ctime(time.time() - self.missing_timeout)
        self.master.data.updates.workerMissing(
            workerid=self.workerid,
            masterid=self.master.masterid,
            last_connection=last_connection,
            notify=self.notify_on_missing
        )

    def updateWorker(self):
        """Called to add or remove builders after the worker has connected.

        @return: a Deferred that indicates when an attached worker has
        accepted the new builders and/or released the old ones."""
        if self.conn:
            return self.sendBuilderList()
        # else:
        return defer.succeed(None)

    @defer.inlineCallbacks
    def attached(self, conn):
        """This is called when the worker connects."""

        assert self.conn is None

        metrics.MetricCountEvent.log("AbstractWorker.attached_workers", 1)

        # now we go through a sequence of calls, gathering information, then
        # tell the Botmaster that it can finally give this worker to all the
        # Builders that care about it.

        # Reset graceful shutdown status
        self._graceful = False

        self.conn = conn
        self._old_builder_list = None  # clear builder list before proceed

        self.worker_status.setConnected(True)

        self._applyWorkerInfo(conn.info)
        self.worker_commands = conn.info.get("worker_commands", {})
        self.worker_environ = conn.info.get("environ", {})
        self.worker_basedir = conn.info.get("basedir", None)
        self.worker_system = conn.info.get("system", None)

        self.conn.notifyOnDisconnect(self.detached)

        workerinfo = {
            'admin': conn.info.get('admin'),
            'host': conn.info.get('host'),
            'access_uri': conn.info.get('access_uri'),
            'version': conn.info.get('version')
        }

        yield self.master.data.updates.workerConnected(
            workerid=self.workerid,
            masterid=self.master.masterid,
            workerinfo=workerinfo
        )

        if self.worker_system == "nt":
            self.path_module = namedModule("ntpath")
        else:
            # most everything accepts / as separator, so posix should be a
            # reasonable fallback
            self.path_module = namedModule("posixpath")
        log.msg("bot attached")
        self.messageReceivedFromWorker()
        self.stopMissingTimer()
        yield self.updateWorker()
        yield self.botmaster.maybeStartBuildsForWorker(self.name)
        self.updateState()

    def messageReceivedFromWorker(self):
        now = time.time()
        self.lastMessageReceived = now
        self.worker_status.setLastMessageReceived(now)

    def setupProperties(self, props):
        for name in self.properties.properties:
            props.setProperty(
                name, self.properties.getProperty(name), "Worker")
        for name in self.defaultProperties.properties:
            if name not in props:
                props.setProperty(
                    name, self.defaultProperties.getProperty(name), "Worker")

    @defer.inlineCallbacks
    def _handle_disconnection_delivery_notifier(self):
        self._pending_disconnection_delivery_notifier = Notifier()
        yield self.conn.waitForNotifyDisconnectedDelivered()
        self._pending_disconnection_delivery_notifier.notify(None)
        self._pending_disconnection_delivery_notifier = None

    @defer.inlineCallbacks
    def detached(self):
        # protect against race conditions in conn disconnect path and someone
        # calling detached directly. At the moment the null worker does that.
        if self.conn is None:
            return

        metrics.MetricCountEvent.log("AbstractWorker.attached_workers", -1)

        self._handle_disconnection_delivery_notifier()

        yield self.conn.waitShutdown()
        self.conn = None
        self._old_builder_list = []
        self.worker_status.setConnected(False)
        log.msg("Worker.detached(%s)" % (self.name,))
        self.releaseLocks()
        yield self.master.data.updates.workerDisconnected(
            workerid=self.workerid,
            masterid=self.master.masterid,
        )

    def disconnect(self):
        """Forcibly disconnect the worker.

        This severs the TCP connection and returns a Deferred that will fire
        (with None) when the connection is probably gone.

        If the worker is still alive, they will probably try to reconnect
        again in a moment.

        This is called in two circumstances. The first is when a worker is
        removed from the config file. In this case, when they try to
        reconnect, they will be rejected as an unknown worker. The second is
        when we wind up with two connections for the same worker, in which
        case we disconnect the older connection.
        """
        if self.conn is None:
            return defer.succeed(None)
        log.msg("disconnecting old worker %s now" % (self.name,))
        # When this Deferred fires, we'll be ready to accept the new worker
        return self._disconnect(self.conn)

    def waitForCompleteShutdown(self):
        # This function waits until the disconnection to happen and the disconnection
        # notifications have been delivered and acted upon.
        return self._waitForCompleteShutdownImpl(self.conn)

    @defer.inlineCallbacks
    def _waitForCompleteShutdownImpl(self, conn):
        if conn:
            d = defer.Deferred()

            def _disconnected():
                eventually(d.callback, None)
            conn.notifyOnDisconnect(_disconnected)
            yield d
            yield conn.waitForNotifyDisconnectedDelivered()
        elif self._pending_disconnection_delivery_notifier is not None:
            yield self._pending_disconnection_delivery_notifier.wait()

    @defer.inlineCallbacks
    def _disconnect(self, conn):
        # This function waits until the disconnection to happen and the disconnection
        # notifications have been delivered and acted upon
        d = self._waitForCompleteShutdownImpl(conn)
        conn.loseConnection()
        log.msg("waiting for worker to finish disconnecting")
        yield d

    @defer.inlineCallbacks
    def sendBuilderList(self):
        our_builders = self.botmaster.getBuildersForWorker(self.name)

        blist = [(b.name, b.config.workerbuilddir) for b in our_builders]

        if blist == self._old_builder_list:
            return

        slist = yield self.conn.remoteSetBuilderList(builders=blist)

        self._old_builder_list = blist

        # Nothing has changed, so don't need to re-attach to everything
        if not slist:
            return

        dl = []
        for name in slist:
            # use get() since we might have changed our mind since then
            b = self.botmaster.builders.get(name)
            if b:
                d1 = self.attachBuilder(b)
                dl.append(d1)
        yield defer.DeferredList(dl)

    def attachBuilder(self, builder):
        return builder.attached(self, self.worker_commands)

    def controlWorker(self, key, params):
        log.msg("worker {} wants to {}: {}".format(self.name, key[-1], params))
        if key[-1] == "stop":
            return self.shutdownRequested()
        if key[-1] == "pause":
            self.pause()
        if key[-1] == "unpause":
            self.unpause()
        if key[-1] == "kill":
            self.shutdown()

    def shutdownRequested(self):
        self._graceful = True
        self.maybeShutdown()
        self.updateState()

    def addWorkerForBuilder(self, wfb):
        self.workerforbuilders[wfb.builder_name] = wfb

    def removeWorkerForBuilder(self, wfb):
        try:
            del self.workerforbuilders[wfb.builder_name]
        except KeyError:
            pass

    def buildFinished(self, wfb):
        """This is called when a build on this worker is finished."""
        self.botmaster.maybeStartBuildsForWorker(self.name)

    def canStartBuild(self):
        """
        I am called when a build is requested to see if this worker
        can start a build.  This function can be used to limit overall
        concurrency on the worker.

        Note for subclassers: if a worker can become willing to start a build
        without any action on that worker (for example, by a resource in use on
        another worker becoming available), then you must arrange for
        L{maybeStartBuildsForWorker} to be called at that time, or builds on
        this worker will not start.
        """

        # If we're waiting to shutdown gracefully or paused, then we shouldn't
        # accept any new jobs.
        if self._graceful or self._paused:
            return False

        if self.max_builds:
            active_builders = [wfb for wfb in self.workerforbuilders.values()
                               if wfb.isBusy()]
            if len(active_builders) >= self.max_builds:
                return False

        if not self.locksAvailable():
            return False

        return True

    @defer.inlineCallbacks
    def shutdown(self):
        """Shutdown the worker"""
        if not self.conn:
            log.msg("no remote; worker is already shut down")
            return

        yield self.conn.remoteShutdown()

    def maybeShutdown(self):
        """Shut down this worker if it has been asked to shut down gracefully,
        and has no active builders."""
        if not self._graceful:
            return
        active_builders = [wfb for wfb in self.workerforbuilders.values()
                           if wfb.isBusy()]
        if active_builders:
            return
        d = self.shutdown()
        d.addErrback(log.err, 'error while shutting down worker')

    def updateState(self):
        self.master.data.updates.setWorkerState(self.workerid, self._paused, self._graceful)

    def pause(self):
        """Stop running new builds on the worker."""
        self._paused = True
        self.updateState()

    def unpause(self):
        """Restart running new builds on the worker."""
        self._paused = False
        self.botmaster.maybeStartBuildsForWorker(self.name)
        self.updateState()

    def isPaused(self):
        return self._paused

    def resetQuarantine(self):
        self.quarantine_timeout = self.quarantine_initial_timeout

    def putInQuarantine(self):
        if self.quarantine_timer:  # already in quarantine
            return

        self.pause()
        self.quarantine_timer = self.master.reactor.callLater(
            self.quarantine_timeout, self.exitQuarantine)
        log.msg("{} has been put in quarantine for {}s".format(
            self.name, self.quarantine_timeout))
        # next we will wait twice as long
        self.quarantine_timeout *= 2
        if self.quarantine_timeout > self.quarantine_max_timeout:
            # unless we hit the max timeout
            self.quarantine_timeout = self.quarantine_max_timeout

    def exitQuarantine(self):
        self.quarantine_timer = None
        self.unpause()

    def stopQuarantineTimer(self):
        if self.quarantine_timer is not None:
            self.quarantine_timer.cancel()
            self.quarantine_timer = None
            self.unpause()


class Worker(AbstractWorker):

    @defer.inlineCallbacks
    def detached(self):
        yield super().detached()
        self.botmaster.workerLost(self)
        self.startMissingTimer()

    @defer.inlineCallbacks
    def attached(self, bot):
        try:
            yield super().attached(bot)
        except Exception as e:
            log.err(e, "worker %s cannot attach" % (self.name,))
            return

    def buildFinished(self, wfb):
        """This is called when a build on this worker is finished."""
        super().buildFinished(wfb)

        # If we're gracefully shutting down, and we have no more active
        # builders, then it's safe to disconnect
        self.maybeShutdown()
