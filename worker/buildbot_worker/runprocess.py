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

"""
Support for running 'shell commands'
"""

from future.utils import iteritems

import os
import re
import signal
import stat
import subprocess
import sys
import traceback

from collections import deque
from tempfile import NamedTemporaryFile

from twisted.internet import defer
from twisted.internet import error
from twisted.internet import protocol
from twisted.internet import reactor
from twisted.internet import task
from twisted.python import log
from twisted.python import runtime
from twisted.python.win32 import quoteArguments

from buildslave import util
from buildslave.exceptions import AbandonChain

if runtime.platformType == 'posix':
    from twisted.internet.process import Process


def win32_batch_quote(cmd_list):
    # Quote cmd_list to a string that is suitable for inclusion in a
    # Windows batch file. This is not quite the same as quoting it for the
    # shell, as cmd.exe doesn't support the %% escape in interactive mode.
    def escape_arg(arg):
        arg = quoteArguments([arg])
        # escape shell special characters
        arg = re.sub(r'[@()^"<>&|]', r'^\g<0>', arg)
        # prevent variable expansion
        return arg.replace('%', '%%')

    return ' '.join(map(escape_arg, cmd_list))


def shell_quote(cmd_list):
    # attempt to quote cmd_list such that a shell will properly re-interpret
    # it.  The pipes module is only available on UNIX; also, the quote
    # function is undocumented (although it looks like it will be documented
    # soon: http://bugs.python.org/issue9723). Finally, it has a nasty bug
    # in some versions where an empty string is not quoted.
    #
    # So:
    #  - use pipes.quote on UNIX, handling '' as a special case
    #  - use our own custom function on Windows
    if runtime.platformType == 'win32':
        return win32_batch_quote(cmd_list)
    else:
        import pipes

        def quote(e):
            if not e:
                return '""'
            return pipes.quote(e)
        return " ".join([quote(e) for e in cmd_list])


class LogFileWatcher(object):
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
                return  # not started yet
            if not s:
                # the file was there, but now it's deleted. Forget about the
                # initial state, clearly the process has deleted the logfile
                # in preparation for creating a new one.
                self.old_logfile_stats = None
                return  # no file to work with
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


if runtime.platformType == 'posix':
    class ProcGroupProcess(Process):

        """Simple subclass of Process to also make the spawned process a process
        group leader, so we can kill all members of the process group."""

        def _setupChild(self, *args, **kwargs):
            Process._setupChild(self, *args, **kwargs)

            # this will cause the child to be the leader of its own process group;
            # it's also spelled setpgrp() on BSD, but this spelling seems to work
            # everywhere
            os.setpgid(0, 0)


class RunProcessPP(protocol.ProcessProtocol):
    debug = False

    def __init__(self, command):
        self.command = command
        self.pending_stdin = ""
        self.stdin_finished = False
        self.killed = False

    def setStdin(self, data):
        assert not self.connected
        self.pending_stdin = data

    def connectionMade(self):
        if self.debug:
            log.msg("RunProcessPP.connectionMade")

        if self.command.useProcGroup:
            if self.debug:
                log.msg(" recording pid %d as subprocess pgid"
                        % (self.transport.pid,))
            self.transport.pgid = self.transport.pid

        if self.pending_stdin:
            if self.debug:
                log.msg(" writing to stdin")
            self.transport.write(self.pending_stdin)
        if self.debug:
            log.msg(" closing stdin")
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
            # windows returns '1' even for signalled failures, while POSIX returns -1
            if runtime.platformType == 'win32':
                rc = 1
            else:
                rc = -1
        self.command.finished(sig, rc)


class RunProcess(object):

    """
    This is a helper class, used by slave commands to run programs in a child
    shell.
    """

    notreally = False
    BACKUP_TIMEOUT = 5
    interruptSignal = "KILL"
    CHUNK_LIMIT = 128 * 1024

    # Don't send any data until at least BUFFER_SIZE bytes have been collected
    # or BUFFER_TIMEOUT elapsed
    BUFFER_SIZE = 64 * 1024
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
                 timeout=None, maxTime=None, sigtermTime=None,
                 initialStdin=None, keepStdout=False, keepStderr=False,
                 logEnviron=True, logfiles={}, usePTY="slave-config",
                 useProcGroup=True):
        """

        @param keepStdout: if True, we keep a copy of all the stdout text
                           that we've seen. This copy is available in
                           self.stdout, which can be read after the command
                           has finished.
        @param keepStderr: same, for stderr

        @param usePTY: "slave-config" -> use the SlaveBuilder's usePTY;
            otherwise, true to use a PTY, false to not use a PTY.

        @param useProcGroup: (default True) use a process group for non-PTY
            process invocations
        """

        self.builder = builder
        if isinstance(command, list):
            def obfus(w):
                if (isinstance(w, tuple) and len(w) == 3
                        and w[0] == 'obfuscated'):
                    return util.Obfuscated(w[1], w[2])
                return w
            command = [obfus(w) for w in command]
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

        def to_str(cmd):
            if isinstance(cmd, (tuple, list)):
                for i, a in enumerate(cmd):
                    if isinstance(a, unicode):
                        cmd[i] = a.encode(self.builder.unicode_encoding)
            elif isinstance(cmd, unicode):
                cmd = cmd.encode(self.builder.unicode_encoding)
            return cmd

        self.command = to_str(util.Obfuscated.get_real(command))
        self.fake_command = to_str(util.Obfuscated.get_fake(command))

        self.sendStdout = sendStdout
        self.sendStderr = sendStderr
        self.sendRC = sendRC
        self.logfiles = logfiles
        self.workdir = workdir
        self.process = None
        if not os.path.exists(workdir):
            os.makedirs(workdir)
        if environ:
            for key, v in iteritems(environ):
                if isinstance(v, list):
                    # Need to do os.pathsep translation.  We could either do that
                    # by replacing all incoming ':'s with os.pathsep, or by
                    # accepting lists.  I like lists better.
                    # If it's not a string, treat it as a sequence to be
                    # turned in to a string.
                    environ[key] = os.pathsep.join(environ[key])

            if "PYTHONPATH" in environ:
                environ['PYTHONPATH'] += os.pathsep + "${PYTHONPATH}"

            # do substitution on variable values matching pattern: ${name}
            p = re.compile(r'\${([0-9a-zA-Z_]*)}')

            def subst(match):
                return os.environ.get(match.group(1), "")
            newenv = {}
            for key in os.environ:
                # setting a key to None will delete it from the slave environment
                if key not in environ or environ[key] is not None:
                    newenv[key] = os.environ[key]
            for key, v in iteritems(environ):
                if v is not None:
                    if not isinstance(v, basestring):
                        raise RuntimeError("'env' values must be strings or "
                                           "lists; key '%s' is incorrect" % (key,))
                    newenv[key] = p.sub(subst, v)

            self.environ = newenv
        else:  # not environ
            self.environ = os.environ.copy()
        self.initialStdin = to_str(initialStdin)
        self.logEnviron = logEnviron
        self.timeout = timeout
        self.ioTimeoutTimer = None
        self.sigtermTime = sigtermTime
        self.maxTime = maxTime
        self.maxTimeoutTimer = None
        self.killTimer = None
        self.keepStdout = keepStdout
        self.keepStderr = keepStderr

        self.buffered = deque()
        self.buflen = 0
        self.sendBuffersTimer = None

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

        # use an explicit process group on POSIX, noting that usePTY always implies
        # a process group.
        if runtime.platformType != 'posix':
            useProcGroup = False
        elif self.usePTY:
            useProcGroup = True
        self.useProcGroup = useProcGroup

        self.logFileWatchers = []
        for name, filevalue in self.logfiles.items():
            filename = filevalue
            follow = False

            # check for a dictionary of options
            # filename is required, others are optional
            if isinstance(filevalue, dict):
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
        except Exception:
            log.err("error in RunProcess._startCommand")
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
            self._addToBuffers('header', "command '%s' in dir %s" %
                               (self.fake_command, self.workdir))
            self._addToBuffers('header', "(not really)\n")
            self.finished(None, 0)
            return

        self.pp = RunProcessPP(self)

        self.using_comspec = False
        if isinstance(self.command, basestring):
            if runtime.platformType == 'win32':
                argv = os.environ['COMSPEC'].split()  # allow %COMSPEC% to have args
                if '/c' not in argv:
                    argv += ['/c']
                argv += [self.command]
                self.using_comspec = True
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
                argv = os.environ['COMSPEC'].split()  # allow %COMSPEC% to have args
                if '/c' not in argv:
                    argv += ['/c']
                argv += list(self.command)
                self.using_comspec = True
            else:
                argv = self.command
            # Attempt to format this for use by a shell, although the process isn't perfect
            display = shell_quote(self.fake_command)

        # $PWD usually indicates the current directory; spawnProcess may not
        # update this value, though, so we set it explicitly here.  This causes
        # weird problems (bug #456) on msys, though..
        if not self.environ.get('MACHTYPE', None) == 'i686-pc-msys':
            self.environ['PWD'] = os.path.abspath(self.workdir)

        # self.stdin is handled in RunProcessPP.connectionMade

        log.msg(" " + display)
        self._addToBuffers('header', display + "\n")

        # then comes the secondary information
        msg = " in dir %s" % (self.workdir,)
        if self.timeout:
            if self.timeout == 1:
                unit = "sec"
            else:
                unit = "secs"
            msg += " (timeout %d %s)" % (self.timeout, unit)
        if self.maxTime:
            if self.maxTime == 1:
                unit = "sec"
            else:
                unit = "secs"
            msg += " (maxTime %d %s)" % (self.maxTime, unit)
        log.msg(" " + msg)
        self._addToBuffers('header', msg + "\n")

        msg = " watching logfiles %s" % (self.logfiles,)
        log.msg(" " + msg)
        self._addToBuffers('header', msg + "\n")

        # then the obfuscated command array for resolving unambiguity
        msg = " argv: %s" % (self.fake_command,)
        log.msg(" " + msg)
        self._addToBuffers('header', msg + "\n")

        # then the environment, since it sometimes causes problems
        if self.logEnviron:
            msg = " environment:\n"
            env_names = sorted(self.environ.keys())
            for name in env_names:
                msg += "  %s=%s\n" % (name, self.environ[name])
            log.msg(" environment: %s" % (self.environ,))
            self._addToBuffers('header', msg)

        if self.initialStdin:
            msg = " writing %d bytes to stdin" % len(self.initialStdin)
            log.msg(" " + msg)
            self._addToBuffers('header', msg + "\n")

        msg = " using PTY: %s" % bool(self.usePTY)
        log.msg(" " + msg)
        self._addToBuffers('header', msg + "\n")

        # put data into stdin and close it, if necessary.  This will be
        # buffered until connectionMade is called
        if self.initialStdin:
            self.pp.setStdin(self.initialStdin)

        self.startTime = util.now(self._reactor)

        # start the process

        self.process = self._spawnProcess(
            self.pp, argv[0], argv,
            self.environ,
            self.workdir,
            usePTY=self.usePTY)

        # set up timeouts

        if self.timeout:
            self.ioTimeoutTimer = self._reactor.callLater(self.timeout, self.doTimeout)

        if self.maxTime:
            self.maxTimeoutTimer = self._reactor.callLater(self.maxTime, self.doMaxTimeout)

        for w in self.logFileWatchers:
            w.start()

    def _spawnProcess(self, processProtocol, executable, args=(), env={},
                      path=None, uid=None, gid=None, usePTY=False, childFDs=None):
        """private implementation of reactor.spawnProcess, to allow use of
        L{ProcGroupProcess}"""

        # use the ProcGroupProcess class, if available
        if runtime.platformType == 'posix':
            if self.useProcGroup and not usePTY:
                return ProcGroupProcess(reactor, executable, args, env, path,
                                        processProtocol, uid, gid, childFDs)

        # fall back
        if self.using_comspec:
            return self._spawnAsBatch(processProtocol, executable, args, env,
                                      path, usePTY=usePTY)
        else:
            return reactor.spawnProcess(processProtocol, executable, args, env,
                                        path, usePTY=usePTY)

    def _spawnAsBatch(self, processProtocol, executable, args, env,
                      path, usePTY):
        """A cheat that routes around the impedance mismatch between
        twisted and cmd.exe with respect to escaping quotes"""

        tf = NamedTemporaryFile(dir='.', suffix=".bat", delete=False)
        # echo off hides this cheat from the log files.
        tf.write("@echo off\n")
        if isinstance(self.command, basestring):
            tf.write(self.command)
        else:
            tf.write(win32_batch_quote(self.command))
        tf.close()

        argv = os.environ['COMSPEC'].split()  # allow %COMSPEC% to have args
        if '/c' not in argv:
            argv += ['/c']
        argv += [tf.name]

        def unlink_temp(result):
            os.unlink(tf.name)
            return result
        self.deferred.addBoth(unlink_temp)

        return reactor.spawnProcess(processProtocol, executable, argv, env,
                                    path, usePTY=usePTY)

    def _chunkForSend(self, data):
        """
        limit the chunks that we send over PB to 128k, since it has a hardwired
        string-size limit of 640k.
        """
        LIMIT = self.CHUNK_LIMIT
        for i in range(0, len(data), LIMIT):
            yield data[i:i + LIMIT]

    def _collapseMsg(self, msg):
        """
        Take msg, which is a dictionary of lists of output chunks, and
        concatenate all the chunks into a single string
        """
        retval = {}
        for logname in msg:
            data = "".join(msg[logname])
            if isinstance(logname, tuple) and logname[0] == 'log':
                retval['log'] = (logname[1], data)
            else:
                retval[logname] = data
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
        self.sendBuffersTimer = None
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
                if len(chunk) == 0:
                    continue
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
        if self.sendBuffersTimer:
            if self.sendBuffersTimer.active():
                self.sendBuffersTimer.cancel()
            self.sendBuffersTimer = None

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
        elif not self.sendBuffersTimer:
            self.sendBuffersTimer = self._reactor.callLater(self.BUFFER_TIMEOUT, self._bufferTimeout)

    def addStdout(self, data):
        if self.sendStdout:
            self._addToBuffers('stdout', data)

        if self.keepStdout:
            self.stdout += data
        if self.ioTimeoutTimer:
            self.ioTimeoutTimer.reset(self.timeout)

    def addStderr(self, data):
        if self.sendStderr:
            self._addToBuffers('stderr', data)

        if self.keepStderr:
            self.stderr += data
        if self.ioTimeoutTimer:
            self.ioTimeoutTimer.reset(self.timeout)

    def addLogfile(self, name, data):
        self._addToBuffers(('log', name), data)

        if self.ioTimeoutTimer:
            self.ioTimeoutTimer.reset(self.timeout)

    def finished(self, sig, rc):
        self.elapsedTime = util.now(self._reactor) - self.startTime
        log.msg("command finished with signal %s, exit code %s, elapsedTime: %0.6f" % (sig, rc, self.elapsedTime))
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
        self._cancelTimers()
        d = self.deferred
        self.deferred = None
        if d:
            d.callback(rc)
        else:
            log.msg("Hey, command %s finished twice" % self)

    def failed(self, why):
        self._sendBuffers()
        log.msg("RunProcess.failed: command failed: %s" % (why,))
        self._cancelTimers()
        d = self.deferred
        self.deferred = None
        if d:
            d.errback(why)
        else:
            log.msg("Hey, command %s finished twice" % self)

    def doTimeout(self):
        self.ioTimeoutTimer = None
        msg = "command timed out: %d seconds without output running %s" % (self.timeout, self.fake_command)
        self.kill(msg)

    def doMaxTimeout(self):
        self.maxTimeoutTimer = None
        msg = "command timed out: %d seconds elapsed running %s" % (self.maxTime, self.fake_command)
        self.kill(msg)

    def isDead(self):
        if self.process.pid is None:
            return True
        pid = int(self.process.pid)
        try:
            os.kill(pid, 0)
        except OSError:
            return True  # dead
        return False  # alive

    def checkProcess(self):
        self.sigtermTimer = None
        if not self.isDead():
            hit = self.sendSig(self.interruptSignal)
        else:
            hit = 1
        self.cleanUp(hit)

    def cleanUp(self, hit):
        if not hit:
            log.msg("signalProcess/os.kill failed both times")

        if runtime.platformType == "posix":
            # we only do this under posix because the win32eventreactor
            # blocks here until the process has terminated, while closing
            # stderr. This is weird.
            self.pp.transport.loseConnection()

        if self.deferred:
            # finished ought to be called momentarily. Just in case it doesn't,
            # set a timer which will abandon the command.
            self.killTimer = self._reactor.callLater(self.BACKUP_TIMEOUT,
                                                     self.doBackupTimeout)

    def sendSig(self, interruptSignal):
        hit = 0
        # try signalling the process group
        if not hit and self.useProcGroup and runtime.platformType == "posix":
            sig = getattr(signal, "SIG" + interruptSignal, None)

            if sig is None:
                log.msg("signal module is missing SIG%s" % interruptSignal)
            elif not hasattr(os, "kill"):
                log.msg("os module is missing the 'kill' function")
            elif self.process.pgid is None:
                log.msg("self.process has no pgid")
            else:
                log.msg("trying to kill process group %d" %
                        (self.process.pgid,))
                try:
                    os.kill(-self.process.pgid, sig)
                    log.msg(" signal %s sent successfully" % sig)
                    self.process.pgid = None
                    hit = 1
                except OSError:
                    log.msg('failed to kill process group (ignored): %s' %
                            (sys.exc_info()[1],))
                    # probably no-such-process, maybe because there is no process
                    # group
                    pass

        elif runtime.platformType == "win32":
            if interruptSignal is None:
                log.msg("interruptSignal==None, only pretending to kill child")
            elif self.process.pid is not None:
                if interruptSignal == "TERM":
                    log.msg("using TASKKILL PID /T to kill pid %s" % self.process.pid)
                    subprocess.check_call("TASKKILL /PID %s /T" % self.process.pid)
                    log.msg("taskkill'd pid %s" % self.process.pid)
                    hit = 1
                elif interruptSignal == "KILL":
                    log.msg("using TASKKILL PID /F /T to kill pid %s" % self.process.pid)
                    subprocess.check_call("TASKKILL /F /PID %s /T" % self.process.pid)
                    log.msg("taskkill'd pid %s" % self.process.pid)
                    hit = 1

        # try signalling the process itself (works on Windows too, sorta)
        if not hit:
            try:
                log.msg("trying process.signalProcess('%s')" % (interruptSignal,))
                self.process.signalProcess(interruptSignal)
                log.msg(" signal %s sent successfully" % (interruptSignal,))
                hit = 1
            except OSError:
                log.err("from process.signalProcess:")
                # could be no-such-process, because they finished very recently
                pass
            except error.ProcessExitedAlready:
                log.msg("Process exited already - can't kill")
                # the process has already exited, and likely finished() has
                # been called already or will be called shortly
                pass

        return hit

    def kill(self, msg):
        # This may be called by the timeout, or when the user has decided to
        # abort this build.
        self._sendBuffers()
        self._cancelTimers()
        msg += ", attempting to kill"
        log.msg(msg)
        self.sendStatus({'header': "\n" + msg + "\n"})

        # let the PP know that we are killing it, so that it can ensure that
        # the exit status comes out right
        self.pp.killed = True

        sendSigterm = self.sigtermTime is not None
        if sendSigterm:
            self.sendSig("TERM")
            self.sigtermTimer = self._reactor.callLater(self.sigtermTime, self.checkProcess)
        else:
            hit = self.sendSig(self.interruptSignal)
            self.cleanUp(hit)

    def doBackupTimeout(self):
        log.msg("we tried to kill the process, and it wouldn't die.."
                " finish anyway")
        self.killTimer = None
        signalName = "SIG" + self.interruptSignal
        self.sendStatus({'header': signalName + " failed to kill process\n"})
        if self.sendRC:
            self.sendStatus({'header': "using fake rc=-1\n"})
            self.sendStatus({'rc': -1})
        self.failed(RuntimeError(signalName + " failed to kill process"))

    def _cancelTimers(self):
        for timerName in ('ioTimeoutTimer', 'killTimer', 'maxTimeoutTimer', 'sendBuffersTimer', 'sigtermTimer'):
            timer = getattr(self, timerName, None)
            if timer:
                timer.cancel()
                setattr(self, timerName, None)
