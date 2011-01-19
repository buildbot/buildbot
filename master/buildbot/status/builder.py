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
import os, shutil, re, urllib, itertools
import gc
import time
from cPickle import load, dump
from cStringIO import StringIO
from bz2 import BZ2File
from gzip import GzipFile

from zope.interface import implements
from twisted.python import log, runtime
from twisted.persisted import styles
from twisted.internet import reactor, defer, threads
from buildbot.process.properties import Properties
from buildbot.util import collections, netstrings
from buildbot.util.eventual import eventually
from buildbot import interfaces, util, sourcestamp

SUCCESS, WARNINGS, FAILURE, SKIPPED, EXCEPTION, RETRY = range(6)
Results = ["success", "warnings", "failure", "skipped", "exception", "retry"]

def worst_status(a, b):
    # SUCCESS > WARNINGS > FAILURE > EXCEPTION > RETRY
    # Retry needs to be considered the worst so that conusmers don't have to
    # worry about other failures undermining the RETRY.
    for s in (RETRY, EXCEPTION, FAILURE, WARNINGS, SKIPPED, SUCCESS):
        if s in (a, b):
            return s

# build processes call the following methods:
#
#  setDefaults
#
#  currentlyBuilding
#  currentlyIdle
#  currentlyInterlocked
#  currentlyOffline
#  currentlyWaiting
#
#  setCurrentActivity
#  updateCurrentActivity
#  addFileToCurrentActivity
#  finishCurrentActivity
#
#  startBuild
#  finishBuild

STDOUT = interfaces.LOG_CHANNEL_STDOUT
STDERR = interfaces.LOG_CHANNEL_STDERR
HEADER = interfaces.LOG_CHANNEL_HEADER
ChunkTypes = ["stdout", "stderr", "header"]

class LogFileScanner(netstrings.NetstringParser):
    def __init__(self, chunk_cb, channels=[]):
        self.chunk_cb = chunk_cb
        self.channels = channels
        netstrings.NetstringParser.__init__(self)

    def stringReceived(self, line):
        channel = int(line[0])
        if not self.channels or (channel in self.channels):
            self.chunk_cb((channel, line[1:]))

