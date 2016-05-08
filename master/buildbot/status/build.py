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
import re

from twisted.internet import defer
from twisted.internet import reactor
from twisted.persisted import styles
from zope.interface import implements

from buildbot import interfaces
from buildbot import util


class BuildStatus(styles.Versioned):
    implements(interfaces.IBuildStatus, interfaces.IStatusEvent)

    persistenceVersion = 4
    persistenceForgets = ('wasUpgraded', )

    sources = None
    reason = None
    changes = []
    blamelist = []
    progress = None
    started = None
    finished = None
    currentStep = None
    text = []
    results = None

    # these lists/dicts are defined here so that unserialized instances have
    # (empty) values. They are set in __init__ to new objects to make sure
    # each instance gets its own copy.
    watchers = []
    updates = {}
    finishedWatchers = []
    testResults = {}

    def __init__(self, parent, master, number):
        """
        @type  parent: L{BuilderStatus}
        @type  number: int
        """
        assert interfaces.IBuilderStatus(parent)
        self.builder = parent
        self.master = master
        self.number = number
        self.watchers = []
        self.updates = {}
        self.finishedWatchers = []
        self.steps = []
        self.testResults = {}
        self.workername = "???"

    def __repr__(self):
        return "<%s #%s>" % (self.__class__.__name__, self.number)

    # IBuildStatus

    def getBuilder(self):
        """
        @rtype: L{BuilderStatus}
        """
        return self.builder

    def getNumber(self):
        return self.number

    def getPreviousBuild(self):
        if self.number == 0:
            return None
        return self.builder.getBuild(self.number - 1)

    def getSourceStamps(self, absolute=False):
        return {}

    def getReason(self):
        return self.reason

    def getChanges(self):
        return self.changes

    def getRevisions(self):
        revs = []
        for c in self.changes:
            rev = str(c.revision)
            if rev > 7:  # for long hashes
                rev = rev[:7]
            revs.append(rev)
        return ", ".join(revs)

    def getResponsibleUsers(self):
        return self.blamelist

    def getSteps(self):
        """Return a list of IBuildStepStatus objects. For invariant builds
        (those which always use the same set of Steps), this should be the
        complete list, however some of the steps may not have started yet
        (step.getTimes()[0] will be None). For variant builds, this may not
        be complete (asking again later may give you more of them)."""
        return self.steps

    def getTimes(self):
        return (self.started, self.finished)

    _sentinel = []  # used as a sentinel to indicate unspecified initial_value

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
        return None

    def getCurrentStep(self):
        return self.currentStep

    # Once you know the build has finished, the following methods are legal.
    # Before this build has finished, they all return None.

    def getText(self):
        text = []
        text.extend(self.text)
        for s in self.steps:
            text.extend(s.text2)
        return text

    def getResults(self):
        return self.results

    def getWorkername(self):
        return self.workername

    def getTestResults(self):
        return self.testResults

    def getLogs(self):
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

    def addTestResult(self, result):
        self.testResults[result.getName()] = result

    def setSourceStamps(self, sourceStamps):
        self.sources = sourceStamps
        self.changes = []
        for source in self.sources:
            self.changes.extend(source.changes)

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

    def setWorkername(self, workername):
        self.workername = workername

    def setText(self, text):
        assert isinstance(text, (list, tuple))
        self.text = text

    def setResults(self, results):
        self.results = results

    def buildFinished(self):
        self.currentStep = None
        self.finished = util.now()

        for update in self.updates:
            if self.updates[update] is not None:
                self.updates[update].cancel()
                del self.updates[update]

        watchers = self.finishedWatchers
        self.finishedWatchers = []
        for w in watchers:
            w.callback(self)

    # methods previously called by our now-departed BuildStepStatus children

    def stepStarted(self, step):
        self.currentStep = step
        for w in self.watchers:
            receiver = w.stepStarted(self, step)
            if receiver:
                if isinstance(receiver, type(())):
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
        for k in ['builder', 'watchers', 'updates', 'finishedWatchers',
                  'master']:
            if k in d:
                del d[k]
        return d

    def __setstate__(self, d):
        styles.Versioned.__setstate__(self, d)
        self.watchers = []
        self.updates = {}
        self.finishedWatchers = []

    def setProcessObjects(self, builder, master):
        self.builder = builder
        self.master = master
        for step in self.steps:
            step.setProcessObjects(self, master)

    def upgradeToVersion1(self):
        if hasattr(self, "sourceStamp"):
            # the old .sourceStamp attribute wasn't actually very useful
            maxChangeNumber, patch = self.sourceStamp
            changes = getattr(self, 'changes', [])
            # the old SourceStamp class is gone, so use the one that is
            # provided for backward compatibility
            from buildbot.util.pickle import SourceStamp
            source = SourceStamp(branch=None,
                                 revision=None,
                                 patch=patch,
                                 changes=changes)
            self.source = source
            self.changes = source.changes
            del self.sourceStamp
        self.wasUpgraded = True

    def upgradeToVersion2(self):
        self.wasUpgraded = True

    def upgradeToVersion3(self):
        self.wasUpgraded = True

    def upgradeToVersion4(self):
        # buildstatus contains list of sourcestamps, convert single to list
        if hasattr(self, "source"):
            self.sources = [self.source]
            del self.source
        self.wasUpgraded = True

    def checkLogfiles(self):
        # check that all logfiles exist, and remove references to any that
        # have been deleted (e.g., by purge())
        for s in self.steps:
            s.checkLogfiles()

    def saveYourself(self):
        return

    def asDict(self):
        result = {}
        # Constant
        result['builderName'] = self.builder.name
        result['number'] = self.getNumber()
        result['sourceStamps'] = [ss.asDict() for ss in self.getSourceStamps()]
        result['reason'] = self.getReason()
        result['blame'] = self.getResponsibleUsers()

        # Transient
        result['times'] = self.getTimes()
        result['text'] = self.getText()
        result['results'] = self.getResults()
        result['worker'] = self.getWorkername()
        # TODO(maruel): Add.
        # result['test_results'] = self.getTestResults()
        result['logs'] = [[l.getName(),
                           self.builder.status.getURLForThing(l)] for l in self.getLogs()]
        result['eta'] = None
        result['steps'] = [bss.asDict() for bss in self.steps]
        if self.getCurrentStep():
            result['currentStep'] = self.getCurrentStep().asDict()
        else:
            result['currentStep'] = None
        return result
