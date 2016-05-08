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
from __future__ import print_function

import cPickle
import cStringIO
import new
import os
import sys
from bz2 import BZ2File
from collections import defaultdict
from cStringIO import StringIO
from functools import reduce
from gzip import GzipFile

from future.utils import iteritems
from future.utils import itervalues
from twisted.internet import defer
from twisted.internet import reactor
from twisted.persisted import styles
from twisted.python import log
from twisted.python import reflect
from twisted.spread import pb
from zope.interface import implements

from buildbot import interfaces
from buildbot import util
from buildbot.util import netstrings

# This module contains classes that are referenced in pickles, and thus needed
# during upgrade operations, but are no longer used in a running Buildbot
# master.
substituteClasses = {}


class SourceStamp(styles.Versioned):  # pragma: no cover
    persistenceVersion = 3
    persistenceForgets = ('wasUpgraded', )

    # all seven of these are publicly visible attributes
    branch = None
    revision = None
    patch = None
    patch_info = None
    changes = ()
    project = ''
    repository = ''
    codebase = ''
    sourcestampsetid = None
    ssid = None

    compare_attrs = ('branch', 'revision', 'patch', 'patch_info',
                     'changes', 'project', 'repository', 'codebase')

    implements(interfaces.ISourceStamp)

    def __init__(self, branch=None, revision=None, patch=None,
                 patch_info=None, changes=None, project='', repository='',
                 codebase='', _ignoreChanges=False):

        if patch is not None:
            assert 2 <= len(patch) <= 3
            assert int(patch[0]) != -1
        self.branch = branch
        self.patch = patch
        self.patch_info = patch_info
        self.project = project or ''
        self.repository = repository or ''
        self.codebase = codebase or ''
        if changes:
            self.changes = changes = list(changes)
            changes.sort()
            if not _ignoreChanges:
                # set branch and revision to most recent change
                self.branch = changes[-1].branch
                revision = changes[-1].revision
                if not self.project and hasattr(changes[-1], 'project'):
                    self.project = changes[-1].project
                if not self.repository and hasattr(changes[-1], 'repository'):
                    self.repository = changes[-1].repository

        if revision is not None:
            if isinstance(revision, int):
                revision = str(revision)

        self.revision = revision

    def upgradeToVersion1(self):
        # version 0 was untyped; in version 1 and later, types matter.
        if self.branch is not None and not isinstance(self.branch, str):
            self.branch = str(self.branch)
        if self.revision is not None and not isinstance(self.revision, str):
            self.revision = str(self.revision)
        if self.patch is not None:
            self.patch = (int(self.patch[0]), str(self.patch[1]))
        self.wasUpgraded = True

    def upgradeToVersion2(self):
        # version 1 did not have project or repository; just set them to a
        # default ''
        self.project = ''
        self.repository = ''
        self.wasUpgraded = True

    def upgradeToVersion3(self):
        # The database has been upgraded where all existing sourcestamps got an
        # setid equal to its ssid
        self.sourcestampsetid = self.ssid
        # version 2 did not have codebase; set to ''
        self.codebase = ''
        self.wasUpgraded = True
substituteClasses['buildbot.sourcestamp', 'SourceStamp'] = SourceStamp


class ChangeMaster:  # pragma: no cover

    def __init__(self):
        self.changes = []
        # self.basedir must be filled in by the parent
        self.nextNumber = 1

    def saveYourself(self):
        return

    # This method is used by contrib/fix_changes_pickle_encoding.py to recode all
    # bytestrings in an old changes.pck into unicode strings
    def recode_changes(self, old_encoding, quiet=False):
        """Processes the list of changes, with the change attributes re-encoded
        unicode objects"""
        nconvert = 0
        for c in self.changes:
            # give revision special handling, in case it is an integer
            if isinstance(c.revision, int):
                c.revision = unicode(c.revision)

            for attr in ("who", "comments", "revlink", "category", "branch", "revision"):
                a = getattr(c, attr)
                if isinstance(a, str):
                    try:
                        setattr(c, attr, a.decode(old_encoding))
                        nconvert += 1
                    except UnicodeDecodeError:
                        raise UnicodeError("Error decoding %s of change #%s as %s:\n%r" %
                                           (attr, c.number, old_encoding, a))

            # filenames are a special case, but in general they'll have the same encoding
            # as everything else on a system.  If not, well, hack this script to do your
            # import!
            newfiles = []
            for filename in util.flatten(c.files):
                if isinstance(filename, str):
                    try:
                        filename = filename.decode(old_encoding)
                        nconvert += 1
                    except UnicodeDecodeError:
                        raise UnicodeError("Error decoding filename '%s' of change #%s as %s:\n%r" %
                                           (filename.decode('ascii', 'replace'),
                                            c.number, old_encoding, a))
                newfiles.append(filename)
            c.files = newfiles
        if not quiet:
            print("converted %d strings" % nconvert)