class LogFileProducer:
    """What's the plan?

    the LogFile has just one FD, used for both reading and writing.
    Each time you add an entry, fd.seek to the end and then write.

    Each reader (i.e. Producer) keeps track of their own offset. The reader
    starts by seeking to the start of the logfile, and reading forwards.
    Between each hunk of file they yield chunks, so they must remember their
    offset before yielding and re-seek back to that offset before reading
    more data. When their read() returns EOF, they're finished with the first
    phase of the reading (everything that's already been written to disk).

    After EOF, the remaining data is entirely in the current entries list.
    These entries are all of the same channel, so we can do one "".join and
    obtain a single chunk to be sent to the listener. But since that involves
    a yield, and more data might arrive after we give up control, we have to
    subscribe them before yielding. We can't subscribe them any earlier,
    otherwise they'd get data out of order.

    We're using a generator in the first place so that the listener can
    throttle us, which means they're pulling. But the subscription means
    we're pushing. Really we're a Producer. In the first phase we can be
    either a PullProducer or a PushProducer. In the second phase we're only a
    PushProducer.

    So the client gives a LogFileConsumer to File.subscribeConsumer . This
    Consumer must have registerProducer(), unregisterProducer(), and
    writeChunk(), and is just like a regular twisted.interfaces.IConsumer,
    except that writeChunk() takes chunks (tuples of (channel,text)) instead
    of the normal write() which takes just text. The LogFileConsumer is
    allowed to call stopProducing, pauseProducing, and resumeProducing on the
    producer instance it is given. """

    paused = False
    subscribed = False
    BUFFERSIZE = 2048

    def __init__(self, logfile, consumer):
        self.logfile = logfile
        self.consumer = consumer
        self.chunkGenerator = self.getChunks()
        consumer.registerProducer(self, True)

    def getChunks(self):
        f = self.logfile.getFile()
        offset = 0
        chunks = []
        p = LogFileScanner(chunks.append)
        f.seek(offset)
        data = f.read(self.BUFFERSIZE)
        offset = f.tell()
        while data:
            p.dataReceived(data)
            while chunks:
                c = chunks.pop(0)
                yield c
            f.seek(offset)
            data = f.read(self.BUFFERSIZE)
            offset = f.tell()
        del f

        # now subscribe them to receive new entries
        self.subscribed = True
        self.logfile.watchers.append(self)
        d = self.logfile.waitUntilFinished()

        # then give them the not-yet-merged data
        if self.logfile.runEntries:
            channel = self.logfile.runEntries[0][0]
            text = "".join([c[1] for c in self.logfile.runEntries])
            yield (channel, text)

        # now we've caught up to the present. Anything further will come from
        # the logfile subscription. We add the callback *after* yielding the
        # data from runEntries, because the logfile might have finished
        # during the yield.
        d.addCallback(self.logfileFinished)

    def stopProducing(self):
        # TODO: should we still call consumer.finish? probably not.
        self.paused = True
        self.consumer = None
        self.done()

    def done(self):
        if self.chunkGenerator:
            self.chunkGenerator = None # stop making chunks
        if self.subscribed:
            self.logfile.watchers.remove(self)
            self.subscribed = False

    def pauseProducing(self):
        self.paused = True

    def resumeProducing(self):
        # Twisted-1.3.0 has a bug which causes hangs when resumeProducing
        # calls transport.write (there is a recursive loop, fixed in 2.0 in
        # t.i.abstract.FileDescriptor.doWrite by setting the producerPaused
        # flag *before* calling resumeProducing). To work around this, we
        # just put off the real resumeProducing for a moment. This probably
        # has a performance hit, but I'm going to assume that the log files
        # are not retrieved frequently enough for it to be an issue.

        eventually(self._resumeProducing)

    def _resumeProducing(self):
        self.paused = False
        if not self.chunkGenerator:
            return
        try:
            while not self.paused:
                chunk = self.chunkGenerator.next()
                self.consumer.writeChunk(chunk)
                # we exit this when the consumer says to stop, or we run out
                # of chunks
        except StopIteration:
            # if the generator finished, it will have done releaseFile
            self.chunkGenerator = None
        # now everything goes through the subscription, and they don't get to
        # pause anymore

    def logChunk(self, build, step, logfile, channel, chunk):
        if self.consumer:
            self.consumer.writeChunk((channel, chunk))

    def logfileFinished(self, logfile):
        self.done()
        if self.consumer:
            self.consumer.unregisterProducer()
            self.consumer.finish()
            self.consumer = None

def _tryremove(filename, timeout, retries):
    """Try to remove a file, and if failed, try again in timeout.
    Increases the timeout by a factor of 4, and only keeps trying for
    another retries-amount of times.

    """
    try:
        os.unlink(filename)
    except OSError:
        if retries > 0:
            reactor.callLater(timeout, _tryremove, filename, timeout * 4, 
                              retries - 1)
        else:
            log.msg("giving up on removing %s after over %d seconds" %
                    (filename, timeout))

