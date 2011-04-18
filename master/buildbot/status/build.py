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

import os, shutil, re
from cPickle import dump
from zope.interface import implements
from twisted.python import log, runtime
from twisted.persisted import styles
from twisted.internet import reactor, defer
from buildbot import interfaces, util, sourcestamp
from buildbot.process.properties import Properties
from buildbot.status.buildstep import BuildStepStatus

class BuildStatus(styles.Versioned):
    implements(interfaces.IBuildStatus, interfaces.IStatusEvent)

    persistenceVersion = 3
    persistenceForgets = ( 'wasUpgraded', )

    source = None
    reason = None
    changes = []
    blamelist = []
    progress = None
    started = None
    finished = None
    currentStep = None
    text = []
    results = None
    slavename = "???"

    # these lists/dicts are defined here so that unserialized instances have
    # (empty) values. They are set in __init__ to new objects to make sure
    # each instance gets its own copy.
    watchers = []
    updates = {}
    finishedWatchers = []
    testResults = {}

    def __init__(self, parent, number):
        """
        @type  parent: L{BuilderStatus}
        @type  number: int
        """
        assert interfaces.IBuilderStatus(parent)
        self.builder = parent
        self.number = number
        self.watchers = []
        self.updates = {}
        self.finishedWatchers = []
        self.steps = []
        self.testResults = {}
        self.properties = Properties()

    def __repr__(self):
        return "<%s #%s>" % (self.__class__.__name__, self.number)

    # IBuildStatus

    def getBuilder(self):
        """
        @rtype: L{BuilderStatus}
        """
        return self.builder

    def getProperty(self, propname):
        return self.properties[propname]

    def getProperties(self):
        return self.properties

    def getNumber(self):
        return self.number

    def getPreviousBuild(self):
        if self.number == 0:
            return None
        return self.builder.getBuild(self.number-1)

    def getSourceStamp(self, absolute=False):
        if not absolute or not self.properties.has_key('got_revision'):
            return self.source
        return self.source.getAbsoluteSourceStamp(self.properties['got_revision'])

    def getReason(self):
        return self.reason

    def getChanges(self):
        return self.changes

    def getResponsibleUsers(self):
        return self.blamelist

    def getInterestedUsers(self):
        # TODO: the Builder should add others: sheriffs, domain-owners
        return self.blamelist + self.properties.getProperty('owners', [])

    def getSteps(self):
        """Return a list of IBuildStepStatus objects. For invariant builds
        (those which always use the same set of Steps), this should be the
        complete list, however some of the steps may not have started yet
        (step.getTimes()[0] will be None). For variant builds, this may not
        be complete (asking again later may give you more of them)."""
        return self.steps

    def getTimes(self):
        return (self.started, self.finished)

    _sentinel = [] # used as a sentinel to indicate unspecified initial_value
    def getSummaryStatistic(self, name, summary_fn, initial_value=_sentinel):
        """Summarize the named statistic over all steps in which it
        exists, using combination_fn and initial_value to combine multiple
        results into a single result.  This translates to a call to Python's
        X{reduce}::
            return reduce(summary_fn, step_stats_list, initial_value)
        """
        step_stats_list = [
                st.getStatistic(name)
                for st in self.steps
                if st.hasStatistic(name) ]
        if initial_value is self._sentinel:
            return reduce(summary_fn, step_stats_list)
        else:
            return reduce(summary_fn, step_stats_list, initial_value)

    def isFinished(self):
        return (self.finished is not None)

    def waitUntilFinished(self):
        if self.finished:
            d = defer.succeed(self)
        else:
            d = defer.Deferred()
            self.finishedWatchers.append(d)
        return d

    # while the build is running, the following methods make sense.
    # Afterwards they return None

    def getETA(self):
        if self.finished is not None:
            return None
        if not self.progress:
            return None
        eta = self.progress.eta()
        if eta is None:
            return None
        return eta - util.now()

    def getCurrentStep(self):
        return self.currentStep

    # Once you know the build has finished, the following methods are legal.
    # Before ths build has finished, they all return None.

    def getText(self):
        text = []
        text.extend(self.text)
        for s in self.steps:
            text.extend(s.text2)
        return text

    def getResults(self):
        return self.results

    def getSlavename(self):
        return self.slavename

    def getTestResults(self):
        return self.testResults

    def getTestResultsOrd(self):
        trs = self.testResults.keys()
        trs.sort()
        ret = [ self.testResults[t] for t in trs]
        return ret

    def getLogs(self):
        # TODO: steps should contribute significant logs instead of this
        # hack, which returns every log from every step. The logs should get
        # names like "compile" and "test" instead of "compile.output"
        logs = []
        for s in self.steps:
            for loog in s.getLogs():
                logs.append(loog)
        return logs

    # subscription interface

    def subscribe(self, receiver, updateInterval=None):
        # will receive stepStarted and stepFinished messages
        # and maybe buildETAUpdate
        self.watchers.append(receiver)
        if updateInterval is not None:
            self.sendETAUpdate(receiver, updateInterval)

    def sendETAUpdate(self, receiver, updateInterval):
        self.updates[receiver] = None
        ETA = self.getETA()
        if ETA is not None:
            receiver.buildETAUpdate(self, self.getETA())
        # they might have unsubscribed during buildETAUpdate
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

    # methods for the base.Build to invoke

    def addStepWithName(self, name):
        """The Build is setting up, and has added a new BuildStep to its
        list. Create a BuildStepStatus object to which it can send status
        updates."""

        s = BuildStepStatus(self, len(self.steps))
        s.setName(name)
        self.steps.append(s)
        return s

    def setProperty(self, propname, value, source, runtime=True):
        self.properties.setProperty(propname, value, source, runtime)

    def addTestResult(self, result):
        self.testResults[result.getName()] = result

    def setSourceStamp(self, sourceStamp):
        self.source = sourceStamp
        self.changes = self.source.changes

    def setReason(self, reason):
        self.reason = reason
    def setBlamelist(self, blamelist):
        self.blamelist = blamelist
    def setProgress(self, progress):
        self.progress = progress

    def buildStarted(self, build):
        """The Build has been set up and is about to be started. It can now
        be safely queried, so it is time to announce the new build."""

        self.started = util.now()
        # now that we're ready to report status, let the BuilderStatus tell
        # the world about us
        self.builder.buildStarted(self)

    def setSlavename(self, slavename):
        self.slavename = slavename

    def setText(self, text):
        assert isinstance(text, (list, tuple))
        self.text = text
    def setResults(self, results):
        self.results = results

    def buildFinished(self):
        self.currentStep = None
        self.finished = util.now()

        for r in self.updates.keys():
            if self.updates[r] is not None:
                self.updates[r].cancel()
                del self.updates[r]

        watchers = self.finishedWatchers
        self.finishedWatchers = []
        for w in watchers:
            w.callback(self)

    # methods called by our BuildStepStatus children

    def stepStarted(self, step):
        self.currentStep = step
        for w in self.watchers:
            receiver = w.stepStarted(self, step)
            if receiver:
                if type(receiver) == type(()):
                    step.subscribe(receiver[0], receiver[1])
                else:
                    step.subscribe(receiver)
                d = step.waitUntilFinished()
                d.addCallback(lambda step: step.unsubscribe(receiver))

        step.waitUntilFinished().addCallback(self._stepFinished)

    def _stepFinished(self, step):
        results = step.getResults()
        for w in self.watchers:
            w.stepFinished(self, step, results)

    # methods called by our BuilderStatus parent

    def pruneSteps(self):
        # this build is very old: remove the build steps too
        self.steps = []

    # persistence stuff

    def generateLogfileName(self, stepname, logname):
        """Return a filename (relative to the Builder's base directory) where
        the logfile's contents can be stored uniquely.

        The base filename is made by combining our build number, the Step's
        name, and the log's name, then removing unsuitable characters. The
        filename is then made unique by appending _0, _1, etc, until it does
        not collide with any other logfile.

        These files are kept in the Builder's basedir (rather than a
        per-Build subdirectory) because that makes cleanup easier: cron and
        find will help get rid of the old logs, but the empty directories are
        more of a hassle to remove."""

        starting_filename = "%d-log-%s-%s" % (self.number, stepname, logname)
        starting_filename = re.sub(r'[^\w\.\-]', '_', starting_filename)
        # now make it unique
        unique_counter = 0
        filename = starting_filename
        while filename in [l.filename
                           for step in self.steps
                           for l in step.getLogs()
                           if l.filename]:
            filename = "%s_%d" % (starting_filename, unique_counter)
            unique_counter += 1
        return filename

    def __getstate__(self):
        d = styles.Versioned.__getstate__(self)
        # for now, a serialized Build is always "finished". We will never
        # save unfinished builds.
        if not self.finished:
            d['finished'] = util.now()
            # TODO: push an "interrupted" step so it is clear that the build
            # was interrupted. The builder will have a 'shutdown' event, but
            # someone looking at just this build will be confused as to why
            # the last log is truncated.
        for k in 'builder', 'watchers', 'updates', 'finishedWatchers':
            if k in d: del d[k]
        return d

    def __setstate__(self, d):
        styles.Versioned.__setstate__(self, d)
        # self.builder must be filled in by our parent when loading
        for step in self.steps:
            step.build = self
        self.watchers = []
        self.updates = {}
        self.finishedWatchers = []

    def upgradeToVersion1(self):
        if hasattr(self, "sourceStamp"):
            # the old .sourceStamp attribute wasn't actually very useful
            maxChangeNumber, patch = self.sourceStamp
            changes = getattr(self, 'changes', [])
            source = sourcestamp.SourceStamp(branch=None,
                                             revision=None,
                                             patch=patch,
                                             changes=changes)
            self.source = source
            self.changes = source.changes
            del self.sourceStamp
        self.wasUpgraded = True

    def upgradeToVersion2(self):
        self.properties = {}
        self.wasUpgraded = True

    def upgradeToVersion3(self):
        # in version 3, self.properties became a Properties object
        propdict = self.properties
        self.properties = Properties()
        self.properties.update(propdict, "Upgrade from previous version")
        self.wasUpgraded = True

    def upgradeLogfiles(self):
        # upgrade any LogFiles that need it. This must occur after we've been
        # attached to our Builder, and after we know about all LogFiles of
        # all Steps (to get the filenames right).
        assert self.builder
        for s in self.steps:
            for l in s.getLogs():
                if l.filename:
                    pass # new-style, log contents are on disk
                else:
                    logfilename = self.generateLogfileName(s.name, l.name)
                    # let the logfile update its .filename pointer,
                    # transferring its contents onto disk if necessary
                    l.upgrade(logfilename)

    def checkLogfiles(self):
        # check that all logfiles exist, and remove references to any that
        # have been deleted (e.g., by purge())
        for s in self.steps:
            s.checkLogfiles()

    def saveYourself(self):
        filename = os.path.join(self.builder.basedir, "%d" % self.number)
        if os.path.isdir(filename):
            # leftover from 0.5.0, which stored builds in directories
            shutil.rmtree(filename, ignore_errors=True)
        tmpfilename = filename + ".tmp"
        try:
            dump(self, open(tmpfilename, "wb"), -1)
            if runtime.platformType  == 'win32':
                # windows cannot rename a file on top of an existing one, so
                # fall back to delete-first. There are ways this can fail and
                # lose the builder's history, so we avoid using it in the
                # general (non-windows) case
                if os.path.exists(filename):
                    os.unlink(filename)
            os.rename(tmpfilename, filename)
        except:
            log.msg("unable to save build %s-#%d" % (self.builder.name,
                                                     self.number))
            log.err()

    def asDict(self):
        result = {}
        # Constant
        result['builderName'] = self.builder.name
        result['number'] = self.getNumber()
        result['sourceStamp'] = self.getSourceStamp().asDict()
        result['reason'] = self.getReason()
        result['blame'] = self.getResponsibleUsers()

        # Transient
        result['properties'] = self.getProperties().asList()
        result['times'] = self.getTimes()
        result['text'] = self.getText()
        result['results'] = self.getResults()
        result['slave'] = self.getSlavename()
        # TODO(maruel): Add.
        #result['test_results'] = self.getTestResults()
        result['logs'] = [[l.getName(),
            self.builder.status.getURLForThing(l)] for l in self.getLogs()]
        result['eta'] = self.getETA()
        result['steps'] = [bss.asDict() for bss in self.steps]
        if self.getCurrentStep():
            result['currentStep'] = self.getCurrentStep().asDict()
        else:
            result['currentStep'] = None
        return result



