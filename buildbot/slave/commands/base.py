# -*- test-case-name: buildbot.test.test_slavecommand -*-

import os, signal, types, time, re, traceback
from stat import ST_CTIME, ST_MTIME, ST_SIZE
from collections import deque

from zope.interface import implements
from twisted.internet.protocol import ProcessProtocol
from twisted.internet import reactor, defer, task
from twisted.python import log, runtime

from buildbot.slave.interfaces import ISlaveCommand
from buildbot.slave.commands.registry import registerSlaveCommand
from buildbot import util

# this used to be a CVS $-style "Revision" auto-updated keyword, but since I
# moved to Darcs as the primary repository, this is updated manually each
# time this file is changed. The last cvs_ver that was here was 1.51 .
command_version = "2.9"

# version history:
#  >=1.17: commands are interruptable
#  >=1.28: Arch understands 'revision', added Bazaar
#  >=1.33: Source classes understand 'retry'
#  >=1.39: Source classes correctly handle changes in branch (except Git)
#          Darcs accepts 'revision' (now all do but Git) (well, and P4Sync)
#          Arch/Baz should accept 'build-config'
#  >=1.51: (release 0.7.3)
#  >= 2.1: SlaveShellCommand now accepts 'initial_stdin', 'keep_stdin_open',
#          and 'logfiles'. It now sends 'log' messages in addition to
#          stdout/stdin/header/rc. It acquired writeStdin/closeStdin methods,
#          but these are not remotely callable yet.
#          (not externally visible: ShellCommandPP has writeStdin/closeStdin.
#          ShellCommand accepts new arguments (logfiles=, initialStdin=,
#          keepStdinOpen=) and no longer accepts stdin=)
#          (release 0.7.4)
#  >= 2.2: added monotone, uploadFile, and downloadFile (release 0.7.5)
#  >= 2.3: added bzr (release 0.7.6)
#  >= 2.4: Git understands 'revision' and branches
#  >= 2.5: workaround added for remote 'hg clone --rev REV' when hg<0.9.2
#  >= 2.6: added uploadDirectory
#  >= 2.7: added usePTY option to SlaveShellCommand
#  >= 2.8: added username and password args to SVN class
#  >= 2.9: add depth arg to SVN class
#  >= 2.10: CVS can handle 'extra_options' and 'export_options'

class CommandInterrupted(Exception):
    pass
class TimeoutError(Exception):
    pass

class Obfuscated:
    """An obfuscated string in a command"""
    def __init__(self, real, fake):
        self.real = real
        self.fake = fake

    def __str__(self):
        return self.fake

    def __repr__(self):
        return `self.fake`

    @staticmethod
    def to_text(s):
        if isinstance(s, (str, unicode)):
            return s
        else:
            return str(s)

    @staticmethod
    def get_real(command):
        rv = command
        if type(command) == types.ListType:
            rv = []
            for elt in command:
                if isinstance(elt, Obfuscated):
                    rv.append(elt.real)
                else:
                    rv.append(Obfuscated.to_text(elt))
        return rv

    @staticmethod
    def get_fake(command):
        rv = command
        if type(command) == types.ListType:
            rv = []
            for elt in command:
                if isinstance(elt, Obfuscated):
                    rv.append(elt.fake)
                else:
                    rv.append(Obfuscated.to_text(elt))
        return rv

class AbandonChain(Exception):
    """A series of chained steps can raise this exception to indicate that
    one of the intermediate ShellCommands has failed, such that there is no
    point in running the remainder. 'rc' should be the non-zero exit code of
    the failing ShellCommand."""

    def __repr__(self):
        return "<AbandonChain rc=%s>" % self.args[0]

