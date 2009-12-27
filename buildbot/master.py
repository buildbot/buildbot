# -*- test-case-name: buildbot.test.test_run -*-

import os
signal = None
try:
    import signal
except ImportError:
    pass
from cPickle import load
import warnings

from zope.interface import implements
from twisted.python import log, components
from twisted.python.failure import Failure
from twisted.internet import defer, reactor
from twisted.spread import pb
from twisted.cred import portal, checkers
from twisted.application import service, strports
from twisted.persisted import styles

import buildbot
# sibling imports
from buildbot.util import now, safeTranslate
from buildbot.pbutil import NewCredPerspective
from buildbot.process.builder import Builder, IDLE
from buildbot.process.base import BuildRequest
from buildbot.status.builder import Status
from buildbot.changes.changes import Change, ChangeMaster, TestChangeMaster
from buildbot.sourcestamp import SourceStamp
from buildbot.buildslave import BuildSlave
from buildbot import interfaces, locks
from buildbot.process.properties import Properties
from buildbot.config import BuilderConfig

########################################

class BotMaster(service.MultiService):

    """This is the master-side service which manages remote buildbot slaves.
    It provides them with BuildSlaves, and distributes file change
    notification messages to them.
    """

    debug = 0

    def __init__(self):
        service.MultiService.__init__(self)
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
        self.statusClientService = None
        self.watchers = {}

        # self.locks holds the real Lock instances
        self.locks = {}

        # self.mergeRequests is the callable override for merging build
        # requests
        self.mergeRequests = None

        # self.prioritizeBuilders is the callable override for builder order
        # traversal
        self.prioritizeBuilders = None

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
        def _add(res):
            for s in added:
                self.addSlave(s)
            for t in remaining_t:
                old_t[t].update(new_t[t])
        d.addCallback(_add)
        return d

    def addSlave(self, s):
        s.setServiceParent(self)
        s.setBotmaster(self)
        self.slaves[s.slavename] = s

    def removeSlave(self, s):
        # TODO: technically, disownServiceParent could return a Deferred
        s.disownServiceParent()
        d = self.slaves[s.slavename].disconnect()
        del self.slaves[s.slavename]
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
        self.builders = {}
        self.builderNames = []
        for b in builders:
            for slavename in b.slavenames:
                # this is actually validated earlier
                assert slavename in self.slaves
            self.builders[b.name] = b
            self.builderNames.append(b.name)
            b.setBotmaster(self)
        d = self._updateAllSlaves()
        return d

    def _updateAllSlaves(self):
        """Notify all buildslaves about changes in their Builders."""
        dl = [s.updateSlave() for s in self.slaves.values()]
        return defer.DeferredList(dl)

    def maybeStartAllBuilds(self):
        builders = self.builders.values()
        if self.prioritizeBuilders is not None:
            try:
                builders = self.prioritizeBuilders(self.parent, builders)
            except:
                log.msg("Exception prioritizing builders")
                log.err(Failure())
                return
        else:
            def _sortfunc(b1, b2):
                t1 = b1.getOldestRequestTime()
                t2 = b2.getOldestRequestTime()
                # If t1 or t2 is None, then there are no build requests,
                # so sort it at the end
                if t1 is None:
                    return 1
                if t2 is None:
                    return -1
                return cmp(t1, t2)
            builders.sort(_sortfunc)
        try:
            for b in builders:
                b.maybeStartBuild()
        except:
            log.msg("Exception starting builds")
            log.err(Failure())

    def shouldMergeRequests(self, builder, req1, req2):
        """Determine whether two BuildRequests should be merged for
        the given builder.

        """
        if self.mergeRequests is not None:
            return self.mergeRequests(builder, req1, req2)
        return req1.canBeMergedWith(req2)

    def getPerspective(self, slavename):
        return self.slaves[slavename]

    def shutdownSlaves(self):
        # TODO: make this into a bot method rather than a builder method
        for b in self.slaves.values():
            b.shutdownSlave()

    def stopService(self):
        for b in self.builders.values():
            b.builder_status.addPointEvent(["master", "shutdown"])
            b.builder_status.saveYourself()
        return service.Service.stopService(self)

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

########################################



class DebugPerspective(NewCredPerspective):
    def attached(self, mind):
        return self
    def detached(self, mind):
        pass

    def perspective_requestBuild(self, buildername, reason, branch, revision, properties={}):
        c = interfaces.IControl(self.master)
        bc = c.getBuilder(buildername)
        ss = SourceStamp(branch, revision)
        bpr = Properties()
        bpr.update(properties, "remote requestBuild")
        br = BuildRequest(reason, ss, builderName=buildername, properties=bpr)
        bc.requestBuild(br)

    def perspective_pingBuilder(self, buildername):
        c = interfaces.IControl(self.master)
        bc = c.getBuilder(buildername)
        bc.ping()

    def perspective_fakeChange(self, file, revision=None, who="fakeUser",
                               branch=None):
        change = Change(who, [file], "some fake comments\n",
                        branch=branch, revision=revision)
        c = interfaces.IControl(self.master)
        c.addChange(change)

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