class LogFile:
    """A LogFile keeps all of its contents on disk, in a non-pickle format to
    which new entries can easily be appended. The file on disk has a name
    like 12-log-compile-output, under the Builder's directory. The actual
    filename is generated (before the LogFile is created) by
    L{BuildStatus.generateLogfileName}.

    Old LogFile pickles (which kept their contents in .entries) must be
    upgraded. The L{BuilderStatus} is responsible for doing this, when it
    loads the L{BuildStatus} into memory. The Build pickle is not modified,
    so users who go from 0.6.5 back to 0.6.4 don't have to lose their
    logs."""

    implements(interfaces.IStatusLog, interfaces.ILogFile)

    finished = False
    length = 0
    nonHeaderLength = 0
    tailLength = 0
    chunkSize = 10*1000
    runLength = 0
    # No max size by default
    logMaxSize = None
    # Don't keep a tail buffer by default
    logMaxTailSize = None
    maxLengthExceeded = False
    runEntries = [] # provided so old pickled builds will getChunks() ok
    entries = None
    BUFFERSIZE = 2048
    filename = None # relative to the Builder's basedir
    openfile = None
    compressMethod = "bz2"

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
        return os.path.join(self.step.build.builder.basedir, self.filename)

    def hasContents(self):
        return os.path.exists(self.getFilename() + '.bz2') or \
            os.path.exists(self.getFilename() + '.gz') or \
            os.path.exists(self.getFilename())

    def getName(self):
        return self.name

    def getStep(self):
        return self.step

    def isFinished(self):
        return self.finished
    def waitUntilFinished(self):
        if self.finished:
            d = defer.succeed(self)
        else:
            d = defer.Deferred()
            self.finishedWatchers.append(d)
        return d

    def getFile(self):
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

    def getText(self):
        # this produces one ginormous string
        return "".join(self.getChunks([STDOUT, STDERR], onlyText=True))

    def getTextWithHeaders(self):
        return "".join(self.getChunks(onlyText=True))

    def getChunks(self, channels=[], onlyText=False):
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

    def readlines(self, channel=STDOUT):
        """Return an iterator that produces newline-terminated lines,
        excluding header chunks."""
        # TODO: make this memory-efficient, by turning it into a generator
        # that retrieves chunks as necessary, like a pull-driven version of
        # twisted.protocols.basic.LineReceiver
        alltext = "".join(self.getChunks([channel], onlyText=True))
        io = StringIO(alltext)
        return io.readlines()

    def subscribe(self, receiver, catchup):
        if self.finished:
            return
        self.watchers.append(receiver)
        if catchup:
            for channel, text in self.getChunks():
                # TODO: add logChunks(), to send over everything at once?
                receiver.logChunk(self.step.build, self.step, self,
                                  channel, text)

    def unsubscribe(self, receiver):
        if receiver in self.watchers:
            self.watchers.remove(receiver)

    def subscribeConsumer(self, consumer):
        p = LogFileProducer(self, consumer)
        p.resumeProducing()

    # interface used by the build steps to add things to the log

    def merge(self):
        # merge all .runEntries (which are all of the same type) into a
        # single chunk for .entries
        if not self.runEntries:
            return
        channel = self.runEntries[0][0]
        text = "".join([c[1] for c in self.runEntries])
        assert channel < 10
        f = self.openfile
        f.seek(0, 2)
        offset = 0
        while offset < len(text):
            size = min(len(text)-offset, self.chunkSize)
            f.write("%d:%d" % (1 + size, channel))
            f.write(text[offset:offset+size])
            f.write(",")
            offset += size
        self.runEntries = []
        self.runLength = 0

    def addEntry(self, channel, text):
        assert not self.finished

        if isinstance(text, unicode):
            text = text.encode('utf-8')
        if channel != HEADER:
            # Truncate the log if it's more than logMaxSize bytes
            if self.logMaxSize and self.nonHeaderLength > self.logMaxSize:
                # Add a message about what's going on
                if not self.maxLengthExceeded:
                    msg = "\nOutput exceeded %i bytes, remaining output has been truncated\n" % self.logMaxSize
                    self.addEntry(HEADER, msg)
                    self.merge()
                    self.maxLengthExceeded = True

                if self.logMaxTailSize:
                    # Update the tail buffer
                    self.tailBuffer.append((channel, text))
                    self.tailLength += len(text)
                    while self.tailLength > self.logMaxTailSize:
                        # Drop some stuff off the beginning of the buffer
                        c,t = self.tailBuffer.pop(0)
                        n = len(t)
                        self.tailLength -= n
                        assert self.tailLength >= 0
                return

            self.nonHeaderLength += len(text)

        # we only add to .runEntries here. merge() is responsible for adding
        # merged chunks to .entries
        if self.runEntries and channel != self.runEntries[0][0]:
            self.merge()
        self.runEntries.append((channel, text))
        self.runLength += len(text)
        if self.runLength >= self.chunkSize:
            self.merge()

        for w in self.watchers:
            w.logChunk(self.step.build, self.step, self, channel, text)
        self.length += len(text)

    def addStdout(self, text):
        self.addEntry(STDOUT, text)
    def addStderr(self, text):
        self.addEntry(STDERR, text)
    def addHeader(self, text):
        self.addEntry(HEADER, text)

    def finish(self):
        if self.tailBuffer:
            msg = "\nFinal %i bytes follow below:\n" % self.tailLength
            tmp = self.runEntries
            self.runEntries = [(HEADER, msg)]
            self.merge()
            self.runEntries = self.tailBuffer
            self.merge()
            self.runEntries = tmp
            self.merge()
            self.tailBuffer = []
        else:
            self.merge()

        if self.openfile:
            # we don't do an explicit close, because there might be readers
            # shareing the filehandle. As soon as they stop reading, the
            # filehandle will be released and automatically closed.
            self.openfile.flush()
            del self.openfile
        self.finished = True
        watchers = self.finishedWatchers
        self.finishedWatchers = []
        for w in watchers:
            w.callback(self)
        self.watchers = []


    def compressLog(self):
        # bail out if there's no compression support
        if self.compressMethod == "bz2":
            compressed = self.getFilename() + ".bz2.tmp"
        elif self.compressMethod == "gz":
            compressed = self.getFilename() + ".gz.tmp"
        d = threads.deferToThread(self._compressLog, compressed)
        d.addCallback(self._renameCompressedLog, compressed)
        d.addErrback(self._cleanupFailedCompress, compressed)
        return d

    def _compressLog(self, compressed):
        infile = self.getFile()
        if self.compressMethod == "bz2":
            cf = BZ2File(compressed, 'w')
        elif self.compressMethod == "gz":
            cf = GzipFile(compressed, 'w')
        bufsize = 1024*1024
        while True:
            buf = infile.read(bufsize)
            cf.write(buf)
            if len(buf) < bufsize:
                break
        cf.close()
    def _renameCompressedLog(self, rv, compressed):
        if self.compressMethod == "bz2":
            filename = self.getFilename() + '.bz2'
        else:
            filename = self.getFilename() + '.gz'
        if runtime.platformType  == 'win32':
            # windows cannot rename a file on top of an existing one, so
            # fall back to delete-first. There are ways this can fail and
            # lose the builder's history, so we avoid using it in the
            # general (non-windows) case
            if os.path.exists(filename):
                os.unlink(filename)
        os.rename(compressed, filename)
        _tryremove(self.getFilename(), 1, 5)
    def _cleanupFailedCompress(self, failure, compressed):
        log.msg("failed to compress %s" % self.getFilename())
        if os.path.exists(compressed):
            _tryremove(compressed, 1, 5)
        failure.trap() # reraise the failure

    # persistence stuff
    def __getstate__(self):
        d = self.__dict__.copy()
        del d['step'] # filled in upon unpickling
        del d['watchers']
        del d['finishedWatchers']
        d['entries'] = [] # let 0.6.4 tolerate the saved log. TODO: really?
        if d.has_key('finished'):
            del d['finished']
        if d.has_key('openfile'):
            del d['openfile']
        return d

    def __setstate__(self, d):
        self.__dict__ = d
        self.watchers = [] # probably not necessary
        self.finishedWatchers = [] # same
        # self.step must be filled in by our parent
        self.finished = True

    def upgrade(self, logfilename):
        """Save our .entries to a new-style offline log file (if necessary),
        and modify our in-memory representation to use it. The original
        pickled LogFile (inside the pickled Build) won't be modified."""
        self.filename = logfilename
        if not os.path.exists(self.getFilename()):
            self.openfile = open(self.getFilename(), "w")
            self.finished = False
            for channel,text in self.entries:
                self.addEntry(channel, text)
            self.finish() # releases self.openfile, which will be closed
        del self.entries

class HTMLLogFile:
    implements(interfaces.IStatusLog)

    filename = None

    def __init__(self, parent, name, logfilename, html):
        self.step = parent
        self.name = name
        self.filename = logfilename
        self.html = html

    def getName(self):
        return self.name # set in BuildStepStatus.addLog
    def getStep(self):
        return self.step

    def isFinished(self):
        return True
    def waitUntilFinished(self):
        return defer.succeed(self)

    def hasContents(self):
        return True
    def getText(self):
        return self.html # looks kinda like text
    def getTextWithHeaders(self):
        return self.html
    def getChunks(self):
        return [(STDERR, self.html)]

    def subscribe(self, receiver, catchup):
        pass
    def unsubscribe(self, receiver):
        pass

    def finish(self):
        pass

    def __getstate__(self):
        d = self.__dict__.copy()
        del d['step']
        return d

    def upgrade(self, logfilename):
        pass


class Event:
    implements(interfaces.IStatusEvent)

    started = None
    finished = None
    text = []

    # IStatusEvent methods
    def getTimes(self):
        return (self.started, self.finished)
    def getText(self):
        return self.text
    def getLogs(self):
        return []

    def finish(self):
        self.finished = util.now()

class TestResult:
    implements(interfaces.ITestResult)

    def __init__(self, name, results, text, logs):
        assert isinstance(name, tuple)
        self.name = name
        self.results = results
        self.text = text
        self.logs = logs

    def getName(self):
        return self.name

    def getResults(self):
        return self.results

    def getText(self):
        return self.text

    def getLogs(self):
        return self.logs


class BuildSetStatus:
    implements(interfaces.IBuildSetStatus)

    def __init__(self, bsid, status, db):
        self.id = bsid
        self.status = status
        self.db = db

    def _get_info(self):
        return self.db.get_buildset_info(self.id)

    # methods for our clients

    def getSourceStamp(self):
        (external_idstring, reason, ssid, complete, results) = self._get_info()
        return self.db.getSourceStampNumberedNow(ssid)

    def getReason(self):
        (external_idstring, reason, ssid, complete, results) = self._get_info()
        return reason
    def getResults(self):
        (external_idstring, reason, ssid, complete, results) = self._get_info()
        return results
    def getID(self):
        (external_idstring, reason, ssid, complete, results) = self._get_info()
        return external_idstring

    def getBuilderNamesAndBuildRequests(self):
        brs = {}
        brids = self.db.get_buildrequestids_for_buildset(self.id)
        for (buildername, brid) in brids.items():
            brs[buildername] = BuildRequestStatus(brid, self.status, self.db)
        return brs

    def getBuilderNames(self):
        brs = self.db.get_buildrequestids_for_buildset(self.id)
        return sorted(brs.keys())

    def getBuildRequests(self):
        brs = self.db.get_buildrequestids_for_buildset(self.id)
        return [BuildRequestStatus(brid, self.status, self.db)
                for brid in brs.values()]

    def isFinished(self):
        (external_idstring, reason, ssid, complete, results) = self._get_info()
        return complete

    def waitUntilSuccess(self):
        return self.status._buildset_waitUntilSuccess(self.id)
    def waitUntilFinished(self):
        return self.status._buildset_waitUntilFinished(self.id)