class ShellCommandPP(ProcessProtocol):
    debug = False

    def __init__(self, command):
        self.command = command
        self.pending_stdin = ""
        self.stdin_finished = False

    def writeStdin(self, data):
        assert not self.stdin_finished
        if self.connected:
            self.transport.write(data)
        else:
            self.pending_stdin += data

    def closeStdin(self):
        if self.connected:
            if self.debug: log.msg(" closing stdin")
            self.transport.closeStdin()
        self.stdin_finished = True

    def connectionMade(self):
        if self.debug:
            log.msg("ShellCommandPP.connectionMade")
        if not self.command.process:
            if self.debug:
                log.msg(" assigning self.command.process: %s" %
                        (self.transport,))
            self.command.process = self.transport

        # TODO: maybe we shouldn't close stdin when using a PTY. I can't test
        # this yet, recent debian glibc has a bug which causes thread-using
        # test cases to SIGHUP trial, and the workaround is to either run
        # the whole test with /bin/sh -c " ".join(argv)  (way gross) or to
        # not use a PTY. Once the bug is fixed, I'll be able to test what
        # happens when you close stdin on a pty. My concern is that it will
        # SIGHUP the child (since we are, in a sense, hanging up on them).
        # But it may well be that keeping stdout open prevents the SIGHUP
        # from being sent.
        #if not self.command.usePTY:

        if self.pending_stdin:
            if self.debug: log.msg(" writing to stdin")
            self.transport.write(self.pending_stdin)
        if self.stdin_finished:
            if self.debug: log.msg(" closing stdin")
            self.transport.closeStdin()

    def outReceived(self, data):
        if self.debug:
            log.msg("ShellCommandPP.outReceived")
        self.command.addStdout(data)

    def errReceived(self, data):
        if self.debug:
            log.msg("ShellCommandPP.errReceived")
        self.command.addStderr(data)

    def processEnded(self, status_object):
        if self.debug:
            log.msg("ShellCommandPP.processEnded", status_object)
        # status_object is a Failure wrapped around an
        # error.ProcessTerminated or and error.ProcessDone.
        # requires twisted >= 1.0.4 to overcome a bug in process.py
        sig = status_object.value.signal
        rc = status_object.value.exitCode
        self.command.finished(sig, rc)

class LogFileWatcher:
    POLL_INTERVAL = 2

    def __init__(self, command, name, logfile, follow=False):
        self.command = command
        self.name = name
        self.logfile = logfile

        log.msg("LogFileWatcher created to watch %s" % logfile)
        # we are created before the ShellCommand starts. If the logfile we're
        # supposed to be watching already exists, record its size and
        # ctime/mtime so we can tell when it starts to change.
        self.old_logfile_stats = self.statFile()
        self.started = False

        # follow the file, only sending back lines
        # added since we started watching
        self.follow = follow

        # every 2 seconds we check on the file again
        self.poller = task.LoopingCall(self.poll)

    def start(self):
        self.poller.start(self.POLL_INTERVAL).addErrback(self._cleanupPoll)

    def _cleanupPoll(self, err):
        log.err(err, msg="Polling error")
        self.poller = None

    def stop(self):
        self.poll()
        if self.poller is not None:
            self.poller.stop()
        if self.started:
            self.f.close()

    def statFile(self):
        if os.path.exists(self.logfile):
            s = os.stat(self.logfile)
            return (s[ST_CTIME], s[ST_MTIME], s[ST_SIZE])
        return None

    def poll(self):
        if not self.started:
            s = self.statFile()
            if s == self.old_logfile_stats:
                return # not started yet
            if not s:
                # the file was there, but now it's deleted. Forget about the
                # initial state, clearly the process has deleted the logfile
                # in preparation for creating a new one.
                self.old_logfile_stats = None
                return # no file to work with
            self.f = open(self.logfile, "rb")
            # if we only want new lines, seek to
            # where we stat'd so we only find new
            # lines
            if self.follow:
                self.f.seek(s[2], 0)
            self.started = True
        self.f.seek(self.f.tell(), 0)
        while True:
            data = self.f.read(10000)
            if not data:
                return
            self.command.addLogfile(self.name, data)


