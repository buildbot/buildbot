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


import os
import signal
import time
import textwrap

from zope.interface import implements
from twisted.python import log, components
from twisted.python.failure import Failure
from twisted.internet import defer, reactor
from twisted.spread import pb
from twisted.application import service
from twisted.application.internet import TimerService

import buildbot
import buildbot.pbmanager
from buildbot.util import now, safeTranslate, eventual, subscription
from buildbot.pbutil import NewCredPerspective
from buildbot.process.builder import Builder, IDLE
from buildbot.status.builder import Status
from buildbot.changes.manager import ChangeManager
from buildbot import interfaces, locks
from buildbot.process.properties import Properties
from buildbot.config import BuilderConfig
from buildbot.process.builder import BuilderControl
from buildbot.db import connector, exceptions
from buildbot.schedulers.manager import SchedulerManager
from buildbot.schedulers.base import isScheduler
from buildbot.util.loop import DelegateLoop

########################################

class BotMaster(service.MultiService):

    """This is the master-side service which manages remote buildbot slaves.
    It provides them with BuildSlaves, and distributes file change
    notification messages to them.
    """

    debug = 0
    reactor = reactor

    def __init__(self, master):
        service.MultiService.__init__(self)
        self.master = master

        self.builders = {}
        self.builderNames = []
        # builders maps Builder names to instances of bb.p.builder.Builder,
        # which is the master-side object that defines and controls a build.
        # They are added by calling botmaster.addBuilder() from the startup
        # code.

        # self.slaves contains a ready BuildSlave instance for each
        # potential buildslave, i.e. all the ones listed in the config file.
        # If the slave is connected, self.slaves[slavename].slave will
        # contain a RemoteReference to their Bot instance. If it is not
        # connected, that attribute will hold None.
        self.slaves = {} # maps slavename to BuildSlave
        self.watchers = {}

        # self.locks holds the real Lock instances
        self.locks = {}

        # self.mergeRequests is the callable override for merging build
        # requests
        self.mergeRequests = None

        # self.prioritizeBuilders is the callable override for builder order
        # traversal
        self.prioritizeBuilders = None

        self.loop = DelegateLoop(self._get_processors)
        self.loop.setServiceParent(self)

        self.shuttingDown = False

        self.lastSlavePortnum = None

    def setMasterName(self, name, incarnation):
        self.master_name = name
        self.master_incarnation = incarnation

    def cleanShutdown(self):
        if self.shuttingDown:
            return
        log.msg("Initiating clean shutdown")
        self.shuttingDown = True

        # Wait for all builds to finish
        l = []
        for builder in self.builders.values():
            for build in builder.builder_status.getCurrentBuilds():
                l.append(build.waitUntilFinished())
        if len(l) == 0:
            log.msg("No running jobs, starting shutdown immediately")
            self.loop.trigger()
            d = self.loop.when_quiet()
        else:
            log.msg("Waiting for %i build(s) to finish" % len(l))
            d = defer.DeferredList(l)
            d.addCallback(lambda ign: self.loop.when_quiet())

        # Flush the eventual queue
        d.addCallback(eventual.flushEventualQueue)

        # Finally, shut the whole process down
        def shutdown(ign):
            # Double check that we're still supposed to be shutting down
            # The shutdown may have been cancelled!
            if self.shuttingDown:
                # Check that there really aren't any running builds
                for builder in self.builders.values():
                    n = len(builder.builder_status.getCurrentBuilds())
                    if n > 0:
                        log.msg("Not shutting down, builder %s has %i builds running" % (builder, n))
                        log.msg("Trying shutdown sequence again")
                        self.shuttingDown = False
                        self.cleanShutdown()
                        return
                log.msg("Stopping reactor")
                self.reactor.stop()
        d.addCallback(shutdown)
        return d

    def cancelCleanShutdown(self):
        if not self.shuttingDown:
            return
        log.msg("Cancelling clean shutdown")
        self.shuttingDown = False

    def _sortfunc(self, b1, b2):
        t1 = b1.getOldestRequestTime()
        t2 = b2.getOldestRequestTime()
        # If t1 or t2 is None, then there are no build requests,
        # so sort it at the end
        if t1 is None:
            return 1
        if t2 is None:
            return -1
        return cmp(t1, t2)

    def _sort_builders(self, parent, builders):
        return sorted(builders, self._sortfunc)

    def _get_processors(self):
        if self.shuttingDown:
            return []
        builders = self.builders.values()
        sorter = self.prioritizeBuilders or self._sort_builders
        try:
            builders = sorter(self.parent, builders)
        except:
            log.msg("Exception prioritizing builders")
            log.err(Failure())
            # leave them in the original order
        return [b.run for b in builders]

    # these four are convenience functions for testing

    def waitUntilBuilderAttached(self, name):
        b = self.builders[name]
        #if b.slaves:
        #    return defer.succeed(None)
        d = defer.Deferred()
        b.watchers['attach'].append(d)
        return d

    def waitUntilBuilderDetached(self, name):
        b = self.builders.get(name)
        if not b or not b.slaves:
            return defer.succeed(None)
        d = defer.Deferred()
        b.watchers['detach'].append(d)
        return d

    def waitUntilBuilderFullyDetached(self, name):
        b = self.builders.get(name)
        # TODO: this looks too deeply inside the Builder object
        if not b or not b.slaves:
            return defer.succeed(None)
        d = defer.Deferred()
        b.watchers['detach_all'].append(d)
        return d

    def waitUntilBuilderIdle(self, name):
        b = self.builders[name]
        # TODO: this looks way too deeply inside the Builder object
        for sb in b.slaves:
            if sb.state != IDLE:
                d = defer.Deferred()
                b.watchers['idle'].append(d)
                return d
        return defer.succeed(None)

    def loadConfig_Slaves(self, new_slaves):
        new_portnum = (self.lastSlavePortnum is not None
                   and self.lastSlavePortnum != self.master.slavePortnum)
        if new_portnum:
            # it turns out this is pretty hard..
            raise ValueError("changing slavePortnum in reconfig is not supported")
        self.lastSlavePortnum = self.master.slavePortnum

        old_slaves = [c for c in list(self)
                      if interfaces.IBuildSlave.providedBy(c)]

        # identify added/removed slaves. For each slave we construct a tuple
        # of (name, password, class), and we consider the slave to be already
        # present if the tuples match. (we include the class to make sure
        # that BuildSlave(name,pw) is different than
        # SubclassOfBuildSlave(name,pw) ). If the password or class has
        # changed, we will remove the old version of the slave and replace it
        # with a new one. If anything else has changed, we just update the
        # old BuildSlave instance in place. If the name has changed, of
        # course, it looks exactly the same as deleting one slave and adding
        # an unrelated one.
        old_t = {}
        for s in old_slaves:
            old_t[(s.slavename, s.password, s.__class__)] = s
        new_t = {}
        for s in new_slaves:
            new_t[(s.slavename, s.password, s.__class__)] = s
        removed = [old_t[t]
                   for t in old_t
                   if t not in new_t]
        added = [new_t[t]
                 for t in new_t
                 if t not in old_t]
        remaining_t = [t
                       for t in new_t
                       if t in old_t]

        # removeSlave will hang up on the old bot
        dl = []
        for s in removed:
            dl.append(self.removeSlave(s))
        d = defer.DeferredList(dl, fireOnOneErrback=True)

        def add_new(res):
            for s in added:
                self.addSlave(s)
        d.addCallback(add_new)

        def update_remaining(_):
            for t in remaining_t:
                old_t[t].update(new_t[t])
        d.addCallback(update_remaining)

        return d

    def addSlave(self, s):
        s.setServiceParent(self)
        s.setBotmaster(self)
        self.slaves[s.slavename] = s
        s.pb_registration = self.master.pbmanager.register(
                self.master.slavePortnum, s.slavename,
                s.password, self.getPerspective)

    def removeSlave(self, s):
        d = s.disownServiceParent()
        d.addCallback(lambda _ : s.pb_registration.unregister())
        d.addCallback(lambda _ : self.slaves[s.slavename].disconnect())
        def delslave(_):
            del self.slaves[s.slavename]
        d.addCallback(delslave)
        return d

    def slaveLost(self, bot):
        for name, b in self.builders.items():
            if bot.slavename in b.slavenames:
                b.detached(bot)

    def getBuildersForSlave(self, slavename):
        return [b
                for b in self.builders.values()
                if slavename in b.slavenames]

    def getBuildernames(self):
        return self.builderNames

    def getBuilders(self):
        allBuilders = [self.builders[name] for name in self.builderNames]
        return allBuilders

    def setBuilders(self, builders):
        # TODO: remove self.builders and just use the Service hierarchy to
        # keep track of active builders. We could keep self.builderNames to
        # retain ordering, if it seems important.
        self.builders = {}
        self.builderNames = []
        d = defer.DeferredList([b.disownServiceParent() for b in list(self)
                                if isinstance(b, Builder)],
                               fireOnOneErrback=True)
        def _add(ign):
            log.msg("setBuilders._add: %s %s" % (list(self), builders))
            for b in builders:
                for slavename in b.slavenames:
                    # this is actually validated earlier
                    assert slavename in self.slaves
                self.builders[b.name] = b
                self.builderNames.append(b.name)
                b.setBotmaster(self)
                b.setServiceParent(self)
        d.addCallback(_add)
        d.addCallback(lambda ign: self._updateAllSlaves())
        return d

    def _updateAllSlaves(self):
        """Notify all buildslaves about changes in their Builders."""
        dl = []
        for s in self.slaves.values():
            d = s.updateSlave()
            d.addErrback(log.err)
            dl.append(d)
        return defer.DeferredList(dl)

    def shouldMergeRequests(self, builder, req1, req2):
        """Determine whether two BuildRequests should be merged for
        the given builder.

        """
        if self.mergeRequests is not None:
            if callable(self.mergeRequests):
                return self.mergeRequests(builder, req1, req2)
            elif self.mergeRequests == False:
                # To save typing, this allows c['mergeRequests'] = False
                return False
        return req1.canBeMergedWith(req2)

    def getPerspective(self, mind, slavename):
        sl = self.slaves[slavename]
        if not sl:
            return None

        # record when this connection attempt occurred
        sl.recordConnectTime()

        if sl.isConnected():
            # duplicate slave - send it to arbitration
            arb = DuplicateSlaveArbitrator(sl)
            return arb.getPerspective(mind, slavename)
        else:
            log.msg("slave '%s' attaching from %s" % (slavename, mind.broker.transport.getPeer()))
            return sl

    def stopService(self):
        for b in self.builders.values():
            b.builder_status.addPointEvent(["master", "shutdown"])
            b.builder_status.saveYourself()
        return service.MultiService.stopService(self)

    def getLockByID(self, lockid):
        """Convert a Lock identifier into an actual Lock instance.
        @param lockid: a locks.MasterLock or locks.SlaveLock instance
        @return: a locks.RealMasterLock or locks.RealSlaveLock instance
        """
        assert isinstance(lockid, (locks.MasterLock, locks.SlaveLock))
        if not lockid in self.locks:
            self.locks[lockid] = lockid.lockClass(lockid)
        # if the master.cfg file has changed maxCount= on the lock, the next
        # time a build is started, they'll get a new RealLock instance. Note
        # that this requires that MasterLock and SlaveLock (marker) instances
        # be hashable and that they should compare properly.
        return self.locks[lockid]

    def triggerNewBuildCheck(self):
        # TODO: old name -- should go
        self.loop.trigger()


