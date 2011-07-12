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

import os, urllib
from cPickle import load
from twisted.python import log
from twisted.persisted import styles
from twisted.internet import defer
from zope.interface import implements
from buildbot import interfaces
from buildbot.util import bbcollections
from buildbot.util.eventual import eventually
from buildbot.changes import changes
from buildbot.status import buildset, builder, buildrequest

class Status:
    """
    I represent the status of the buildmaster.
    """
    implements(interfaces.IStatus)

    def __init__(self, master):
        self.master = master
        self.botmaster = master.botmaster
        self.db = None
        self.basedir = master.basedir
        self.watchers = []
        # compress logs bigger than 4k, a good default on linux
        self.logCompressionLimit = 4*1024
        self.logCompressionMethod = "bz2"
        # No default limit to the log size
        self.logMaxSize = None
        self.logMaxTailSize = None

        # subscribe to the things we need to know about
        self.master.subscribeToBuildsetCompletions(
                self._buildsetCompletionCallback)
        self.master.subscribeToBuildsets(
                self._buildsetCallback)
        self.master.subscribeToBuildRequests(
                self._buildRequestCallback)

        self._builder_observers = bbcollections.KeyedSets()
        self._buildreq_observers = bbcollections.KeyedSets()
        self._buildset_finished_waiters = bbcollections.KeyedSets()

    @property
    def shuttingDown(self):
        return self.botmaster.shuttingDown

    def cleanShutdown(self):
        return self.botmaster.cleanShutdown()

    def cancelCleanShutdown(self):
        return self.botmaster.cancelCleanShutdown()

    # methods called by our clients

    def getTitle(self):
        return self.master.title
    def getTitleURL(self):
        return self.master.titleURL
    def getBuildbotURL(self):
        return self.master.buildbotURL

    def getMetrics(self):
        return self.master.metrics

    def getURLForThing(self, thing):
        prefix = self.getBuildbotURL()
        if not prefix:
            return None
        if interfaces.IStatus.providedBy(thing):
            return prefix
        if interfaces.ISchedulerStatus.providedBy(thing):
            pass
        if interfaces.IBuilderStatus.providedBy(thing):
            bldr = thing
            return prefix + "builders/%s" % (
                urllib.quote(bldr.getName(), safe=''),
                )
        if interfaces.IBuildStatus.providedBy(thing):
            build = thing
            bldr = build.getBuilder()
            return prefix + "builders/%s/builds/%d" % (
                urllib.quote(bldr.getName(), safe=''),
                build.getNumber())
        if interfaces.IBuildStepStatus.providedBy(thing):
            step = thing
            build = step.getBuild()
            bldr = build.getBuilder()
            return prefix + "builders/%s/builds/%d/steps/%s" % (
                urllib.quote(bldr.getName(), safe=''),
                build.getNumber(),
                urllib.quote(step.getName(), safe=''))
        # IBuildSetStatus
        # IBuildRequestStatus
        # ISlaveStatus

        # IStatusEvent
        if interfaces.IStatusEvent.providedBy(thing):
            # TODO: this is goofy, create IChange or something
            if isinstance(thing, changes.Change):
                change = thing
                return "%schanges/%d" % (prefix, change.number)

        if interfaces.IStatusLog.providedBy(thing):
            loog = thing
            step = loog.getStep()
            build = step.getBuild()
            bldr = build.getBuilder()

            logs = step.getLogs()
            for i in range(len(logs)):
                if loog is logs[i]:
                    break
            else:
                return None
            return prefix + "builders/%s/builds/%d/steps/%s/logs/%s" % (
                urllib.quote(bldr.getName(), safe=''),
                build.getNumber(),
                urllib.quote(step.getName(), safe=''),
                urllib.quote(loog.getName()))

    def getChangeSources(self):
        return list(self.master.change_svc)

    def getChange(self, number):
        """Get a Change object; returns a deferred"""
        d = self.master.db.changes.getChange(number)
        def chdict2change(chdict):
            if not chdict:
                return None
            return changes.Change.fromChdict(self.master, chdict)
        d.addCallback(chdict2change)
        return d

    def getSchedulers(self):
        return self.master.allSchedulers()

    def getBuilderNames(self, categories=None):
        if categories == None:
            return self.botmaster.builderNames[:] # don't let them break it
        
        l = []
        # respect addition order
        for name in self.botmaster.builderNames:
            bldr = self.botmaster.builders[name]
            if bldr.builder_status.category in categories:
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
        d = self.master.db.buildsets.getBuildsets(complete=False)
        def make_status_objects(bsdicts):
            return [ buildset.BuildSetStatus(bsdict, self)
                    for bsdict in bsdicts ]
        d.addCallback(make_status_objects)
        return d

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
            builder_status = builder.BuilderStatus(name, category)
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
        result['title'] = self.getTitle()
        result['titleURL'] = self.getTitleURL()
        result['buildbotURL'] = self.getBuildbotURL()
        # TODO: self.getSchedulers()
        # self.getChangeSources()
        return result

    def buildreqs_retired(self, requests):
        for r in requests:
            #r.id: notify subscribers (none right now)
            # r.bsid: check for completion, notify subscribers, unsubscribe
            pass

    def build_started(self, brid, buildername, build_status):
        if brid in self._buildreq_observers:
            for o in self._buildreq_observers[brid]:
                eventually(o, build_status)

    def _buildrequest_subscribe(self, brid, observer):
        self._buildreq_observers.add(brid, observer)

    def _buildrequest_unsubscribe(self, brid, observer):
        self._buildreq_observers.discard(brid, observer)

    def _buildset_waitUntilFinished(self, bsid):
        d = defer.Deferred()
        self._buildset_finished_waiters.add(bsid, d)
        self._maybeBuildsetFinished(bsid)
        return d

    def _maybeBuildsetFinished(self, bsid):
        # check bsid to see if it's successful or finished, and notify anyone
        # who cares
        if bsid not in self._buildset_finished_waiters:
            return
        d = self.master.db.buildsets.getBuildset(bsid)
        def do_notifies(bsdict):
            bss = buildset.BuildSetStatus(bsdict, self)
            if bss.isFinished():
                for d in self._buildset_finished_waiters.pop(bsid):
                    eventually(d.callback, bss)
        d.addCallback(do_notifies)
        d.addErrback(log.err, 'while notifying for buildset finishes')

    def _builder_subscribe(self, buildername, watcher):
        # should get requestSubmitted and requestCancelled
        self._builder_observers.add(buildername, watcher)

    def _builder_unsubscribe(self, buildername, watcher):
        self._builder_observers.discard(buildername, watcher)

    def _buildsetCallback(self, **kwargs):
        bsid = kwargs['bsid']
        d = self.master.db.buildsets.getBuildset(bsid)
        def do_notifies(bsdict):
            bss = buildset.BuildSetStatus(bsdict, self)
            for t in self.watchers:
                if hasattr(t, 'buildsetSubmitted'):
                    t.buildsetSubmitted(bss)
        d.addCallback(do_notifies)
        d.addErrback(log.err, 'while notifying buildsetSubmitted')

    def _buildsetCompletionCallback(self, bsid, result):
        self._maybeBuildsetFinished(bsid)

    def _buildRequestCallback(self, notif):
        buildername = notif['buildername']
        if buildername in self._builder_observers:
            brs = buildrequest.BuildRequestStatus(buildername,
                                                notif['brid'], self)
            for observer in self._builder_observers[buildername]:
                if hasattr(observer, 'requestSubmitted'):
                    eventually(observer.requestSubmitted, brs)
