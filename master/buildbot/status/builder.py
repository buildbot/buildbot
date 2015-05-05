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

from __future__ import with_statement


import os, re, itertools
from cPickle import load, dump
import datetime
from buildbot.interfaces import IStatusReceiver
from twisted.internet import defer

from zope.interface import implements
from twisted.python import log, runtime
from twisted.persisted import styles
from buildbot import interfaces, util
from buildbot.util.lru import LRUCache
from buildbot.status.event import Event
from buildbot.status.build import BuildStatus
from buildbot.status.buildrequest import BuildRequestStatus
from twisted.internet import threads

# user modules expect these symbols to be present here
from buildbot.status.results import SUCCESS, WARNINGS, FAILURE, SKIPPED
from buildbot.status.results import EXCEPTION, RETRY, Results, worst_status
_hush_pyflakes = [ SUCCESS, WARNINGS, FAILURE, SKIPPED,
                   EXCEPTION, RETRY, Results, worst_status ]

LATEST_BUILD_FORMAT = "{0}={1};"

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

    persistenceVersion = 2
    persistenceForgets = ( 'wasUpgraded', )

    category = None
    currentBigState = "offline" # or idle/waiting/interlocked/building
    basedir = None # filled in by our parent
    unavailable_build_numbers = set()
    status = None

    def __init__(self, buildername, category, master, friendly_name=None):
        self.name = buildername
        self.category = category
        self.master = master
        self.project = None
        self.friendly_name = friendly_name

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
        self.buildCache = LRUCache(self.cacheMiss)
        self.reason = None
        self.unavailable_build_numbers = set()
        self.latestBuildCache = {}
        self.pendingBuildsCache = None
        self.tags = []


    # persistence

    def setStatus(self, status):
        self.status = status
        self.pendingBuildCache = PendingBuildsCache(self)

        if not hasattr(self, 'latestBuildCache'):
            self.latestBuildCache = {}

    def deleteKey(self, key, d):
        if d.has_key(key):
            del d[key]

    def __getstate__(self):
        # when saving, don't record transient stuff like what builds are
        # currently running, because they won't be there when we start back
        # up. Nor do we save self.watchers, nor anything that gets set by our
        # parent like .basedir and .status
        d = styles.Versioned.__getstate__(self)
        d['watchers'] = []
        del d['buildCache']
        for b in self.currentBuilds:
            b.saveYourself()
            # TODO: push a 'hey, build was interrupted' event
        del d['currentBuilds']
        d.pop('pendingBuilds', None)
        self.deleteKey('currentBigState', d)
        del d['basedir']
        self.deleteKey('status', d)
        self.deleteKey('nextBuildNumber', d)
        del d['master']

        if 'pendingBuildCache' in d:
            del d['pendingBuildCache']

        self.deleteKey('latestBuildCache', d)
        return d

    def __setstate__(self, d):
        # when loading, re-initialize the transient stuff. Remember that
        # upgradeToVersion1 and such will be called after this finishes.
        styles.Versioned.__setstate__(self, d)
        self.buildCache = LRUCache(self.cacheMiss)
        self.currentBuilds = []
        self.watchers = []
        self.slavenames = []
        # self.basedir must be filled in by our parent
        # self.status must be filled in by our parent
        # self.master must be filled in by our parent

    def upgradeToVersion1(self):
        if hasattr(self, 'slavename'):
            self.slavenames = [self.slavename]
            del self.slavename
        if hasattr(self, 'nextBuildNumber'):
            del self.nextBuildNumber # determineNextBuildNumber chooses this
        self.wasUpgraded = True

    def upgradeToVersion2(self):
        if hasattr(self, 'latestBuildCache'):
            del self.latestBuildCache
        self.wasUpgraded = True

    def determineNextBuildNumber(self):
        """Scan our directory of saved BuildStatus instances to determine
        what our self.nextBuildNumber should be. Set it one larger than the
        highest-numbered build we discover. This is called by the top-level
        Status object shortly after we are created or loaded from disk.
        """
        existing_builds = []
        for f in os.listdir(self.basedir):
            r = re.search("^(\d+).*$", f)

            if r is not None and len(r.groups()) > 0:
                existing_builds.append(int(r.groups()[0]))

        if len(existing_builds):
            self.nextBuildNumber = max(existing_builds) + 1
        else:
            self.nextBuildNumber = 0

    def saveYourself(self, skipBuilds=False):
        if skipBuilds is False:
            for b in self.currentBuilds:
                if not b.isFinished:
                    # interrupted build, need to save it anyway.
                    # BuildStatus.saveYourself will mark it as interrupted.
                    b.saveYourself()

        filename = os.path.join(self.basedir, "builder")
        tmpfilename = filename + ".tmp"
        try:
            with open(tmpfilename, "wb") as f:
                dump(self, f, -1)
            if runtime.platformType  == 'win32':
                # windows cannot rename a file on top of an existing one
                if os.path.exists(filename):
                    os.unlink(filename)
            os.rename(tmpfilename, filename)
        except:
            log.msg("unable to save builder %s" % self.name)
            log.err()

    # build cache management

    def setCacheSize(self, size):
        self.buildCache.set_max_size(size)

    def makeBuildFilename(self, number):
        return os.path.join(self.basedir, "%d" % number)

    def getBuildByNumber(self, number):
        return self.buildCache.get(number)

    def loadBuildFromFile(self, number):
        if number in self.unavailable_build_numbers:
            return None

        filename = self.makeBuildFilename(number)
        try:
            if not os.path.exists(filename):
                if number < self.nextBuildNumber:
                    self.unavailable_build_numbers.add(number)
                return None

            log.msg("Loading builder %s's build %d from on-disk pickle" % (self.name, number))
            with open(filename, "rb") as f:
                build = load(f)
            build.setProcessObjects(self, self.master)

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

            # check that logfiles exist
            build.checkLogfiles()
            return build
        except IOError:
            raise IndexError("no such build %d" % number)
        except EOFError:
            raise IndexError("corrupted build pickle %d" % number)

    def cacheMiss(self, number, **kwargs):
        # If kwargs['val'] exists, this is a new value being added to
        # the cache.  Just return it.
        if 'val' in kwargs:
            return kwargs['val']

        # first look in currentBuilds
        for b in self.currentBuilds:
            if b.number == number:
                return b

        # then fall back to loading it from disk
        return self.loadBuildFromFile(number)

    def prune(self, events_only=False):
        # begin by pruning our own events
        eventHorizon = self.master.config.eventHorizon
        self.events = self.events[-eventHorizon:]

        if events_only:
            return

        # get the horizons straight
        buildHorizon = self.master.config.buildHorizon
        if buildHorizon is not None:
            earliest_build = self.nextBuildNumber - buildHorizon
        else:
            earliest_build = 0

        logHorizon = self.master.config.logHorizon
        if logHorizon is not None:
            earliest_log = self.nextBuildNumber - logHorizon
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
            if num in self.buildCache.cache: continue

            if (is_logfile and num < earliest_log) or num < earliest_build:
                pathname = os.path.join(self.basedir, filename)
                log.msg("pruning '%s'" % pathname)
                try: os.unlink(pathname)
                except OSError: pass

    # IBuilderStatus methods
    def getName(self):
        # if builderstatus page does show not up without any reason then 
        # str(self.name) may be a workaround
        return self.name

    def getFriendlyName(self):
        if self.friendly_name is None:
            return self.name

        return self.friendly_name

    def setFriendlyName(self, name):
        self.friendly_name = name

    def setTags(self, tags):
        self.tags = tags

    def getState(self):
        return (self.currentBigState, self.currentBuilds)

    def getSlaves(self):
        return [self.status.getSlave(name) for name in self.slavenames]

    @defer.inlineCallbacks
    def getPendingBuildRequestStatuses(self):
        db = self.status.master.db

        brdicts = yield db.buildrequests.getBuildRequests(claimed=False,
                                             buildername=self.name)

        result = [BuildRequestStatus(self.name, brdict['brid'],self.status) for brdict in brdicts]
        defer.returnValue(result)

    def foundCodebasesInBuild(self, build, codebases):
        if len(codebases) > 0:
            build_sourcestamps = build.getSourceStamps()
            foundcodebases = []
            for ss in build_sourcestamps:
                if ss.codebase in codebases.keys() and ss.branch == codebases[ss.codebase]:
                    foundcodebases.append(ss)
            return len(foundcodebases) == len(build_sourcestamps)

    @defer.inlineCallbacks
    def foundCodebasesInBuildRequest(self, build, codebases):
        if len(codebases) > 0:
            build_sourcestamps = yield build.getSourceStamps()
            foundcodebases = []
            for ss in build_sourcestamps.values():
                if ss.codebase in codebases.keys() and ss.branch == codebases[ss.codebase]:
                    foundcodebases.append(ss)
            defer.returnValue(len(foundcodebases) == len(build_sourcestamps))

    def getCurrentBuilds(self, codebases={}):
        if len(codebases) == 0:
            return self.currentBuilds

        currentBuildsCodebases = []
        for build in self.currentBuilds:
                if self.foundCodebasesInBuild(build, codebases):
                    currentBuildsCodebases.append(build)
        return currentBuildsCodebases

    def getCachedBuilds(self, codebases={}):
        builds = []
        for id in self.buildCache.keys():
            build = self.getBuild(id)
            if len(codebases) == 0 or self.foundCodebasesInBuild(build, codebases):
                builds.append(build)

        return builds

    def getLastFinishedBuild(self):
        b = self.getBuild(-1)
        if not (b and b.isFinished()):
            b = self.getBuild(-2)
        return b

    def setCategory(self, category):
        # used during reconfig
        self.category = category

    def getCategory(self):
        return self.category

    def setProject(self, project):
        self.project = project

    def getProject(self):
        return self.project

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

    def _getBuildBranches(self, build):
        return set([ ss.branch
            for ss in build.getSourceStamps() ])

    @defer.inlineCallbacks
    def generateBuildNumbers(self, codebases, num_builds):
        sourcestamps = []

        if codebases:
            for key, value in codebases.iteritems():
                sourcestamps.append({'b_codebase': key, 'b_branch': value})

        # Handles the condition where the last build status couldn't be saved into pickles,
        # in that case we need to search more builds and use the previous one 
        retries = num_builds
        if num_builds == 1:
            retries = num_builds + 9

        lastBuildsNumbers = yield self.master.db.builds.getLastBuildsNumbers(buildername=self.name,
                                                                             sourcestamps=sourcestamps,
                                                                             num_builds=retries)

        defer.returnValue(lastBuildsNumbers)
        return

    def getLatestBuildCache(self, key):
        cache = self.latestBuildCache[key]
        max_cache = datetime.timedelta(days=self.master.config.lastBuildCacheDays)
        if datetime.datetime.now() - cache["date"] > max_cache:
            del self.latestBuildCache[key]
        elif cache["build"] is not None:
            return self.getBuild(self.latestBuildCache[key]["build"])
        return None

    def shouldUseLatestBuildCache(self, useCache, num_builds, key):
        return key and useCache and num_builds == 1 and key in self.latestBuildCache

    @defer.inlineCallbacks
    def generateFinishedBuildsAsync(self, branches=[], codebases={},
                               num_builds=None,
                               max_search=None,
                               results=None,
                               slavename=None,
                               useCache=False):

        build = None
        finishedBuilds = []
        max_search = max_search if max_search is not None else num_builds
        branches = set(branches)

        key = self.getLatestBuildKey(codebases)
        if self.shouldUseLatestBuildCache(useCache, num_builds, key):
            build = self.getLatestBuildCache(key)

            if build:
                finishedBuilds.append(build)
            defer.returnValue(finishedBuilds)
            return

        buildNumbers = yield self.generateBuildNumbers(codebases, max_search)

        for bn in buildNumbers:
            build = yield threads.deferToThread(self.getBuild, bn)

            if build is None:
                continue

            if results is not None:
                if build.getResults() not in results:
                    continue

            if branches and not branches & self._getBuildBranches(build):
                continue

            if slavename and build.getSlavename() != slavename:
                continue

            finishedBuilds.append(build)

            if num_builds == 1 or (max_search > num_builds and len(finishedBuilds) == num_builds):
                break

        if key and useCache and num_builds == 1:
            self.saveLatestBuild(build, key)

        defer.returnValue(finishedBuilds)
        return


    def generateFinishedBuilds(self, branches=[], codebases={},
                               num_builds=None,
                               max_buildnum=None,
                               finished_before=None,
                               results=None,
                               max_search=2000,
                               useCache=False):

        key = self.getLatestBuildKey(codebases)
        if self.shouldUseLatestBuildCache(useCache, num_builds, key):
            build = self.getLatestBuildCache(key)
            if build:
                yield build
            # Warning: if there is a problem saving the build in the cache the build wont be loaded
            return

        got = 0
        branches = set(branches)
        codebases = codebases
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
            # if we were asked to filter on branches, and none of the
            # sourcestamps match, skip this build
            if len(codebases) > 0:
                if not self.foundCodebasesInBuild(build, codebases):
                    continue
            elif branches and not branches & self._getBuildBranches(build):
                continue
            if results is not None:
                if build.getResults() not in results:
                    continue
            got += 1
            yield build
            if num_builds and num_builds == 1 and useCache:
                    #Save our latest builds to the cache
                    self.saveLatestBuild(build, key)
                    return

        if useCache and num_builds == 1:
            self.saveLatestBuild(build=None, key=key)


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
        branches = set(branches)
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
            # if we were asked to filter on branches, and none of the
            # sourcestamps match, skip this build
            if branches and not branches & self._getBuildBranches(b):
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
        s = BuildStatus(self, self.master, number)
        s.waitUntilFinished().addCallback(self._buildFinished)
        return s

    # buildStarted is called by our child BuildStatus instances
    def buildStarted(self, s):
        """Now the BuildStatus object is ready to go (it knows all of its
        Steps, its ETA, etc), so it is safe to notify our watchers."""

        assert s.builder is self # paranoia
        assert s not in self.currentBuilds
        self.currentBuilds.append(s)
        self.buildCache.get(s.number, val=s)

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

        self.saveLatestBuild(s)
        self.prune() # conserve disk

    def getCodebaseBranch(self, branch, codebases, key):
        if key in codebases:
            return codebases[key]

        branch = branch if isinstance(branch, str) \
            else branch[0] if (isinstance(branch, list) and len(branch) > 0) else ''

        codebases[key] = branch

        return branch

    def getCodebaseConfiguredBranch(self, cb, key):
        return cb[key]['defaultbranch'] if 'defaultbranch' in cb[key] \
            else cb[key]['branch'] if 'branch' in cb[key] else ''

    def getLatestBuildKey(self, codebases):
        output = ""

        if not codebases:
            return output

        project = self.master.getProject(self.getProject())
        if project and project.codebases:
            project_codebases = project.codebases
            cb_keys = sorted(project_codebases, key=lambda s: s.keys()[0])

            for cb in cb_keys:
                key = cb.keys()[0]
                branch = self.getCodebaseConfiguredBranch(cb, key)
                branch = self.getCodebaseBranch(branch, codebases, key)
                output += LATEST_BUILD_FORMAT.format(key, branch)

        return output

    def updateLatestBuildCache(self, cache, k):
        def nonEmptyCacheUpdateToEmptyBuild():
            return self.latestBuildCache and k in self.latestBuildCache and 'build' in self.latestBuildCache[k] and \
                self.latestBuildCache[k]["build"] and cache["build"] is None

        def buildCacheAlreadyHasLastBuild():
            return self.latestBuildCache and k in self.latestBuildCache and self.latestBuildCache[k] and\
                self.latestBuildCache[k]["build"] and self.latestBuildCache[k]["build"] > cache["build"]

        def keyHasMultipleCodebasesAndEmptyBuild():
            codebases = [key for key in k.split(';') if key]
            return not cache["build"] and len(codebases) > 1

        if nonEmptyCacheUpdateToEmptyBuild():
            return

        if buildCacheAlreadyHasLastBuild():
            return

        if keyHasMultipleCodebasesAndEmptyBuild():
            return

        self.latestBuildCache[k] = cache

    def saveLatestBuild(self, build, key=None):
        cache = {"build": None, "date": datetime.datetime.now()}

        if build is not None:
            cache["build"] = build.number

            # Save the latest build using the build's codebases
            ss = build.getSourceStamps()
            codebases = {}
            for s in ss:
                if s.codebase and s.branch:
                    codebases[s.codebase] = s.branch

            # We save it in the same way as we access it
            key = self.getLatestBuildKey(codebases)

        self.updateLatestBuildCache(cache, key)


    def asDict(self, codebases={}, request=None, base_build_dict=False):
        from buildbot.status.web.base import codebases_to_args

        result = {}
        # Constant
        # TODO(maruel): Fix me. We don't want to leak the full path.
        result['name'] = self.name
        result['url'] = self.status.getURLForThing(self) + codebases_to_args(codebases)
        result['friendly_name'] = self.getFriendlyName()
        result['project'] = self.project
        result['slaves'] = self.slavenames
        result['tags'] = self.tags

        # TODO(maruel): Add cache settings? Do we care?

        # Transient
        def build_dict(b):
            if base_build_dict is True:
                return b.asBaseDict(request, include_current_step=True)
            else:
                return b.asDict(request)

        current_builds_dict = [build_dict(b) for b in self.getCurrentBuilds(codebases)]
        result['currentBuilds'] = current_builds_dict
        result['state'] = self.getState()[0]
        # lies, but we don't have synchronous access to this info; use
        # asDict_async instead
        result['pendingBuilds'] = 0
        return result

    @defer.inlineCallbacks
    def asDict_async(self, codebases={}, request=None, base_build_dict=False):
        """Just like L{asDict}, but with a nonzero pendingBuilds."""
        result = self.asDict(codebases, request, base_build_dict)
        builds = self.pendingBuildCache.getPendingBuilds()

        #Remove builds not within this codebase
        count = 0
        defers = []
        if len(codebases) > 0:
            for b in builds:
                de = self.foundCodebasesInBuildRequest(b, codebases)
                defers.append(de)

            #Allow the defers to run async
            for d in defers:
                in_codebase = yield d
                if in_codebase:
                    count += 1
        else:
            count = len(builds)

        result['pendingBuilds'] = count
        defer.returnValue(result)

    def getMetrics(self):
        return self.botmaster.parent.metrics

# vim: set ts=4 sts=4 sw=4 et:

class PendingBuildsCache():
    implements(IStatusReceiver)

    """
    A class which caches the pending builds for a builder
    it will clear the cache and request them again when
    a build is requested or started
    """
    def __init__(self, builder):
        self.builder = builder
        self.cache = []
        self.cache_now()
        self.builder.subscribe(self)

    @defer.inlineCallbacks
    def cache_now(self):
        if hasattr(self.builder, "status"):
            self.cache = yield self.builder.getPendingBuildRequestStatuses()
            defer.returnValue(self.cache)

    def getPendingBuilds(self):
        return self.cache

    def buildStarted(self, builderName, state):
        self.cache_now()

    def buildFinished(self, builderName, state, results):
        self.cache_now()
        
    def requestSubmitted(self, req):
        self.cache_now()

    def requestCancelled(self, req):
        self.cache_now()

    def builderChangedState(self, builderName, state):
        """
        Do nothing
        """



