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
from future.utils import itervalues

import time

from email.message import Message
from email.utils import formatdate
from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log
from twisted.python.reflect import namedModule
from zope.interface import implements

from buildbot import config
from buildbot.interfaces import IBuildSlave
from buildbot.interfaces import ILatentBuildSlave
from buildbot.interfaces import LatentBuildSlaveFailedToSubstantiate
from buildbot.process import metrics
from buildbot.process.properties import Properties
from buildbot.reporters.mail import MailNotifier
from buildbot.status.slave import SlaveStatus
from buildbot.util import ascii2unicode
from buildbot.util import service
from buildbot.util.eventual import eventually


class AbstractBuildSlave(service.BuildbotService, object):

    """This is the master-side representative for a remote buildbot slave.
    There is exactly one for each slave described in the config file (the
    c['slaves'] list). When buildbots connect in (.attach), they get a
    reference to this instance. The BotMaster object is stashed as the
    .botmaster attribute. The BotMaster is also our '.parent' Service.

    I represent a build slave -- a remote machine capable of
    running builds.  I am instantiated by the configuration file, and can be
    subclassed to add extra functionality."""

    implements(IBuildSlave)

    # reconfig slaves after builders
    reconfig_priority = 64

    def checkConfig(self, name, password, max_builds=None,
                    notify_on_missing=None,
                    missing_timeout=10 * 60,   # Ten minutes
                    properties=None, locks=None, keepalive_interval=3600):
        """
        @param name: botname this machine will supply when it connects
        @param password: password this machine will supply when
                         it connects
        @param max_builds: maximum number of simultaneous builds that will
                           be run concurrently on this buildslave (the
                           default is None for no limit)
        @param properties: properties that will be applied to builds run on
                           this slave
        @type properties: dictionary
        @param locks: A list of locks that must be acquired before this slave
                      can be used
        @type locks: dictionary
        """
        self.name = name = ascii2unicode(name)

        if properties is None:
            properties = {}

        self.password = password

        # protocol registration
        self.registration = None

        # these are set when the service is started
        self.manager = None
        self.buildslaveid = None

        self.slave_status = SlaveStatus(name)
        self.slave_commands = None
        self.slavebuilders = {}
        self.max_builds = max_builds
        self.access = []
        if locks:
            self.access = locks
        self.lock_subscriptions = []

        self.properties = Properties()
        self.properties.update(properties, "BuildSlave")
        self.properties.setProperty("slavename", name, "BuildSlave")

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

        self._old_builder_list = None

    def __repr__(self):
        return "<%s %r>" % (self.__class__.__name__, self.name)

    @property
    def slavename(self):
        # slavename is now an alias to twisted.Service's name
        return self.name

    @property
    def botmaster(self):
        if self.master is None:
            return None
        return self.master.botmaster

    def updateLocks(self):
        """Convert the L{LockAccess} objects in C{self.locks} into real lock
        objects, while also maintaining the subscriptions to lock releases."""
        # unsubscribe from any old locks
        for s in self.lock_subscriptions:
            s.unsubscribe()

        # convert locks into their real form
        locks = [(self.botmaster.getLockFromLockAccess(a), a)
                 for a in self.access]
        self.locks = [(l.getLock(self), la) for l, la in locks]
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
        my caller should give up the build and try to get another slave
        to look at it.
        """
        log.msg("acquireLocks(slave %s, locks %s)" % (self, self.locks))
        if not self.locksAvailable():
            log.msg("slave %s can't lock, giving up" % (self, ))
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
        """One of the locks for this slave was released; try scheduling
        builds."""
        if not self.botmaster:
            return  # oh well..
        self.botmaster.maybeStartBuildsForSlave(self.name)

    def _applySlaveInfo(self, info):
        if not info:
            return

        self.slave_status.setAdmin(info.get("admin"))
        self.slave_status.setHost(info.get("host"))
        self.slave_status.setAccessURI(info.get("access_uri", None))
        self.slave_status.setVersion(info.get("version", "(unknown)"))

    @defer.inlineCallbacks
    def _getSlaveInfo(self):
        buildslave = yield self.master.data.get(
            ('buildslaves', self.buildslaveid))
        self._applySlaveInfo(buildslave['slaveinfo'])

    def setServiceParent(self, parent):
        # botmaster needs to set before setServiceParent which calls startService

        self.manager = parent
        return service.BuildbotService.setServiceParent(self, parent)

    @defer.inlineCallbacks
    def startService(self):
        self.updateLocks()
        self.startMissingTimer()
        self.buildslaveid = yield self.master.data.updates.findBuildslaveId(
            self.name)

        yield self._getSlaveInfo()
        yield service.BuildbotService.startService(self)

    @defer.inlineCallbacks
    def reconfigService(self, name, password, max_builds=None,
                        notify_on_missing=None, missing_timeout=3600,
                        properties=None, locks=None, keepalive_interval=3600):
        # Given a BuildSlave config arguments, configure this one identically.
        # Because BuildSlave objects are remotely referenced, we can't replace them
        # without disconnecting the slave, yet there's no reason to do that.

        assert self.name == name
        self.password = password

        # adopt new instance's configuration parameters
        self.max_builds = max_builds
        self.access = []
        if locks:
            self.access = locks
        self.notify_on_missing = notify_on_missing

        if self.missing_timeout != missing_timeout:
            running_missing_timer = self.missing_timer
            self.stopMissingTimer()
            self.missing_timeout = missing_timeout
            if running_missing_timer:
                self.startMissingTimer()

        if properties is None:
            properties = {}
        self.properties = Properties()
        self.properties.update(properties, "BuildSlave")
        self.properties.setProperty("slavename", name, "BuildSlave")

        # update our records with the buildslave manager
        if not self.registration:
            self.registration = yield self.master.buildslaves.register(self)
        yield self.registration.update(self, self.master.config)

        self.updateLocks()

        bids = [b._builderid for b in self.botmaster.getBuildersForSlave(self.name)]
        yield self.master.data.updates.buildslaveConfigured(self.buildslaveid, self.master.masterid, bids)

        # update the attached slave's notion of which builders are attached.
        # This assumes that the relevant builders have already been configured,
        # which is why the reconfig_priority is set low in this class.
        yield self.updateSlave()

    @defer.inlineCallbacks
    def stopService(self):
        if self.registration:
            yield self.registration.unregister()
            self.registration = None
        self.stopMissingTimer()
        # mark this slave as configured for zero builders in this master
        yield self.master.data.updates.buildslaveConfigured(self.buildslaveid, self.master.masterid, [])
        yield service.BuildbotService.stopService(self)

    def startMissingTimer(self):
        if self.notify_on_missing and self.missing_timeout and self.parent:
            self.stopMissingTimer()  # in case it's already running
            self.missing_timer = reactor.callLater(self.missing_timeout,
                                                   self._missing_timer_fired)

    def stopMissingTimer(self):
        if self.missing_timer:
            self.missing_timer.cancel()
            self.missing_timer = None

    def isConnected(self):
        return self.conn

    def _missing_timer_fired(self):
        self.missing_timer = None
        # notify people, but only if we're still in the config
        if not self.parent:
            return

        buildmaster = self.botmaster.master
        status = buildmaster.getStatus()
        text = "The Buildbot working for '%s'\n" % status.getTitle()
        text += ("has noticed that the buildslave named %s went away\n" %
                 self.name)
        text += "\n"
        text += ("It last disconnected at %s (buildmaster-local time)\n" %
                 time.ctime(time.time() - self.missing_timeout))  # approx
        text += "\n"
        text += "The admin on record (as reported by BUILDSLAVE:info/admin)\n"
        text += "was '%s'.\n" % self.slave_status.getAdmin()
        text += "\n"
        text += "Sincerely,\n"
        text += " The Buildbot\n"
        text += " %s\n" % status.getTitleURL()
        text += "\n"
        text += "%s\n" % status.getURLForThing(self.slave_status)
        subject = "Buildbot: buildslave %s was lost" % (self.name,)
        return self._mail_missing_message(subject, text)

    def updateSlave(self):
        """Called to add or remove builders after the slave has connected.

        @return: a Deferred that indicates when an attached slave has
        accepted the new builders and/or released the old ones."""
        if self.conn:
            return self.sendBuilderList()
        else:
            return defer.succeed(None)

    def updateSlaveStatus(self, buildStarted=None, buildFinished=None):
        # TODO
        pass

    @defer.inlineCallbacks
    def attached(self, conn):
        """This is called when the slave connects."""

        metrics.MetricCountEvent.log("AbstractBuildSlave.attached_slaves", 1)

        # now we go through a sequence of calls, gathering information, then
        # tell the Botmaster that it can finally give this slave to all the
        # Builders that care about it.

        # Reset graceful shutdown status
        self.slave_status.setGraceful(False)
        # We want to know when the graceful shutdown flag changes
        self.slave_status.addGracefulWatcher(self._gracefulChanged)
        self.conn = conn
        self._old_builder_list = None  # clear builder list before proceed
        self.slave_status.addPauseWatcher(self._pauseChanged)

        self.slave_status.setConnected(True)

        self._applySlaveInfo(conn.info)
        self.slave_commands = conn.info.get("slave_commands", {})
        self.slave_environ = conn.info.get("environ", {})
        self.slave_basedir = conn.info.get("basedir", None)
        self.slave_system = conn.info.get("system", None)

        self.conn.notifyOnDisconnect(self.detached)

        slaveinfo = {
            'admin': conn.info.get('admin'),
            'host': conn.info.get('host'),
            'access_uri': conn.info.get('access_uri'),
            'version': conn.info.get('version')
        }

        yield self.master.data.updates.buildslaveConnected(
            buildslaveid=self.buildslaveid,
            masterid=self.master.masterid,
            slaveinfo=slaveinfo
        )

        if self.slave_system == "nt":
            self.path_module = namedModule("ntpath")
        else:
            # most everything accepts / as separator, so posix should be a
            # reasonable fallback
            self.path_module = namedModule("posixpath")
        log.msg("bot attached")
        self.messageReceivedFromSlave()
        self.stopMissingTimer()
        self.master.status.slaveConnected(self.name)
        yield self.updateSlave()
        yield self.botmaster.maybeStartBuildsForSlave(self.name)

    def messageReceivedFromSlave(self):
        now = time.time()
        self.lastMessageReceived = now
        self.slave_status.setLastMessageReceived(now)

    @defer.inlineCallbacks
    def detached(self):
        metrics.MetricCountEvent.log("AbstractBuildSlave.attached_slaves", -1)
        self.conn = None
        self._old_builder_list = []
        self.slave_status.removeGracefulWatcher(self._gracefulChanged)
        self.slave_status.removePauseWatcher(self._pauseChanged)
        self.slave_status.setConnected(False)
        log.msg("BuildSlave.detached(%s)" % (self.name,))
        self.master.status.slaveDisconnected(self.name)
        self.releaseLocks()
        yield self.master.data.updates.buildslaveDisconnected(
            buildslaveid=self.buildslaveid,
            masterid=self.master.masterid,
        )

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

        if self.conn is None:
            return defer.succeed(None)
        log.msg("disconnecting old slave %s now" % (self.name,))
        # When this Deferred fires, we'll be ready to accept the new slave
        return self._disconnect(self.conn)

    def _disconnect(self, conn):
        # all kinds of teardown will happen as a result of
        # loseConnection(), but it happens after a reactor iteration or
        # two. Hook the actual disconnect so we can know when it is safe
        # to connect the new slave. We have to wait one additional
        # iteration (with callLater(0)) to make sure the *other*
        # notifyOnDisconnect handlers have had a chance to run.
        d = defer.Deferred()

        # notifyOnDisconnect runs the callback
        def _disconnected():
            eventually(d.callback, None)
        conn.notifyOnDisconnect(_disconnected)
        conn.loseConnection()
        log.msg("waiting for slave to finish disconnecting")

        return d

    def sendBuilderList(self):
        our_builders = self.botmaster.getBuildersForSlave(self.name)
        blist = [(b.name, b.config.slavebuilddir) for b in our_builders]
        if blist == self._old_builder_list:
            return defer.succeed(None)

        d = self.conn.remoteSetBuilderList(builders=blist)

        @d.addCallback
        def sentBuilderList(ign):
            self._old_builder_list = blist
            return ign
        return d

    def shutdownRequested(self):
        log.msg("slave %s wants to shut down" % (self.name,))
        self.slave_status.setGraceful(True)

    def addSlaveBuilder(self, sb):
        self.slavebuilders[sb.builder_name] = sb

    def removeSlaveBuilder(self, sb):
        try:
            del self.slavebuilders[sb.builder_name]
        except KeyError:
            pass

    def buildFinished(self, sb):
        """This is called when a build on this slave is finished."""
        self.botmaster.maybeStartBuildsForSlave(self.name)

    def canStartBuild(self):
        """
        I am called when a build is requested to see if this buildslave
        can start a build.  This function can be used to limit overall
        concurrency on the buildslave.

        Note for subclassers: if a slave can become willing to start a build
        without any action on that slave (for example, by a resource in use on
        another slave becoming available), then you must arrange for
        L{maybeStartBuildsForSlave} to be called at that time, or builds on
        this slave will not start.
        """

        if self.slave_status.isPaused():
            return False

        # If we're waiting to shutdown gracefully, then we shouldn't
        # accept any new jobs.
        if self.slave_status.getGraceful():
            return False

        if self.max_builds:
            active_builders = [sb for sb in itervalues(self.slavebuilders)
                               if sb.isBusy()]
            if len(active_builders) >= self.max_builds:
                return False

        if not self.locksAvailable():
            return False

        return True

    def _mail_missing_message(self, subject, text):
        # FIXME: This should be handled properly via the event api
        # we should send a missing message on the mq, and let any reporter handle that

        # first, see if we have a MailNotifier we can use. This gives us a
        # fromaddr and a relayhost.
        buildmaster = self.botmaster.master
        for st in buildmaster.services:
            if isinstance(st, MailNotifier):
                break
        else:
            # if not, they get a default MailNotifier, which always uses SMTP
            # to localhost and uses a dummy fromaddr of "buildbot".
            log.msg("buildslave-missing msg using default MailNotifier")
            st = MailNotifier("buildbot")
        # now construct the mail

        m = Message()
        m.set_payload(text)
        m['Date'] = formatdate(localtime=True)
        m['Subject'] = subject
        m['From'] = st.fromaddr
        recipients = self.notify_on_missing
        m['To'] = ", ".join(recipients)
        d = st.sendMessage(m, recipients)
        # return the Deferred for testing purposes
        return d

    def _gracefulChanged(self, graceful):
        """This is called when our graceful shutdown setting changes"""
        self.maybeShutdown()

    @defer.inlineCallbacks
    def shutdown(self):
        """Shutdown the slave"""
        if not self.conn:
            log.msg("no remote; slave is already shut down")
            return

        yield self.conn.remoteShutdown()

    def maybeShutdown(self):
        """Shut down this slave if it has been asked to shut down gracefully,
        and has no active builders."""
        if not self.slave_status.getGraceful():
            return
        active_builders = [sb for sb in itervalues(self.slavebuilders)
                           if sb.isBusy()]
        if active_builders:
            return
        d = self.shutdown()
        d.addErrback(log.err, 'error while shutting down slave')

    def _pauseChanged(self, paused):
        if paused is True:
            self.botmaster.master.status.slavePaused(self.name)
        else:
            self.botmaster.master.status.slaveUnpaused(self.name)

    def pause(self):
        """Stop running new builds on the slave."""
        self.slave_status.setPaused(True)

    def unpause(self):
        """Restart running new builds on the slave."""
        self.slave_status.setPaused(False)
        self.botmaster.maybeStartBuildsForSlave(self.name)

    def isPaused(self):
        return self.slave_status.isPaused()


class BuildSlave(AbstractBuildSlave):

    def sendBuilderList(self):
        d = AbstractBuildSlave.sendBuilderList(self)

        def _sent(slist):
            # Nothing has changed, so don't need to re-attach to everything
            if not slist:
                return
            dl = []
            for name in slist:
                # use get() since we might have changed our mind since then
                b = self.botmaster.builders.get(name)
                if b:
                    d1 = b.attached(self, self.slave_commands)
                    dl.append(d1)
            return defer.DeferredList(dl)

        def _set_failed(why):
            log.msg("BuildSlave.sendBuilderList (%s) failed" % self)
            log.err(why)
            # TODO: hang up on them?, without setBuilderList we can't use
            # them
        d.addCallbacks(_sent, _set_failed)
        return d

    def detached(self):
        AbstractBuildSlave.detached(self)
        self.botmaster.slaveLost(self)
        self.startMissingTimer()

    def buildFinished(self, sb):
        """This is called when a build on this slave is finished."""
        AbstractBuildSlave.buildFinished(self, sb)

        # If we're gracefully shutting down, and we have no more active
        # builders, then it's safe to disconnect
        self.maybeShutdown()


class AbstractLatentBuildSlave(AbstractBuildSlave):

    """A build slave that will start up a slave instance when needed.

    To use, subclass and implement start_instance and stop_instance.

    See ec2buildslave.py for a concrete example.  Also see the stub example in
    test/test_slaves.py.
    """

    implements(ILatentBuildSlave)

    substantiated = False
    substantiation_deferred = None
    substantiation_build = None
    insubstantiating = False
    build_wait_timer = None
    _shutdown_callback_handle = None

    def __init__(self, name, password,
                 build_wait_timeout=60 * 10,
                 **kwargs):
        AbstractBuildSlave.__init__(self, name, password, **kwargs)

        self.building = set()
        self.build_wait_timeout = build_wait_timeout

    def failed_to_start(self, instance_id, instance_state):
        log.msg('%s %s failed to start instance %s (%s)' %
                (self.__class__.__name__, self.slavename,
                    instance_id, instance_state))
        raise LatentBuildSlaveFailedToSubstantiate(instance_id, instance_state)

    def start_instance(self, build):
        # responsible for starting instance that will try to connect with this
        # master.  Should return deferred with either True (instance started)
        # or False (instance not started, so don't run a build here).  Problems
        # should use an errback.
        raise NotImplementedError

    def stop_instance(self, fast=False):
        # responsible for shutting down instance.
        raise NotImplementedError

    def substantiate(self, sb, build):
        if self.substantiated:
            self._clearBuildWaitTimer()
            self._setBuildWaitTimer()
            return defer.succeed(True)
        if self.substantiation_deferred is None:
            if self.parent and not self.missing_timer:
                # start timer.  if timer times out, fail deferred
                self.missing_timer = reactor.callLater(
                    self.missing_timeout,
                    self._substantiation_failed, defer.TimeoutError())
            self.substantiation_deferred = defer.Deferred()
            self.substantiation_build = build
            if self.conn is None:
                d = self._substantiate(build)  # start up instance
                d.addErrback(log.err, "while substantiating")
            # else: we're waiting for an old one to detach.  the _substantiate
            # will be done in ``detached`` below.
        return self.substantiation_deferred

    def _substantiate(self, build):
        # register event trigger
        d = self.start_instance(build)
        self._shutdown_callback_handle = reactor.addSystemEventTrigger(
            'before', 'shutdown', self._soft_disconnect, fast=True)

        def start_instance_result(result):
            # If we don't report success, then preparation failed.
            if not result:
                log.msg("Slave '%s' does not want to substantiate at this time" % (self.name,))
                d = self.substantiation_deferred
                self.substantiation_deferred = None
                d.callback(False)
            return result

        def clean_up(failure):
            if self.missing_timer is not None:
                self.missing_timer.cancel()
                self._substantiation_failed(failure)
            if self._shutdown_callback_handle is not None:
                handle = self._shutdown_callback_handle
                del self._shutdown_callback_handle
                reactor.removeSystemEventTrigger(handle)
            return failure
        d.addCallbacks(start_instance_result, clean_up)
        return d

    def attached(self, bot):
        if self.substantiation_deferred is None and self.build_wait_timeout >= 0:
            msg = 'Slave %s received connection while not trying to ' \
                'substantiate.  Disconnecting.' % (self.name,)
            log.msg(msg)
            self._disconnect(bot)
            return defer.fail(RuntimeError(msg))
        return AbstractBuildSlave.attached(self, bot)

    def detached(self):
        AbstractBuildSlave.detached(self)
        if self.substantiation_deferred is not None:
            d = self._substantiate(self.substantiation_build)
            d.addErrback(log.err, 'while re-substantiating')

    def _substantiation_failed(self, failure):
        self.missing_timer = None
        if self.substantiation_deferred:
            d = self.substantiation_deferred
            self.substantiation_deferred = None
            self.substantiation_build = None
            d.errback(failure)
        d = self.insubstantiate()
        d.addErrback(log.err, 'while insubstantiating')
        # notify people, but only if we're still in the config
        if not self.parent or not self.notify_on_missing:
            return

        buildmaster = self.botmaster.master
        status = buildmaster.getStatus()
        text = "The Buildbot working for '%s'\n" % status.getTitle()
        text += ("has noticed that the latent buildslave named %s \n" %
                 self.name)
        text += "never substantiated after a request\n"
        text += "\n"
        text += ("The request was made at %s (buildmaster-local time)\n" %
                 time.ctime(time.time() - self.missing_timeout))  # approx
        text += "\n"
        text += "Sincerely,\n"
        text += " The Buildbot\n"
        text += " %s\n" % status.getTitleURL()
        subject = "Buildbot: buildslave %s never substantiated" % (self.name,)
        return self._mail_missing_message(subject, text)

    def canStartBuild(self):
        if self.insubstantiating:
            return False
        return AbstractBuildSlave.canStartBuild(self)

    def buildStarted(self, sb):
        assert self.substantiated
        self._clearBuildWaitTimer()
        self.building.add(sb.builder_name)

    def buildFinished(self, sb):
        AbstractBuildSlave.buildFinished(self, sb)

        self.building.remove(sb.builder_name)
        if not self.building:
            if self.build_wait_timeout == 0:
                d = self.insubstantiate()
                # try starting builds for this slave after insubstantiating;
                # this will cause the slave to re-substantiate immediately if
                # there are pending build requests.
                d.addCallback(lambda _:
                              self.botmaster.maybeStartBuildsForSlave(self.slavename))
            else:
                self._setBuildWaitTimer()

    def _clearBuildWaitTimer(self):
        if self.build_wait_timer is not None:
            if self.build_wait_timer.active():
                self.build_wait_timer.cancel()
            self.build_wait_timer = None

    def _setBuildWaitTimer(self):
        self._clearBuildWaitTimer()
        if self.build_wait_timeout <= 0:
            return
        self.build_wait_timer = reactor.callLater(
            self.build_wait_timeout, self._soft_disconnect)

    @defer.inlineCallbacks
    def insubstantiate(self, fast=False):
        self.insubstantiating = True
        self._clearBuildWaitTimer()
        d = self.stop_instance(fast)
        if self._shutdown_callback_handle is not None:
            handle = self._shutdown_callback_handle
            del self._shutdown_callback_handle
            reactor.removeSystemEventTrigger(handle)
        self.substantiated = False
        self.building.clear()  # just to be sure
        yield d
        self.insubstantiating = False
        self.botmaster.maybeStartBuildsForSlave(self.name)

    @defer.inlineCallbacks
    def _soft_disconnect(self, fast=False):
        # a negative build_wait_timeout means the slave should never be shut
        # down, so just disconnect.
        if self.build_wait_timeout < 0:
            yield AbstractBuildSlave.disconnect(self)
            return

        if self.missing_timer:
            self.missing_timer.cancel()
            self.missing_timer = None

        if self.substantiation_deferred is not None:
            log.msg("Weird: Got request to stop before started. Allowing "
                    "slave to start cleanly to avoid inconsistent state")
            yield self.substantiation_deferred
            self.substantiation_deferred = None
            self.substantiation_build = None
            log.msg("Substantiation complete, immediately terminating.")

        if self.conn is not None:
            # this could be called when the slave needs to shut down, such as
            # in BotMaster.removeSlave, *or* when a new slave requests a
            # connection when we already have a slave. It's not clear what to
            # do in the second case: this shouldn't happen, and if it
            # does...if it's a latent slave, shutting down will probably kill
            # something we want...but we can't know what the status is. So,
            # here, we just do what should be appropriate for the first case,
            # and put our heads in the sand for the second, at least for now.
            # The best solution to the odd situation is removing it as a
            # possibility: make the master in charge of connecting to the
            # slave, rather than vice versa. TODO.
            yield defer.DeferredList([
                AbstractBuildSlave.disconnect(self),
                self.insubstantiate(fast)
            ], consumeErrors=True, fireOnOneErrback=True)
        else:
            yield AbstractBuildSlave.disconnect(self)
            yield self.stop_instance(fast)

    def disconnect(self):
        # This returns a Deferred but we don't use it
        self._soft_disconnect()
        # this removes the slave from all builders.  It won't come back
        # without a restart (or maybe a sighup)
        self.botmaster.slaveLost(self)

    def stopService(self):
        res = defer.maybeDeferred(AbstractBuildSlave.stopService, self)
        if self.conn is not None:
            d = self._soft_disconnect()
            res = defer.DeferredList([res, d])
        return res

    def updateSlave(self):
        """Called to add or remove builders after the slave has connected.

        Also called after botmaster's builders are initially set.

        @return: a Deferred that indicates when an attached slave has
        accepted the new builders and/or released the old ones."""
        for b in self.botmaster.getBuildersForSlave(self.name):
            if b.name not in self.slavebuilders:
                b.addLatentSlave(self)
        return AbstractBuildSlave.updateSlave(self)

    def sendBuilderList(self):
        d = AbstractBuildSlave.sendBuilderList(self)

        def _sent(slist):
            if not slist:
                return
            dl = []
            for name in slist:
                # use get() since we might have changed our mind since then.
                # we're checking on the builder in addition to the
                # slavebuilders out of a bit of paranoia.
                b = self.botmaster.builders.get(name)
                sb = self.slavebuilders.get(name)
                if b and sb:
                    d1 = sb.attached(self, self.slave_commands)
                    dl.append(d1)
            return defer.DeferredList(dl)

        def _set_failed(why):
            log.msg("BuildSlave.sendBuilderList (%s) failed" % self)
            log.err(why)
            # TODO: hang up on them?, without setBuilderList we can't use
            # them
            if self.substantiation_deferred:
                d = self.substantiation_deferred
                self.substantiation_deferred = None
                self.substantiation_build = None
                d.errback(why)
            if self.missing_timer:
                self.missing_timer.cancel()
                self.missing_timer = None
            # TODO: maybe log?  send an email?
            return why
        d.addCallbacks(_sent, _set_failed)

        @d.addCallback
        def _substantiated(res):
            log.msg(r"Slave %s substantiated \o/" % (self.name,))
            self.substantiated = True
            if not self.substantiation_deferred:
                log.msg("No substantiation deferred for %s" % (self.name,))
            if self.substantiation_deferred:
                log.msg("Firing %s substantiation deferred with success" % (self.name,))
                d = self.substantiation_deferred
                self.substantiation_deferred = None
                self.substantiation_build = None
                d.callback(True)
            # note that the missing_timer is already handled within
            # ``attached``
            if not self.building:
                self._setBuildWaitTimer()
        return d