substituteClasses['buildbot.changes.changes', 'ChangeMaster'] = ChangeMaster


class BuildStepStatus(styles.Versioned):

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

    # Note: setter methods have been removed

    def checkLogfiles(self):
        # filter out logs that have been deleted
        self.logs = [l for l in self.logs if l.old_hasContents()]

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

        for attr in ("getStatistic", "hasStatistic", "setStatistic"):
            if attr in d:
                del d[attr]

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
        result = {
            # Constant
            'name': self.getName(),

            # Transient
            'text': self.getText(),
            'results': self.getResults(),
            'isStarted': self.isStarted(),
            'isFinished': self.isFinished(),
            'times': self.getTimes(),
            'expectations': self.getExpectations(),
            'eta': self.getETA(),
            'urls': self.getURLs(),
            'step_number': self.step_number,
            'hidden': self.hidden,
            'logs': [[l.getName(), None]  # used to be (name, URL)
                     for l in self.getLogs()]
        }
        return result
# styles.Versioned requires this latter, as it keys the version numbers on the
# fully qualified class name.  This module appeared in two different modules
# historically
BuildStepStatus.__module__ = 'buildbot.status.builder'
substituteClasses[
    'buildbot.status.buildstep', 'BuildStepStatus'] = BuildStepStatus
substituteClasses[
    'buildbot.status.builder', 'BuildStepStatus'] = BuildStepStatus

STDOUT = 0
STDERR = 1
HEADER = 2


class LogFileScanner(netstrings.NetstringParser):

    def __init__(self, chunk_cb, channels=None):
        self.chunk_cb = chunk_cb
        if channels is None:
            channels = []
        self.channels = channels
        netstrings.NetstringParser.__init__(self)

    def stringReceived(self, line):
        channel = int(line[0])
        if not self.channels or (channel in self.channels):
            self.chunk_cb((channel, line[1:]))