class ShellCommand:
    # This is a helper class, used by SlaveCommands to run programs in a
    # child shell.

    notreally = False
    BACKUP_TIMEOUT = 5
    KILL = "KILL"
    CHUNK_LIMIT = 128*1024

    # Don't send any data until at least BUFFER_SIZE bytes have been collected
    # or BUFFER_TIMEOUT elapsed
    BUFFER_SIZE = 64*1024
    BUFFER_TIMEOUT = 5

    # For sending elapsed time:
    startTime = None
    elapsedTime = None

    # For scheduling future events
    _reactor = reactor

    # I wish we had easy access to CLOCK_MONOTONIC in Python:
    # http://www.opengroup.org/onlinepubs/000095399/functions/clock_getres.html
    # Then changes to the system clock during a run wouldn't effect the "elapsed
    # time" results.

    def __init__(self, builder, command,
                 workdir, environ=None,
                 sendStdout=True, sendStderr=True, sendRC=True,
                 timeout=None, maxTime=None, initialStdin=None,
                 keepStdinOpen=False, keepStdout=False, keepStderr=False,
                 logEnviron=True, logfiles={}, usePTY="slave-config"):
        """

        @param keepStdout: if True, we keep a copy of all the stdout text
                           that we've seen. This copy is available in
                           self.stdout, which can be read after the command
                           has finished.
        @param keepStderr: same, for stderr

        @param usePTY: "slave-config" -> use the SlaveBuilder's usePTY;
            otherwise, true to use a PTY, false to not use a PTY.
        """

        self.builder = builder
        self.command = Obfuscated.get_real(command)

        # We need to take unicode commands and arguments and encode them using
        # the appropriate encoding for the slave.  This is mostly platform
        # specific, but can be overridden in the slave's buildbot.tac file.
        #
        # Encoding the command line here ensures that the called executables
        # receive arguments as bytestrings encoded with an appropriate
        # platform-specific encoding.  It also plays nicely with twisted's
        # spawnProcess which checks that arguments are regular strings or
        # unicode strings that can be encoded as ascii (which generates a
        # warning).
        if isinstance(self.command, (tuple, list)):
            for i, a in enumerate(self.command):
                if isinstance(a, unicode):
                    self.command[i] = a.encode(self.builder.unicode_encoding)
        elif isinstance(self.command, unicode):
            self.command = self.command.encode(self.builder.unicode_encoding)

        self.fake_command = Obfuscated.get_fake(command)
        self.sendStdout = sendStdout
        self.sendStderr = sendStderr
        self.sendRC = sendRC
        self.logfiles = logfiles
        self.workdir = workdir
        if not os.path.exists(workdir):
            os.makedirs(workdir)
        if environ:
            if environ.has_key('PYTHONPATH'):
                ppath = environ['PYTHONPATH']
                # Need to do os.pathsep translation.  We could either do that
                # by replacing all incoming ':'s with os.pathsep, or by
                # accepting lists.  I like lists better.
                if not isinstance(ppath, str):
                    # If it's not a string, treat it as a sequence to be
                    # turned in to a string.
                    ppath = os.pathsep.join(ppath)

                environ['PYTHONPATH'] = ppath + os.pathsep + "${PYTHONPATH}"

            # do substitution on variable values matching patern: ${name}
            p = re.compile('\${([0-9a-zA-Z_]*)}')
            def subst(match):
                return os.environ.get(match.group(1), "")
            newenv = {}
            for key in os.environ.keys():
                # setting a key to None will delete it from the slave environment
                if key not in environ or environ[key] is not None:
                    newenv[key] = os.environ[key]
            for key in environ.keys():
                if environ[key] is not None:
                    newenv[key] = p.sub(subst, environ[key])

            self.environ = newenv
        else: # not environ
            self.environ = os.environ.copy()
        self.initialStdin = initialStdin
        self.keepStdinOpen = keepStdinOpen
        self.logEnviron = logEnviron
        self.timeout = timeout
        self.timer = None
        self.maxTime = maxTime
        self.maxTimer = None
        self.keepStdout = keepStdout
        self.keepStderr = keepStderr

        self.buffered = deque()
        self.buflen = 0
        self.buftimer = None

        if usePTY == "slave-config":
            self.usePTY = self.builder.usePTY
        else:
            self.usePTY = usePTY

        # usePTY=True is a convenience for cleaning up all children and
        # grandchildren of a hung command. Fall back to usePTY=False on systems
        # and in situations where ptys cause problems.  PTYs are posix-only,
        # and for .closeStdin to matter, we must use a pipe, not a PTY
        if runtime.platformType != "posix" or initialStdin is not None:
            if self.usePTY and usePTY != "slave-config":
                self.sendStatus({'header': "WARNING: disabling usePTY for this command"})
            self.usePTY = False

        self.logFileWatchers = []
        for name,filevalue in self.logfiles.items():
            filename = filevalue
            follow = False

            # check for a dictionary of options
            # filename is required, others are optional
            if type(filevalue) == dict:
                filename = filevalue['filename']
                follow = filevalue.get('follow', False)

            w = LogFileWatcher(self, name,
                               os.path.join(self.workdir, filename),
                               follow=follow)
            self.logFileWatchers.append(w)

    def __repr__(self):
        return "<slavecommand.ShellCommand '%s'>" % self.fake_command

    def sendStatus(self, status):
        self.builder.sendUpdate(status)

    def start(self):
        # return a Deferred which fires (with the exit code) when the command
        # completes
        if self.keepStdout:
            self.stdout = ""
        if self.keepStderr:
            self.stderr = ""
        self.deferred = defer.Deferred()
        try:
            self._startCommand()
        except:
            log.msg("error in ShellCommand._startCommand")
            log.err()
            self._addToBuffers('stderr', "error in ShellCommand._startCommand\n")
            self._addToBuffers('stderr', traceback.format_exc())
            self._sendBuffers()
            # pretend it was a shell error
            self.deferred.errback(AbandonChain(-1))
        return self.deferred

    def _startCommand(self):
        # ensure workdir exists
        if not os.path.isdir(self.workdir):
            os.makedirs(self.workdir)
        log.msg("ShellCommand._startCommand")
        if self.notreally:
            self._addToBuffers('header', "command '%s' in dir %s" % \
                             (self.fake_command, self.workdir))
            self._addToBuffers('header', "(not really)\n")
            self.finished(None, 0)
            return

        self.pp = ShellCommandPP(self)

        if type(self.command) in types.StringTypes:
            if runtime.platformType  == 'win32':
                argv = os.environ['COMSPEC'].split() # allow %COMSPEC% to have args
                if '/c' not in argv: argv += ['/c']
                argv += [self.command]
            else:
                # for posix, use /bin/sh. for other non-posix, well, doesn't
                # hurt to try
                argv = ['/bin/sh', '-c', self.command]
            display = self.fake_command
        else:
            # On windows, CreateProcess requires an absolute path to the executable.
            # When we call spawnProcess below, we pass argv[0] as the executable.
            # So, for .exe's that we have absolute paths to, we can call directly
            # Otherwise, we should run under COMSPEC (usually cmd.exe) to
            # handle path searching, etc.
            if runtime.platformType == 'win32' and not \
                    (self.command[0].lower().endswith(".exe") and os.path.isabs(self.command[0])):
                argv = os.environ['COMSPEC'].split() # allow %COMSPEC% to have args
                if '/c' not in argv: argv += ['/c']
                argv += list(self.command)
            else:
                argv = self.command
            display = " ".join(self.fake_command)

        # $PWD usually indicates the current directory; spawnProcess may not
        # update this value, though, so we set it explicitly here.  This causes
        # weird problems (bug #456) on msys, though..
        if not self.environ.get('MACHTYPE', None) == 'i686-pc-msys':
            self.environ['PWD'] = os.path.abspath(self.workdir)

        # self.stdin is handled in ShellCommandPP.connectionMade

        # first header line is the command in plain text, argv joined with
        # spaces. You should be able to cut-and-paste this into a shell to
        # obtain the same results. If there are spaces in the arguments, too
        # bad.
        log.msg(" " + display)
        self._addToBuffers('header', display+"\n")

        # then comes the secondary information
        msg = " in dir %s" % (self.workdir,)
        if self.timeout:
            msg += " (timeout %d secs)" % (self.timeout,)
        log.msg(" " + msg)
        self._addToBuffers('header', msg+"\n")

        msg = " watching logfiles %s" % (self.logfiles,)
        log.msg(" " + msg)
        self._addToBuffers('header', msg+"\n")

        # then the obfuscated command array for resolving unambiguity
        msg = " argv: %s" % (self.fake_command,)
        log.msg(" " + msg)
        self._addToBuffers('header', msg+"\n")

        # then the environment, since it sometimes causes problems
        if self.logEnviron:
            msg = " environment:\n"
            env_names = self.environ.keys()
            env_names.sort()
            for name in env_names:
                msg += "  %s=%s\n" % (name, self.environ[name])
            log.msg(" environment: %s" % (self.environ,))
            self._addToBuffers('header', msg)

        if self.initialStdin:
            msg = " writing %d bytes to stdin" % len(self.initialStdin)
            log.msg(" " + msg)
            self._addToBuffers('header', msg+"\n")

        if self.keepStdinOpen:
            msg = " leaving stdin open"
        else:
            msg = " closing stdin"
        log.msg(" " + msg)
        self._addToBuffers('header', msg+"\n")

        msg = " using PTY: %s" % bool(self.usePTY)
        log.msg(" " + msg)
        self._addToBuffers('header', msg+"\n")

        # this will be buffered until connectionMade is called
        if self.initialStdin:
            self.pp.writeStdin(self.initialStdin)
        if not self.keepStdinOpen:
            self.pp.closeStdin()

        # win32eventreactor's spawnProcess (under twisted <= 2.0.1) returns
        # None, as opposed to all the posixbase-derived reactors (which
        # return the new Process object). This is a nuisance. We can make up
        # for it by having the ProcessProtocol give us their .transport
        # attribute after they get one. I'd prefer to get it from
        # spawnProcess because I'm concerned about returning from this method
        # without having a valid self.process to work with. (if kill() were
        # called right after we return, but somehow before connectionMade
        # were called, then kill() would blow up).
        self.process = None
        self.startTime = util.now(self._reactor)

        p = reactor.spawnProcess(self.pp, argv[0], argv,
                                 self.environ,
                                 self.workdir,
                                 usePTY=self.usePTY)
        # connectionMade might have been called during spawnProcess
        if not self.process:
            self.process = p

        # connectionMade also closes stdin as long as we're not using a PTY.
        # This is intended to kill off inappropriately interactive commands
        # better than the (long) hung-command timeout. ProcessPTY should be
        # enhanced to allow the same childFDs argument that Process takes,
        # which would let us connect stdin to /dev/null .

        if self.timeout:
            self.timer = self._reactor.callLater(self.timeout, self.doTimeout)

        if self.maxTime:
            self.maxTimer = self._reactor.callLater(self.maxTime, self.doMaxTimeout)

        for w in self.logFileWatchers:
            w.start()


    def _chunkForSend(self, data):
        """
        limit the chunks that we send over PB to 128k, since it has a hardwired
        string-size limit of 640k.
        """
        LIMIT = self.CHUNK_LIMIT
        for i in range(0, len(data), LIMIT):
            yield data[i:i+LIMIT]

    def _collapseMsg(self, msg):
        """
        Take msg, which is a dictionary of lists of output chunks, and
        concatentate all the chunks into a single string
        """
        retval = {}
        for log in msg:
            data = "".join(msg[log])
            if isinstance(log, tuple) and log[0] == 'log':
                retval['log'] = (log[1], data)
            else:
                retval[log] = data
        return retval

    def _sendMessage(self, msg):
        """
        Collapse and send msg to the master
        """
        if not msg:
            return
        msg = self._collapseMsg(msg)
        self.sendStatus(msg)

    def _bufferTimeout(self):
        self.buftimer = None
        self._sendBuffers()

    def _sendBuffers(self):
        """
        Send all the content in our buffers.
        """
        msg = {}
        msg_size = 0
        lastlog = None
        while self.buffered:
            # Grab the next bits from the buffer
            logname, data = self.buffered.popleft()

            # If this log is different than the last one, then we have to send
            # out the message so far.  This is because the message is
            # transferred as a dictionary, which makes the ordering of keys
            # unspecified, and makes it impossible to interleave data from
            # different logs.  A future enhancement could be to change the
            # master to support a list of (logname, data) tuples instead of a
            # dictionary. TODO: In 0.8.0?
            # On our first pass through this loop lastlog is None
            if lastlog is None:
                lastlog = logname
            elif logname != lastlog:
                self._sendMessage(msg)
                msg = {}
                msg_size = 0
            lastlog = logname

            logdata = msg.setdefault(logname, [])

            # Chunkify the log data to make sure we're not sending more than
            # CHUNK_LIMIT at a time
            for chunk in self._chunkForSend(data):
                logdata.append(chunk)
                msg_size += len(chunk)
                if msg_size > self.CHUNK_LIMIT:
                    # We've gone beyond the chunk limit, so send out our
                    # message.  At worst this results in a message slightly
                    # larger than (2*CHUNK_LIMIT)-1
                    self._sendMessage(msg)
                    msg = {}
                    msg_size = 0
        self.buflen = 0
        self._sendMessage(msg)
        if self.buftimer:
            if self.buftimer.active():
                self.buftimer.cancel()
            self.buftimer = None

    def _addToBuffers(self, logname, data):
        """
        Add data to the buffer for logname
        Start a timer to send the buffers if BUFFER_TIMEOUT elapses.
        If adding data causes the buffer size to grow beyond BUFFER_SIZE, then
        the buffers will be sent.
        """
        n = len(data)

        self.buflen += n
        self.buffered.append((logname, data))
        if self.buflen > self.BUFFER_SIZE:
            self._sendBuffers()
        elif not self.buftimer:
            self.buftimer = self._reactor.callLater(self.BUFFER_TIMEOUT, self._bufferTimeout)

    def addStdout(self, data):
        if self.sendStdout:
            self._addToBuffers('stdout', data)

        if self.keepStdout:
            self.stdout += data
        if self.timer:
            self.timer.reset(self.timeout)

    def addStderr(self, data):
        if self.sendStderr:
            self._addToBuffers('stderr', data)

        if self.keepStderr:
            self.stderr += data
        if self.timer:
            self.timer.reset(self.timeout)

    def addLogfile(self, name, data):
        self._addToBuffers( ('log', name), data)

        if self.timer:
            self.timer.reset(self.timeout)

    def finished(self, sig, rc):
        self.elapsedTime = util.now(self._reactor) - self.startTime
        log.msg("command finished with signal %s, exit code %s, elapsedTime: %0.6f" % (sig,rc,self.elapsedTime))
        for w in self.logFileWatchers:
            # this will send the final updates
            w.stop()
        self._sendBuffers()
        if sig is not None:
            rc = -1
        if self.sendRC:
            if sig is not None:
                self.sendStatus(
                    {'header': "process killed by signal %d\n" % sig})
            self.sendStatus({'rc': rc})
        self.sendStatus({'header': "elapsedTime=%0.6f\n" % self.elapsedTime})
        if self.timer:
            self.timer.cancel()
            self.timer = None
        if self.maxTimer:
            self.maxTimer.cancel()
            self.maxTimer = None
        if self.buftimer:
            self.buftimer.cancel()
            self.buftimer = None
        d = self.deferred
        self.deferred = None
        if d:
            d.callback(rc)
        else:
            log.msg("Hey, command %s finished twice" % self)

    def failed(self, why):
        self._sendBuffers()
        log.msg("ShellCommand.failed: command failed: %s" % (why,))
        if self.timer:
            self.timer.cancel()
            self.timer = None
        if self.maxTimer:
            self.maxTimer.cancel()
            self.maxTimer = None
        if self.buftimer:
            self.buftimer.cancel()
            self.buftimer = None
        d = self.deferred
        self.deferred = None
        if d:
            d.errback(why)
        else:
            log.msg("Hey, command %s finished twice" % self)

    def doTimeout(self):
        self.timer = None
        msg = "command timed out: %d seconds without output" % self.timeout
        self.kill(msg)

    def doMaxTimeout(self):
        self.maxTimer = None
        msg = "command timed out: %d seconds elapsed" % self.maxTime
        self.kill(msg)

    def kill(self, msg):
        # This may be called by the timeout, or when the user has decided to
        # abort this build.
        self._sendBuffers()
        if self.timer:
            self.timer.cancel()
            self.timer = None
        if self.maxTimer:
            self.maxTimer.cancel()
            self.maxTimer = None
        if self.buftimer:
            self.buftimer.cancel()
            self.buftimer = None
        if hasattr(self.process, "pid") and self.process.pid is not None:
            msg += ", killing pid %s" % self.process.pid
        log.msg(msg)
        self.sendStatus({'header': "\n" + msg + "\n"})

        hit = 0
        if runtime.platformType == "posix":
            try:
                # really want to kill off all child processes too. Process
                # Groups are ideal for this, but that requires
                # spawnProcess(usePTY=1). Try both ways in case process was
                # not started that way.

                # the test suite sets self.KILL=None to tell us we should
                # only pretend to kill the child. This lets us test the
                # backup timer.

                sig = None
                if self.KILL is not None:
                    sig = getattr(signal, "SIG"+ self.KILL, None)

                if self.KILL == None:
                    log.msg("self.KILL==None, only pretending to kill child")
                elif sig is None:
                    log.msg("signal module is missing SIG%s" % self.KILL)
                elif not hasattr(os, "kill"):
                    log.msg("os module is missing the 'kill' function")
                elif not hasattr(self.process, "pid") or self.process.pid is None:
                    log.msg("self.process has no pid")
                else:
                    log.msg("trying os.kill(-pid, %d)" % (sig,))
                    # TODO: maybe use os.killpg instead of a negative pid?
                    os.kill(-self.process.pid, sig)
                    log.msg(" signal %s sent successfully" % sig)
                    hit = 1
            except OSError:
                # probably no-such-process, maybe because there is no process
                # group
                pass
        if not hit:
            try:
                if self.KILL is None:
                    log.msg("self.KILL==None, only pretending to kill child")
                else:
                    log.msg("trying process.signalProcess('KILL')")
                    self.process.signalProcess(self.KILL)
                    log.msg(" signal %s sent successfully" % (self.KILL,))
                    hit = 1
            except OSError:
                # could be no-such-process, because they finished very recently
                pass
        if not hit:
            log.msg("signalProcess/os.kill failed both times")

        if runtime.platformType == "posix":
            # we only do this under posix because the win32eventreactor
            # blocks here until the process has terminated, while closing
            # stderr. This is weird.
            self.pp.transport.loseConnection()

        # finished ought to be called momentarily. Just in case it doesn't,
        # set a timer which will abandon the command.
        self.timer = self._reactor.callLater(self.BACKUP_TIMEOUT,
                                       self.doBackupTimeout)

    def doBackupTimeout(self):
        log.msg("we tried to kill the process, and it wouldn't die.."
                " finish anyway")
        self.timer = None
        self.sendStatus({'header': "SIGKILL failed to kill process\n"})
        if self.sendRC:
            self.sendStatus({'header': "using fake rc=-1\n"})
            self.sendStatus({'rc': -1})
        self.failed(TimeoutError("SIGKILL failed to kill process"))


    def writeStdin(self, data):
        self.pp.writeStdin(data)

    def closeStdin(self):
        self.pp.closeStdin()


