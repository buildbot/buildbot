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

from bz2 import BZ2File
from cStringIO import StringIO
from gzip import GzipFile

from buildbot import interfaces
from buildbot.util import netstrings
from buildbot.util.eventual import eventually
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import threads
from twisted.python import log
from twisted.python import runtime
from zope.interface import implements

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
                yield chunks.pop(0)
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
            self.chunkGenerator = None  # stop making chunks
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

    """
    A LogFile keeps all of its contents on disk, in a non-pickle format to
    which new entries can easily be appended. The file on disk has a name like
    12-log-compile-output, under the Builder's directory. The actual filename
    is generated (before the LogFile is created) by
    L{BuildStatus.generateLogfileName}.

    @ivar length: length of the data in the logfile (sum of chunk sizes; not
    the length of the on-disk encoding)
    """

    implements(interfaces.IStatusLog, interfaces.ILogFile)

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
    _isNewStyle = False  # set to True by new-style buildsteps

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

    def hasContents(self):
        """
        Return true if this logfile's contents are available.  For a newly
        created logfile, this is always true, but for a L{LogFile} instance
        that has been persisted, the logfiles themselves may have been deleted,
        in which case this method will return False.

        @returns: boolean
        """
        assert not self._isNewStyle, "not available in new-style steps"
        return self.old_hasContents()

    def old_hasContents(self):
        return os.path.exists(self.getFilename() + '.bz2') or \
            os.path.exists(self.getFilename() + '.gz') or \
            os.path.exists(self.getFilename())

    def getName(self):
        """
        Get this logfile's name

        @returns: string
        """
        return self.name

    def getStep(self):
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

    def getText(self):
        # this produces one ginormous string
        assert not self._isNewStyle, "not available in new-style steps"
        return "".join(self.getChunks([STDOUT, STDERR], onlyText=True))

    def getTextWithHeaders(self):
        assert not self._isNewStyle, "not available in new-style steps"
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

        assert not self._isNewStyle, "not available in new-style steps"

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

    def readlines(self):
        """Return an iterator that produces newline-terminated lines,
        excluding header chunks."""
        assert not self._isNewStyle, "not available in new-style steps"
        alltext = "".join(self.getChunks([STDOUT], onlyText=True))
        io = StringIO(alltext)
        return io.readlines()

    def subscribe(self, receiver, catchup):
        assert not self._isNewStyle, "not available in new-style steps"
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
        # NOTE: this method is called by WebStatus, so it must remain available
        # even for new-style steps
        p = LogFileProducer(self, consumer)
        p.resumeProducing()

    # interface used by the build steps to add things to the log

    def _merge(self):
        # merge all .runEntries (which are all of the same type) into a
        # single chunk for .entries
        if not self.runEntries:
            return
        channel = self.runEntries[0][0]
        text = "".join([c[1] for c in self.runEntries])
        assert channel < 10, "channel number must be a single decimal digit"
        f = self.openfile
        f.seek(0, 2)
        offset = 0
        while offset < len(text):
            size = min(len(text) - offset, self.chunkSize)
            f.write("%d:%d" % (1 + size, channel))
            f.write(text[offset:offset + size])
            f.write(",")
            offset += size
        self.runEntries = []
        self.runLength = 0

    def addEntry(self, channel, text, _no_watchers=False):
        """
        Add an entry to the logfile.  The C{channel} is one of L{STDOUT},
        L{STDERR}, or L{HEADER}.  The C{text} is the text to add to the
        logfile, which can be a unicode string or a bytestring which is
        presumed to be encoded with utf-8.

        This method cannot be called after the logfile is finished.

        @param channel: channel to add a chunk for
        @param text: chunk of text
        @param _no_watchers: private
        """

        assert not self.finished, "logfile is already finished"

        if isinstance(text, unicode):
            text = text.encode('utf-8')

        # notify watchers first, before the chunk gets munged, so that they get
        # a complete picture of the actual log output
        # TODO: is this right, or should the watchers get a picture of the chunks?
        if not _no_watchers:
            for w in self.watchers:
                w.logChunk(self.step.build, self.step, self, channel, text)

        if channel != HEADER:
            # Truncate the log if it's more than logMaxSize bytes
            logMaxSize = self.master.config.logMaxSize
            logMaxTailSize = self.master.config.logMaxTailSize
            if logMaxSize:
                self.nonHeaderLength += len(text)
                if self.nonHeaderLength > logMaxSize:
                    # Add a message about what's going on and truncate this
                    # chunk if necessary
                    if not self.maxLengthExceeded:
                        if self.runEntries and channel != self.runEntries[0][0]:
                            self._merge()
                        i = -(self.nonHeaderLength - logMaxSize)
                        trunc, text = text[:i], text[i:]
                        self.runEntries.append((channel, trunc))
                        self._merge()
                        msg = ("\nOutput exceeded %i bytes, remaining output "
                               "has been truncated\n" % logMaxSize)
                        self.runEntries.append((HEADER, msg))
                        self.maxLengthExceeded = True

                    # and track the tail of the text
                    if logMaxTailSize and text:
                        # Update the tail buffer
                        self.tailBuffer.append((channel, text))
                        self.tailLength += len(text)
                        while self.tailLength > logMaxTailSize:
                            # Drop some stuff off the beginning of the buffer
                            c, t = self.tailBuffer.pop(0)
                            n = len(t)
                            self.tailLength -= n
                            assert self.tailLength >= 0
                    return

        # we only add to .runEntries here. _merge() is responsible for adding
        # merged chunks to .entries
        if self.runEntries and channel != self.runEntries[0][0]:
            self._merge()
        self.runEntries.append((channel, text))
        self.runLength += len(text)
        if self.runLength >= self.chunkSize:
            self._merge()

        self.length += len(text)

    def addStdout(self, text):
        """
        Shortcut to add stdout text to the logfile

        @param text: text to add to the logfile
        """
        self.addEntry(STDOUT, text)
        return defer.succeed(None)

    def addStderr(self, text):
        """
        Shortcut to add stderr text to the logfile

        @param text: text to add to the logfile
        """
        self.addEntry(STDERR, text)
        return defer.succeed(None)

    def addHeader(self, text):
        """
        Shortcut to add header text to the logfile

        @param text: text to add to the logfile
        """
        self.addEntry(HEADER, text)
        return defer.succeed(None)

    def finish(self):
        """
        Finish the logfile, flushing any buffers and preventing any further
        writes to the log.
        """
        self._merge()
        if self.tailBuffer:
            msg = "\nFinal %i bytes follow below:\n" % self.tailLength
            tmp = self.runEntries
            self.runEntries = [(HEADER, msg)]
            self._merge()
            self.runEntries = self.tailBuffer
            self._merge()
            self.runEntries = tmp
            self._merge()
            self.tailBuffer = []

        if self.openfile:
            # we don't do an explicit close, because there might be readers
            # shareing the filehandle. As soon as they stop reading, the
            # filehandle will be released and automatically closed.
            self.openfile.flush()
            self.openfile = None
        self.finished = True
        watchers = self.finishedWatchers
        self.finishedWatchers = []
        for w in watchers:
            w.callback(self)
        self.watchers = []
        return defer.succeed(None)

    def compressLog(self):
        logCompressionMethod = self.master.config.logCompressionMethod
        # bail out if there's no compression support
        if logCompressionMethod == "bz2":
            compressed = self.getFilename() + ".bz2.tmp"
        elif logCompressionMethod == "gz":
            compressed = self.getFilename() + ".gz.tmp"
        else:
            return defer.succeed(None)

        def _compressLog():
            infile = self.getFile()
            if logCompressionMethod == "bz2":
                cf = BZ2File(compressed, 'w')
            elif logCompressionMethod == "gz":
                cf = GzipFile(compressed, 'w')
            bufsize = 1024 * 1024
            while True:
                buf = infile.read(bufsize)
                cf.write(buf)
                if len(buf) < bufsize:
                    break
            cf.close()
        d = threads.deferToThread(_compressLog)

        def _renameCompressedLog(rv):
            if logCompressionMethod == "bz2":
                filename = self.getFilename() + '.bz2'
            else:
                filename = self.getFilename() + '.gz'
            if runtime.platformType == 'win32':
                # windows cannot rename a file on top of an existing one, so
                # fall back to delete-first. There are ways this can fail and
                # lose the builder's history, so we avoid using it in the
                # general (non-windows) case
                if os.path.exists(filename):
                    os.unlink(filename)
            os.rename(compressed, filename)
            _tryremove(self.getFilename(), 1, 5)
        d.addCallback(_renameCompressedLog)

        def _cleanupFailedCompress(failure):
            log.msg("failed to compress %s" % self.getFilename())
            if os.path.exists(compressed):
                _tryremove(compressed, 1, 5)
            failure.trap()  # reraise the failure
        d.addErrback(_cleanupFailedCompress)
        return d

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


class HTMLLogFile(LogFile):

    def __init__(self, parent, name, logfilename, html):
        LogFile.__init__(self, parent, name, logfilename)
        self.addStderr(html)
        self.finish()

    def hasContents(self):
        assert not self._isNewStyle, "not available in new-style steps"
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