class LogFile:

    """
    A LogFile keeps all of its contents on disk, in a non-pickle format to
    which new entries can easily be appended. The file on disk has a name like
    12-log-compile-output, under the Builder's directory. The actual filename
    is generated (before the LogFile is created) by
    L{BuildStatus.generateLogfileName}.

    @ivar length: length of the data in the logfile (sum of chunk sizes; not
    the length of the on-disk encoding)
    """

    finished = False
    length = 0
    nonHeaderLength = 0
    tailLength = 0
    chunkSize = 10 * 1000
    runLength = 0
    # No max size by default
    # Don't keep a tail buffer by default
    logMaxTailSize = None
    maxLengthExceeded = False
    runEntries = []  # provided so old pickled builds will getChunks() ok
    entries = None
    BUFFERSIZE = 2048
    filename = None  # relative to the Builder's basedir
    openfile = None

    def __init__(self, parent, name, logfilename):
        """
        @type  parent: L{BuildStepStatus}
        @param parent: the Step that this log is a part of
        @type  name: string
        @param name: the name of this log, typically 'output'
        @type  logfilename: string
        @param logfilename: the Builder-relative pathname for the saved entries
        """
        self.step = parent
        self.master = parent.build.builder.master
        self.name = name
        self.filename = logfilename
        fn = self.getFilename()
        if os.path.exists(fn):
            # the buildmaster was probably stopped abruptly, before the
            # BuilderStatus could be saved, so BuilderStatus.nextBuildNumber
            # is out of date, and we're overlapping with earlier builds now.
            # Warn about it, but then overwrite the old pickle file
            log.msg("Warning: Overwriting old serialized Build at %s" % fn)
        dirname = os.path.dirname(fn)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        self.openfile = open(fn, "w+")
        self.runEntries = []
        self.watchers = []
        self.finishedWatchers = []
        self.tailBuffer = []

    def getFilename(self):
        """
        Get the base (uncompressed) filename for this log file.

        @returns: filename
        """
        return os.path.join(self.step.build.builder.basedir, self.filename)

    def old_hasContents(self):
        """
        Return true if this logfile's contents are available.  For a newly
        created logfile, this is always true, but for a L{LogFile} instance
        that has been persisted, the logfiles themselves may have been deleted,
        in which case this method will return False.

        @returns: boolean
        """
        return os.path.exists(self.getFilename() + '.bz2') or \
            os.path.exists(self.getFilename() + '.gz') or \
            os.path.exists(self.getFilename())

    def getName(self):
        """
        Get this logfile's name

        @returns: string
        """
        return self.name

    def old_getStep(self):
        """
        Get the L{BuildStepStatus} instance containing this logfile

        @returns: L{BuildStepStatus} instance
        """
        return self.step

    def isFinished(self):
        """
        Return true if this logfile is finished (that is, if it will not
        receive any additional data

        @returns: boolean
        """

        return self.finished

    def waitUntilFinished(self):
        """
        Return a Deferred that will fire when this logfile is finished, or will
        fire immediately if the logfile is already finished.
        """
        if self.finished:
            d = defer.succeed(self)
        else:
            d = defer.Deferred()
            self.finishedWatchers.append(d)
        return d

    def getFile(self):
        """
        Get an open file object for this log.  The file may also be in use for
        writing, so it should not be closed by the caller, and the caller
        should not rely on its file position remaining constant between
        asynchronous code segments.

        @returns: file object
        """
        if self.openfile:
            # this is the filehandle we're using to write to the log, so
            # don't close it!
            return self.openfile
        # otherwise they get their own read-only handle
        # try a compressed log first
        try:
            return BZ2File(self.getFilename() + ".bz2", "r")
        except IOError:
            pass
        try:
            return GzipFile(self.getFilename() + ".gz", "r")
        except IOError:
            pass
        return open(self.getFilename(), "r")

    def old_getText(self):
        # this produces one ginormous string
        return "".join(self.old_getChunks([STDOUT, STDERR], onlyText=True))

    def old_getChunks(self, channels=None, onlyText=False):
        # generate chunks for everything that was logged at the time we were
        # first called, so remember how long the file was when we started.
        # Don't read beyond that point. The current contents of
        # self.runEntries will follow.

        # this returns an iterator, which means arbitrary things could happen
        # while we're yielding. This will faithfully deliver the log as it
        # existed when it was started, and not return anything after that
        # point. To use this in subscribe(catchup=True) without missing any
        # data, you must insure that nothing will be added to the log during
        # yield() calls.
        if channels is None:
            channels = []

        f = self.getFile()
        if not self.finished:
            offset = 0
            f.seek(0, 2)
            remaining = f.tell()
        else:
            offset = 0
            remaining = None

        leftover = None
        if self.runEntries and (not channels or
                                (self.runEntries[0][0] in channels)):
            leftover = (self.runEntries[0][0],
                        "".join([c[1] for c in self.runEntries]))

        # freeze the state of the LogFile by passing a lot of parameters into
        # a generator
        return self._generateChunks(f, offset, remaining, leftover,
                                    channels, onlyText)

    def _generateChunks(self, f, offset, remaining, leftover,
                        channels, onlyText):
        chunks = []
        p = LogFileScanner(chunks.append, channels)
        f.seek(offset)
        if remaining is not None:
            data = f.read(min(remaining, self.BUFFERSIZE))
            remaining -= len(data)
        else:
            data = f.read(self.BUFFERSIZE)

        offset = f.tell()
        while data:
            p.dataReceived(data)
            while chunks:
                channel, text = chunks.pop(0)
                if onlyText:
                    yield text
                else:
                    yield (channel, text)
            f.seek(offset)
            if remaining is not None:
                data = f.read(min(remaining, self.BUFFERSIZE))
                remaining -= len(data)
            else:
                data = f.read(self.BUFFERSIZE)
            offset = f.tell()
        del f

        if leftover:
            if onlyText:
                yield leftover[1]
            else:
                yield leftover

    def subscribe(self, receiver, catchup):
        if self.finished:
            return
        self.watchers.append(receiver)
        if catchup:
            for channel, text in self.old_getChunks():
                receiver.logChunk(self.step.build, self.step, self,
                                  channel, text)

    def unsubscribe(self, receiver):
        if receiver in self.watchers:
            self.watchers.remove(receiver)

    def old_subscribeConsumer(self, consumer):
        raise NotImplementedError()

    # interface used by the build steps to add things to the log are removed

    # persistence stuff
    def __getstate__(self):
        d = self.__dict__.copy()
        del d['step']  # filled in upon unpickling
        del d['watchers']
        del d['finishedWatchers']
        del d['master']
        d['entries'] = []  # let 0.6.4 tolerate the saved log. TODO: really?
        if "finished" in d:
            del d['finished']
        if "openfile" in d:
            del d['openfile']
        return d

    def __setstate__(self, d):
        self.__dict__ = d
        self.watchers = []  # probably not necessary
        self.finishedWatchers = []  # same
        # self.step must be filled in by our parent
        self.finished = True
