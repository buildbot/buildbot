
import random, weakref
from zope.interface import implements
from twisted.python import log
from twisted.python.failure import Failure
from twisted.spread import pb
from twisted.application import service, internet
from twisted.internet import defer

from buildbot import interfaces, util
from buildbot.status.progress import Expectations
from buildbot.status.builder import RETRY
from buildbot.process.properties import Properties
from buildbot.util.eventual import eventually

(ATTACHING, # slave attached, still checking hostinfo/etc
 IDLE, # idle, available for use
 PINGING, # build about to start, making sure it is still alive
 BUILDING, # build is running
 LATENT, # latent slave is not substantiated; similar to idle
 SUBSTANTIATING,
 ) = range(6)


class AbstractSlaveBuilder(pb.Referenceable):
    """I am the master-side representative for one of the
    L{buildbot.slave.bot.SlaveBuilder} objects that lives in a remote
    buildbot. When a remote builder connects, I query it for command versions
    and then make it available to any Builds that are ready to run. """

    def __init__(self):
        self.ping_watchers = []
        self.state = None # set in subclass
        self.remote = None
        self.slave = None
        self.builder_name = None

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
        self.builder.triggerNewBuildCheck()

    def attached(self, slave, remote, commands):
        """
        @type  slave: L{buildbot.buildslave.BuildSlave}
        @param slave: the BuildSlave that represents the buildslave as a
                      whole
        @type  remote: L{twisted.spread.pb.RemoteReference}
        @param remote: a reference to the L{buildbot.slave.bot.SlaveBuilder}
        @type  commands: dict: string -> string, or None
        @param commands: provides the slave's version of each RemoteCommand
        """
        self.state = ATTACHING
        self.remote = remote
        self.remoteCommands = commands # maps command name to version
        if self.slave is None:
            self.slave = slave
            self.slave.addSlaveBuilder(self)
        else:
            assert self.slave == slave
        log.msg("Buildslave %s attached to %s" % (slave.slavename,
                                                  self.builder_name))
        d = self.remote.callRemote("setMaster", self)
        d.addErrback(self._attachFailure, "Builder.setMaster")
        d.addCallback(self._attached2)
        return d

    def _attached2(self, res):
        d = self.remote.callRemote("print", "attached")
        d.addErrback(self._attachFailure, "Builder.print 'attached'")
        d.addCallback(self._attached3)
        return d

    def _attached3(self, res):
        # now we say they're really attached
        self.state = IDLE
        return self

    def _attachFailure(self, why, where):
        assert isinstance(where, str)
        log.msg(where)
        log.err(why)
        return why

    def prepare(self, builder_status):
        return defer.succeed(None)

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
            Ping().ping(self.remote).addCallback(self._pong)

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
        self.remote = None
        self.remoteCommands = None


class Ping:
    running = False

    def ping(self, remote):
        assert not self.running
        if not remote:
            # clearly the ping must fail
            return defer.succeed(False)
        self.running = True
        log.msg("sending ping")
        self.d = defer.Deferred()
        # TODO: add a distinct 'ping' command on the slave.. using 'print'
        # for this purpose is kind of silly.
        remote.callRemote("print", "ping").addCallbacks(self._pong,
                                                        self._ping_failed,
                                                        errbackArgs=(remote,))
        return self.d

    def _pong(self, res):
        log.msg("ping finished: success")
        self.d.callback(True)

    def _ping_failed(self, res, remote):
        log.msg("ping finished: failure")
        # the slave has some sort of internal error, disconnect them. If we
        # don't, we'll requeue a build and ping them again right away,
        # creating a nasty loop.
        remote.broker.transport.loseConnection()
        # TODO: except, if they actually did manage to get this far, they'll
        # probably reconnect right away, and we'll do this game again. Maybe
        # it would be better to leave them in the PINGING state.
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

    def buildFinished(self):
        # Call the slave's buildFinished if we can; the slave may be waiting
        # to do a graceful shutdown and needs to know when it's idle.
        # After, we check to see if we can start other builds.
        self.state = IDLE
        if self.slave:
            d = self.slave.buildFinished(self)
            d.addCallback(lambda x: self.builder.triggerNewBuildCheck())
        else:
            self.builder.triggerNewBuildCheck()