class DuplicateSlaveArbitrator(object):
    """Utility class to arbitrate the situation when a new slave connects with
    the name of an existing, connected slave"""
    # There are several likely duplicate slave scenarios in practice:
    #
    # 1. two slaves are configured with the same username/password
    #
    # 2. the same slave process believes it is disconnected (due to a network
    # hiccup), and is trying to reconnect
    #
    # For the first case, we want to prevent the two slaves from repeatedly
    # superseding one another (which results in lots of failed builds), so we
    # will prefer the old slave.  However, for the second case we need to
    # detect situations where the old slave is "gone".  Sometimes "gone" means
    # that the TCP/IP connection to it is in a long timeout period (10-20m,
    # depending on the OS configuration), so this can take a while.

    PING_TIMEOUT = 10
    """Timeout for pinging the old slave.  Set this to something quite long, as
    a very busy slave (e.g., one sending a big log chunk) may take a while to
    return a ping."""

    def __init__(self, slave):
        self.old_slave = slave
        "L{buildbot.buildslave.AbstractSlaveBuilder} instance"

    def getPerspective(self, mind, slavename):
        self.new_slave_mind = mind

        old_tport = self.old_slave.slave.broker.transport
        new_tport = mind.broker.transport
        log.msg("duplicate slave %s; delaying new slave (%s) and pinging old (%s)" % 
                (self.old_slave.slavename, new_tport.getPeer(), old_tport.getPeer()))

        # delay the new slave until we decide what to do with it
        self.new_slave_d = defer.Deferred()

        # Ping the old slave.  If this kills it, then we can allow the new
        # slave to connect.  If this does not kill it, then we disconnect
        # the new slave.
        self.ping_old_slave_done = False
        self.old_slave_connected = True
        self.ping_old_slave(new_tport.getPeer())

        # Print a message on the new slave, if possible.
        self.ping_new_slave_done = False
        self.ping_new_slave()

        return self.new_slave_d

    def ping_new_slave(self):
        d = self.new_slave_mind.callRemote("print",
            "master already has a connection named '%s' - checking its liveness"
                        % self.old_slave.slavename)
        def done(_):
            # failure or success, doesn't matter
            self.ping_new_slave_done = True
            self.maybe_done()
        d.addBoth(done)

    def ping_old_slave(self, new_peer):
        # set a timer on this ping, in case the network is bad.  TODO: a timeout
        # on the ping itself is not quite what we want.  If there is other data
        # flowing over the PB connection, then we should keep waiting.  Bug #1703
        def timeout():
            self.ping_old_slave_timeout = None
            self.ping_old_slave_timed_out = True
            self.old_slave_connected = False
            self.ping_old_slave_done = True
            self.maybe_done()
        self.ping_old_slave_timeout = reactor.callLater(self.PING_TIMEOUT, timeout)
        self.ping_old_slave_timed_out = False

        d = self.old_slave.slave.callRemote("print",
            "master got a duplicate connection from %s; keeping this one" % new_peer)

        def clear_timeout(r):
            if self.ping_old_slave_timeout:
                self.ping_old_slave_timeout.cancel()
                self.ping_old_slave_timeout = None
            return r
        d.addBoth(clear_timeout)

        def old_gone(f):
            if self.ping_old_slave_timed_out:
                return # ignore after timeout
            f.trap(pb.PBConnectionLost)
            log.msg(("connection lost while pinging old slave '%s' - " +
                     "keeping new slave") % self.old_slave.slavename)
            self.old_slave_connected = False
        d.addErrback(old_gone)

        def other_err(f):
            if self.ping_old_slave_timed_out:
                return # ignore after timeout
            log.msg("unexpected error while pinging old slave; disconnecting it")
            log.err(f)
            self.old_slave_connected = False
        d.addErrback(other_err)

        def done(_):
            if self.ping_old_slave_timed_out:
                return # ignore after timeout
            self.ping_old_slave_done = True
            self.maybe_done()
        d.addCallback(done)

    def maybe_done(self):
        if not self.ping_new_slave_done or not self.ping_old_slave_done:
            return

        # both pings are done, so sort out the results
        if self.old_slave_connected:
            self.disconnect_new_slave()
        else:
            self.start_new_slave()

    def start_new_slave(self, count=20):
        if not self.new_slave_d:
            return

        # we need to wait until the old slave has actually disconnected, which
        # can take a little while -- but don't wait forever!
        if self.old_slave.isConnected():
            if self.old_slave.slave:
                self.old_slave.slave.broker.transport.loseConnection()
            if count < 0:
                log.msg("WEIRD: want to start new slave, but the old slave will not disconnect")
                self.disconnect_new_slave()
            else:
                reactor.callLater(0.1, self.start_new_slave, count-1)
            return

        d = self.new_slave_d
        self.new_slave_d = None
        d.callback(self.old_slave)

    def disconnect_new_slave(self):
        if not self.new_slave_d:
            return
        d = self.new_slave_d
        self.new_slave_d = None
        log.msg("rejecting duplicate slave with exception")
        d.errback(Failure(RuntimeError("rejecting duplicate slave")))