substituteClasses['buildbot.status.logfile', 'LogFile'] = LogFile
substituteClasses['buildbot.status.builder', 'LogFile'] = LogFile


class HTMLLogFile(LogFile):

    def __init__(self, parent, name, logfilename, html):
        LogFile.__init__(self, parent, name, logfilename)
        self.addStderr(html)
        self.finish()

    def old_hasContents(self):
        return True

    def __setstate__(self, d):
        self.__dict__ = d
        self.watchers = []
        self.finishedWatchers = []
        self.finished = True

        # buildbot <= 0.8.8 stored all html logs in the html property
        if 'html' in self.__dict__:
            buf = "%d:%d%s," % (len(self.html) + 1, STDERR, self.html)
            self.openfile = StringIO(buf)
            del self.__dict__['html']
substituteClasses['buildbot.status.logfile', 'HTMLLogFile'] = HTMLLogFile
substituteClasses['buildbot.status.builder', 'HTMLLogFile'] = HTMLLogFile


class StepProgress:

    """I keep track of how much progress a single BuildStep has made.

    Progress is measured along various axes. Time consumed is one that is
    available for all steps. Amount of command output is another, and may be
    better quantified by scanning the output for markers to derive number of
    files compiled, directories walked, tests run, etc.

    I am created when the build begins, and given to a BuildProgress object
    so it can track the overall progress of the whole build.

    """

    startTime = None
    stopTime = None
    expectedTime = None
    buildProgress = None
    debug = False

    def __init__(self, name, metricNames):
        self.name = name
        self.progress = {}
        self.expectations = {}
        for m in metricNames:
            self.progress[m] = None
            self.expectations[m] = None

    def setBuildProgress(self, bp):
        self.buildProgress = bp

    def setExpectations(self, metrics):
        """The step can call this to explicitly set a target value for one
        of its metrics. E.g., ShellCommands knows how many commands it will
        execute, so it could set the 'commands' expectation."""
        for metric, value in iteritems(metrics):
            self.expectations[metric] = value
        self.buildProgress.newExpectations()

    def setExpectedTime(self, seconds):
        self.expectedTime = seconds
        self.buildProgress.newExpectations()

    def start(self):
        if self.debug:
            print("StepProgress.start[%s]" % self.name)
        self.startTime = util.now()

    def setProgress(self, metric, value):
        """The step calls this as progress is made along various axes."""
        if self.debug:
            print("setProgress[%s][%s] = %s" % (self.name, metric, value))
        self.progress[metric] = value
        if self.debug:
            r = self.remaining()
            print(" step remaining:", r)
        self.buildProgress.newProgress()

    def finish(self):
        """This stops the 'time' metric and marks the step as finished
        overall. It should be called after the last .setProgress has been
        done for each axis."""
        if self.debug:
            print("StepProgress.finish[%s]" % self.name)
        self.stopTime = util.now()
        self.buildProgress.stepFinished(self.name)

    def totalTime(self):
        if self.startTime is not None and self.stopTime is not None:
            return self.stopTime - self.startTime

    def remaining(self):
        if self.startTime is None:
            return self.expectedTime
        if self.stopTime is not None:
            return 0  # already finished
        # TODO: replace this with cleverness that graphs each metric vs.
        # time, then finds the inverse function. Will probably need to save
        # a timestamp with each setProgress update, when finished, go back
        # and find the 2% transition points, then save those 50 values in a
        # list. On the next build, do linear interpolation between the two
        # closest samples to come up with a percentage represented by that
        # metric.

        # TODO: If no other metrics are available, just go with elapsed
        # time. Given the non-time-uniformity of text output from most
        # steps, this would probably be better than the text-percentage
        # scheme currently implemented.

        percentages = []
        for metric, value in iteritems(self.progress):
            expectation = self.expectations[metric]
            if value is not None and expectation is not None:
                p = 1.0 * value / expectation
                percentages.append(p)
        if percentages:
            avg = reduce(lambda x, y: x + y, percentages) / len(percentages)
            if avg > 1.0:
                # overdue
                avg = 1.0
            if avg < 0.0:
                avg = 0.0
        if percentages and self.expectedTime is not None:
            return self.expectedTime - (avg * self.expectedTime)
        if self.expectedTime is not None:
            # fall back to pure time
            return self.expectedTime - (util.now() - self.startTime)
        return None  # no idea