class Dispatcher:
    implements(portal.IRealm)

    def __init__(self):
        self.names = {}

    def register(self, name, afactory):
        self.names[name] = afactory
    def unregister(self, name):
        del self.names[name]

    def requestAvatar(self, avatarID, mind, interface):
        assert interface == pb.IPerspective
        afactory = self.names.get(avatarID)
        if afactory:
            p = afactory.getPerspective()
        elif avatarID == "debug":
            p = DebugPerspective()
            p.master = self.master
            p.botmaster = self.botmaster
        elif avatarID == "statusClient":
            p = self.statusClientService.getPerspective()
        else:
            # it must be one of the buildslaves: no other names will make it
            # past the checker
            p = self.botmaster.getPerspective(avatarID)

        if not p:
            raise ValueError("no perspective for '%s'" % avatarID)

        d = defer.maybeDeferred(p.attached, mind)
        d.addCallback(self._avatarAttached, mind)
        return d

    def _avatarAttached(self, p, mind):
        return (pb.IPerspective, p, lambda p=p,mind=mind: p.detached(mind))

########################################

# service hierarchy:
#  BuildMaster
#   BotMaster
#   ChangeMaster
#    all IChangeSource objects
#   StatusClientService
#   TCPClient(self.ircFactory)
#   TCPServer(self.slaveFactory) -> dispatcher.requestAvatar
#   TCPServer(self.site)
#   UNIXServer(ResourcePublisher(self.site))


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

        # the dispatcher is the realm in which all inbound connections are
        # looked up: slave builders, change notifications, status clients, and
        # the debug port
        dispatcher = Dispatcher()
        dispatcher.master = self
        self.dispatcher = dispatcher
        self.checker = checkers.InMemoryUsernamePasswordDatabaseDontUse()
        # the checker starts with no user/passwd pairs: they are added later
        p = portal.Portal(dispatcher)
        p.registerChecker(self.checker)
        self.slaveFactory = pb.PBServerFactory(p)
        self.slaveFactory.unsafeTracebacks = True # let them see exceptions

        self.slavePortnum = None
        self.slavePort = None

        self.botmaster = BotMaster()
        self.botmaster.setName("botmaster")
        self.botmaster.setServiceParent(self)
        dispatcher.botmaster = self.botmaster

        self.status = Status(self.botmaster, self.basedir)

        self.statusTargets = []

        # this ChangeMaster is a dummy, only used by tests. In the real
        # buildmaster, where the BuildMaster instance is activated
        # (startService is called) by twistd, this attribute is overwritten.
        self.useChanges(TestChangeMaster())

        self.readConfig = False

    def startService(self):
        service.MultiService.startService(self)
        self.loadChanges() # must be done before loading the config file
        if not self.readConfig:
            # TODO: consider catching exceptions during this call to
            # loadTheConfigFile and bailing (reactor.stop) if it fails,
            # since without a config file we can't do anything except reload
            # the config file, and it would be nice for the user to discover
            # this quickly.
            self.loadTheConfigFile()
        if signal and hasattr(signal, "SIGHUP"):
            signal.signal(signal.SIGHUP, self._handleSIGHUP)
        for b in self.botmaster.builders.values():
            b.builder_status.addPointEvent(["master", "started"])
            b.builder_status.saveYourself()

    def useChanges(self, changes):
        if self.change_svc:
            # TODO: can return a Deferred
            self.change_svc.disownServiceParent()
        self.change_svc = changes
        self.change_svc.basedir = self.basedir
        self.change_svc.setName("changemaster")
        self.dispatcher.changemaster = self.change_svc
        self.change_svc.setServiceParent(self)

    def loadChanges(self):
        filename = os.path.join(self.basedir, "changes.pck")
        try:
            changes = load(open(filename, "rb"))
            styles.doUpgrade()
        except IOError:
            log.msg("changes.pck missing, using new one")
            changes = ChangeMaster()
        except EOFError:
            log.msg("corrupted changes.pck, using new one")
            changes = ChangeMaster()
        self.useChanges(changes)

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
            self.loadConfig(f)
        except:
            log.msg("error during loadConfig")
            log.err()
            log.msg("The new config file is unusable, so I'll ignore it.")
            log.msg("I will keep using the previous config file instead.")
        f.close()

    def loadConfig(self, f):
        """Internal function to load a specific configuration file. Any
        errors in the file will be signalled by raising an exception.

        @return: a Deferred that will fire (with None) when the configuration
        changes have been completed. This may involve a round-trip to each
        buildslave that was involved."""

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

        known_keys = ("bots", "slaves",
                      "sources", "change_source",
                      "schedulers", "builders", "mergeRequests",
                      "slavePortnum", "debugPassword", "logCompressionLimit",
                      "manhole", "status", "projectName", "projectURL",
                      "buildbotURL", "properties", "prioritizeBuilders",
                      "eventHorizon", "buildCacheSize", "logHorizon", "buildHorizon",
                      "changeHorizon", "logMaxSize", "logMaxTailSize",
                      "logCompressionMethod",
                      )
        for k in config.keys():
            if k not in known_keys:
                log.msg("unknown key '%s' defined in config dictionary" % k)

        try:
            # required
            schedulers = config['schedulers']
            builders = config['builders']
            slavePortnum = config['slavePortnum']
            #slaves = config['slaves']
            #change_source = config['change_source']

            # optional
            debugPassword = config.get('debugPassword')
            manhole = config.get('manhole')
            status = config.get('status', [])
            projectName = config.get('projectName')
            projectURL = config.get('projectURL')
            buildbotURL = config.get('buildbotURL')
            properties = config.get('properties', {})
            buildCacheSize = config.get('buildCacheSize', None)
            eventHorizon = config.get('eventHorizon', None)
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
            if mergeRequests is not None and not callable(mergeRequests):
                raise ValueError("mergeRequests must be a callable")
            prioritizeBuilders = config.get('prioritizeBuilders')
            if prioritizeBuilders is not None and not callable(prioritizeBuilders):
                raise ValueError("prioritizeBuilders must be callable")
            changeHorizon = config.get("changeHorizon")
            if changeHorizon is not None and not isinstance(changeHorizon, int):
                raise ValueError("changeHorizon needs to be an int")

        except KeyError, e:
            log.msg("config dictionary is missing a required parameter")
            log.msg("leaving old configuration in place")
            raise

        #if "bots" in config:
        #    raise KeyError("c['bots'] is no longer accepted")

        slaves = config.get('slaves', [])
        if "bots" in config:
            m = ("c['bots'] is deprecated as of 0.7.6 and will be "
                 "removed by 0.8.0 . Please use c['slaves'] instead.")
            log.msg(m)
            warnings.warn(m, DeprecationWarning)
            for name, passwd in config['bots']:
                slaves.append(BuildSlave(name, passwd))

        if "bots" not in config and "slaves" not in config:
            log.msg("config dictionary must have either 'bots' or 'slaves'")
            log.msg("leaving old configuration in place")
            raise KeyError("must have either 'bots' or 'slaves'")

        #if "sources" in config:
        #    raise KeyError("c['sources'] is no longer accepted")

        if changeHorizon is not None:
            self.change_svc.changeHorizon = changeHorizon

        change_source = config.get('change_source', [])
        if isinstance(change_source, (list, tuple)):
            change_sources = change_source
        else:
            change_sources = [change_source]
        if "sources" in config:
            m = ("c['sources'] is deprecated as of 0.7.6 and will be "
                 "removed by 0.8.0 . Please use c['change_source'] instead.")
            log.msg(m)
            warnings.warn(m, DeprecationWarning)
            for s in config['sources']:
                change_sources.append(s)

        # do some validation first
        for s in slaves:
            assert interfaces.IBuildSlave.providedBy(s)
            if s.slavename in ("debug", "change", "status"):
                raise KeyError(
                    "reserved name '%s' used for a bot" % s.slavename)
        if config.has_key('interlocks'):
            raise KeyError("c['interlocks'] is no longer accepted")

        assert isinstance(change_sources, (list, tuple))
        for s in change_sources:
            assert interfaces.IChangeSource(s, None)
        # this assertion catches c['schedulers'] = Scheduler(), since
        # Schedulers are service.MultiServices and thus iterable.
        errmsg = "c['schedulers'] must be a list of Scheduler instances"
        assert isinstance(schedulers, (list, tuple)), errmsg
        for s in schedulers:
            assert interfaces.IScheduler(s, None), errmsg
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

            # Fix the dictionnary with default values, in case this wasn't
            # specified with a BuilderConfig object (which sets the same defaults)
            b.setdefault('builddir', safeTranslate(b['name']))
            b.setdefault('slavebuilddir', b['builddir'])

            if b['builddir'] in dirnames:
                raise ValueError("builder %s reuses builddir %s"
                                 % (b['name'], b['builddir']))
            dirnames.append(b['builddir'])

        unscheduled_buildernames = buildernames[:]
        schedulernames = []
        for s in schedulers:
            for b in s.listBuilderNames():
                assert b in buildernames, \
                       "%s uses unknown builder %s" % (s, b)
                if b in unscheduled_buildernames:
                    unscheduled_buildernames.remove(b)

            if s.name in schedulernames:
                # TODO: schedulers share a namespace with other Service
                # children of the BuildMaster node, like status plugins, the
                # Manhole, the ChangeMaster, and the BotMaster (although most
                # of these don't have names)
                msg = ("Schedulers must have unique names, but "
                       "'%s' was a duplicate" % (s.name,))
                raise ValueError(msg)
            schedulernames.append(s.name)

        if unscheduled_buildernames:
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

        # now we're committed to implementing the new configuration, so do
        # it atomically
        # TODO: actually, this is spread across a couple of Deferreds, so it
        # really isn't atomic.

        d = defer.succeed(None)

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
        self.eventHorizon = eventHorizon
        self.logHorizon = logHorizon
        self.buildHorizon = buildHorizon

        # self.slaves: Disconnect any that were attached and removed from the
        # list. Update self.checker with the new list of passwords, including
        # debug/change/status.
        d.addCallback(lambda res: self.loadConfig_Slaves(slaves))

        # self.debugPassword
        if debugPassword:
            self.checker.addUser("debug", debugPassword)
            self.debugPassword = debugPassword

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
        d.addCallback(lambda res: self.loadConfig_Schedulers(schedulers))
        # and Sources go after Schedulers for the same reason
        d.addCallback(lambda res: self.loadConfig_Sources(change_sources))

        # self.slavePort
        if self.slavePortnum != slavePortnum:
            if self.slavePort:
                def closeSlavePort(res):
                    d1 = self.slavePort.disownServiceParent()
                    self.slavePort = None
                    return d1
                d.addCallback(closeSlavePort)
            if slavePortnum is not None:
                def openSlavePort(res):
                    self.slavePort = strports.service(slavePortnum,
                                                      self.slaveFactory)
                    self.slavePort.setServiceParent(self)
                d.addCallback(openSlavePort)
                log.msg("BuildMaster listening on port %s" % slavePortnum)
            self.slavePortnum = slavePortnum

        log.msg("configuration update started")
        def _done(res):
            self.readConfig = True
            log.msg("configuration update complete")
        d.addCallback(_done)
        d.addCallback(lambda res: self.botmaster.maybeStartAllBuilds())
        return d

    def loadConfig_Slaves(self, new_slaves):
        # set up the Checker with the names and passwords of all valid bots
        self.checker.users = {} # violates abstraction, oh well
        for s in new_slaves:
            self.checker.addUser(s.slavename, s.password)
        self.checker.addUser("change", "changepw")
        # let the BotMaster take care of the rest
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

    def allSchedulers(self):
        return [child for child in self
                if interfaces.IScheduler.providedBy(child)]


    def loadConfig_Schedulers(self, newschedulers):
        oldschedulers = self.allSchedulers()
        removed = [s for s in oldschedulers if s not in newschedulers]
        added = [s for s in newschedulers if s not in oldschedulers]
        dl = [defer.maybeDeferred(s.disownServiceParent) for s in removed]
        def addNewOnes(res):
            log.msg("adding %d new schedulers, removed %d" % 
                    (len(added), len(dl)))
            for s in added:
                s.setServiceParent(self)
        d = defer.DeferredList(dl, fireOnOneErrback=1)
        d.addCallback(addNewOnes)
        if removed or added:
            # notify Downstream schedulers to potentially pick up
            # new schedulers now that we have removed and added some
            def updateDownstreams(res):
                log.msg("notifying downstream schedulers of changes")
                for s in newschedulers:
                    if interfaces.IDownstreamScheduler.providedBy(s):
                        s.checkUpstreamScheduler()
            d.addCallback(updateDownstreams)
        return d

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


    def addChange(self, change):
        for s in self.allSchedulers():
            s.addChange(change)

    def submitBuildSet(self, bs):
        # determine the set of Builders to use
        builders = []
        for name in bs.builderNames:
            b = self.botmaster.builders.get(name)
            if b:
                if b not in builders:
                    builders.append(b)
                continue
            # TODO: add aliases like 'all'
            raise KeyError("no such builder named '%s'" % name)

        # now tell the BuildSet to create BuildRequests for all those
        # Builders and submit them
        bs.start(builders)
        self.status.buildsetSubmitted(bs.status)


class Control:
    implements(interfaces.IControl)

    def __init__(self, master):
        self.master = master

    def addChange(self, change):
        self.master.change_svc.addChange(change)

    def submitBuildSet(self, bs):
        self.master.submitBuildSet(bs)

    def getBuilder(self, name):
        b = self.master.botmaster.builders[name]
        return interfaces.IBuilderControl(b)

components.registerAdapter(Control, BuildMaster, interfaces.IControl)

# so anybody who can get a handle on the BuildMaster can cause a build with:
#  IControl(master).getBuilder("full-2.3").requestBuild(buildrequest)