class BuildRequestStatus:
    implements(interfaces.IBuildRequestStatus)

    def __init__(self, brid, status, db):
        self.brid = brid
        self.status = status
        self.db = db

    def buildStarted(self, build):
        self.status._buildrequest_buildStarted(build.status)
        self.builds.append(build.status)

    # methods called by our clients
    def getSourceStamp(self):
        br = self.db.getBuildRequestWithNumber(self.brid)
        return br.source
    def getBuilderName(self):
        br = self.db.getBuildRequestWithNumber(self.brid)
        return br.builderName
    def getBuilds(self):
        builder = self.status.getBuilder(self.getBuilderName())
        builds = []
        buildnums = sorted(self.db.get_buildnums_for_brid(self.brid))
        for buildnum in buildnums:
            bs = builder.getBuild(buildnum)
            if bs:
                builds.append(bs)
        return builds

    def subscribe(self, observer):
        oldbuilds = self.getBuilds()
        for bs in oldbuilds:
            eventually(observer, bs)
        self.status._buildrequest_subscribe(self.brid, observer)
    def unsubscribe(self, observer):
        self.status._buildrequest_unsubscribe(self.brid, observer)

    def getSubmitTime(self):
        br = self.db.getBuildRequestWithNumber(self.brid)
        return br.submittedAt

    def asDict(self):
        result = {}
        # Constant
        result['source'] = self.getSourceStamp().asDict()
        result['builderName'] = self.getBuilderName()
        result['submittedAt'] = self.getSubmitTime()

        # Transient
        result['builds'] = [build.asDict() for build in self.getBuilds()]
        return result


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
    @type logs: dict of string -> L{buildbot.status.builder.LogFile}
    @ivar logs: logs of steps
    @type statistics: dict
    @ivar statistics: results from running this step
    """
    # note that these are created when the Build is set up, before each
    # corresponding BuildStep has started.
    implements(interfaces.IBuildStepStatus, interfaces.IStatusEvent)

    persistenceVersion = 3
    persistenceForgets = ( 'wasUpgraded', )

    started = None
    finished = None
    progress = None
    text = []
    results = (None, [])
    text2 = []
    watchers = []
    updates = {}
    finishedWatchers = []
    statistics = {}
    step_number = None

    def __init__(self, parent, step_number):
        assert interfaces.IBuildStatus(parent)
        self.build = parent
        self.step_number = step_number
        self.logs = []
        self.urls = {}
        self.watchers = []
        self.updates = {}
        self.finishedWatchers = []
        self.statistics = {}
        self.skipped = False

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
        metrics = self.progress.progress.keys()
        metrics.sort()
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
            return None # not started yet
        if self.finished is not None:
            return None # already finished
        if not self.progress:
            return None # no way to predict
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
        return self.statistics.has_key(name)

    def getStatistic(self, name, default=None):
        """Return the given statistic, if present
        """
        return self.statistics.get(name, default)

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

    def stepStarted(self):
        self.started = util.now()
        if self.build:
            self.build.stepStarted(self)

    def addLog(self, name):
        assert self.started # addLog before stepStarted won't notify watchers
        logfilename = self.build.generateLogfileName(self.name, name)
        log = LogFile(self, name, logfilename)
        log.logMaxSize = self.build.builder.logMaxSize
        log.logMaxTailSize = self.build.builder.logMaxTailSize
        log.compressMethod = self.build.builder.logCompressionMethod
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
        assert self.started # addLog before stepStarted won't notify watchers
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
        cld = [] # deferreds for log compression
        logCompressionLimit = self.build.builder.logCompressionLimit
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
        self.logs = [ l for l in self.logs if l.hasContents() ]

    def isWaitingForLocks(self):
        return self.waitingForLocks

    def setWaitingForLocks(self, waiting):
        self.waitingForLocks = waiting

    # persistence

    def __getstate__(self):
        d = styles.Versioned.__getstate__(self)
        del d['build'] # filled in when loading
        if d.has_key('progress'):
            del d['progress']
        del d['watchers']
        del d['finishedWatchers']
        del d['updates']
        return d

    def __setstate__(self, d):
        styles.Versioned.__setstate__(self, d)
        # self.build must be filled in by our parent

        # point the logs to this object
        for loog in self.logs:
            loog.step = self
        self.watchers = []
        self.finishedWatchers = []
        self.updates = {}

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
        result['logs'] = [[l.getName(),
            self.build.builder.status.getURLForThing(l)]
                for l in self.getLogs()]
        return result


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
            for log in s.getLogs():
                logs.append(log)
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
            d['finished'] = True
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



class BuilderStatus(styles.Versioned):
    """I handle status information for a single process.base.Builder object.
    That object sends status changes to me (frequently as Events), and I
    provide them on demand to the various status recipients, like the HTML
    waterfall display and the live status clients. It also sends build
    summaries to me, which I log and provide to status clients who aren't
    interested in seeing details of the individual build steps.

    I am responsible for maintaining the list of historic Events and Builds,
    pruning old ones, and loading them from / saving them to disk.

    I live in the buildbot.process.base.Builder object, in the
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
    def sendLastBuildStatus(self, client):
        #client.newLastBuildStatus(self.lastBuildStatus)
        pass
    def sendCurrentActivityBigToEveryone(self):
        for s in self.subscribers:
            self.sendCurrentActivityBig(s)
    def sendCurrentActivityBig(self, client):
        state = self.currentBigState
        if state == "offline":
            client.currentlyOffline()
        elif state == "idle":
            client.currentlyIdle()
        elif state == "building":
            client.currentlyBuilding()
        else:
            log.msg("Hey, self.currentBigState is weird:", state)
            
    
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
            self.sendLastBuildStatus(client)
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