substituteClasses['buildbot.status.progress', 'StepProgress'] = StepProgress


class WatcherState:

    def __init__(self, interval):
        self.interval = interval
        self.timer = None
        self.needUpdate = 0
substituteClasses['buildbot.status.progress', 'WatcherState'] = WatcherState


class BuildProgress(pb.Referenceable):

    """I keep track of overall build progress. I hold a list of StepProgress
    objects.
    """

    def __init__(self, stepProgresses):
        self.steps = {}
        for s in stepProgresses:
            self.steps[s.name] = s
            s.setBuildProgress(self)
        self.finishedSteps = []
        self.watchers = {}
        self.debug = 0

    def setExpectationsFrom(self, exp):
        """Set our expectations from the builder's Expectations object."""
        for name, metrics in iteritems(exp.steps):
            s = self.steps.get(name)
            if s:
                s.setExpectedTime(exp.times[name])
                s.setExpectations(exp.steps[name])

    def newExpectations(self):
        """Call this when one of the steps has changed its expectations.
        This should trigger us to update our ETA value and notify any
        subscribers."""
        pass  # subscribers are not implemented: they just poll

    def stepFinished(self, stepname):
        assert(stepname not in self.finishedSteps)
        self.finishedSteps.append(stepname)
        if len(self.finishedSteps) == len(list(self.steps)):
            self.sendLastUpdates()

    def newProgress(self):
        r = self.remaining()
        if self.debug:
            print(" remaining:", r)
        if r is not None:
            self.sendAllUpdates()

    def remaining(self):
        # sum eta of all steps
        sum = 0
        for name, step in iteritems(self.steps):
            rem = step.remaining()
            if rem is None:
                return None  # not sure
            sum += rem
        return sum

    def eta(self):
        left = self.remaining()
        if left is None:
            return None  # not sure
        done = util.now() + left
        return done

    def remote_subscribe(self, remote, interval=5):
        # [interval, timer, needUpdate]
        # don't send an update more than once per interval
        self.watchers[remote] = WatcherState(interval)
        remote.notifyOnDisconnect(self.removeWatcher)
        self.updateWatcher(remote)
        self.startTimer(remote)
        log.msg("BuildProgress.remote_subscribe(%s)" % remote)

    def remote_unsubscribe(self, remote):
        # TODO: this doesn't work. I think 'remote' will always be different
        # than the object that appeared in _subscribe.
        log.msg("BuildProgress.remote_unsubscribe(%s)" % remote)
        self.removeWatcher(remote)
        # remote.dontNotifyOnDisconnect(self.removeWatcher)

    def removeWatcher(self, remote):
        # log.msg("removeWatcher(%s)" % remote)
        try:
            timer = self.watchers[remote].timer
            if timer:
                timer.cancel()
            del self.watchers[remote]
        except KeyError:
            log.msg("Weird, removeWatcher on non-existent subscriber:",
                    remote)

    def sendAllUpdates(self):
        for r in self.watchers:
            self.updateWatcher(r)

    def updateWatcher(self, remote):
        # an update wants to go to this watcher. Send it if we can, otherwise
        # queue it for later
        w = self.watchers[remote]
        if not w.timer:
            # no timer, so send update now and start the timer
            self.sendUpdate(remote)
            self.startTimer(remote)
        else:
            # timer is running, just mark as needing an update
            w.needUpdate = 1

    def startTimer(self, remote):
        w = self.watchers[remote]
        timer = reactor.callLater(w.interval, self.watcherTimeout, remote)
        w.timer = timer

    def sendUpdate(self, remote, last=0):
        self.watchers[remote].needUpdate = 0
        # text = self.asText() # TODO: not text, duh
        try:
            remote.callRemote("progress", self.remaining())
            if last:
                remote.callRemote("finished", self)
        except Exception:
            log.err('while updating remote progress')
            self.removeWatcher(remote)

    def watcherTimeout(self, remote):
        w = self.watchers.get(remote, None)
        if not w:
            return  # went away
        w.timer = None
        if w.needUpdate:
            self.sendUpdate(remote)
            self.startTimer(remote)

    def sendLastUpdates(self):
        for remote in self.watchers:
            self.sendUpdate(remote, 1)
            self.removeWatcher(remote)
