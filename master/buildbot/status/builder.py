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

from __future__ import absolute_import
from __future__ import print_function

import itertools
import os

from twisted.persisted import styles
from twisted.python import log
from zope.interface import implementer

from buildbot import interfaces
from buildbot import util
# user modules expect these symbols to be present here
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SKIPPED
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.process.results import Results
from buildbot.process.results import worst_status
from buildbot.status.build import BuildStatus
from buildbot.status.buildrequest import BuildRequestStatus
from buildbot.status.event import Event
from buildbot.util.lru import LRUCache

_hush_pyflakes = [SUCCESS, WARNINGS, FAILURE, SKIPPED,
                  EXCEPTION, RETRY, CANCELLED, Results, worst_status]


@implementer(interfaces.IBuilderStatus, interfaces.IEventSource)
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

    @type  tags: None or list of strings
    @ivar  tags: user-defined "tag" this builder has; can be
                     used to filter on in status clients
    """

    persistenceVersion = 2
    persistenceForgets = ('wasUpgraded', )

    tags = None
    currentBigState = "offline"  # or idle/waiting/interlocked/building
    basedir = None  # filled in by our parent

    def __init__(self, buildername, tags, master, description):
        self.name = buildername
        self.tags = tags
        self.description = description
        self.master = master

        self.workernames = []
        self.events = []
        # these three hold Events, and are used to retrieve the current
        # state of the boxes.
        self.lastBuildStatus = None
        self.currentBuilds = []
        self.nextBuild = None
        self.watchers = []
        self.buildCache = LRUCache(self.cacheMiss)

    # build cache management
    def setCacheSize(self, size):
        self.buildCache.set_max_size(size)

    def getBuildByNumber(self, number):
        return self.buildCache.get(number)

    def cacheMiss(self, number, **kwargs):
        # If kwargs['val'] exists, this is a new value being added to
        # the cache.  Just return it.
        if 'val' in kwargs:
            return kwargs['val']

        # first look in currentBuilds
        for b in self.currentBuilds:
            if b.number == number:
                return b

        # Otherwise it is in the database and thus inaccessible.
        return None

    def prune(self, events_only=False):
        pass

    # IBuilderStatus methods
    def getName(self):
        # if builderstatus page does show not up without any reason then
        # str(self.name) may be a workaround
        return self.name

    def setDescription(self, description):
        # used during reconfig
        self.description = description

    def getDescription(self):
        return self.description

    def getState(self):
        return (self.currentBigState, self.currentBuilds)

    def getWorkers(self):
        return [self.status.getWorker(name) for name in self.workernames]

    def getPendingBuildRequestStatuses(self):
        # just assert 0 here. According to dustin the whole class will go away
        # soon.
        assert 0
        db = self.status.master.db
        d = db.buildrequests.getBuildRequests(claimed=False,
                                              buildername=self.name)

        @d.addCallback
        def make_statuses(brdicts):
            return [BuildRequestStatus(self.name, brdict['brid'],
                                       self.status, brdict=brdict)
                    for brdict in brdicts]
        return d

    def getCurrentBuilds(self):
        return self.currentBuilds

    def getLastFinishedBuild(self):
        b = self.getBuild(-1)
        if not (b and b.isFinished()):
            b = self.getBuild(-2)
        return b

    def getTags(self):
        return self.tags

    def setTags(self, tags):
        # used during reconfig
        self.tags = tags

    def matchesAnyTag(self, tags):
        # Need to guard against None with the "or []".
        return bool(set(self.tags or []) & set(tags))

    def getBuildByRevision(self, rev):
        number = self.nextBuildNumber - 1
        while number > 0:
            build = self.getBuildByNumber(number)
            got_revision = build.getAllGotRevisions().get("")

            if rev == got_revision:
                return build
            number -= 1
        return None

    def getBuild(self, number, revision=None):
        if revision is not None:
            return self.getBuildByRevision(revision)

        if number < 0:
            number = self.nextBuildNumber + number
        if number < 0 or number >= self.nextBuildNumber:
            return None

        try:
            return self.getBuildByNumber(number)
        except IndexError:
            return None

    def getEvent(self, number):
        return None

    def _getBuildBranches(self, build):
        return set([ss.branch
                    for ss in build.getSourceStamps()])

    def generateFinishedBuilds(self, branches=None,
                               num_builds=None,
                               max_buildnum=None,
                               finished_before=None,
                               results=None,
                               max_search=200,
                               filter_fn=None):
        got = 0
        if branches is None:
            branches = set()
        else:
            branches = set(branches)
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
            if branches and not branches & self._getBuildBranches(build):
                continue
            if results is not None:
                if build.getResults() not in results:
                    continue
            if filter_fn is not None:
                if not filter_fn(build):
                    continue
            got += 1
            yield build
            if num_builds is not None:
                if got >= num_builds:
                    return

    def eventGenerator(self, branches=None, categories=None, committers=None, projects=None, minTime=0):
        if False:  # pylint: disable=using-constant-test
            yield

    def subscribe(self, receiver):
        # will get builderChangedState, buildStarted, buildFinished,
        # requestSubmitted, requestCancelled. Note that a request which is
        # resubmitted (due to a worker disconnect) will cause requestSubmitted
        # to be invoked multiple times.
        self.watchers.append(receiver)
        self.publishState(receiver)
        # our parent Status provides requestSubmitted and requestCancelled
        self.status._builder_subscribe(self.name, receiver)

    def unsubscribe(self, receiver):
        self.watchers.remove(receiver)
        self.status._builder_unsubscribe(self.name, receiver)

    # Builder interface (methods called by the Builder which feeds us)

    def setWorkernames(self, names):
        self.workernames = names

    def addEvent(self, text=None):
        # this adds a duration event. When it is done, the user should call
        # e.finish(). They can also mangle it by modifying .text
        e = Event()
        e.started = util.now()
        if text is None:
            text = []
        e.text = text
        return e  # they are free to mangle it further

    def addPointEvent(self, text=None):
        # this adds a point event, one which occurs as a single atomic
        # instant of time.
        e = Event()
        e.started = util.now()
        e.finished = 0
        if text is None:
            text = []
        e.text = text
        return e  # for consistency, but they really shouldn't touch it

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
            except Exception:
                log.msg("Exception caught publishing state to %r" % w)
                log.err()

    def newBuild(self):
        s = BuildStatus(self, self.master, 0)
        return s

    # buildStarted is called by our child BuildStatus instances
    def buildStarted(self, s):
        """Now the BuildStatus object is ready to go (it knows all of its
        Steps, its ETA, etc), so it is safe to notify our watchers."""

        assert s.builder is self  # paranoia
        assert s not in self.currentBuilds
        self.currentBuilds.append(s)
        self.buildCache.get(s.number, val=s)

        # now that the BuildStatus is prepared to answer queries, we can
        # announce the new build to all our watchers

        for w in self.watchers:  # TODO: maybe do this later? callLater(0)?
            try:
                receiver = w.buildStarted(self.getName(), s)
                if receiver:
                    if isinstance(receiver, type(())):
                        s.subscribe(receiver[0], receiver[1])
                    else:
                        s.subscribe(receiver)
                    d = s.waitUntilFinished()
                    # TODO: This actually looks like a bug, but this code
                    # will be removed anyway.
                    # pylint: disable=cell-var-from-loop
                    d.addCallback(lambda s: s.unsubscribe(receiver))
            except Exception:
                log.msg(
                    "Exception caught notifying %r of buildStarted event" % w)
                log.err()

    def _buildFinished(self, s):
        assert s in self.currentBuilds
        self.currentBuilds.remove(s)

        name = self.getName()
        results = s.getResults()
        for w in self.watchers:
            try:
                w.buildFinished(name, s, results)
            except Exception:
                log.msg(
                    "Exception caught notifying %r of buildFinished event" % w)
                log.err()

    def asDict(self):
        # Collect build numbers.
        # Important: Only grab the *cached* builds numbers to reduce I/O.
        current_builds = [b.getNumber() for b in self.currentBuilds]
        cached_builds = sorted(set(list(self.buildCache) + current_builds))

        result = {
            # Constant
            # TODO(maruel): Fix me. We don't want to leak the full path.
            'basedir': os.path.basename(self.basedir),
            'tags': self.getTags(),
            'workers': self.workernames,
            'schedulers': [s.name for s in self.status.master.allSchedulers()
                           if self.name in s.builderNames],
            # TODO(maruel): Add cache settings? Do we care?

            # Transient
            'cachedBuilds': cached_builds,
            'currentBuilds': current_builds,
            'state': self.getState()[0],
            # lies, but we don't have synchronous access to this info; use
            # asDict_async instead
            'pendingBuilds': 0
        }
        return result

    def asDict_async(self):
        """Just like L{asDict}, but with a nonzero pendingBuilds."""
        result = self.asDict()
        d = self.getPendingBuildRequestStatuses()

        @d.addCallback
        def combine(statuses):
            result['pendingBuilds'] = len(statuses)
            return result
        return d

    def getMetrics(self):
        return self.botmaster.parent.metrics

# vim: set ts=4 sts=4 sw=4 et:
