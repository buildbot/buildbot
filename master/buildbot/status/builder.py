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


import weakref
import gc
import os, re, urllib, itertools
from cPickle import load, dump

from zope.interface import implements
from twisted.python import log, runtime
from twisted.persisted import styles
from twisted.internet import defer
from buildbot.util import collections
from buildbot.util.eventual import eventually
from buildbot import interfaces, util
from buildbot.status.event import Event
from buildbot.status.build import BuildStatus
from buildbot.status.buildset import BuildSetStatus
from buildbot.status.buildrequest import BuildRequestStatus

# user modules expect these symbols to be present here
from buildbot.status.results import SUCCESS, WARNINGS, FAILURE, SKIPPED
from buildbot.status.results import EXCEPTION, RETRY, Results, worst_status
_hush_pyflakes = [ SUCCESS, WARNINGS, FAILURE, SKIPPED,
                   EXCEPTION, RETRY, Results, worst_status ]


class BuilderStatus(styles.Versioned):
    """I handle status information for a single process.build.Builder object.
    That object sends status changes to me (frequently as Events), and I
    provide them on demand to the various status recipients, like the HTML
    waterfall display and the live status clients. It also sends build
    summaries to me, which I log and provide to status clients who aren't
    interested in seeing details of the individual build steps.

    I am responsible for maintaining the list of historic Events and Builds,
    pruning old ones, and loading them from / saving them to disk.

    I live in the buildbot.process.build.Builder object, in the
    .builder_status attribute.

    @type  category: string
    @ivar  category: user-defined category this builder belongs to; can be
                     used to filter on in status clients
    """

    implements(interfaces.IBuilderStatus, interfaces.IEventSource)

    persistenceVersion = 1
    persistenceForgets = ( 'wasUpgraded', )

    # these limit the amount of memory we consume, as well as the size of the
    # main Builder pickle. The Build and LogFile pickles on disk must be
    # handled separately.
    buildCacheSize = 15
    eventHorizon = 50 # forget events beyond this

    # these limit on-disk storage
    logHorizon = 40 # forget logs in steps in builds beyond this
    buildHorizon = 100 # forget builds beyond this

    category = None
    currentBigState = "offline" # or idle/waiting/interlocked/building
    basedir = None # filled in by our parent

    def __init__(self, buildername, category=None):
        self.name = buildername
        self.category = category

        self.slavenames = []
        self.events = []
        # these three hold Events, and are used to retrieve the current
        # state of the boxes.
        self.lastBuildStatus = None
        #self.currentBig = None
        #self.currentSmall = None
        self.currentBuilds = []
        self.nextBuild = None
        self.watchers = []
        self.buildCache = weakref.WeakValueDictionary()
        self.buildCache_LRU = []
        self.logCompressionLimit = False # default to no compression for tests
        self.logCompressionMethod = "bz2"
        self.logMaxSize = None # No default limit
        self.logMaxTailSize = None # No tail buffering

    # persistence

    def __getstate__(self):
        # when saving, don't record transient stuff like what builds are
        # currently running, because they won't be there when we start back
        # up. Nor do we save self.watchers, nor anything that gets set by our
        # parent like .basedir and .status
        d = styles.Versioned.__getstate__(self)
        d['watchers'] = []
        del d['buildCache']
        del d['buildCache_LRU']
        for b in self.currentBuilds:
            b.saveYourself()
            # TODO: push a 'hey, build was interrupted' event
        del d['currentBuilds']
        d.pop('pendingBuilds', None)
        del d['currentBigState']
        del d['basedir']
        del d['status']
        del d['nextBuildNumber']
        return d

    def __setstate__(self, d):
        # when loading, re-initialize the transient stuff. Remember that
        # upgradeToVersion1 and such will be called after this finishes.
        styles.Versioned.__setstate__(self, d)
        self.buildCache = weakref.WeakValueDictionary()
        self.buildCache_LRU = []
        self.currentBuilds = []
        self.watchers = []
        self.slavenames = []
        # self.basedir must be filled in by our parent
        # self.status must be filled in by our parent

    def reconfigFromBuildmaster(self, buildmaster):
        # Note that we do not hang onto the buildmaster, since this object
        # gets pickled and unpickled.
        if buildmaster.buildCacheSize is not None:
            self.buildCacheSize = buildmaster.buildCacheSize

    def upgradeToVersion1(self):
        if hasattr(self, 'slavename'):
            self.slavenames = [self.slavename]
            del self.slavename
        if hasattr(self, 'nextBuildNumber'):
            del self.nextBuildNumber # determineNextBuildNumber chooses this
        self.wasUpgraded = True

    def determineNextBuildNumber(self):
        """Scan our directory of saved BuildStatus instances to determine
        what our self.nextBuildNumber should be. Set it one larger than the
        highest-numbered build we discover. This is called by the top-level
        Status object shortly after we are created or loaded from disk.
        """
        existing_builds = [int(f)
                           for f in os.listdir(self.basedir)
                           if re.match("^\d+$", f)]
        if existing_builds:
            self.nextBuildNumber = max(existing_builds) + 1
        else:
            self.nextBuildNumber = 0

    def setLogCompressionLimit(self, lowerLimit):
        self.logCompressionLimit = lowerLimit

    def setLogCompressionMethod(self, method):
        assert method in ("bz2", "gz")
        self.logCompressionMethod = method

    def setLogMaxSize(self, upperLimit):
        self.logMaxSize = upperLimit

    def setLogMaxTailSize(self, tailSize):
        self.logMaxTailSize = tailSize

    def saveYourself(self):
        for b in self.currentBuilds:
            if not b.isFinished:
                # interrupted build, need to save it anyway.
                # BuildStatus.saveYourself will mark it as interrupted.
                b.saveYourself()
        filename = os.path.join(self.basedir, "builder")
        tmpfilename = filename + ".tmp"
        try:
            dump(self, open(tmpfilename, "wb"), -1)
            if runtime.platformType  == 'win32':
                # windows cannot rename a file on top of an existing one
                if os.path.exists(filename):
                    os.unlink(filename)
            os.rename(tmpfilename, filename)
        except:
            log.msg("unable to save builder %s" % self.name)
            log.err()
        

    # build cache management

    def makeBuildFilename(self, number):
        return os.path.join(self.basedir, "%d" % number)

    def touchBuildCache(self, build):
        self.buildCache[build.number] = build
        if build in self.buildCache_LRU:
            self.buildCache_LRU.remove(build)
        self.buildCache_LRU = self.buildCache_LRU[-(self.buildCacheSize-1):] + [ build ]
        return build

    def getBuildByNumber(self, number):
        # first look in currentBuilds
        for b in self.currentBuilds:
            if b.number == number:
                return self.touchBuildCache(b)

        # then in the buildCache
        if number in self.buildCache:
            return self.touchBuildCache(self.buildCache[number])

        # then fall back to loading it from disk
        filename = self.makeBuildFilename(number)
        try:
            log.msg("Loading builder %s's build %d from on-disk pickle"
                % (self.name, number))
            build = load(open(filename, "rb"))
            build.builder = self

            # (bug #1068) if we need to upgrade, we probably need to rewrite
            # this pickle, too.  We determine this by looking at the list of
            # Versioned objects that have been unpickled, and (after doUpgrade)
            # checking to see if any of them set wasUpgraded.  The Versioneds'
            # upgradeToVersionNN methods all set this.
            versioneds = styles.versionedsToUpgrade
            styles.doUpgrade()
            if True in [ hasattr(o, 'wasUpgraded') for o in versioneds.values() ]:
                log.msg("re-writing upgraded build pickle")
                build.saveYourself()

            # handle LogFiles from after 0.5.0 and before 0.6.5
            build.upgradeLogfiles()
            # check that logfiles exist
            build.checkLogfiles()
            return self.touchBuildCache(build)
        except IOError:
            raise IndexError("no such build %d" % number)
        except EOFError:
            raise IndexError("corrupted build pickle %d" % number)

    def prune(self, events_only=False):
        # begin by pruning our own events
        self.events = self.events[-self.eventHorizon:]

        if events_only:
            return

        gc.collect()

        # get the horizons straight
        if self.buildHorizon is not None:
            earliest_build = self.nextBuildNumber - self.buildHorizon
        else:
            earliest_build = 0

        if self.logHorizon is not None:
            earliest_log = self.nextBuildNumber - self.logHorizon
        else:
            earliest_log = 0

        if earliest_log < earliest_build:
            earliest_log = earliest_build

        if earliest_build == 0:
            return

        # skim the directory and delete anything that shouldn't be there anymore
        build_re = re.compile(r"^([0-9]+)$")
        build_log_re = re.compile(r"^([0-9]+)-.*$")
        # if the directory doesn't exist, bail out here
        if not os.path.exists(self.basedir):
            return

        for filename in os.listdir(self.basedir):
            num = None
            mo = build_re.match(filename)
            is_logfile = False
            if mo:
                num = int(mo.group(1))
            else:
                mo = build_log_re.match(filename)
                if mo:
                    num = int(mo.group(1))
                    is_logfile = True

            if num is None: continue
            if num in self.buildCache: continue

            if (is_logfile and num < earliest_log) or num < earliest_build:
                pathname = os.path.join(self.basedir, filename)
                log.msg("pruning '%s'" % pathname)
                try: os.unlink(pathname)
                except OSError: pass

    # IBuilderStatus methods
    def getName(self):
        return self.name

    def getState(self):
        return (self.currentBigState, self.currentBuilds)

    def getSlaves(self):
        return [self.status.getSlave(name) for name in self.slavenames]

    def getPendingBuilds(self):
        db = self.status.db
        return [BuildRequestStatus(brid, self.status, db)
                for brid in db.get_pending_brids_for_builder(self.name)]

    def getCurrentBuilds(self):
        return self.currentBuilds

    def getLastFinishedBuild(self):
        b = self.getBuild(-1)
        if not (b and b.isFinished()):
            b = self.getBuild(-2)
        return b

    def getCategory(self):
        return self.category

    def getBuild(self, number):
        if number < 0:
            number = self.nextBuildNumber + number
        if number < 0 or number >= self.nextBuildNumber:
            return None

        try:
            return self.getBuildByNumber(number)
        except IndexError:
            return None

    def getEvent(self, number):
        try:
            return self.events[number]
        except IndexError:
            return None

    def generateFinishedBuilds(self, branches=[],
                               num_builds=None,
                               max_buildnum=None,
                               finished_before=None,
                               max_search=200):
        got = 0
        for Nb in itertools.count(1):
            if Nb > self.nextBuildNumber:
                break
            if Nb > max_search:
                break
            build = self.getBuild(-Nb)
            if build is None:
                continue
            if max_buildnum is not None:
                if build.getNumber() > max_buildnum:
                    continue
            if not build.isFinished():
                continue
            if finished_before is not None:
                start, end = build.getTimes()
                if end >= finished_before:
                    continue
            if branches:
                if build.getSourceStamp().branch not in branches:
                    continue
            got += 1
            yield build
            if num_builds is not None:
                if got >= num_builds:
                    return

    def eventGenerator(self, branches=[], categories=[], committers=[], minTime=0):
        """This function creates a generator which will provide all of this
        Builder's status events, starting with the most recent and
        progressing backwards in time. """

        # remember the oldest-to-earliest flow here. "next" means earlier.

        # TODO: interleave build steps and self.events by timestamp.
        # TODO: um, I think we're already doing that.

        # TODO: there's probably something clever we could do here to
        # interleave two event streams (one from self.getBuild and the other
        # from self.getEvent), which would be simpler than this control flow

        eventIndex = -1
        e = self.getEvent(eventIndex)
        for Nb in range(1, self.nextBuildNumber+1):
            b = self.getBuild(-Nb)
            if not b:
                # HACK: If this is the first build we are looking at, it is
                # possible it's in progress but locked before it has written a
                # pickle; in this case keep looking.
                if Nb == 1:
                    continue
                break
            if b.getTimes()[0] < minTime:
                break
            if branches and not b.getSourceStamp().branch in branches:
                continue
            if categories and not b.getBuilder().getCategory() in categories:
                continue
            if committers and not [True for c in b.getChanges() if c.who in committers]:
                continue
            steps = b.getSteps()
            for Ns in range(1, len(steps)+1):
                if steps[-Ns].started:
                    step_start = steps[-Ns].getTimes()[0]
                    while e is not None and e.getTimes()[0] > step_start:
                        yield e
                        eventIndex -= 1
                        e = self.getEvent(eventIndex)
                    yield steps[-Ns]
            yield b
        while e is not None:
            yield e
            eventIndex -= 1
            e = self.getEvent(eventIndex)
            if e and e.getTimes()[0] < minTime:
                break

    def subscribe(self, receiver):
        # will get builderChangedState, buildStarted, buildFinished,
        # requestSubmitted, requestCancelled. Note that a request which is
        # resubmitted (due to a slave disconnect) will cause requestSubmitted
        # to be invoked multiple times.
        self.watchers.append(receiver)
        self.publishState(receiver)
        # our parent Status provides requestSubmitted and requestCancelled
        self.status._builder_subscribe(self.name, receiver)

    def unsubscribe(self, receiver):
        self.watchers.remove(receiver)
        self.status._builder_unsubscribe(self.name, receiver)

    ## Builder interface (methods called by the Builder which feeds us)

    def setSlavenames(self, names):
        self.slavenames = names

    def addEvent(self, text=[]):
        # this adds a duration event. When it is done, the user should call
        # e.finish(). They can also mangle it by modifying .text
        e = Event()
        e.started = util.now()
        e.text = text
        self.events.append(e)
        self.prune(events_only=True)
        return e # they are free to mangle it further

    def addPointEvent(self, text=[]):
        # this adds a point event, one which occurs as a single atomic
        # instant of time.
        e = Event()
        e.started = util.now()
        e.finished = 0
        e.text = text
        self.events.append(e)
        self.prune(events_only=True)
        return e # for consistency, but they really shouldn't touch it

    def setBigState(self, state):
        needToUpdate = state != self.currentBigState
        self.currentBigState = state
        if needToUpdate:
            self.publishState()

    def publishState(self, target=None):
        state = self.currentBigState

        if target is not None:
            # unicast
            target.builderChangedState(self.name, state)
            return
        for w in self.watchers:
            try:
                w.builderChangedState(self.name, state)
            except:
                log.msg("Exception caught publishing state to %r" % w)
                log.err()

    def newBuild(self):
        """The Builder has decided to start a build, but the Build object is
        not yet ready to report status (it has not finished creating the
        Steps). Create a BuildStatus object that it can use."""
        number = self.nextBuildNumber
        self.nextBuildNumber += 1
        # TODO: self.saveYourself(), to make sure we don't forget about the
        # build number we've just allocated. This is not quite as important
        # as it was before we switch to determineNextBuildNumber, but I think
        # it may still be useful to have the new build save itself.
        s = BuildStatus(self, number)
        s.waitUntilFinished().addCallback(self._buildFinished)
        return s

    # buildStarted is called by our child BuildStatus instances
    def buildStarted(self, s):
        """Now the BuildStatus object is ready to go (it knows all of its
        Steps, its ETA, etc), so it is safe to notify our watchers."""

        assert s.builder is self # paranoia
        assert s.number == self.nextBuildNumber - 1
        assert s not in self.currentBuilds
        self.currentBuilds.append(s)
        self.touchBuildCache(s)

        # now that the BuildStatus is prepared to answer queries, we can
        # announce the new build to all our watchers

        for w in self.watchers: # TODO: maybe do this later? callLater(0)?
            try:
                receiver = w.buildStarted(self.getName(), s)
                if receiver:
                    if type(receiver) == type(()):
                        s.subscribe(receiver[0], receiver[1])
                    else:
                        s.subscribe(receiver)
                    d = s.waitUntilFinished()
                    d.addCallback(lambda s: s.unsubscribe(receiver))
            except:
                log.msg("Exception caught notifying %r of buildStarted event" % w)
                log.err()

    def _buildFinished(self, s):
        assert s in self.currentBuilds
        s.saveYourself()
        self.currentBuilds.remove(s)

        name = self.getName()
        results = s.getResults()
        for w in self.watchers:
            try:
                w.buildFinished(name, s, results)
            except:
                log.msg("Exception caught notifying %r of buildFinished event" % w)
                log.err()

        self.prune() # conserve disk


    # waterfall display (history)

    # I want some kind of build event that holds everything about the build:
    # why, what changes went into it, the results of the build, itemized
    # test results, etc. But, I do kind of need something to be inserted in
    # the event log first, because intermixing step events and the larger
    # build event is fraught with peril. Maybe an Event-like-thing that
    # doesn't have a file in it but does have links. Hmm, that's exactly
    # what it does now. The only difference would be that this event isn't
    # pushed to the clients.

    # publish to clients
    ## HTML display interface

    def getEventNumbered(self, num):
        # deal with dropped events, pruned events
        first = self.events[0].number
        if first + len(self.events)-1 != self.events[-1].number:
            log.msg(self,
                    "lost an event somewhere: [0] is %d, [%d] is %d" % \
                    (self.events[0].number,
                     len(self.events) - 1,
                     self.events[-1].number))
            for e in self.events:
                log.msg("e[%d]: " % e.number, e)
            return None
        offset = num - first
        log.msg(self, "offset", offset)
        try:
            return self.events[offset]
        except IndexError:
            return None

    ## Persistence of Status
    def loadYourOldEvents(self):
        if hasattr(self, "allEvents"):
            # first time, nothing to get from file. Note that this is only if
            # the Application gets .run() . If it gets .save()'ed, then the
            # .allEvents attribute goes away in the initial __getstate__ and
            # we try to load a non-existent file.
            return
        self.allEvents = self.loadFile("events", [])
        if self.allEvents:
            self.nextEventNumber = self.allEvents[-1].number + 1
        else:
            self.nextEventNumber = 0
    def saveYourOldEvents(self):
        self.saveFile("events", self.allEvents)

    ## clients

    def addClient(self, client):
        if client not in self.subscribers:
            self.subscribers.append(client)
            self.sendCurrentActivityBig(client)
            client.newEvent(self.currentSmall)
    def removeClient(self, client):
        if client in self.subscribers:
            self.subscribers.remove(client)

    def asDict(self):
        result = {}
        # Constant
        # TODO(maruel): Fix me. We don't want to leak the full path.
        result['basedir'] = os.path.basename(self.basedir)
        result['category'] = self.category
        result['slaves'] = self.slavenames
        #result['url'] = self.parent.getURLForThing(self)
        # TODO(maruel): Add cache settings? Do we care?

        # Transient
        # Collect build numbers.
        # Important: Only grab the *cached* builds numbers to reduce I/O.
        current_builds = [b.getNumber() for b in self.currentBuilds]
        cached_builds = list(set(self.buildCache.keys() + current_builds))
        cached_builds.sort()
        result['cachedBuilds'] = cached_builds
        result['currentBuilds'] = current_builds
        result['state'] = self.getState()[0]
        result['pendingBuilds'] = len(self.getPendingBuilds())
        return result