class Command:
    implements(ISlaveCommand)

    """This class defines one command that can be invoked by the build master.
    The command is executed on the slave side, and always sends back a
    completion message when it finishes. It may also send intermediate status
    as it runs (by calling builder.sendStatus). Some commands can be
    interrupted (either by the build master or a local timeout), in which
    case the step is expected to complete normally with a status message that
    indicates an error occurred.

    These commands are used by BuildSteps on the master side. Each kind of
    BuildStep uses a single Command. The slave must implement all the
    Commands required by the set of BuildSteps used for any given build:
    this is checked at startup time.

    All Commands are constructed with the same signature:
     c = CommandClass(builder, args)
    where 'builder' is the parent SlaveBuilder object, and 'args' is a
    dict that is interpreted per-command.

    The setup(args) method is available for setup, and is run from __init__.

    The Command is started with start(). This method must be implemented in a
    subclass, and it should return a Deferred. When your step is done, you
    should fire the Deferred (the results are not used). If the command is
    interrupted, it should fire the Deferred anyway.

    While the command runs. it may send status messages back to the
    buildmaster by calling self.sendStatus(statusdict). The statusdict is
    interpreted by the master-side BuildStep however it likes.

    A separate completion message is sent when the deferred fires, which
    indicates that the Command has finished, but does not carry any status
    data. If the Command needs to return an exit code of some sort, that
    should be sent as a regular status message before the deferred is fired .
    Once builder.commandComplete has been run, no more status messages may be
    sent.

    If interrupt() is called, the Command should attempt to shut down as
    quickly as possible. Child processes should be killed, new ones should
    not be started. The Command should send some kind of error status update,
    then complete as usual by firing the Deferred.

    .interrupted should be set by interrupt(), and can be tested to avoid
    sending multiple error status messages.

    If .running is False, the bot is shutting down (or has otherwise lost the
    connection to the master), and should not send any status messages. This
    is checked in Command.sendStatus .

    """

    # builder methods:
    #  sendStatus(dict) (zero or more)
    #  commandComplete() or commandInterrupted() (one, at end)

    debug = False
    interrupted = False
    running = False # set by Builder, cleared on shutdown or when the
                    # Deferred fires

    _reactor = reactor

    def __init__(self, builder, stepId, args):
        self.builder = builder
        self.stepId = stepId # just for logging
        self.args = args
        self.setup(args)

    def setup(self, args):
        """Override this in a subclass to extract items from the args dict."""
        pass

    def doStart(self):
        self.running = True
        d = defer.maybeDeferred(self.start)
        d.addBoth(self.commandComplete)
        return d

    def start(self):
        """Start the command. This method should return a Deferred that will
        fire when the command has completed. The Deferred's argument will be
        ignored.

        This method should be overridden by subclasses."""
        raise NotImplementedError, "You must implement this in a subclass"

    def sendStatus(self, status):
        """Send a status update to the master."""
        if self.debug:
            log.msg("sendStatus", status)
        if not self.running:
            log.msg("would sendStatus but not .running")
            return
        self.builder.sendUpdate(status)

    def doInterrupt(self):
        self.running = False
        self.interrupt()

    def interrupt(self):
        """Override this in a subclass to allow commands to be interrupted.
        May be called multiple times, test and set self.interrupted=True if
        this matters."""
        pass

    def commandComplete(self, res):
        self.running = False
        return res

    # utility methods, mostly used by SlaveShellCommand and the like

    def _abandonOnFailure(self, rc):
        if type(rc) is not int:
            log.msg("weird, _abandonOnFailure was given rc=%s (%s)" % \
                    (rc, type(rc)))
        assert isinstance(rc, int)
        if rc != 0:
            raise AbandonChain(rc)
        return rc

    def _sendRC(self, res):
        self.sendStatus({'rc': 0})

    def _checkAbandoned(self, why):
        log.msg("_checkAbandoned", why)
        why.trap(AbandonChain)
        log.msg(" abandoning chain", why.value)
        self.sendStatus({'rc': why.value.args[0]})
        return None



class SlaveShellCommand(Command):
    """This is a Command which runs a shell command. The args dict contains
    the following keys:

        - ['command'] (required): a shell command to run. If this is a string,
                                  it will be run with /bin/sh (['/bin/sh',
                                  '-c', command]). If it is a list
                                  (preferred), it will be used directly.
        - ['workdir'] (required): subdirectory in which the command will be
                                  run, relative to the builder dir
        - ['env']: a dict of environment variables to augment/replace
                   os.environ . PYTHONPATH is treated specially, and
                   should be a list of path components to be prepended to
                   any existing PYTHONPATH environment variable.
        - ['initial_stdin']: a string which will be written to the command's
                             stdin as soon as it starts
        - ['keep_stdin_open']: unless True, the command's stdin will be
                               closed as soon as initial_stdin has been
                               written. Set this to True if you plan to write
                               to stdin after the command has been started.
        - ['want_stdout']: 0 if stdout should be thrown away
        - ['want_stderr']: 0 if stderr should be thrown away
        - ['usePTY']: True or False if the command should use a PTY (defaults to
                      configuration of the slave)
        - ['not_really']: 1 to skip execution and return rc=0
        - ['timeout']: seconds of silence to tolerate before killing command
        - ['maxTime']: seconds before killing command
        - ['logfiles']: dict mapping LogFile name to the workdir-relative
                        filename of a local log file. This local file will be
                        watched just like 'tail -f', and all changes will be
                        written to 'log' status updates.
        - ['logEnviron']: False to not log the environment variables on the slave

    ShellCommand creates the following status messages:
        - {'stdout': data} : when stdout data is available
        - {'stderr': data} : when stderr data is available
        - {'header': data} : when headers (command start/stop) are available
        - {'log': (logfile_name, data)} : when log files have new contents
        - {'rc': rc} : when the process has terminated
    """

    def start(self):
        args = self.args
        # args['workdir'] is relative to Builder directory, and is required.
        assert args['workdir'] is not None
        workdir = os.path.join(self.builder.basedir, args['workdir'])

        c = ShellCommand(self.builder, args['command'],
                         workdir, environ=args.get('env'),
                         timeout=args.get('timeout', None),
                         maxTime=args.get('maxTime', None),
                         sendStdout=args.get('want_stdout', True),
                         sendStderr=args.get('want_stderr', True),
                         sendRC=True,
                         initialStdin=args.get('initial_stdin'),
                         keepStdinOpen=args.get('keep_stdin_open'),
                         logfiles=args.get('logfiles', {}),
                         usePTY=args.get('usePTY', "slave-config"),
                         logEnviron=args.get('logEnviron', True),
                         )
        c._reactor = self._reactor
        self.command = c
        d = self.command.start()
        return d

    def interrupt(self):
        self.interrupted = True
        self.command.kill("command interrupted")

    def writeStdin(self, data):
        self.command.writeStdin(data)

    def closeStdin(self):
        self.command.closeStdin()