substituteClasses['buildbot.status.progress', 'BuildProgress'] = BuildProgress


class Expectations:
    debug = False
    # decay=1.0 ignores all but the last build
    # 0.9 is short time constant. 0.1 is very long time constant
    # TODO: let decay be specified per-metric
    decay = 0.5

    def __init__(self, buildprogress):
        """Create us from a successful build. We will expect each step to
        take as long as it did in that build."""

        # .steps maps stepname to dict2
        # dict2 maps metricname to final end-of-step value
        self.steps = defaultdict(dict)

        # .times maps stepname to per-step elapsed time
        self.times = {}

        for name, step in iteritems(buildprogress.steps):
            self.steps[name] = {}
            for metric, value in iteritems(step.progress):
                self.steps[name][metric] = value
            self.times[name] = None
            if step.startTime is not None and step.stopTime is not None:
                self.times[name] = step.stopTime - step.startTime

    def wavg(self, old, current):
        if old is None:
            return current
        if current is None:
            return old
        else:
            return (current * self.decay) + (old * (1 - self.decay))

    def update(self, buildprogress):
        for name, stepprogress in iteritems(buildprogress.steps):
            old = self.times.get(name)
            current = stepprogress.totalTime()
            if current is None:
                log.msg("Expectations.update: current[%s] was None!" % name)
                continue
            new_ = self.wavg(old, current)
            self.times[name] = new_
            if self.debug:
                print("new expected time[%s] = %s, old %s, cur %s" %
                      (name, new_, old, current))

            for metric, current in iteritems(stepprogress.progress):
                old = self.steps[name].get(metric)
                new_ = self.wavg(old, current)
                if self.debug:
                    print("new expectation[%s][%s] = %s, old %s, cur %s" %
                          (name, metric, new_, old, current))
                self.steps[name][metric] = new_

    def expectedBuildTime(self):
        if None in list(itervalues(self.times)):
            return None
        return sum(list(itervalues(self.times)))

substituteClasses['buildbot.status.progress', 'Expectations'] = Expectations


# replacements for stdlib pickle methods

_already_setup = False


def setup():
    global _already_setup
    if _already_setup:
        return

    # move each of the substitute classes to its proper module in sys.modules,
    # creating it if necessary, and set its __module__ attribute.
    for info, cls in iteritems(substituteClasses):
        mod_name, cls_name = info
        try:
            mod = reflect.namedModule(mod_name)
        except (ImportError, AttributeError):
            mod = new.module(mod_name)
            sys.modules[mod_name] = mod
        setattr(mod, cls_name, cls)

    _already_setup = True


def _makeUnpickler(file):
    setup()
    up = cPickle.Unpickler(file)
    # see http://docs.python.org/2/library/pickle.html#subclassing-unpicklers

    def find_global(modname, clsname):
        try:
            return substituteClasses[(modname, clsname)]
        except KeyError:
            mod = reflect.namedModule(modname)
            try:
                return getattr(mod, clsname)
            except AttributeError:
                raise AttributeError("Module %r (%s) has no attribute %s"
                                     % (mod, modname, clsname))
    up.find_global = find_global
    return up


def load(file):
    return _makeUnpickler(file).load()


def loads(str):
    file = cStringIO.StringIO(str)
    return _makeUnpickler(file).load()

dump = cPickle.dump
dumps = cPickle.dumps