class Status:
    """
    I represent the status of the buildmaster.
    """
    implements(interfaces.IStatus)

    def __init__(self, botmaster, basedir):
        """
        @type  botmaster: L{buildbot.process.botmaster.BotMaster}
        @param botmaster: the Status object uses C{.botmaster} to get at
                          both the L{buildbot.master.BuildMaster} (for
                          various buildbot-wide parameters) and the
                          actual Builders (to get at their L{BuilderStatus}
                          objects). It is not allowed to change or influence
                          anything through this reference.
        @type  basedir: string
        @param basedir: this provides a base directory in which saved status
                        information (changes.pck, saved Build status
                        pickles) can be stored
        """
        self.botmaster = botmaster
        self.master = botmaster.parent # TODO: temporary; this should get set more formally
        self.db = None
        self.basedir = basedir
        self.watchers = []
        assert os.path.isdir(basedir)
        # compress logs bigger than 4k, a good default on linux
        self.logCompressionLimit = 4*1024
        self.logCompressionMethod = "bz2"
        # No default limit to the log size
        self.logMaxSize = None
        self.logMaxTailSize = None

        self._builder_observers = collections.KeyedSets()
        self._buildreq_observers = collections.KeyedSets()
        self._buildset_success_waiters = collections.KeyedSets()
        self._buildset_finished_waiters = collections.KeyedSets()

    @property
    def shuttingDown(self):
        return self.botmaster.shuttingDown

    def cleanShutdown(self):
        return self.botmaster.cleanShutdown()

    def cancelCleanShutdown(self):
        return self.botmaster.cancelCleanShutdown()

    def setDB(self, db):
        self.db = db
        self.db.subscribe_to("add-build", self._db_builds_changed)
        self.db.subscribe_to("add-buildset", self._db_buildset_added)
        self.db.subscribe_to("modify-buildset", self._db_buildsets_changed)
        self.db.subscribe_to("add-buildrequest", self._db_buildrequest_added)
        self.db.subscribe_to("cancel-buildrequest", self._db_buildrequest_cancelled)

    # methods called by our clients

    def getProjectName(self):
        return self.master.projectName
    def getProjectURL(self):
        return self.master.projectURL
    def getBuildbotURL(self):
        return self.master.buildbotURL

    def getURLForThing(self, thing):
        prefix = self.getBuildbotURL()
        if not prefix:
            return None
        if interfaces.IStatus.providedBy(thing):
            return prefix
        if interfaces.ISchedulerStatus.providedBy(thing):
            pass
        if interfaces.IBuilderStatus.providedBy(thing):
            builder = thing
            return prefix + "builders/%s" % (
                urllib.quote(builder.getName(), safe=''),
                )
        if interfaces.IBuildStatus.providedBy(thing):
            build = thing
            builder = build.getBuilder()
            return prefix + "builders/%s/builds/%d" % (
                urllib.quote(builder.getName(), safe=''),
                build.getNumber())
        if interfaces.IBuildStepStatus.providedBy(thing):
            step = thing
            build = step.getBuild()
            builder = build.getBuilder()
            return prefix + "builders/%s/builds/%d/steps/%s" % (
                urllib.quote(builder.getName(), safe=''),
                build.getNumber(),
                urllib.quote(step.getName(), safe=''))
        # IBuildSetStatus
        # IBuildRequestStatus
        # ISlaveStatus

        # IStatusEvent
        if interfaces.IStatusEvent.providedBy(thing):
            from buildbot.changes import changes
            # TODO: this is goofy, create IChange or something
            if isinstance(thing, changes.Change):
                change = thing
                return "%schanges/%d" % (prefix, change.number)

        if interfaces.IStatusLog.providedBy(thing):
            log = thing
            step = log.getStep()
            build = step.getBuild()
            builder = build.getBuilder()

            logs = step.getLogs()
            for i in range(len(logs)):
                if log is logs[i]:
                    break
            else:
                return None
            return prefix + "builders/%s/builds/%d/steps/%s/logs/%s" % (
                urllib.quote(builder.getName(), safe=''),
                build.getNumber(),
                urllib.quote(step.getName(), safe=''),
                urllib.quote(log.getName()))

    def getChangeSources(self):
        return list(self.master.change_svc)

    def getChange(self, number):
        """Get a Change object; returns a deferred"""
        return self.master.db.changes.getChangeInstance(number)

    def getSchedulers(self):
        return self.master.allSchedulers()

    def getBuilderNames(self, categories=None):
        if categories == None:
            return self.botmaster.builderNames[:] # don't let them break it
        
        l = []
        # respect addition order
        for name in self.botmaster.builderNames:
            builder = self.botmaster.builders[name]
            if builder.builder_status.category in categories:
                l.append(name)
        return l

    def getBuilder(self, name):
        """
        @rtype: L{BuilderStatus}
        """
        return self.botmaster.builders[name].builder_status

    def getSlaveNames(self):
        return self.botmaster.slaves.keys()

    def getSlave(self, slavename):
        return self.botmaster.slaves[slavename].slave_status

    def getBuildSets(self):
        return [BuildSetStatus(bsid, self, self.db)
                for bsid in self.db.get_active_buildset_ids()]

    def generateFinishedBuilds(self, builders=[], branches=[],
                               num_builds=None, finished_before=None,
                               max_search=200):

        def want_builder(bn):
            if builders:
                return bn in builders
            return True
        builder_names = [bn
                         for bn in self.getBuilderNames()
                         if want_builder(bn)]

        # 'sources' is a list of generators, one for each Builder we're
        # using. When the generator is exhausted, it is replaced in this list
        # with None.
        sources = []
        for bn in builder_names:
            b = self.getBuilder(bn)
            g = b.generateFinishedBuilds(branches,
                                         finished_before=finished_before,
                                         max_search=max_search)
            sources.append(g)

        # next_build the next build from each source
        next_build = [None] * len(sources)

        def refill():
            for i,g in enumerate(sources):
                if next_build[i]:
                    # already filled
                    continue
                if not g:
                    # already exhausted
                    continue
                try:
                    next_build[i] = g.next()
                except StopIteration:
                    next_build[i] = None
                    sources[i] = None

        got = 0
        while True:
            refill()
            # find the latest build among all the candidates
            candidates = [(i, b, b.getTimes()[1])
                          for i,b in enumerate(next_build)
                          if b is not None]
            candidates.sort(lambda x,y: cmp(x[2], y[2]))
            if not candidates:
                return

            # and remove it from the list
            i, build, finshed_time = candidates[-1]
            next_build[i] = None
            got += 1
            yield build
            if num_builds is not None:
                if got >= num_builds:
                    return

    def subscribe(self, target):
        self.watchers.append(target)
        for name in self.botmaster.builderNames:
            self.announceNewBuilder(target, name, self.getBuilder(name))
    def unsubscribe(self, target):
        self.watchers.remove(target)


    # methods called by upstream objects

    def announceNewBuilder(self, target, name, builder_status):
        t = target.builderAdded(name, builder_status)
        if t:
            builder_status.subscribe(t)

    def builderAdded(self, name, basedir, category=None):
        """
        @rtype: L{BuilderStatus}
        """
        filename = os.path.join(self.basedir, basedir, "builder")
        log.msg("trying to load status pickle from %s" % filename)
        builder_status = None
        try:
            builder_status = load(open(filename, "rb"))
            
            # (bug #1068) if we need to upgrade, we probably need to rewrite
            # this pickle, too.  We determine this by looking at the list of
            # Versioned objects that have been unpickled, and (after doUpgrade)
            # checking to see if any of them set wasUpgraded.  The Versioneds'
            # upgradeToVersionNN methods all set this.
            versioneds = styles.versionedsToUpgrade
            styles.doUpgrade()
            if True in [ hasattr(o, 'wasUpgraded') for o in versioneds.values() ]:
                log.msg("re-writing upgraded builder pickle")
                builder_status.saveYourself()

        except IOError:
            log.msg("no saved status pickle, creating a new one")
        except:
            log.msg("error while loading status pickle, creating a new one")
            log.msg("error follows:")
            log.err()
        if not builder_status:
            builder_status = BuilderStatus(name, category)
            builder_status.addPointEvent(["builder", "created"])
        log.msg("added builder %s in category %s" % (name, category))
        # an unpickled object might not have category set from before,
        # so set it here to make sure
        builder_status.category = category
        builder_status.basedir = os.path.join(self.basedir, basedir)
        builder_status.name = name # it might have been updated
        builder_status.status = self

        if not os.path.isdir(builder_status.basedir):
            os.makedirs(builder_status.basedir)
        builder_status.determineNextBuildNumber()

        builder_status.setBigState("offline")
        builder_status.setLogCompressionLimit(self.logCompressionLimit)
        builder_status.setLogCompressionMethod(self.logCompressionMethod)
        builder_status.setLogMaxSize(self.logMaxSize)
        builder_status.setLogMaxTailSize(self.logMaxTailSize)

        for t in self.watchers:
            self.announceNewBuilder(t, name, builder_status)

        return builder_status

    def builderRemoved(self, name):
        for t in self.watchers:
            if hasattr(t, 'builderRemoved'):
                t.builderRemoved(name)

    def slaveConnected(self, name):
        for t in self.watchers:
            if hasattr(t, 'slaveConnected'):
                t.slaveConnected(name)

    def slaveDisconnected(self, name):
        for t in self.watchers:
            if hasattr(t, 'slaveDisconnected'):
                t.slaveDisconnected(name)

    def changeAdded(self, change):
        for t in self.watchers:
            if hasattr(t, 'changeAdded'):
                t.changeAdded(change)

    def asDict(self):
        result = {}
        # Constant
        result['projectName'] = self.getProjectName()
        result['projectURL'] = self.getProjectURL()
        result['buildbotURL'] = self.getBuildbotURL()
        # TODO: self.getSchedulers()
        # self.getChangeSources()
        return result

    def buildreqs_retired(self, requests):
        for r in requests:
            #r.id: notify subscribers (none right now)
            # r.bsid: check for completion, notify subscribers, unsubscribe
            pass

    def get_buildreq_for_id(self, brid):
        return BuildRequestStatus(brid, self, self.db)

    def _db_builds_changed(self, category, bid):
        brid,buildername,buildnum = self.db.get_build_info(bid)
        if brid in self._buildreq_observers:
            bs = self.getBuilder(buildername).getBuild(buildnum)
            if bs:
                for o in self._buildreq_observers[brid]:
                    eventually(o, bs)

    def _buildrequest_subscribe(self, brid, observer):
        self._buildreq_observers.add(brid, observer)

    def _buildrequest_unsubscribe(self, brid, observer):
        self._buildreq_observers.discard(brid, observer)

    def _db_buildset_added(self, category, bsid):
        bss = BuildSetStatus(bsid, self, self.db)
        for t in self.watchers:
            if hasattr(t, 'buildsetSubmitted'):
                t.buildsetSubmitted(bss)

    def _buildset_waitUntilSuccess(self, bsid):
        d = defer.Deferred()
        self._buildset_success_waiters.add(bsid, d)
        # now check for a buildset which was already successful
        self._db_buildsets_changed("modify-buildset", bsid)
        return d
    def _buildset_waitUntilFinished(self, bsid):
        d = defer.Deferred()
        self._buildset_finished_waiters.add(bsid, d)
        self._db_buildsets_changed("modify-buildset", bsid)
        return d

    def _db_buildsets_changed(self, category, *bsids):
        for bsid in bsids:
            self._db_buildset_changed(bsid)

    def _db_buildset_changed(self, bsid):
        # check bsid to see if it's successful or finished, and notify anyone
        # who cares
        if (bsid not in self._buildset_success_waiters
            and bsid not in self._buildset_finished_waiters):
            return
        successful,finished = self.db.examine_buildset(bsid)
        bss = BuildSetStatus(bsid, self, self.db)
        if successful is not None:
            for d in self._buildset_success_waiters.pop(bsid):
                eventually(d.callback, bss)
        if finished:
            for d in self._buildset_finished_waiters.pop(bsid):
                eventually(d.callback, bss)

    def _builder_subscribe(self, buildername, watcher):
        # should get requestSubmitted and requestCancelled
        self._builder_observers.add(buildername, watcher)

    def _builder_unsubscribe(self, buildername, watcher):
        self._builder_observers.discard(buildername, watcher)

    def _db_buildrequest_added(self, category, *brids):
        self._handle_buildrequest_event("added", brids)
    def _db_buildrequest_cancelled(self, category, *brids):
        self._handle_buildrequest_event("cancelled", brids)
    def _handle_buildrequest_event(self, mode, brids):
        for brid in brids:
            buildername = self.db.get_buildername_for_brid(brid)
            if buildername in self._builder_observers:
                brs = BuildRequestStatus(brid, self, self.db)
                for observer in self._builder_observers[buildername]:
                    if mode == "added":
                        if hasattr(observer, 'requestSubmitted'):
                            eventually(observer.requestSubmitted, brs)
                    else:
                        if hasattr(observer, 'requestCancelled'):
                            builder = self.getBuilder(buildername)
                            eventually(observer.requestCancelled, builder, brs)

# vim: set ts=4 sts=4 sw=4 et:
