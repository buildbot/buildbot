"""
Support for running 'shell commands'
"""

import os
import signal
import types
import re
import traceback
import stat
from collections import deque

from twisted.python import runtime, log
from twisted.internet import reactor, defer, protocol, task, error

from buildslave import util
from buildslave.exceptions import AbandonChain

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
            return (s[stat.ST_CTIME], s[stat.ST_MTIME], s[stat.ST_SIZE])
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


class RunProcessPP(protocol.ProcessProtocol):
    debug = False

    def __init__(self, command):
        self.command = command
        self.pending_stdin = ""
        self.stdin_finished = False
        self.killed = False

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
            log.msg("RunProcessPP.connectionMade")
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
            log.msg("RunProcessPP.outReceived")
        self.command.addStdout(data)

    def errReceived(self, data):
        if self.debug:
            log.msg("RunProcessPP.errReceived")
        self.command.addStderr(data)

    def processEnded(self, status_object):
        if self.debug:
            log.msg("RunProcessPP.processEnded", status_object)
        # status_object is a Failure wrapped around an
        # error.ProcessTerminated or and error.ProcessDone.
        # requires twisted >= 1.0.4 to overcome a bug in process.py
        sig = status_object.value.signal
        rc = status_object.value.exitCode

        # sometimes, even when we kill a process, GetExitCodeProcess will still return
        # a zero exit status.  So we force it.  See
        # http://stackoverflow.com/questions/2061735/42-passed-to-terminateprocess-sometimes-getexitcodeprocess-returns-0
        if self.killed and rc == 0:
            log.msg("process was killed, but exited with status 0; faking a failure")
            # windows returns '1' even for signalled failsres, while POSIX returns -1
            if runtime.platformType == 'win32':
                rc = 1
            else:
                rc = -1
        self.command.finished(sig, rc)

class RunProcess:
    """
    This is a helper class, used by slave commands to run programs in a child
    shell.
    """

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
        self.command = util.Obfuscated.get_real(command)

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

        self.fake_command = util.Obfuscated.get_fake(command)
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
        return "<%s '%s'>" % (self.__class__.__name__, self.fake_command)

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
            log.msg("error in RunProcess._startCommand")
            log.err()
            self._addToBuffers('stderr', "error in RunProcess._startCommand\n")
            self._addToBuffers('stderr', traceback.format_exc())
            self._sendBuffers()
            # pretend it was a shell error
            self.deferred.errback(AbandonChain(-1))
        return self.deferred

    def _startCommand(self):
        # ensure workdir exists
        if not os.path.isdir(self.workdir):
            os.makedirs(self.workdir)
        log.msg("RunProcess._startCommand")
        if self.notreally:
            self._addToBuffers('header', "command '%s' in dir %s" % \
                             (self.fake_command, self.workdir))
            self._addToBuffers('header', "(not really)\n")
            self.finished(None, 0)
            return

        self.pp = RunProcessPP(self)

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

        # self.stdin is handled in RunProcessPP.connectionMade

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
        logdata = []
        while self.buffered:
            # Grab the next bits from the buffer
            logname, data = self.buffered.popleft()

            # If this log is different than the last one, then we have to send
            # out the message so far.  This is because the message is
            # transferred as a dictionary, which makes the ordering of keys
            # unspecified, and makes it impossible to interleave data from
            # different logs.  A future enhancement could be to change the
            # master to support a list of (logname, data) tuples instead of a
            # dictionary.
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
                if len(chunk) == 0: continue
                logdata.append(chunk)
                msg_size += len(chunk)
                if msg_size >= self.CHUNK_LIMIT:
                    # We've gone beyond the chunk limit, so send out our
                    # message.  At worst this results in a message slightly
                    # larger than (2*CHUNK_LIMIT)-1
                    self._sendMessage(msg)
                    msg = {}
                    logdata = msg.setdefault(logname, [])
                    msg_size = 0
        self.buflen = 0
        if logdata:
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
        log.msg("RunProcess.failed: command failed: %s" % (why,))
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

        # let the PP know that we are killing it, so that it can ensure that
        # the exit status comes out right
        self.pp.killed = True

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
            except error.ProcessExitedAlready:
                # Twisted thinks the process has already exited
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
        self.failed(RuntimeError("SIGKILL failed to kill process"))


    def writeStdin(self, data):
        self.pp.writeStdin(data)

    def closeStdin(self):
        self.pp.closeStdin()