class LatentSlaveBuilder(AbstractSlaveBuilder):
    def __init__(self, slave, builder):
        AbstractSlaveBuilder.__init__(self)
        self.slave = slave
        self.state = LATENT
        self.setBuilder(builder)
        self.slave.addSlaveBuilder(self)
        log.msg("Latent buildslave %s attached to %s" % (slave.slavename,
                                                         self.builder_name))

    def prepare(self, builder_status):
        log.msg("substantiating slave %s" % (self,))
        d = self.substantiate()
        def substantiation_failed(f):
            builder_status.addPointEvent(['removing', 'latent',
                                          self.slave.slavename])
            self.slave.disconnect()
            # TODO: should failover to a new Build
            return f
        d.addErrback(substantiation_failed)
        return d

    def substantiate(self):
        self.state = SUBSTANTIATING
        d = self.slave.substantiate(self)
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

    def buildFinished(self):
        AbstractSlaveBuilder.buildFinished(self)
        self.slave.buildFinished(self)

    def _attachFailure(self, why, where):
        self.state = LATENT
        return AbstractSlaveBuilder._attachFailure(self, why, where)

    def ping(self, status=None):
        if not self.slave.substantiated:
            if status:
                status.addEvent(["ping", "latent"]).finish()
            return defer.succeed(True)
        return AbstractSlaveBuilder.ping(self, status)


class Builder(pb.Referenceable, service.MultiService):
    """I manage all Builds of a given type.

    Each Builder is created by an entry in the config file (the c['builders']
    list), with a number of parameters.

    One of these parameters is the L{buildbot.process.factory.BuildFactory}
    object that is associated with this Builder. The factory is responsible
    for creating new L{Build<buildbot.process.base.Build>} objects. Each
    Build object defines when and how the build is performed, so a new
    Factory or Builder should be defined to control this behavior.

    The Builder holds on to a number of L{base.BuildRequest} objects in a
    list named C{.buildable}. Incoming BuildRequest objects will be added to
    this list, or (if possible) merged into an existing request. When a slave
    becomes available, I will use my C{BuildFactory} to turn the request into
    a new C{Build} object. The C{BuildRequest} is forgotten, the C{Build}
    goes into C{.building} while it runs. Once the build finishes, I will
    discard it.

    I maintain a list of available SlaveBuilders, one for each connected
    slave that the C{slavenames} parameter says we can use. Some of these
    will be idle, some of them will be busy running builds for me. If there
    are multiple slaves, I can run multiple builds at once.

    I also manage forced builds, progress expectation (ETA) management, and
    some status delivery chores.

    @type buildable: list of L{buildbot.process.base.BuildRequest}
    @ivar buildable: BuildRequests that are ready to build, but which are
                     waiting for a buildslave to be available.

    @type building: list of L{buildbot.process.base.Build}
    @ivar building: Builds that are actively running

    @type slaves: list of L{buildbot.buildslave.BuildSlave} objects
    @ivar slaves: the slaves currently available for building
    """

    expectations = None # this is created the first time we get a good build
    CHOOSE_SLAVES_RANDOMLY = True # disabled for determinism during tests

    def __init__(self, setup, builder_status):
        """
        @type  setup: dict
        @param setup: builder setup data, as stored in
                      BuildmasterConfig['builders'].  Contains name,
                      slavename(s), builddir, slavebuilddir, factory, locks.
        @type  builder_status: L{buildbot.status.builder.BuilderStatus}
        """
        service.MultiService.__init__(self)
        self.name = setup['name']
        self.slavenames = []
        if setup.has_key('slavename'):
            self.slavenames.append(setup['slavename'])
        if setup.has_key('slavenames'):
            self.slavenames.extend(setup['slavenames'])
        self.builddir = setup['builddir']
        self.slavebuilddir = setup['slavebuilddir']
        self.buildFactory = setup['factory']
        self.nextSlave = setup.get('nextSlave')
        if self.nextSlave is not None and not callable(self.nextSlave):
            raise ValueError("nextSlave must be callable")
        self.locks = setup.get("locks", [])
        self.env = setup.get('env', {})
        assert isinstance(self.env, dict)
        if setup.has_key('periodicBuildTime'):
            raise ValueError("periodicBuildTime can no longer be defined as"
                             " part of the Builder: use scheduler.Periodic"
                             " instead")
        self.nextBuild = setup.get('nextBuild')
        if self.nextBuild is not None and not callable(self.nextBuild):
            raise ValueError("nextBuild must be callable")
        self.buildHorizon = setup.get('buildHorizon')
        self.logHorizon = setup.get('logHorizon')
        self.eventHorizon = setup.get('eventHorizon')
        self.mergeRequests = setup.get('mergeRequests', True)
        self.properties = setup.get('properties', {})

        # build/wannabuild slots: Build objects move along this sequence
        self.building = []
        # old_building holds active builds that were stolen from a predecessor
        self.old_building = weakref.WeakKeyDictionary()

        # buildslaves which have connected but which are not yet available.
        # These are always in the ATTACHING state.
        self.attaching_slaves = []

        # buildslaves at our disposal. Each SlaveBuilder instance has a
        # .state that is IDLE, PINGING, or BUILDING. "PINGING" is used when a
        # Build is about to start, to make sure that they're still alive.
        self.slaves = []

        self.builder_status = builder_status
        self.builder_status.setSlavenames(self.slavenames)
        self.builder_status.buildHorizon = self.buildHorizon
        self.builder_status.logHorizon = self.logHorizon
        self.builder_status.eventHorizon = self.eventHorizon
        t = internet.TimerService(10*60, self.reclaimAllBuilds)
        t.setServiceParent(self)

        # for testing, to help synchronize tests
        self.watchers = {'attach': [], 'detach': [], 'detach_all': [],
                         'idle': []}
        self.run_count = 0

    def setBotmaster(self, botmaster):
        self.botmaster = botmaster
        self.db = botmaster.db
        self.master_name = botmaster.master_name
        self.master_incarnation = botmaster.master_incarnation

    def compareToSetup(self, setup):
        diffs = []
        setup_slavenames = []
        if setup.has_key('slavename'):
            setup_slavenames.append(setup['slavename'])
        setup_slavenames.extend(setup.get('slavenames', []))
        if setup_slavenames != self.slavenames:
            diffs.append('slavenames changed from %s to %s' \
                         % (self.slavenames, setup_slavenames))
        if setup['builddir'] != self.builddir:
            diffs.append('builddir changed from %s to %s' \
                         % (self.builddir, setup['builddir']))
        if setup['slavebuilddir'] != self.slavebuilddir:
            diffs.append('slavebuilddir changed from %s to %s' \
                         % (self.slavebuilddir, setup['slavebuilddir']))
        if setup['factory'] != self.buildFactory: # compare objects
            diffs.append('factory changed')
        if setup.get('locks', []) != self.locks:
            diffs.append('locks changed from %s to %s' % (self.locks, setup.get('locks')))
        if setup.get('nextSlave') != self.nextSlave:
            diffs.append('nextSlave changed from %s to %s' % (self.nextSlave, setup.get('nextSlave')))
        if setup.get('nextBuild') != self.nextBuild:
            diffs.append('nextBuild changed from %s to %s' % (self.nextBuild, setup.get('nextBuild')))
        if setup['buildHorizon'] != self.buildHorizon:
            diffs.append('buildHorizon changed from %s to %s' % (self.buildHorizon, setup['buildHorizon']))
        if setup['logHorizon'] != self.logHorizon:
            diffs.append('logHorizon changed from %s to %s' % (self.logHorizon, setup['logHorizon']))
        if setup['eventHorizon'] != self.eventHorizon:
            diffs.append('eventHorizon changed from %s to %s' % (self.eventHorizon, setup['eventHorizon']))
        return diffs

    def __repr__(self):
        return "<Builder '%r' at %d>" % (self.name, id(self))

    def triggerNewBuildCheck(self):
        self.botmaster.triggerNewBuildCheck()

    def run(self):
        """Check for work to be done. This should be called any time I might
        be able to start a job:

         - when the Builder is first created
         - when a new job has been added to the [buildrequests] DB table
         - when a slave has connected

        If I have both an available slave and the database contains a
        BuildRequest that I can handle, I will claim the BuildRequest and
        start the build. When the build finishes, I will retire the
        BuildRequest.
        """
        # overall plan:
        #  move .expectations to DB

        assert self.running
        log.msg("Builder.run %s: %s" % (self, self.slaves))
        self.run_count += 1

        available_slaves = [sb for sb in self.slaves if sb.isAvailable()]
        if not available_slaves:
            self.updateBigStatus()
            return
        d = self.db.runInteraction(self._claim_buildreqs, available_slaves)
        d.addCallback(self._start_builds)
        return d

    # slave-managers must refresh their claim on a build at least once an
    # hour, less any inter-manager clock skew
    RECLAIM_INTERVAL = 1*3600

    def _claim_buildreqs(self, t, available_slaves):
        # return a dict mapping slave -> (brid,ssid)
        now = util.now()
        old = now - self.RECLAIM_INTERVAL
        requests = self.db.get_unclaimed_buildrequests(self.name, old,
                                                       self.master_name,
                                                       self.master_incarnation,
                                                       t)

        assignments = {}
        while requests and available_slaves:
            sb = self._choose_slave(available_slaves)
            if not sb:
                log.msg("%s: want to start build, but we don't have a remote"
                        % self)
                break
            available_slaves.remove(sb)
            breq = self._choose_build(requests)
            if not breq:
                log.msg("%s: went to start build, but nextBuild said not to"
                        % self)
                break
            requests.remove(breq)
            merged_requests = [breq]
            for other_breq in requests[:]:
                if (self.mergeRequests and
                    self.botmaster.shouldMergeRequests(self, breq, other_breq)
                    ):
                    requests.remove(other_breq)
                    merged_requests.append(other_breq)
            assignments[sb] = merged_requests
            brids = [br.id for br in merged_requests]
            self.db.claim_buildrequests(now, self.master_name,
                                        self.master_incarnation, brids, t)
        return assignments

    def _choose_slave(self, available_slaves):
        # note: this might return None if the nextSlave() function decided to
        # not give us anything
        if self.nextSlave:
            try:
                return self.nextSlave(self, available_slaves)
            except:
                log.msg("Exception choosing next slave")
                log.err(Failure())
            return None
        if self.CHOOSE_SLAVES_RANDOMLY:
            return random.choice(available_slaves)
        return available_slaves[0]

    def _choose_build(self, buildable):
        if self.nextBuild:
            try:
                return self.nextBuild(self, buildable)
            except:
                log.msg("Exception choosing next build")
                log.err(Failure())
            return None
        return buildable[0]

    def _start_builds(self, assignments):
        # because _claim_buildreqs runs in a separate thread, we might have
        # lost a slave by this point. We treat that case the same as if we
        # lose the slave right after the build starts: the initial ping
        # fails.
        for (sb, requests) in assignments.items():
            build = self.buildFactory.newBuild(requests)
            build.setBuilder(self)
            build.setLocks(self.locks)
            if len(self.env) > 0:
                build.setSlaveEnvironment(self.env)
            self.startBuild(build, sb)
        self.updateBigStatus()


    def getBuildable(self):
        return self.db.runInteractionNow(self._getBuildable)
    def _getBuildable(self, t):
        now = util.now()
        old = now - self.RECLAIM_INTERVAL
        return self.db.get_unclaimed_buildrequests(self.name, old,
                                                   self.master_name,
                                                   self.master_incarnation,
                                                   t)

    def getOldestRequestTime(self):
        """Returns the timestamp of the oldest build request for this builder.

        If there are no build requests, None is returned."""
        buildable = self.getBuildable()
        if buildable:
            # TODO: this is sorted by priority first, not strictly reqtime
            return buildable[0].getSubmitTime()
        return None

    def cancelBuildRequest(self, brid):
        return self.db.cancel_buildrequests([brid])

    def consumeTheSoulOfYourPredecessor(self, old):
        """Suck the brain out of an old Builder.

        This takes all the runtime state from an existing Builder and moves
        it into ourselves. This is used when a Builder is changed in the
        master.cfg file: the new Builder has a different factory, but we want
        all the builds that were queued for the old one to get processed by
        the new one. Any builds which are already running will keep running.
        The new Builder will get as many of the old SlaveBuilder objects as
        it wants."""

        log.msg("consumeTheSoulOfYourPredecessor: %s feeding upon %s" %
                (self, old))
        # all pending builds are stored in the DB, so we don't have to do
        # anything to claim them. The old builder will be stopService'd,
        # which should make sure they don't start any new work

        # old.building (i.e. builds which are still running) is not migrated
        # directly: it keeps track of builds which were in progress in the
        # old Builder. When those builds finish, the old Builder will be
        # notified, not us. However, since the old SlaveBuilder will point to
        # us, it is our maybeStartBuild() that will be triggered.
        if old.building:
            self.builder_status.setBigState("building")
        # however, we do grab a weakref to the active builds, so that our
        # BuilderControl can see them and stop them. We use a weakref because
        # we aren't the one to get notified, so there isn't a convenient
        # place to remove it from self.building .
        for b in old.building:
            self.old_building[b] = None
        for b in old.old_building:
            self.old_building[b] = None

        # Our set of slavenames may be different. Steal any of the old
        # buildslaves that we want to keep using.
        for sb in old.slaves[:]:
            if sb.slave.slavename in self.slavenames:
                log.msg(" stealing buildslave %s" % sb)
                self.slaves.append(sb)
                old.slaves.remove(sb)
                sb.setBuilder(self)

        # old.attaching_slaves:
        #  these SlaveBuilders are waiting on a sequence of calls:
        #  remote.setMaster and remote.print . When these two complete,
        #  old._attached will be fired, which will add a 'connect' event to
        #  the builder_status and try to start a build. However, we've pulled
        #  everything out of the old builder's queue, so it will have no work
        #  to do. The outstanding remote.setMaster/print call will be holding
        #  the last reference to the old builder, so it will disappear just
        #  after that response comes back.
        #
        #  The BotMaster will ask the slave to re-set their list of Builders
        #  shortly after this function returns, which will cause our
        #  attached() method to be fired with a bunch of references to remote
        #  SlaveBuilders, some of which we already have (by stealing them
        #  from the old Builder), some of which will be new. The new ones
        #  will be re-attached.

        #  Therefore, we don't need to do anything about old.attaching_slaves

        return # all done

    def reclaimAllBuilds(self):
        now = util.now()
        brids = set()
        for b in self.building:
            brids.update([br.id for br in b.requests])
        for b in self.old_building:
            brids.update([br.id for br in b.requests])
        self.db.claim_buildrequests(now, self.master_name,
                                    self.master_incarnation, brids)

    def getBuild(self, number):
        for b in self.building:
            if b.build_status and b.build_status.number == number:
                return b
        for b in self.old_building.keys():
            if b.build_status and b.build_status.number == number:
                return b
        return None

    def fireTestEvent(self, name, fire_with=None):
        if fire_with is None:
            fire_with = self
        watchers = self.watchers[name]
        self.watchers[name] = []
        for w in watchers:
            eventually(w.callback, fire_with)

    def addLatentSlave(self, slave):
        assert interfaces.ILatentBuildSlave.providedBy(slave)
        for s in self.slaves:
            if s == slave:
                break
        else:
            sb = LatentSlaveBuilder(slave, self)
            self.builder_status.addPointEvent(
                ['added', 'latent', slave.slavename])
            self.slaves.append(sb)
            self.triggerNewBuildCheck()

    def attached(self, slave, remote, commands):
        """This is invoked by the BuildSlave when the self.slavename bot
        registers their builder.

        @type  slave: L{buildbot.buildslave.BuildSlave}
        @param slave: the BuildSlave that represents the buildslave as a whole
        @type  remote: L{twisted.spread.pb.RemoteReference}
        @param remote: a reference to the L{buildbot.slave.bot.SlaveBuilder}
        @type  commands: dict: string -> string, or None
        @param commands: provides the slave's version of each RemoteCommand

        @rtype:  L{twisted.internet.defer.Deferred}
        @return: a Deferred that fires (with 'self') when the slave-side
                 builder is fully attached and ready to accept commands.
        """
        for s in self.attaching_slaves + self.slaves:
            if s.slave == slave:
                # already attached to them. This is fairly common, since
                # attached() gets called each time we receive the builder
                # list from the slave, and we ask for it each time we add or
                # remove a builder. So if the slave is hosting builders
                # A,B,C, and the config file changes A, we'll remove A and
                # re-add it, triggering two builder-list requests, getting
                # two redundant calls to attached() for B, and another two
                # for C.
                #
                # Therefore, when we see that we're already attached, we can
                # just ignore it. TODO: build a diagram of the state
                # transitions here, I'm concerned about sb.attached() failing
                # and leaving sb.state stuck at 'ATTACHING', and about
                # the detached() message arriving while there's some
                # transition pending such that the response to the transition
                # re-vivifies sb
                return defer.succeed(self)

        sb = SlaveBuilder()
        sb.setBuilder(self)
        self.attaching_slaves.append(sb)
        d = sb.attached(slave, remote, commands)
        d.addCallback(self._attached)
        d.addErrback(self._not_attached, slave)
        return d

    def _attached(self, sb):
        # TODO: make this .addSlaveEvent(slave.slavename, ['connect']) ?
        self.builder_status.addPointEvent(['connect', sb.slave.slavename])
        self.attaching_slaves.remove(sb)
        self.slaves.append(sb)

        self.fireTestEvent('attach')
        return self

    def _not_attached(self, why, slave):
        # already log.err'ed by SlaveBuilder._attachFailure
        # TODO: make this .addSlaveEvent?
        # TODO: remove from self.slaves (except that detached() should get
        #       run first, right?)
        self.builder_status.addPointEvent(['failed', 'connect',
                                           slave.slave.slavename])
        # TODO: add an HTMLLogFile of the exception
        self.fireTestEvent('attach', why)

    def detached(self, slave):
        """This is called when the connection to the bot is lost."""
        for sb in self.attaching_slaves + self.slaves:
            if sb.slave == slave:
                break
        else:
            log.msg("WEIRD: Builder.detached(%s) (%s)"
                    " not in attaching_slaves(%s)"
                    " or slaves(%s)" % (slave, slave.slavename,
                                        self.attaching_slaves,
                                        self.slaves))
            return
        if sb.state == BUILDING:
            # the Build's .lostRemote method (invoked by a notifyOnDisconnect
            # handler) will cause the Build to be stopped, probably right
            # after the notifyOnDisconnect that invoked us finishes running.

            # TODO: should failover to a new Build
            #self.retryBuild(sb.build)
            pass

        if sb in self.attaching_slaves:
            self.attaching_slaves.remove(sb)
        if sb in self.slaves:
            self.slaves.remove(sb)

        # TODO: make this .addSlaveEvent?
        self.builder_status.addPointEvent(['disconnect', slave.slavename])
        sb.detached() # inform the SlaveBuilder that their slave went away
        self.updateBigStatus()
        self.fireTestEvent('detach')
        if not self.slaves:
            self.fireTestEvent('detach_all')

    def updateBigStatus(self):
        if not self.slaves:
            self.builder_status.setBigState("offline")
        elif self.building:
            self.builder_status.setBigState("building")
        else:
            self.builder_status.setBigState("idle")
            self.fireTestEvent('idle')

    def startBuild(self, build, sb):
        """Start a build on the given slave.
        @param build: the L{base.Build} to start
        @param sb: the L{SlaveBuilder} which will host this build

        @return: a Deferred which fires with a
        L{buildbot.interfaces.IBuildControl} that can be used to stop the
        Build, or to access a L{buildbot.interfaces.IBuildStatus} which will
        watch the Build as it runs. """

        self.building.append(build)
        self.updateBigStatus()
        log.msg("starting build %s using slave %s" % (build, sb))
        d = sb.prepare(self.builder_status)
        def _ping(ign):
            # ping the slave to make sure they're still there. If they've
            # fallen off the map (due to a NAT timeout or something), this
            # will fail in a couple of minutes, depending upon the TCP
            # timeout.
            #
            # TODO: This can unnecessarily suspend the starting of a build, in
            # situations where the slave is live but is pushing lots of data to
            # us in a build.
            log.msg("starting build %s.. pinging the slave %s" % (build, sb))
            return sb.ping()
        d.addCallback(_ping)
        d.addCallback(self._startBuild_1, build, sb)
        return d

    def _startBuild_1(self, res, build, sb):
        if not res:
            return self._startBuildFailed("slave ping failed", build, sb)
        # The buildslave is ready to go. sb.buildStarted() sets its state to
        # BUILDING (so we won't try to use it for any other builds). This
        # gets set back to IDLE by the Build itself when it finishes.
        sb.buildStarted()
        d = sb.remote.callRemote("startBuild")
        d.addCallbacks(self._startBuild_2, self._startBuildFailed,
                       callbackArgs=(build,sb), errbackArgs=(build,sb))
        return d

    def _startBuild_2(self, res, build, sb):
        # create the BuildStatus object that goes with the Build
        bs = self.builder_status.newBuild()

        # start the build. This will first set up the steps, then tell the
        # BuildStatus that it has started, which will announce it to the
        # world (through our BuilderStatus object, which is its parent).
        # Finally it will start the actual build process.
        bids = [self.db.build_started(req.id, bs.number) for req in build.requests]
        d = build.startBuild(bs, self.expectations, sb)
        d.addCallback(self.buildFinished, sb, bids)
        # this shouldn't happen. if it does, the slave will be wedged
        d.addErrback(log.err)
        return build # this is the IBuildControl

    def _startBuildFailed(self, why, build, sb):
        # put the build back on the buildable list
        log.msg("I tried to tell the slave that the build %s started, but "
                "remote_startBuild failed: %s" % (build, why))
        # release the slave. This will queue a call to maybeStartBuild, which
        # will fire after other notifyOnDisconnect handlers have marked the
        # slave as disconnected (so we don't try to use it again).
        sb.buildFinished()

        log.msg("re-queueing the BuildRequest")
        self.building.remove(build)
        self._resubmit_buildreqs(build).addErrback(log.err)

    def setupProperties(self, props):
        props.setProperty("buildername", self.name, "Builder")
        if len(self.properties) > 0:
            for propertyname in self.properties:
                props.setProperty(propertyname, self.properties[propertyname], "Builder")

    def buildFinished(self, build, sb, bids):
        """This is called when the Build has finished (either success or
        failure). Any exceptions during the build are reported with
        results=FAILURE, not with an errback."""

        # by the time we get here, the Build has already released the slave
        # (which queues a call to maybeStartBuild)

        self.db.builds_finished(bids)

        results = build.build_status.getResults()
        self.building.remove(build)
        if results == RETRY:
            self._resubmit_buildreqs(build).addErrback(log.err) # returns Deferred
        else:
            brids = [br.id for br in build.requests]
            self.db.retire_buildrequests(brids, results)
        self.triggerNewBuildCheck()

    def _resubmit_buildreqs(self, build):
        brids = [br.id for br in build.requests]
        return self.db.resubmit_buildrequests(brids)

    def setExpectations(self, progress):
        """Mark the build as successful and update expectations for the next
        build. Only call this when the build did not fail in any way that
        would invalidate the time expectations generated by it. (if the
        compile failed and thus terminated early, we can't use the last
        build to predict how long the next one will take).
        """
        if self.expectations:
            self.expectations.update(progress)
        else:
            # the first time we get a good build, create our Expectations
            # based upon its results
            self.expectations = Expectations(progress)
        log.msg("new expectations: %s seconds" % \
                self.expectations.expectedBuildTime())

    def shutdownSlave(self):
        if self.remote:
            self.remote.callRemote("shutdown")


