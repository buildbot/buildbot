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

from buildbot import interfaces
from buildbot import util
from buildbot.status.logfile import HTMLLogFile
from buildbot.status.logfile import LogFile
from twisted.internet import defer
from twisted.internet import reactor
from twisted.persisted import styles
from twisted.python import log
from zope.interface import implements


class BuildStepStatus(styles.Versioned):

    """
    I represent a collection of output status for a
    L{buildbot.process.step.BuildStep}.

    Statistics contain any information gleaned from a step that is
    not in the form of a logfile.  As an example, steps that run
    tests might gather statistics about the number of passed, failed,
    or skipped tests.

    @type progress: L{buildbot.status.progress.StepProgress}
    @cvar progress: tracks ETA for the step
    @type text: list of strings
    @cvar text: list of short texts that describe the command and its status
    @type text2: list of strings
    @cvar text2: list of short texts added to the overall build description
    @type logs: dict of string -> L{buildbot.status.logfile.LogFile}
    @ivar logs: logs of steps
    @type statistics: dict
    @ivar statistics: results from running this step
    """
    # note that these are created when the Build is set up, before each
    # corresponding BuildStep has started.
    implements(interfaces.IBuildStepStatus, interfaces.IStatusEvent)

    persistenceVersion = 4
    persistenceForgets = ('wasUpgraded', )

    started = None
    finished = None
    progress = None
    text = []
    results = None
    text2 = []
    watchers = []
    updates = {}
    finishedWatchers = []
    statistics = {}
    step_number = None
    hidden = False

    def __init__(self, parent, master, step_number):
        assert interfaces.IBuildStatus(parent)
        self.build = parent
        self.step_number = step_number
        self.hidden = False
        self.logs = []
        self.urls = {}
        self.watchers = []
        self.updates = {}
        self.finishedWatchers = []
        self.statistics = {}
        self.skipped = False

        self.master = master

        self.waitingForLocks = False

    def getName(self):
        """Returns a short string with the name of this step. This string
        may have spaces in it."""
        return self.name

    def getBuild(self):
        return self.build

    def getTimes(self):
        return (self.started, self.finished)

    def getExpectations(self):
        """Returns a list of tuples (name, current, target)."""
        if not self.progress:
            return []
        ret = []
        metrics = sorted(self.progress.progress.keys())
        for m in metrics:
            t = (m, self.progress.progress[m], self.progress.expectations[m])
            ret.append(t)
        return ret

    def getLogs(self):
        return self.logs

    def getURLs(self):
        return self.urls.copy()

    def isStarted(self):
        return (self.started is not None)

    def isSkipped(self):
        return self.skipped

    def isFinished(self):
        return (self.finished is not None)

    def isHidden(self):
        return self.hidden

    def waitUntilFinished(self):
        if self.finished:
            d = defer.succeed(self)
        else:
            d = defer.Deferred()
            self.finishedWatchers.append(d)
        return d

    # while the step is running, the following methods make sense.
    # Afterwards they return None

    def getETA(self):
        if self.started is None:
            return None  # not started yet
        if self.finished is not None:
            return None  # already finished
        if not self.progress:
            return None  # no way to predict
        return self.progress.remaining()

    # Once you know the step has finished, the following methods are legal.
    # Before this step has finished, they all return None.

    def getText(self):
        """Returns a list of strings which describe the step. These are
        intended to be displayed in a narrow column. If more space is
        available, the caller should join them together with spaces before
        presenting them to the user."""
        return self.text

    def getResults(self):
        """Return a tuple describing the results of the step.
        'result' is one of the constants in L{buildbot.status.builder}:
        SUCCESS, WARNINGS, FAILURE, or SKIPPED.
        'strings' is an optional list of strings that the step wants to
        append to the overall build's results. These strings are usually
        more terse than the ones returned by getText(): in particular,
        successful Steps do not usually contribute any text to the
        overall build.

        @rtype:   tuple of int, list of strings
        @returns: (result, strings)
        """
        return (self.results, self.text2)

    def hasStatistic(self, name):
        """Return true if this step has a value for the given statistic.
        """
        return name in self.statistics

    def getStatistic(self, name, default=None):
        """Return the given statistic, if present
        """
        return self.statistics.get(name, default)

    def getStatistics(self):
        return self.statistics.copy()

    # subscription interface

    def subscribe(self, receiver, updateInterval=10):
        # will get logStarted, logFinished, stepETAUpdate
        assert receiver not in self.watchers
        self.watchers.append(receiver)
        self.sendETAUpdate(receiver, updateInterval)

    def sendETAUpdate(self, receiver, updateInterval):
        self.updates[receiver] = None
        # they might unsubscribe during stepETAUpdate
        receiver.stepETAUpdate(self.build, self,
                               self.getETA(), self.getExpectations())
        if receiver in self.watchers:
            self.updates[receiver] = reactor.callLater(updateInterval,
                                                       self.sendETAUpdate,
                                                       receiver,
                                                       updateInterval)

    def unsubscribe(self, receiver):
        if receiver in self.watchers:
            self.watchers.remove(receiver)
        if receiver in self.updates:
            if self.updates[receiver] is not None:
                self.updates[receiver].cancel()
            del self.updates[receiver]

    # methods to be invoked by the BuildStep
    def setName(self, stepname):
        self.name = stepname

    def setColor(self, color):
        log.msg("BuildStepStatus.setColor is no longer supported -- ignoring color %s" % (color,))

    def setProgress(self, stepprogress):
        self.progress = stepprogress

    def setHidden(self, hidden):
        self.hidden = hidden

    def stepStarted(self):
        self.started = util.now()
        if self.build:
            self.build.stepStarted(self)

    def addLog(self, name):
        assert self.started  # addLog before stepStarted won't notify watchers
        logfilename = self.build.generateLogfileName(self.name, name)
        log = LogFile(self, name, logfilename)
        self.logs.append(log)
        for w in self.watchers:
            receiver = w.logStarted(self.build, self, log)
            if receiver:
                log.subscribe(receiver, True)
                d = log.waitUntilFinished()
                d.addCallback(lambda log: log.unsubscribe(receiver))
        d = log.waitUntilFinished()
        d.addCallback(self.logFinished)
        return log

    def addHTMLLog(self, name, html):
        assert self.started  # addLog before stepStarted won't notify watchers
        logfilename = self.build.generateLogfileName(self.name, name)
        log = HTMLLogFile(self, name, logfilename, html)
        self.logs.append(log)
        for w in self.watchers:
            w.logStarted(self.build, self, log)
            w.logFinished(self.build, self, log)

    def logFinished(self, log):
        for w in self.watchers:
            w.logFinished(self.build, self, log)

    def addURL(self, name, url):
        self.urls[name] = url

    def setText(self, text):
        self.text = text
        for w in self.watchers:
            w.stepTextChanged(self.build, self, text)

    def setText2(self, text):
        self.text2 = text
        for w in self.watchers:
            w.stepText2Changed(self.build, self, text)

    def setStatistic(self, name, value):
        """Set the given statistic.  Usually called by subclasses.
        """
        self.statistics[name] = value

    def setSkipped(self, skipped):
        self.skipped = skipped

    def stepFinished(self, results):
        self.finished = util.now()
        self.results = results
        cld = []  # deferreds for log compression
        logCompressionLimit = self.master.config.logCompressionLimit
        for loog in self.logs:
            if not loog.isFinished():
                loog.finish()
            # if log compression is on, and it's a real LogFile,
            # HTMLLogFiles aren't files
            if logCompressionLimit is not False and \
                    isinstance(loog, LogFile):
                if os.path.getsize(loog.getFilename()) > logCompressionLimit:
                    loog_deferred = loog.compressLog()
                    if loog_deferred:
                        cld.append(loog_deferred)

        for r in self.updates.keys():
            if self.updates[r] is not None:
                self.updates[r].cancel()
                del self.updates[r]

        watchers = self.finishedWatchers
        self.finishedWatchers = []
        for w in watchers:
            w.callback(self)
        if cld:
            return defer.DeferredList(cld)

    def checkLogfiles(self):
        # filter out logs that have been deleted
        self.logs = [l for l in self.logs if l.old_hasContents()]

    def isWaitingForLocks(self):
        return self.waitingForLocks

    def setWaitingForLocks(self, waiting):
        self.waitingForLocks = waiting

    # persistence

    def __getstate__(self):
        d = styles.Versioned.__getstate__(self)
        del d['build']  # filled in when loading
        if "progress" in d:
            del d['progress']
        del d['watchers']
        del d['finishedWatchers']
        del d['updates']
        del d['master']
        return d

    def __setstate__(self, d):
        styles.Versioned.__setstate__(self, d)
        # self.build must be filled in by our parent

        # point the logs to this object
        self.watchers = []
        self.finishedWatchers = []
        self.updates = {}

    def setProcessObjects(self, build, master):
        self.build = build
        self.master = master
        for loog in self.logs:
            loog.step = self
            loog.master = master

    def upgradeToVersion1(self):
        if not hasattr(self, "urls"):
            self.urls = {}
        self.wasUpgraded = True

    def upgradeToVersion2(self):
        if not hasattr(self, "statistics"):
            self.statistics = {}
        self.wasUpgraded = True

    def upgradeToVersion3(self):
        if not hasattr(self, "step_number"):
            self.step_number = 0
        self.wasUpgraded = True

    def upgradeToVersion4(self):
        if not hasattr(self, "hidden"):
            self.hidden = False
        self.wasUpgraded = True

    def asDict(self):
        result = {}
        # Constant
        result['name'] = self.getName()

        # Transient
        result['text'] = self.getText()
        result['results'] = self.getResults()
        result['isStarted'] = self.isStarted()
        result['isFinished'] = self.isFinished()
        result['statistics'] = self.statistics
        result['times'] = self.getTimes()
        result['expectations'] = self.getExpectations()
        result['eta'] = self.getETA()
        result['urls'] = self.getURLs()
        result['step_number'] = self.step_number
        result['hidden'] = self.hidden
        result['logs'] = [[l.getName(),
                           self.build.builder.status.getURLForThing(l)]
                          for l in self.getLogs()]
        return result