registerSlaveCommand("shell", SlaveShellCommand, command_version)


class DummyCommand(Command):
    """
    I am a dummy no-op command that by default takes 5 seconds to complete.
    See L{buildbot.steps.dummy.RemoteDummy}
    """

    def start(self):
        self.d = defer.Deferred()
        log.msg("  starting dummy command [%s]" % self.stepId)
        self.timer = self._reactor.callLater(1, self.doStatus)
        return self.d

    def interrupt(self):
        if self.interrupted:
            return
        self.timer.cancel()
        self.timer = None
        self.interrupted = True
        self.finished()

    def doStatus(self):
        log.msg("  sending intermediate status")
        self.sendStatus({'stdout': 'data'})
        timeout = self.args.get('timeout', 5) + 1
        self.timer = self._reactor.callLater(timeout - 1, self.finished)

    def finished(self):
        log.msg("  dummy command finished [%s]" % self.stepId)
        if self.interrupted:
            self.sendStatus({'rc': 1})
        else:
            self.sendStatus({'rc': 0})
        self.d.callback(0)

registerSlaveCommand("dummy", DummyCommand, command_version)


# this maps handle names to a callable. When the WaitCommand starts, this
# callable is invoked with no arguments. It should return a Deferred. When
# that Deferred fires, our WaitCommand will finish.
waitCommandRegistry = {}