########################################



class DebugPerspective(NewCredPerspective):
    def attached(self, mind):
        return self
    def detached(self, mind):
        pass

    def perspective_requestBuild(self, buildername, reason, branch, revision, properties={}):
        from buildbot.sourcestamp import SourceStamp
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

    def perspective_setCurrentState(self, buildername, state):
        builder = self.botmaster.builders.get(buildername)
        if not builder: return
        if state == "offline":
            builder.statusbag.currentlyOffline()
        if state == "idle":
            builder.statusbag.currentlyIdle()
        if state == "waiting":
            builder.statusbag.currentlyWaiting(now()+10)
        if state == "building":
            builder.statusbag.currentlyBuilding(None)
    def perspective_reload(self):
        print "doing reload of the config file"
        self.master.loadTheConfigFile()
    def perspective_pokeIRC(self):
        print "saying something on IRC"
        from buildbot.status import words
        for s in self.master:
            if isinstance(s, words.IRC):
                bot = s.f
                for channel in bot.channels:
                    print " channel", channel
                    bot.p.msg(channel, "Ow, quit it")

    def perspective_print(self, msg):
        print "debug", msg

########################################

class _Unset: pass  # marker

class LogRotation: 
    '''holds log rotation parameters (for WebStatus)'''
    def __init__(self):
        self.rotateLength = 1 * 1000 * 1000 
        self.maxRotatedFiles = 10

