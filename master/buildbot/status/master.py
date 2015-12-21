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

from future.moves.urllib.parse import quote as urlquote
from future.utils import iteritems
from future.utils import itervalues

import os

from buildbot import interfaces
from buildbot import util
from buildbot.changes import changes
from buildbot.status import builder
from buildbot.status import buildrequest
from buildbot.status import buildset
from buildbot.util import bbcollections
from buildbot.util import pickle
from buildbot.util import service
from buildbot.util.eventual import eventually
from twisted.internet import defer
from twisted.persisted import styles
from twisted.python import log
from zope.interface import implements


class Status(service.ReconfigurableServiceMixin, service.AsyncMultiService):
    implements(interfaces.IStatus)

    def __init__(self):
        service.AsyncMultiService.__init__(self)
        self.watchers = []
        # No default limit to the log size
        self.logMaxSize = None

        self._builder_observers = bbcollections.KeyedSets()
        self._buildreq_observers = bbcollections.KeyedSets()
        self._buildset_finished_waiters = bbcollections.KeyedSets()
        self._buildset_completion_sub = None
        self._buildset_sub = None
        self._build_request_sub = None
        self._change_sub = None

    @property
    def botmaster(self):
        return self.master.botmaster

    @property
    def buildslaves(self):
        return self.master.buildslaves

    @property
    def basedir(self):
        return self.master.basedir

    # service management

    @defer.inlineCallbacks
    def startService(self):
        # subscribe to the things we need to know about
        self._buildset_new_consumer = yield self.master.mq.startConsuming(
            self.bs_new_consumer_cb, ('buildsets', None, 'new'))
        self._buildset_complete_consumer = yield self.master.mq.startConsuming(
            self.bs_complete_consumer_cb, ('buildsets', None, 'complete'))
        self._br_consumer = yield self.master.mq.startConsuming(
            self.br_consumer_cb, ('buildrequests', None, 'new'))
        self._change_consumer = yield self.master.mq.startConsuming(
            self.change_consumer_cb, ('changes', None, 'new'))

        yield service.AsyncMultiService.startService(self)

    @defer.inlineCallbacks
    def reconfigServiceWithBuildbotConfig(self, new_config):
        # remove the old listeners, then add the new
        for sr in list(self):
            yield sr.disownServiceParent()

        for sr in new_config.status:
            yield sr.setServiceParent(self)

        # reconfig any newly-added change sources, as well as existing
        yield service.ReconfigurableServiceMixin.reconfigServiceWithBuildbotConfig(self,
                                                                                   new_config)

    def stopService(self):
        if self._buildset_complete_consumer:
            self._buildset_complete_consumer.stopConsuming()
            self._buildset_complete_consumer = None

        if self._buildset_new_consumer:
            self._buildset_new_consumer.stopConsuming()
            self._buildset_new_consumer = None

        if self._change_consumer:
            self._change_consumer.stopConsuming()
            self._change_consumer = None

        return service.AsyncMultiService.stopService(self)

    # clean shutdown

    @property
    def shuttingDown(self):
        return self.botmaster.shuttingDown

    def cleanShutdown(self):
        return self.botmaster.cleanShutdown()

    def cancelCleanShutdown(self):
        return self.botmaster.cancelCleanShutdown()

    # methods called by our clients

    def getTitle(self):
        return self.master.config.title

    def getTitleURL(self):
        return self.master.config.titleURL

    def getBuildbotURL(self):
        return self.master.config.buildbotURL

    def getStatus(self):
        # some listeners expect their .parent to be a BuildMaster object, and
        # use this method to get the Status object.  This is documented, so for
        # now keep it working.
        return self

    def getMetrics(self):
        return self.master.metrics

    def getURLForBuild(self, builderid, build_number):
        prefix = self.getBuildbotURL()
        return prefix + "#builders/%d/builds/%d" % (
            builderid,
            build_number)

    def _getURLForBuildWithBuildername(self, builder_name, build_number):
        # dont use this API. this URL is not supported
        # its here waiting for getURLForThing removal or switch to deferred
        prefix = self.getBuildbotURL()
        return prefix + "#builders/%s/builds/%d" % (
            urlquote(builder_name, safe=''),
            build_number)

    def getURLForBuildrequest(self, buildrequestid):
        prefix = self.getBuildbotURL()
        return prefix + "#buildrequests/%d" % (buildrequestid,)

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
            return prefix + "#builders/%s" % (
                urlquote(bldr.getName(), safe=''),
            )
        if interfaces.IBuildStatus.providedBy(thing):
            build = thing
            bldr = build.getBuilder()
            # should be:
            # builderid = yield bldr.getBuilderId()
            # return self.getURLForBuild(self, builderid, build.getNumber())
            return self._getURLForBuildWithBuildername(bldr.getName(), build.getNumber())

        if interfaces.IBuildStepStatus.providedBy(thing):
            step = thing
            build = step.getBuild()
            bldr = build.getBuilder()
            return prefix + "#builders/%s/builds/%d/steps/%s" % (
                urlquote(bldr.getName(), safe=''),
                build.getNumber(),
                urlquote(step.getName(), safe=''))
        # IBuildSetStatus
        # IBuildRequestStatus
        # ISlaveStatus
        if interfaces.ISlaveStatus.providedBy(thing):
            slave = thing
            return prefix + "#buildslaves/%s" % (
                urlquote(slave.getName(), safe=''),
            )

        # IStatusEvent
        if interfaces.IStatusEvent.providedBy(thing):
            # TODO: this is goofy, create IChange or something
            if isinstance(thing, changes.Change):
                change = thing
                return "%s#changes/%d" % (prefix, change.number)

    def getChangeSources(self):
        return list(self.master.change_svc)

    def getChange(self, number):
        """Get a Change object; returns a deferred"""
        d = self.master.db.changes.getChange(number)

        @d.addCallback
        def chdict2change(chdict):
            if not chdict:
                return None
            return changes.Change.fromChdict(self.master, chdict)
        return d

    def getSchedulers(self):
        return self.master.allSchedulers()

    def getBuilderNames(self, tags=None, categories=None):
        if categories is not None:
            # Categories is deprecated; pretend they said "tags".
            tags = categories

        if tags is None:
            return util.naturalSort(self.botmaster.builderNames)  # don't let them break it

        l = []
        # respect addition order
        for name in self.botmaster.builderNames:
            bldr = self.getBuilder(name)
            if bldr.matchesAnyTag(tags):
                l.append(name)
        return util.naturalSort(l)

    def getBuilder(self, name):
        """
        @rtype: L{BuilderStatus}
        """
        return self.botmaster.builders[name].builder_status

    def getSlaveNames(self):
        return list(iteritems(self.buildslaves.slaves))

    def getSlave(self, slavename):
        return self.buildslaves.slaves[slavename].slave_status

    def getBuildSets(self):
        d = self.master.db.buildsets.getBuildsets(complete=False)

        @d.addCallback
        def make_status_objects(bsdicts):
            return [buildset.BuildSetStatus(bsdict, self)
                    for bsdict in bsdicts]
        return d

    def generateFinishedBuilds(self, builders=None, branches=None,
                               num_builds=None, finished_before=None,
                               max_search=200):
        if builders is None:
            builders = []

        if branches is None:
            branches = []

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
            bldr = self.getBuilder(bn)
            g = bldr.generateFinishedBuilds(branches,
                                            finished_before=finished_before,
                                            max_search=max_search)
            sources.append(g)

        # next_build the next build from each source
        next_build = [None] * len(sources)

        def refill():
            for i, g in enumerate(sources):
                if next_build[i]:
                    # already filled
                    continue
                if not g:
                    # already exhausted
                    continue
                try:
                    next_build[i] = next(g)
                except StopIteration:
                    next_build[i] = None
                    sources[i] = None

        got = 0
        while True:
            refill()
            # find the latest build among all the candidates
            candidates = [(i, b, b.getTimes()[1])
                          for i, b in enumerate(next_build)
                          if b is not None]
            candidates.sort(lambda x, y: cmp(x[2], y[2]))
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

    def builderAdded(self, name, basedir, tags=None, description=None):
        """
        @rtype: L{BuilderStatus}
        """
        filename = os.path.join(self.basedir, basedir, "builder")
        log.msg("trying to load status pickle from %s" % filename)
        builder_status = None
        try:
            with open(filename, "rb") as f:
                builder_status = pickle.load(f)
            builder_status.master = self.master

            # (bug #1068) if we need to upgrade, we probably need to rewrite
            # this pickle, too.  We determine this by looking at the list of
            # Versioned objects that have been unpickled, and (after doUpgrade)
            # checking to see if any of them set wasUpgraded.  The Versioneds'
            # upgradeToVersionNN methods all set this.
            versioneds = styles.versionedsToUpgrade
            styles.doUpgrade()
            if True in [hasattr(o, 'wasUpgraded') for o in itervalues(versioneds)]:
                log.msg("re-writing upgraded builder pickle")
                builder_status.saveYourself()

        except IOError:
            log.msg("no saved status pickle, creating a new one")
        except Exception:
            log.err("error while loading status pickle, creating a new one")
        if not builder_status:
            builder_status = builder.BuilderStatus(name, tags, self.master,
                                                   description)
            builder_status.addPointEvent(["builder", "created"])
        log.msg("added builder %s with tags %r" % (name, tags))
        # an unpickled object might not have tags set from before,
        # so set it here to make sure
        builder_status.setTags(tags)
        builder_status.description = description
        builder_status.master = self.master
        builder_status.basedir = os.path.join(self.basedir, basedir)
        builder_status.name = name  # it might have been updated
        builder_status.status = self

        if not os.path.isdir(builder_status.basedir):
            os.makedirs(builder_status.basedir)
        builder_status.determineNextBuildNumber()

        builder_status.setBigState("offline")

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

    def slavePaused(self, name):
        for t in self.watchers:
            if hasattr(t, 'slavePaused'):
                t.slavePaused(name)

    def slaveUnpaused(self, name):
        for t in self.watchers:
            if hasattr(t, 'slaveUnpaused'):
                t.slaveUnpaused(name)

    def changeAdded(self, change):
        for t in self.watchers:
            if hasattr(t, 'changeAdded'):
                t.changeAdded(change)

    @defer.inlineCallbacks
    def br_consumer_cb(self, key, msg):
        builderid = msg['builderid']
        buildername = None
        # convert builderid to buildername
        for b in itervalues(self.botmaster.builders):
            if builderid == (yield b.getBuilderId()):
                buildername = b.name
                break
        if buildername in self._builder_observers:
            brs = buildrequest.BuildRequestStatus(buildername,
                                                  msg['buildrequestid'], self)
            for observer in self._builder_observers[buildername]:
                if hasattr(observer, 'requestSubmitted'):
                    eventually(observer.requestSubmitted, brs)

    @defer.inlineCallbacks
    def change_consumer_cb(self, key, msg):
        # get a list of watchers - no sense querying the change
        # if nobody's listening
        interested = [t for t in self.watchers
                      if hasattr(t, 'changeAdded')]
        if not interested:
            return

        chdict = yield self.master.db.changes.getChange(msg['changeid'])
        change = yield changes.Change.fromChdict(self.master, chdict)

        for t in interested:
            t.changeAdded(change)

    def asDict(self):
        result = {
            # Constant
            'title': self.getTitle(),
            'titleURL': self.getTitleURL(),
            'buildbotURL': self.getBuildbotURL(),
            # TODO: self.getSchedulers()
            # self.getChangeSources()
        }
        return result

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

        @d.addCallback
        def do_notifies(bsdict):
            bss = buildset.BuildSetStatus(bsdict, self)
            if bss.isFinished():
                for d in self._buildset_finished_waiters.pop(bsid):
                    eventually(d.callback, bss)
        d.addErrback(log.err, 'while notifying for buildset finishes')

    def _builder_subscribe(self, buildername, watcher):
        # should get requestSubmitted and requestCancelled
        self._builder_observers.add(buildername, watcher)

    def _builder_unsubscribe(self, buildername, watcher):
        self._builder_observers.discard(buildername, watcher)

    def bs_new_consumer_cb(self, key, msg):
        bsid = msg['bsid']
        d = self.master.db.buildsets.getBuildset(bsid)

        @d.addCallback
        def do_notifies(bsdict):
            bss = buildset.BuildSetStatus(bsdict, self)
            for t in self.watchers:
                if hasattr(t, 'buildsetSubmitted'):
                    t.buildsetSubmitted(bss)
        return d

    def bs_complete_consumer_cb(self, key, msg):
        self._maybeBuildsetFinished(msg['bsid'])