class SlaveStatus:
    implements(interfaces.ISlaveStatus)

    admin = None
    host = None
    access_uri = None
    version = None
    connected = False
    graceful_shutdown = False

    def __init__(self, name):
        self.name = name
        self._lastMessageReceived = 0
        self.runningBuilds = []
        self.graceful_callbacks = []
        self.connect_times = []

    def getName(self):
        return self.name
    def getAdmin(self):
        return self.admin
    def getHost(self):
        return self.host
    def getAccessURI(self):
        return self.access_uri
    def getVersion(self):
        return self.version
    def isConnected(self):
        return self.connected
    def lastMessageReceived(self):
        return self._lastMessageReceived
    def getRunningBuilds(self):
        return self.runningBuilds
    def getConnectCount(self):
        then = time.time() - 3600
        return len([ t for t in self.connect_times if t > then ])

    def setAdmin(self, admin):
        self.admin = admin
    def setHost(self, host):
        self.host = host
    def setAccessURI(self, access_uri):
        self.access_uri = access_uri
    def setVersion(self, version):
        self.version = version
    def setConnected(self, isConnected):
        self.connected = isConnected
    def setLastMessageReceived(self, when):
        self._lastMessageReceived = when

    def recordConnectTime(self):
        # record this connnect, and keep data for the last hour
        now = time.time()
        self.connect_times = [ t for t in self.connect_times if t > now - 3600 ] + [ now ]

    def buildStarted(self, build):
        self.runningBuilds.append(build)
    def buildFinished(self, build):
        self.runningBuilds.remove(build)

    def getGraceful(self):
        """Return the graceful shutdown flag"""
        return self.graceful_shutdown
    def setGraceful(self, graceful):
        """Set the graceful shutdown flag, and notify all the watchers"""
        self.graceful_shutdown = graceful
        for cb in self.graceful_callbacks:
            eventually(cb, graceful)
    def addGracefulWatcher(self, watcher):
        """Add watcher to the list of watchers to be notified when the
        graceful shutdown flag is changed."""
        if not watcher in self.graceful_callbacks:
            self.graceful_callbacks.append(watcher)
    def removeGracefulWatcher(self, watcher):
        """Remove watcher from the list of watchers to be notified when the
        graceful shutdown flag is changed."""
        if watcher in self.graceful_callbacks:
            self.graceful_callbacks.remove(watcher)

    def asDict(self):
        result = {}
        # Constant
        result['name'] = self.getName()
        result['access_uri'] = self.getAccessURI()

        # Transient (since it changes when the slave reconnects)
        result['host'] = self.getHost()
        result['admin'] = self.getAdmin()
        result['version'] = self.getVersion()
        result['connected'] = self.isConnected()
        result['runningBuilds'] = [b.asDict() for b in self.getRunningBuilds()]
        return result

class Status:
    """
    I represent the status of the buildmaster.
    """
    implements(interfaces.IStatus)

    def __init__(self, botmaster, basedir):
        """
        @type  botmaster: L{buildbot.master.BotMaster}
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