class BuildMaster(service.MultiService):
    debug = 0
    manhole = None
    debugPassword = None
    projectName = "(unspecified)"
    projectURL = None
    buildbotURL = None
    change_svc = None
    properties = Properties()

    def __init__(self, basedir, configFileName="master.cfg"):
        service.MultiService.__init__(self)
        self.setName("buildmaster")
        self.basedir = basedir
        self.configFileName = configFileName

        self.pbmanager = buildbot.pbmanager.PBManager()
        self.pbmanager.setServiceParent(self)
        "L{buildbot.pbmanager.PBManager} instance managing connections for this master"

        self.slavePortnum = None
        self.slavePort = None

        self.change_svc = ChangeManager()
        self.change_svc.setServiceParent(self)

        try:
            hostname = os.uname()[1] # only on unix
        except AttributeError:
            hostname = "?"
        self.master_name = "%s:%s" % (hostname, os.path.abspath(self.basedir))
        self.master_incarnation = "pid%d-boot%d" % (os.getpid(), time.time())

        self.botmaster = BotMaster(self)
        self.botmaster.setName("botmaster")
        self.botmaster.setMasterName(self.master_name, self.master_incarnation)
        self.botmaster.setServiceParent(self)

        self.scheduler_manager = SchedulerManager(self)
        self.scheduler_manager.setName('scheduler_manager')
        self.scheduler_manager.setServiceParent(self)

        self.debugClientRegistration = None

        self.status = Status(self.botmaster, self.basedir)
        self.statusTargets = []

        self.db = None
        self.db_url = None
        self.db_poll_interval = _Unset

        # note that "read" here is taken in the past participal (i.e., "I read
        # the config already") rather than the imperative ("you should read the
        # config later")
        self.readConfig = False
        
        # create log_rotation object and set default parameters (used by WebStatus)
        self.log_rotation = LogRotation()

        # subscription points
        self._change_subs = \
                subscription.SubscriptionPoint("changes")
        self._new_buildset_subs = \
                subscription.SubscriptionPoint("buildset_additions")
        self._complete_buildset_subs = \
                subscription.SubscriptionPoint("buildset_completion")

    def startService(self):
        service.MultiService.startService(self)
        if not self.readConfig:
            # TODO: consider catching exceptions during this call to
            # loadTheConfigFile and bailing (reactor.stop) if it fails,
            # since without a config file we can't do anything except reload
            # the config file, and it would be nice for the user to discover
            # this quickly.
            self.loadTheConfigFile()
        if hasattr(signal, "SIGHUP"):
            signal.signal(signal.SIGHUP, self._handleSIGHUP)
        for b in self.botmaster.builders.values():
            b.builder_status.addPointEvent(["master", "started"])
            b.builder_status.saveYourself()

    def _handleSIGHUP(self, *args):
        reactor.callLater(0, self.loadTheConfigFile)

    def getStatus(self):
        """
        @rtype: L{buildbot.status.builder.Status}
        """
        return self.status

    def loadTheConfigFile(self, configFile=None):
        if not configFile:
            configFile = os.path.join(self.basedir, self.configFileName)

        log.msg("Creating BuildMaster -- buildbot.version: %s" % buildbot.version)
        log.msg("loading configuration from %s" % configFile)
        configFile = os.path.expanduser(configFile)

        try:
            f = open(configFile, "r")
        except IOError, e:
            log.msg("unable to open config file '%s'" % configFile)
            log.msg("leaving old configuration in place")
            log.err(e)
            return

        try:
            d = self.loadConfig(f)
        except:
            log.msg("error during loadConfig")
            log.err()
            log.msg("The new config file is unusable, so I'll ignore it.")
            log.msg("I will keep using the previous config file instead.")
            return # sorry unit tests
        f.close()
        return d # for unit tests

    def loadConfig(self, f, checkOnly=False):
        """Internal function to load a specific configuration file. Any
        errors in the file will be signalled by raising a failure.  Returns
        a deferred.
        """

        # this entire operation executes in a deferred, so that any exceptions
        # are automatically converted to a failure object.
        d = defer.succeed(None)

        def do_load(_):
            log.msg("configuration update started")

            # execute the config file

            localDict = {'basedir': os.path.expanduser(self.basedir)}
            try:
                exec f in localDict
            except:
                log.msg("error while parsing config file")
                raise

            try:
                config = localDict['BuildmasterConfig']
            except KeyError:
                log.err("missing config dictionary")
                log.err("config file must define BuildmasterConfig")
                raise

            # check for unknown keys

            known_keys = ("slaves", "change_source",
                          "schedulers", "builders", "mergeRequests",
                          "slavePortnum", "debugPassword", "logCompressionLimit",
                          "manhole", "status", "projectName", "projectURL",
                          "buildbotURL", "properties", "prioritizeBuilders",
                          "eventHorizon", "buildCacheSize", "changeCacheSize",
                          "logHorizon", "buildHorizon", "changeHorizon",
                          "logMaxSize", "logMaxTailSize", "logCompressionMethod",
                          "db_url", "multiMaster", "db_poll_interval",
                          )
            for k in config.keys():
                if k not in known_keys:
                    log.msg("unknown key '%s' defined in config dictionary" % k)

            # load known keys into local vars, applying defaults

            try:
                # required
                schedulers = config['schedulers']
                builders = config['builders']
                slavePortnum = config['slavePortnum']
                #slaves = config['slaves']
                #change_source = config['change_source']

                # optional
                db_url = config.get("db_url", "sqlite:///state.sqlite")
                db_poll_interval = config.get("db_poll_interval", None)
                debugPassword = config.get('debugPassword')
                manhole = config.get('manhole')
                status = config.get('status', [])
                projectName = config.get('projectName')
                projectURL = config.get('projectURL')
                buildbotURL = config.get('buildbotURL')
                properties = config.get('properties', {})
                buildCacheSize = config.get('buildCacheSize', None)
                changeCacheSize = config.get('changeCacheSize', None)
                eventHorizon = config.get('eventHorizon', 50)
                logHorizon = config.get('logHorizon', None)
                buildHorizon = config.get('buildHorizon', None)
                logCompressionLimit = config.get('logCompressionLimit', 4*1024)
                if logCompressionLimit is not None and not \
                        isinstance(logCompressionLimit, int):
                    raise ValueError("logCompressionLimit needs to be bool or int")
                logCompressionMethod = config.get('logCompressionMethod', "bz2")
                if logCompressionMethod not in ('bz2', 'gz'):
                    raise ValueError("logCompressionMethod needs to be 'bz2', or 'gz'")
                logMaxSize = config.get('logMaxSize')
                if logMaxSize is not None and not \
                        isinstance(logMaxSize, int):
                    raise ValueError("logMaxSize needs to be None or int")
                logMaxTailSize = config.get('logMaxTailSize')
                if logMaxTailSize is not None and not \
                        isinstance(logMaxTailSize, int):
                    raise ValueError("logMaxTailSize needs to be None or int")
                mergeRequests = config.get('mergeRequests')
                if mergeRequests not in (None, False) and not callable(mergeRequests):
                    raise ValueError("mergeRequests must be a callable or False")
                prioritizeBuilders = config.get('prioritizeBuilders')
                if prioritizeBuilders is not None and not callable(prioritizeBuilders):
                    raise ValueError("prioritizeBuilders must be callable")
                changeHorizon = config.get("changeHorizon")
                if changeHorizon is not None and not isinstance(changeHorizon, int):
                    raise ValueError("changeHorizon needs to be an int")

                multiMaster = config.get("multiMaster", False)

            except KeyError:
                log.msg("config dictionary is missing a required parameter")
                log.msg("leaving old configuration in place")
                raise

            if "sources" in config:
                m = ("c['sources'] is deprecated as of 0.7.6 and is no longer "
                     "accepted in >= 0.8.0 . Please use c['change_source'] instead.")
                raise KeyError(m)

            if "bots" in config:
                m = ("c['bots'] is deprecated as of 0.7.6 and is no longer "
                     "accepted in >= 0.8.0 . Please use c['slaves'] instead.")
                raise KeyError(m)

            slaves = config.get('slaves', [])
            if "slaves" not in config:
                log.msg("config dictionary must have a 'slaves' key")
                log.msg("leaving old configuration in place")
                raise KeyError("must have a 'slaves' key")

            if changeHorizon is not None:
                self.change_svc.changeHorizon = changeHorizon

            change_source = config.get('change_source', [])
            if isinstance(change_source, (list, tuple)):
                change_sources = change_source
            else:
                change_sources = [change_source]

            # do some validation first
            for s in slaves:
                assert interfaces.IBuildSlave.providedBy(s)
                if s.slavename in ("debug", "change", "status"):
                    raise KeyError(
                        "reserved name '%s' used for a bot" % s.slavename)
            if config.has_key('interlocks'):
                raise KeyError("c['interlocks'] is no longer accepted")
            assert self.db_url is None or db_url == self.db_url, \
                    "Cannot change db_url after master has started"
            assert db_poll_interval is None or isinstance(db_poll_interval, int), \
                   "db_poll_interval must be an integer: seconds between polls"
            assert self.db_poll_interval is _Unset or db_poll_interval == self.db_poll_interval, \
                   "Cannot change db_poll_interval after master has started"

            assert isinstance(change_sources, (list, tuple))
            for s in change_sources:
                assert interfaces.IChangeSource(s, None)
            self.checkConfig_Schedulers(schedulers)
            assert isinstance(status, (list, tuple))
            for s in status:
                assert interfaces.IStatusReceiver(s, None)

            slavenames = [s.slavename for s in slaves]
            buildernames = []
            dirnames = []

            # convert builders from objects to config dictionaries
            builders_dicts = []
            for b in builders:
                if isinstance(b, BuilderConfig):
                    builders_dicts.append(b.getConfigDict())
                elif type(b) is dict:
                    builders_dicts.append(b)
                else:
                    raise ValueError("builder %s is not a BuilderConfig object (or a dict)" % b)
            builders = builders_dicts

            for b in builders:
                if b.has_key('slavename') and b['slavename'] not in slavenames:
                    raise ValueError("builder %s uses undefined slave %s" \
                                     % (b['name'], b['slavename']))
                for n in b.get('slavenames', []):
                    if n not in slavenames:
                        raise ValueError("builder %s uses undefined slave %s" \
                                         % (b['name'], n))
                if b['name'] in buildernames:
                    raise ValueError("duplicate builder name %s"
                                     % b['name'])
                buildernames.append(b['name'])

                # sanity check name (BuilderConfig does this too)
                if b['name'].startswith("_"):
                    errmsg = ("builder names must not start with an "
                              "underscore: " + b['name'])
                    log.err(errmsg)
                    raise ValueError(errmsg)

                # Fix the dictionary with default values, in case this wasn't
                # specified with a BuilderConfig object (which sets the same defaults)
                b.setdefault('builddir', safeTranslate(b['name']))
                b.setdefault('slavebuilddir', b['builddir'])
                b.setdefault('buildHorizon', buildHorizon)
                b.setdefault('logHorizon', logHorizon)
                b.setdefault('eventHorizon', eventHorizon)
                if b['builddir'] in dirnames:
                    raise ValueError("builder %s reuses builddir %s"
                                     % (b['name'], b['builddir']))
                dirnames.append(b['builddir'])

            unscheduled_buildernames = buildernames[:]
            schedulernames = []
            for s in schedulers:
                for b in s.listBuilderNames():
                    # Skip checks for builders in multimaster mode
                    if not multiMaster:
                        assert b in buildernames, \
                               "%s uses unknown builder %s" % (s, b)
                    if b in unscheduled_buildernames:
                        unscheduled_buildernames.remove(b)

                if s.name in schedulernames:
                    msg = ("Schedulers must have unique names, but "
                           "'%s' was a duplicate" % (s.name,))
                    raise ValueError(msg)
                schedulernames.append(s.name)

            # Skip the checks for builders in multimaster mode
            if not multiMaster and unscheduled_buildernames:
                log.msg("Warning: some Builders have no Schedulers to drive them:"
                        " %s" % (unscheduled_buildernames,))

            # assert that all locks used by the Builds and their Steps are
            # uniquely named.
            lock_dict = {}
            for b in builders:
                for l in b.get('locks', []):
                    if isinstance(l, locks.LockAccess): # User specified access to the lock
                        l = l.lockid
                    if lock_dict.has_key(l.name):
                        if lock_dict[l.name] is not l:
                            raise ValueError("Two different locks (%s and %s) "
                                             "share the name %s"
                                             % (l, lock_dict[l.name], l.name))
                    else:
                        lock_dict[l.name] = l
                # TODO: this will break with any BuildFactory that doesn't use a
                # .steps list, but I think the verification step is more
                # important.
                for s in b['factory'].steps:
                    for l in s[1].get('locks', []):
                        if isinstance(l, locks.LockAccess): # User specified access to the lock
                            l = l.lockid
                        if lock_dict.has_key(l.name):
                            if lock_dict[l.name] is not l:
                                raise ValueError("Two different locks (%s and %s)"
                                                 " share the name %s"
                                                 % (l, lock_dict[l.name], l.name))
                        else:
                            lock_dict[l.name] = l

            if not isinstance(properties, dict):
                raise ValueError("c['properties'] must be a dictionary")

            # slavePortnum supposed to be a strports specification
            if type(slavePortnum) is int:
                slavePortnum = "tcp:%d" % slavePortnum

            ### ---- everything from here on down is done only on an actual (re)start
            if checkOnly:
                return

            self.projectName = projectName
            self.projectURL = projectURL
            self.buildbotURL = buildbotURL

            self.properties = Properties()
            self.properties.update(properties, self.configFileName)

            self.status.logCompressionLimit = logCompressionLimit
            self.status.logCompressionMethod = logCompressionMethod
            self.status.logMaxSize = logMaxSize
            self.status.logMaxTailSize = logMaxTailSize
            # Update any of our existing builders with the current log parameters.
            # This is required so that the new value is picked up after a
            # reconfig.
            for builder in self.botmaster.builders.values():
                builder.builder_status.setLogCompressionLimit(logCompressionLimit)
                builder.builder_status.setLogCompressionMethod(logCompressionMethod)
                builder.builder_status.setLogMaxSize(logMaxSize)
                builder.builder_status.setLogMaxTailSize(logMaxTailSize)

            if mergeRequests is not None:
                self.botmaster.mergeRequests = mergeRequests
            if prioritizeBuilders is not None:
                self.botmaster.prioritizeBuilders = prioritizeBuilders

            self.buildCacheSize = buildCacheSize
            self.changeCacheSize = changeCacheSize
            self.eventHorizon = eventHorizon
            self.logHorizon = logHorizon
            self.buildHorizon = buildHorizon
            self.slavePortnum = slavePortnum # TODO: move this to master.config.slavePortnum

            # Set up the database
            d.addCallback(lambda res:
                          self.loadConfig_Database(db_url, db_poll_interval))

            # set up slaves
            d.addCallback(lambda res: self.loadConfig_Slaves(slaves))

            # self.manhole
            if manhole != self.manhole:
                # changing
                if self.manhole:
                    # disownServiceParent may return a Deferred
                    d.addCallback(lambda res: self.manhole.disownServiceParent())
                    def _remove(res):
                        self.manhole = None
                        return res
                    d.addCallback(_remove)
                if manhole:
                    def _add(res):
                        self.manhole = manhole
                        manhole.setServiceParent(self)
                    d.addCallback(_add)

            # add/remove self.botmaster.builders to match builders. The
            # botmaster will handle startup/shutdown issues.
            d.addCallback(lambda res: self.loadConfig_Builders(builders))

            d.addCallback(lambda res: self.loadConfig_status(status))

            # Schedulers are added after Builders in case they start right away
            d.addCallback(lambda _: self.loadConfig_Schedulers(schedulers))

            # and Sources go after Schedulers for the same reason
            d.addCallback(lambda res: self.loadConfig_Sources(change_sources))

            # debug client
            d.addCallback(lambda res: self.loadConfig_DebugClient(debugPassword))

        d.addCallback(do_load)

        def _done(res):
            self.readConfig = True
            log.msg("configuration update complete")
        # the remainder is only done if we are really loading the config
        if not checkOnly:
            d.addCallback(_done)
            # trigger the bostmaster to try to start builds
            d.addCallback(lambda _: self.botmaster.loop.trigger())
            d.addErrback(log.err)
        return d

    def loadDatabase(self, db_url, db_poll_interval=None):
        if self.db:
            return

        self.db = connector.DBConnector(self, db_url, self.basedir)
        if self.changeCacheSize:
            pass # TODO: set this in self.db.changes, or in self.config?
        self.db.start()

        # make sure it's up to date
        d = self.db.model.is_current()
        def check_current(res):
            if res:
                return # good to go!
            raise exceptions.DatabaseNotReadyError, textwrap.dedent("""
                The Buildmaster database needs to be upgraded before this version of buildbot
                can run.  Use the following command-line
                    buildbot upgrade-master path/to/master
                to upgrade the database, and try starting the buildmaster again.  You may want
                to make a backup of your buildmaster before doing so.  If you are using MySQL,
                you must specify the connector string on the upgrade-master command line:
                    buildbot upgrade-master --db=<db-url> path/to/master
                """)
        d.addCallback(check_current)

        # set up the stuff that depends on the db
        def set_up_db_dependents(r):
            # TODO: these need to go
            self.botmaster.db = self.db
            self.status.setDB(self.db)

            # subscribe the various parts of the system to changes
            self._change_subs.subscribe(self.status.changeAdded)
            self._new_buildset_subs.subscribe(
                    lambda **kwargs : self.botmaster.loop.trigger())

            # Set db_poll_interval (perhaps to 30 seconds) if you are using
            # multiple buildmasters that share a common database, such that the
            # masters need to discover what each other is doing by polling the
            # database.
            if db_poll_interval:
                t1 = TimerService(db_poll_interval, self.pollDatabase)
                t1.setServiceParent(self)
                t2 = TimerService(db_poll_interval, self.botmaster.loop.trigger)
                t2.setServiceParent(self)
            # adding schedulers (like when loadConfig happens) will trigger the
            # scheduler loop at least once, which we need to jump-start things
            # like Periodic.
        d.addCallback(set_up_db_dependents)
        return d

    def loadConfig_Database(self, db_url, db_poll_interval):
        self.db_url = db_url
        self.db_poll_interval = db_poll_interval
        return self.loadDatabase(db_url, db_poll_interval)

    def loadConfig_Slaves(self, new_slaves):
        return self.botmaster.loadConfig_Slaves(new_slaves)

    def loadConfig_Sources(self, sources):
        if not sources:
            log.msg("warning: no ChangeSources specified in c['change_source']")
        # shut down any that were removed, start any that were added
        deleted_sources = [s for s in self.change_svc if s not in sources]
        added_sources = [s for s in sources if s not in self.change_svc]
        log.msg("adding %d new changesources, removing %d" %
                (len(added_sources), len(deleted_sources)))
        dl = [self.change_svc.removeSource(s) for s in deleted_sources]
        def addNewOnes(res):
            [self.change_svc.addSource(s) for s in added_sources]
        d = defer.DeferredList(dl, fireOnOneErrback=1, consumeErrors=0)
        d.addCallback(addNewOnes)
        return d

    def loadConfig_DebugClient(self, debugPassword):
        def makeDbgPerspective():
            persp = DebugPerspective()
            persp.master = self
            persp.botmaster = self.botmaster
            return persp

        # unregister the old name..
        if self.debugClientRegistration:
            d = self.debugClientRegistration.unregister()
            self.debugClientRegistration = None
        else:
            d = defer.succeed(None)

        # and register the new one
        def reg(_):
            if debugPassword:
                self.debugClientRegistration = self.pbmanager.register(
                        self.slavePortnum, "debug", debugPassword, makeDbgPerspective)
        d.addCallback(reg)
        return d

    def allSchedulers(self):
        return list(self.scheduler_manager)

    def loadConfig_Builders(self, newBuilderData):
        somethingChanged = False
        newList = {}
        newBuilderNames = []
        allBuilders = self.botmaster.builders.copy()
        for data in newBuilderData:
            name = data['name']
            newList[name] = data
            newBuilderNames.append(name)

        # identify all that were removed
        for oldname in self.botmaster.getBuildernames():
            if oldname not in newList:
                log.msg("removing old builder %s" % oldname)
                del allBuilders[oldname]
                somethingChanged = True
                # announce the change
                self.status.builderRemoved(oldname)

        # everything in newList is either unchanged, changed, or new
        for name, data in newList.items():
            old = self.botmaster.builders.get(name)
            basedir = data['builddir']
            #name, slave, builddir, factory = data
            if not old: # new
                # category added after 0.6.2
                category = data.get('category', None)
                log.msg("adding new builder %s for category %s" %
                        (name, category))
                statusbag = self.status.builderAdded(name, basedir, category)
                builder = Builder(data, statusbag)
                allBuilders[name] = builder
                somethingChanged = True
            elif old.compareToSetup(data):
                # changed: try to minimize the disruption and only modify the
                # pieces that really changed
                diffs = old.compareToSetup(data)
                log.msg("updating builder %s: %s" % (name, "\n".join(diffs)))

                statusbag = old.builder_status
                statusbag.saveYourself() # seems like a good idea
                # TODO: if the basedir was changed, we probably need to make
                # a new statusbag
                new_builder = Builder(data, statusbag)
                new_builder.consumeTheSoulOfYourPredecessor(old)
                # that migrates any retained slavebuilders too

                # point out that the builder was updated. On the Waterfall,
                # this will appear just after any currently-running builds.
                statusbag.addPointEvent(["config", "updated"])

                allBuilders[name] = new_builder
                somethingChanged = True
            else:
                # unchanged: leave it alone
                log.msg("builder %s is unchanged" % name)
                pass

        # regardless of whether anything changed, get each builder status
        # to update its config
        for builder in allBuilders.values():
            builder.builder_status.reconfigFromBuildmaster(self)

        # and then tell the botmaster if anything's changed
        if somethingChanged:
            sortedAllBuilders = [allBuilders[name] for name in newBuilderNames]
            d = self.botmaster.setBuilders(sortedAllBuilders)
            return d
        return None

    def loadConfig_status(self, status):
        dl = []

        # remove old ones
        for s in self.statusTargets[:]:
            if not s in status:
                log.msg("removing IStatusReceiver", s)
                d = defer.maybeDeferred(s.disownServiceParent)
                dl.append(d)
                self.statusTargets.remove(s)
        # after those are finished going away, add new ones
        def addNewOnes(res):
            for s in status:
                if not s in self.statusTargets:
                    log.msg("adding IStatusReceiver", s)
                    s.setServiceParent(self)
                    self.statusTargets.append(s)
        d = defer.DeferredList(dl, fireOnOneErrback=1)
        d.addCallback(addNewOnes)
        return d

    def checkConfig_Schedulers(self, schedulers):
        # this assertion catches c['schedulers'] = Scheduler(), since
        # Schedulers are service.MultiServices and thus iterable.
        errmsg = "c['schedulers'] must be a list of Scheduler instances"
        assert isinstance(schedulers, (list, tuple)), errmsg
        for s in schedulers:
            assert isScheduler(s), errmsg

    def loadConfig_Schedulers(self, schedulers):
        return self.scheduler_manager.updateSchedulers(schedulers)

    ## triggering methods and subscriptions

    def addChange(self, **kwargs):
        """Add a change to the buildmaster and act on it.  Interface is
        identical to
        L{buildbot.db.changes.ChangesConnectorComponent.addChange}, including
        returning a deferred, but also triggers schedulers to examine the
        change."""
        d = self.db.changes.addChange(**kwargs)
        def notify(change):
            msg = u"added change %s to database" % change
            log.msg(msg.encode('utf-8', 'replace'))
            # only deliver messages immediately if we're not polling
            if not self.db_poll_interval:
                self._change_subs.deliver(change)
            return change
        d.addCallback(notify)
        return d

    def subscribeToChanges(self, callback):
        """
        Request that C{callback} be called with each Change object added to the
        cluster.

        Note: this method will go away in 0.9.x
        """
        return self._change_subs.subscribe(callback)

    def addBuildset(self, **kwargs):
        """
        Add a buildset to the buildmaster and act on it.  Interface is
        identical to
        L{buildbot.db.buildsets.BuildsetConnectorComponent.addBuildset},
        including returning a Deferred, but also potentially triggers the
        resulting builds.
        """
        d = self.db.buildsets.addBuildset(**kwargs)
        def notify(bsid):
            log.msg("added buildset %d to database" % bsid)
            # note that buildset additions are only reported on this master
            self._new_buildset_subs.deliver(bsid=bsid, **kwargs)
            return bsid
        d.addCallback(notify)
        return d

    def subscribeToBuildsets(self, callback):
        """
        Request that C{callback(bsid=bsid, ssid=ssid, reason=reason,
        properties=properties, builderNames=builderNames,
        external_idstring=external_idstring)} be called whenever a buildset is
        added.

        Note: this method will go away in 0.9.x
        """
        return self._new_buildset_subs.subscribe(callback)

    def buildsetComplete(self, bsid, result):
        """
        Notifies the master that the given buildset with ID C{bsid} is
        complete, with result C{result}.
        """
        # note that buildset completions are only reported on this master
        self._complete_buildset_subs.deliver(bsid, result)

    def subscribeToBuildsetCompletions(self, callback):
        """
        Request that C{callback(bsid, result)} be called whenever a
        buildset is complete.

        Note: this method will go away in 0.9.x
        """
        return self._complete_buildset_subs.subscribe(callback)

    ## database polling

    def pollDatabase(self):
        # poll each of the tables that can indicate new, actionable stuff for
        # this buildmaster to do.  This is used in a TimerService, so returning
        # a Deferred means that we won't run two polling operations
        # simultaneously.  Each particular poll method handles errors itself.
        return defer.gatherResults([
            # only changes at the moment
            self.pollDatabaseChanges(),
        ])

    _last_processed_change = None
    @defer.deferredGenerator
    def pollDatabaseChanges(self):
        # Older versions of Buildbot had each scheduler polling the database
        # independently, and storing a "last_processed" state indicating the
        # last change it had processed.  This had the advantage of allowing
        # schedulers to pick up changes that arrived in the database while
        # the scheduler was not running, but was horribly inefficient.

        # This version polls the database on behalf of the schedulers, using a
        # similar state at the master level.

        need_setState = False

        # get the last processed change id
        if self._last_processed_change is None:
            wfd = defer.waitForDeferred(
                self._getState('last_processed_change'))
            yield wfd
            self._last_processed_change = wfd.getResult()

        # if it's still None, assume we've processed up to the latest changeid
        if self._last_processed_change is None:
            wfd = defer.waitForDeferred(
                self.db.changes.getLatestChangeid())
            yield wfd
            self._last_processed_change = wfd.getResult()
            need_setState = True

        if self._last_processed_change is None:
            return

        while True:
            changeid = self._last_processed_change + 1
            wfd = defer.waitForDeferred(
                self.db.changes.getChangeInstance(changeid))
            yield wfd
            change = wfd.getResult()

            # if there's no such change, we've reached the end and can
            # stop polling
            if not change:
                break

            self._change_subs.deliver(change)

            self._last_processed_change = changeid
            need_setState = True

        # write back the updated state, if it's changed
        if need_setState:
            wfd = defer.waitForDeferred(
                self._setState('last_processed_change',
                               self._last_processed_change))
            yield wfd
            wfd.getResult()

    ## state maintenance (private)

    _master_objectid = None

    def _getObjectId(self):
        if self._master_objectid is None:
            d = self.db.state.getObjectId('master',
                                    'buildbot.master.BuildMaster')
            def keep(objectid):
                self._master_objectid = objectid
                return objectid
            d.addCallback(keep)
            return d
        return defer.succeed(self._master_objectid)

    def _getState(self, name, default=None):
        "private wrapper around C{self.db.state.getState}"
        d = self._getObjectId()
        def get(objectid):
            return self.db.state.getState(self._master_objectid, name, default)
        d.addCallback(get)
        return d

    def _setState(self, name, value):
        "private wrapper around C{self.db.state.setState}"
        d = self._getObjectId()
        def set(objectid):
            return self.db.state.setState(self._master_objectid, name, value)
        d.addCallback(set)
        return d

class Control:
    implements(interfaces.IControl)

    def __init__(self, master):
        self.master = master

    def addChange(self, change):
        self.master.addChange(change)

    def addBuildset(self, **kwargs):
        return self.master.addBuildset(**kwargs)

    def getBuilder(self, name):
        b = self.master.botmaster.builders[name]
        return BuilderControl(b, self)

components.registerAdapter(Control, BuildMaster, interfaces.IControl)