class BuilderControl:
    implements(interfaces.IBuilderControl)

    def __init__(self, builder, parent):
        self.original = builder
        self.parent = parent # the IControl object

    def submitBuildRequest(self, ss, reason, props=None, now=False):
        bss = self.parent.submitBuildSet([self.original.name], ss, reason,
                                         props, now)
        brs = bss.getBuildRequests()[0]
        return brs

    def rebuildBuild(self, bs, reason="<rebuild, no reason given>", extraProperties=None):
        if not bs.isFinished():
            return

        ss = bs.getSourceStamp(absolute=True)
        if extraProperties is None:
            properties = bs.getProperties()
        else:
            # Make a copy so as not to modify the original build.
            properties = Properties()
            properties.updateFromProperties(bs.getProperties())
            properties.updateFromProperties(extraProperties)
        self.submitBuildRequest(ss, reason, props=properties)

    def getPendingBuilds(self):
        # return IBuildRequestControl objects
        retval = []
        for r in self.original.getBuildable():
            retval.append(BuildRequestControl(self.original, r))

        return retval

    def getBuild(self, number):
        return self.original.getBuild(number)

    def ping(self):
        if not self.original.slaves:
            self.original.builder_status.addPointEvent(["ping", "no slave"])
            return defer.succeed(False) # interfaces.NoSlaveError
        dl = []
        for s in self.original.slaves:
            dl.append(s.ping(self.original.builder_status))
        d = defer.DeferredList(dl)
        d.addCallback(self._gatherPingResults)
        return d

    def _gatherPingResults(self, res):
        for ignored,success in res:
            if not success:
                return False
        return True

class BuildRequestControl:
    implements(interfaces.IBuildRequestControl)

    def __init__(self, builder, request):
        self.original_builder = builder
        self.original_request = request
        self.brid = request.id

    def subscribe(self, observer):
        raise NotImplementedError

    def unsubscribe(self, observer):
        raise NotImplementedError

    def cancel(self):
        self.original_builder.cancelBuildRequest(self.brid)
