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
from cStringIO import StringIO
from bz2 import BZ2File
from gzip import GzipFile

from zope.interface import implements
from twisted.python import log, runtime
from twisted.internet import defer, threads, reactor
from buildbot.util import netstrings
from buildbot.util.eventual import eventually
from buildbot import interfaces

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