class WaitCommand(Command):
    """
    I am a dummy command used by the buildbot unit test suite. I want for the
    unit test to tell us to finish. See L{buildbot.steps.dummy.Wait}
    """

    def start(self):
        self.d = defer.Deferred()
        log.msg("  starting wait command [%s]" % self.stepId)
        handle = self.args['handle']
        cb = waitCommandRegistry[handle]
        del waitCommandRegistry[handle]
        def _called():
            log.msg(" wait-%s starting" % (handle,))
            d = cb()
            def _done(res):
                log.msg(" wait-%s finishing: %s" % (handle, res))
                return res
            d.addBoth(_done)
            d.addCallbacks(self.finished, self.failed)
        self._reactor.callLater(0, _called)
        return self.d

    def interrupt(self):
        log.msg("  wait command interrupted")
        if self.interrupted:
            return
        self.interrupted = True
        self.finished("interrupted")

    def finished(self, res):
        log.msg("  wait command finished [%s]" % self.stepId)
        if self.interrupted:
            self.sendStatus({'rc': 2})
        else:
            self.sendStatus({'rc': 0})
        self.d.callback(0)
    def failed(self, why):
        log.msg("  wait command failed [%s]" % self.stepId)
        self.sendStatus({'rc': 1})
        self.d.callback(0)

registerSlaveCommand("dummy.wait", WaitCommand, command_version)
