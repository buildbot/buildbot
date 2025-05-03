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

from __future__ import annotations

import os
import pprint
import re
import shlex
import signal
import stat
import subprocess
import sys
import traceback
from codecs import getincrementaldecoder
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING

from twisted.internet import defer
from twisted.internet import error
from twisted.internet import protocol
from twisted.internet import reactor
from twisted.internet import task
from twisted.python import log
from twisted.python import runtime
from twisted.python.win32 import quoteArguments

from buildbot_worker import util
from buildbot_worker.compat import bytes2NativeString
from buildbot_worker.compat import bytes2unicode
from buildbot_worker.compat import unicode2bytes
from buildbot_worker.exceptions import AbandonChain

if TYPE_CHECKING:
    import datetime

if runtime.platformType == 'posix':
    from twisted.internet.process import Process
if runtime.platformType == 'win32':
    import win32api
    import win32con
    import win32job
    import win32process


def win32_batch_quote(cmd_list, unicode_encoding='utf-8'):
    # Quote cmd_list to a string that is suitable for inclusion in a
    # Windows batch file. This is not quite the same as quoting it for the
    # shell, as cmd.exe doesn't support the %% escape in interactive mode.
    def escape_arg(arg):
        arg = bytes2NativeString(arg, unicode_encoding)
        arg = quoteArguments([arg])
        # escape shell special characters
        arg = re.sub(r'[@()^"<>&|]', r'^\g<0>', arg)
        # prevent variable expansion
        return arg.replace('%', '%%')

    return ' '.join(map(escape_arg, cmd_list))


def shell_quote(cmd_list, unicode_encoding='utf-8'):
    # attempt to quote cmd_list such that a shell will properly re-interpret
    # it.  The shlex module is only designed for UNIX;
    #
    # So:
    #  - use shlex.quote on UNIX, handling '' as a special case
    #  - use our own custom function on Windows
    if isinstance(cmd_list, bytes):
        cmd_list = bytes2unicode(cmd_list, unicode_encoding)

    if runtime.platformType == 'win32':
        return win32_batch_quote(cmd_list, unicode_encoding)

    def quote(e):
        if not e:
            return '""'
        e = bytes2unicode(e, unicode_encoding)
        return shlex.quote(e)

    return " ".join(quote(e) for e in cmd_list)


class LogFileWatcher:
    POLL_INTERVAL = 2

    def __init__(self, command, name, logfile, follow=False, poll=True):
        self.command = command
        self.name = name
        self.logfile = logfile
        decoderFactory = getincrementaldecoder(self.command.unicode_encoding)
        self.logDecode = decoderFactory(errors='replace')

        self.command.log_msg(f"LogFileWatcher created to watch {logfile}")
        # we are created before the ShellCommand starts. If the logfile we're
        # supposed to be watching already exists, record its size and
        # ctime/mtime so we can tell when it starts to change.
        self.old_logfile_stats = self.statFile()
        self.started = False

        # follow the file, only sending back lines
        # added since we started watching
        self.follow = follow

        # every 2 seconds we check on the file again
        self.poller = task.LoopingCall(self.poll) if poll else None

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

        # Mac OS X and Linux differ in behaviour when reading from a file that has previously
        # reached EOF. On Linux, any new data that has been appended to the file will be returned.
        # On Mac OS X, the empty string will always be returned. Seeking to the current position
        # in the file resets the EOF flag on Mac OS X and will allow future reads to work as
        # intended.
        self.f.seek(self.f.tell(), 0)

        while True:
            data = self.f.read(10000)
            if not data:
                return
            decodedData = self.logDecode.decode(data)
            self.command.addLogfile(self.name, decodedData)


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
        self.pending_stdin = b""
        self.stdin_finished = False
        self.killed = False
        decoderFactory = getincrementaldecoder(self.command.unicode_encoding)
        self.stdoutDecode = decoderFactory(errors='replace')
        self.stderrDecode = decoderFactory(errors='replace')

    def setStdin(self, data):
        assert not self.connected
        self.pending_stdin = data

    def connectionMade(self):
        if self.debug:
            self.command.log_msg("RunProcessPP.connectionMade")

        if self.command.useProcGroup:
            if self.debug:
                self.command.log_msg(f"pid {self.transport.pid} set as subprocess pgid")
            self.transport.pgid = self.transport.pid

        if self.pending_stdin:
            if self.debug:
                self.command.log_msg("writing to stdin")
            self.transport.write(self.pending_stdin)
        if self.debug:
            self.command.log_msg("closing stdin")
        self.transport.closeStdin()

    def outReceived(self, data):
        if self.debug:
            self.command.log_msg("RunProcessPP.outReceived")
        decodedData = self.stdoutDecode.decode(data)
        self.command.addStdout(decodedData)

    def errReceived(self, data):
        if self.debug:
            self.command.log_msg("RunProcessPP.errReceived")
        decodedData = self.stderrDecode.decode(data)
        self.command.addStderr(decodedData)

    def processEnded(self, status_object):
        if self.debug:
            self.command.log_msg(f"RunProcessPP.processEnded {status_object}")
        # status_object is a Failure wrapped around an
        # error.ProcessTerminated or and error.ProcessDone.
        # requires twisted >= 1.0.4 to overcome a bug in process.py
        sig = status_object.value.signal
        rc = status_object.value.exitCode

        # sometimes, even when we kill a process, GetExitCodeProcess will still return
        # a zero exit status.  So we force it.  See
        # http://stackoverflow.com/questions/2061735/42-passed-to-terminateprocess-sometimes-getexitcodeprocess-returns-0
        if self.killed and rc == 0:
            self.command.log_msg("process was killed, but exited with status 0; faking a failure")
            # windows returns '1' even for signalled failures, while POSIX
            # returns -1
            if runtime.platformType == 'win32':
                rc = 1
            else:
                rc = -1
        self.command.finished(sig, rc)


class RunProcess:
    """
    This is a helper class, used by worker commands to run programs in a child
    shell.
    """

    BACKUP_TIMEOUT = 5
    interruptSignal = "KILL"

    # For sending elapsed time:
    startTime: datetime.datetime | None = None
    elapsedTime: datetime.timedelta | None = None

    # For scheduling future events
    _reactor = reactor

    # I wish we had easy access to CLOCK_MONOTONIC in Python:
    # http://www.opengroup.org/onlinepubs/000095399/functions/clock_getres.html
    # Then changes to the system clock during a run wouldn't effect the "elapsed
    # time" results.

    def __init__(
        self,
        command_id,
        command,
        workdir,
        unicode_encoding,
        send_update,
        environ=None,
        sendStdout=True,
        sendStderr=True,
        sendRC=True,
        timeout=None,
        maxTime=None,
        max_lines=None,
        sigtermTime=None,
        initialStdin=None,
        keepStdout=False,
        keepStderr=False,
        logEnviron=True,
        logfiles=None,
        usePTY=False,
        useProcGroup=True,
    ):
        """

        @param keepStdout: if True, we keep a copy of all the stdout text
                           that we've seen. This copy is available in
                           self.stdout, which can be read after the command
                           has finished.
        @param keepStderr: same, for stderr

        @param usePTY: true to use a PTY, false to not use a PTY.

        @param useProcGroup: (default True) use a process group for non-PTY
            process invocations
        """
        if logfiles is None:
            logfiles = {}

        if isinstance(command, list):

            def obfus(w):
                if isinstance(w, tuple) and len(w) == 3 and w[0] == 'obfuscated':
                    return util.Obfuscated(w[1], w[2])
                return w

            command = [obfus(w) for w in command]

        self.command_id = command

        # We need to take unicode commands and arguments and encode them using
        # the appropriate encoding for the worker.  This is mostly platform
        # specific, but can be overridden in the worker's buildbot.tac file.
        #
        # Encoding the command line here ensures that the called executables
        # receive arguments as bytestrings encoded with an appropriate
        # platform-specific encoding.  It also plays nicely with twisted's
        # spawnProcess which checks that arguments are regular strings or
        # unicode strings that can be encoded as ascii (which generates a
        # warning).

        def to_bytes(cmd):
            if isinstance(cmd, (tuple, list)):
                for i, a in enumerate(cmd):
                    if isinstance(a, str):
                        cmd[i] = a.encode(unicode_encoding)
            elif isinstance(cmd, str):
                cmd = cmd.encode(unicode_encoding)
            return cmd

        self.command = to_bytes(util.Obfuscated.get_real(command))
        self.fake_command = to_bytes(util.Obfuscated.get_fake(command))

        self.sendStdout = sendStdout
        self.sendStderr = sendStderr
        self.sendRC = sendRC
        self.logfiles = logfiles
        self.workdir = workdir
        self.unicode_encoding = unicode_encoding
        self.send_update = send_update
        self.process = None
        self.line_count = 0
        self.max_line_kill = False
        if not os.path.exists(workdir):
            os.makedirs(workdir)
        if environ:
            for key, v in environ.items():
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
                # setting a key to None will delete it from the worker
                # environment
                if key not in environ or environ[key] is not None:
                    newenv[key] = os.environ[key]
            for key, v in environ.items():
                if v is not None:
                    if not isinstance(v, str):
                        raise RuntimeError(
                            f"'env' values must be strings or lists; key '{key}' is incorrect"
                        )
                    newenv[key] = p.sub(subst, v)

            self.environ = newenv
        else:  # not environ
            self.environ = os.environ.copy()
        self.initialStdin = to_bytes(initialStdin)
        self.logEnviron = logEnviron
        self.timeout = timeout
        self.ioTimeoutTimer = None
        self.sigtermTime = sigtermTime
        self.maxTime = maxTime
        self.max_lines = max_lines
        self.maxTimeoutTimer = None
        self.killTimer = None
        self.keepStdout = keepStdout
        self.keepStderr = keepStderr
        self.job_object = None

        assert usePTY in (
            True,
            False,
        ), f"Unexpected usePTY argument value: {usePTY!r}. Expected boolean."
        self.usePTY = usePTY

        # usePTY=True is a convenience for cleaning up all children and
        # grandchildren of a hung command. Fall back to usePTY=False on systems
        # and in situations where ptys cause problems.  PTYs are posix-only,
        # and for .closeStdin to matter, we must use a pipe, not a PTY
        if runtime.platformType != "posix" or initialStdin is not None:
            if self.usePTY:
                self.send_update([('header', "WARNING: disabling usePTY for this command")])
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

            w = LogFileWatcher(self, name, os.path.join(self.workdir, filename), follow=follow)
            self.logFileWatchers.append(w)

    def log_msg(self, msg):
        log.msg(f"(command {self.command_id}): {msg}")

    def __repr__(self):
        return f"<{self.__class__.__name__} '{self.fake_command}'>"

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
        except Exception as e:
            log.err(e, "error in RunProcess._startCommand")
            self.send_update([('stderr', f"error in RunProcess._startCommand ({e!s})\n")])

            self.send_update([('stderr', traceback.format_exc())])
            # pretend it was a shell error
            self.deferred.errback(AbandonChain(-1, f'Got exception ({e!s})'))
        return self.deferred

    def _startCommand(self):
        # ensure workdir exists
        if not os.path.isdir(self.workdir):
            os.makedirs(self.workdir)
        self.log_msg("RunProcess._startCommand")

        self.pp = RunProcessPP(self)

        self.using_comspec = False
        self.command = unicode2bytes(self.command, encoding=self.unicode_encoding)
        if isinstance(self.command, bytes):
            if runtime.platformType == 'win32':
                # allow %COMSPEC% to have args
                argv = os.environ['COMSPEC'].split()
                if '/c' not in argv:
                    argv += ['/c']
                argv += [self.command]
                self.using_comspec = True
            else:
                # for posix, use /bin/sh. for other non-posix, well, doesn't
                # hurt to try
                argv = [b'/bin/sh', b'-c', self.command]
            display = self.fake_command
        else:
            # On windows, CreateProcess requires an absolute path to the executable.
            # When we call spawnProcess below, we pass argv[0] as the executable.
            # So, for .exe's that we have absolute paths to, we can call directly
            # Otherwise, we should run under COMSPEC (usually cmd.exe) to
            # handle path searching, etc.
            if runtime.platformType == 'win32' and not (
                bytes2unicode(self.command[0], self.unicode_encoding).lower().endswith(".exe")
                and os.path.isabs(self.command[0])
            ):
                # allow %COMSPEC% to have args
                argv = os.environ['COMSPEC'].split()
                if '/c' not in argv:
                    argv += ['/c']
                argv += list(self.command)
                self.using_comspec = True
            else:
                argv = self.command
            # Attempt to format this for use by a shell, although the process
            # isn't perfect
            display = shell_quote(self.fake_command, self.unicode_encoding)

        display = bytes2unicode(display, self.unicode_encoding)

        # $PWD usually indicates the current directory; spawnProcess may not
        # update this value, though, so we set it explicitly here.  This causes
        # weird problems (bug #456) on msys, though..
        if not self.environ.get('MACHTYPE', None) == 'i686-pc-msys':
            self.environ['PWD'] = os.path.abspath(self.workdir)

        # self.stdin is handled in RunProcessPP.connectionMade

        self.log_msg(" " + display)
        self.send_update([('header', display + "\n")])

        # then comes the secondary information
        msg = f" in dir {self.workdir}"
        if self.timeout:
            if self.timeout == 1:
                unit = "sec"
            else:
                unit = "secs"
            msg += f" (timeout {self.timeout} {unit})"
        if self.maxTime:
            if self.maxTime == 1:
                unit = "sec"
            else:
                unit = "secs"
            msg += f" (maxTime {self.maxTime} {unit})"
        self.log_msg(" " + msg)
        self.send_update([('header', msg + "\n")])

        msg = f" watching logfiles {self.logfiles}"
        self.log_msg(" " + msg)
        self.send_update([('header', msg + "\n")])

        # then the obfuscated command array for resolving unambiguity
        msg = f" argv: {self.fake_command}"
        self.log_msg(" " + msg)
        self.send_update([('header', msg + "\n")])

        # then the environment, since it sometimes causes problems
        if self.logEnviron:
            msg = " environment:\n"
            env_names = sorted(self.environ.keys())
            for name in env_names:
                msg += f"  {bytes2unicode(name, encoding=self.unicode_encoding)}={bytes2unicode(self.environ[name], encoding=self.unicode_encoding)}\n"
            self.log_msg(f" environment:\n{pprint.pformat(self.environ)}")
            self.send_update([('header', msg)])

        if self.initialStdin:
            msg = f" writing {len(self.initialStdin)} bytes to stdin"
            self.log_msg(" " + msg)
            self.send_update([('header', msg + "\n")])

        msg = f" using PTY: {bool(self.usePTY)}"
        self.log_msg(" " + msg)
        self.send_update([('header', msg + "\n")])

        # put data into stdin and close it, if necessary.  This will be
        # buffered until connectionMade is called
        if self.initialStdin:
            self.pp.setStdin(self.initialStdin)

        self.startTime = util.now(self._reactor)

        # start the process

        self.process = self._spawnProcess(
            self.pp, argv[0], argv, self.environ, self.workdir, usePTY=self.usePTY
        )

        # set up timeouts

        if self.timeout:
            self.ioTimeoutTimer = self._reactor.callLater(self.timeout, self.doTimeout)

        if self.maxTime:
            self.maxTimeoutTimer = self._reactor.callLater(self.maxTime, self.doMaxTimeout)

        for w in self.logFileWatchers:
            w.start()

    def _create_job_object(self):
        job = win32job.CreateJobObject(None, "")
        extented_info = win32job.QueryInformationJobObject(
            job, win32job.JobObjectExtendedLimitInformation
        )
        extented_info['BasicLimitInformation']['LimitFlags'] = (
            win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            | win32job.JOB_OBJECT_TERMINATE_AT_END_OF_JOB
        )
        win32job.SetInformationJobObject(
            job, win32job.JobObjectExtendedLimitInformation, extented_info
        )
        return job

    def _spawnProcess(
        self,
        processProtocol,
        executable,
        args=(),
        env=None,
        path=None,
        uid=None,
        gid=None,
        usePTY=False,
        childFDs=None,
    ):
        """private implementation of reactor.spawnProcess, to allow use of
        L{ProcGroupProcess}"""
        if env is None:
            env = {}

        if runtime.platformType == 'win32':
            if self.using_comspec:
                process = self._spawnAsBatch(
                    processProtocol, executable, args, env, path, usePTY=usePTY
                )
            else:
                process = reactor.spawnProcess(
                    processProtocol, executable, args, env, path, usePTY=usePTY
                )
            pHandle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, False, int(process.pid))
            if win32process.GetExitCodeProcess(pHandle) == win32con.STILL_ACTIVE:
                # use JobObject to group subprocesses
                self.job_object = self._create_job_object()
                win32job.AssignProcessToJobObject(self.job_object, pHandle)
            return process

        # use the ProcGroupProcess class, if available
        elif runtime.platformType == 'posix':
            if self.useProcGroup and not usePTY:
                return ProcGroupProcess(
                    reactor, executable, args, env, path, processProtocol, uid, gid, childFDs
                )

        # fall back
        return reactor.spawnProcess(processProtocol, executable, args, env, path, usePTY=usePTY)

    def _spawnAsBatch(self, processProtocol, executable, args, env, path, usePTY):
        """A cheat that routes around the impedance mismatch between
        twisted and cmd.exe with respect to escaping quotes"""

        tf = NamedTemporaryFile(
            mode='w+', dir='.', suffix=".bat", delete=False, encoding=self.unicode_encoding
        )

        # echo off hides this cheat from the log files.
        tf.write("@echo off\n")
        if isinstance(self.command, (str, bytes)):
            tf.write(bytes2NativeString(self.command, self.unicode_encoding))
        else:
            tf.write(win32_batch_quote(self.command, self.unicode_encoding))
        tf.close()

        argv = os.environ['COMSPEC'].split()  # allow %COMSPEC% to have args
        if '/c' not in argv:
            argv += ['/c']
        argv += [tf.name]

        def unlink_temp(result):
            os.unlink(tf.name)
            return result

        self.deferred.addBoth(unlink_temp)

        return reactor.spawnProcess(processProtocol, executable, argv, env, path, usePTY=usePTY)

    def addStdout(self, data):
        if self.sendStdout:
            self._check_max_lines(data)
            self.send_update([('stdout', data)])

        if self.keepStdout:
            self.stdout += data
        if self.ioTimeoutTimer:
            self.ioTimeoutTimer.reset(self.timeout)

    def addStderr(self, data):
        if self.sendStderr:
            self._check_max_lines(data)
            self.send_update([('stderr', data)])

        if self.keepStderr:
            self.stderr += data
        if self.ioTimeoutTimer:
            self.ioTimeoutTimer.reset(self.timeout)

    def addLogfile(self, name, data):
        self.send_update([('log', (name, data))])

        if self.ioTimeoutTimer:
            self.ioTimeoutTimer.reset(self.timeout)

    def finished(self, sig, rc):
        self.elapsedTime = util.now(self._reactor) - self.startTime
        self.log_msg(
            ("command finished with signal {0}, exit code {1}, " + "elapsedTime: {2:0.6f}").format(
                sig, rc, self.elapsedTime
            )
        )
        for w in self.logFileWatchers:
            # this will send the final updates
            w.stop()
        if sig is not None:
            rc = -1
        if self.sendRC:
            if sig is not None:
                self.send_update([('header', f"process killed by signal {sig}\n")])
            self.send_update([('rc', rc)])
        self.send_update([('header', f"elapsedTime={self.elapsedTime:0.6f}\n")])
        self._cancelTimers()
        d = self.deferred
        self.deferred = None
        if d:
            d.callback(rc)
        else:
            self.log_msg(f"Hey, command {self} finished twice")

    def failed(self, why):
        self.log_msg(f"RunProcess.failed: command failed: {why}")
        self._cancelTimers()
        d = self.deferred
        self.deferred = None
        if d:
            d.errback(why)
        else:
            self.log_msg(f"Hey, command {self} finished twice")

    def doTimeout(self):
        self.ioTimeoutTimer = None
        msg = (
            f"command timed out: {self.timeout} seconds without output running {self.fake_command}"
        )
        self.send_update([("failure_reason", "timeout_without_output")])
        self.kill(msg)

    def doMaxTimeout(self):
        self.maxTimeoutTimer = None
        msg = f"command timed out: {self.maxTime} seconds elapsed running {self.fake_command}"
        self.send_update([("failure_reason", "timeout")])
        self.kill(msg)

    def _check_max_lines(self, data):
        if self.max_lines is not None:
            self.line_count += len(re.findall(r"\r\n|\r|\n", data))
            if self.line_count > self.max_lines and not self.max_line_kill:
                self.pp.transport.closeStdout()
                self.max_line_kill = True
                self.do_max_lines()

    def do_max_lines(self):
        msg = (
            f"command exceeds max lines: {self.line_count}/{self.max_lines} "
            f"written/allowed running {self.fake_command}"
        )
        self.send_update([("failure_reason", "max_lines_failure")])
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
            self.log_msg("signalProcess/os.kill failed both times")

        if runtime.platformType == "posix":
            # we only do this under posix because the win32eventreactor
            # blocks here until the process has terminated, while closing
            # stderr. This is weird.
            self.pp.transport.loseConnection()
        elif runtime.platformType == 'win32':
            if self.job_object is not None:
                win32job.TerminateJobObject(self.job_object, 0)
                self.job_object.Close()

        if self.deferred:
            # finished ought to be called momentarily. Just in case it doesn't,
            # set a timer which will abandon the command.
            self.killTimer = self._reactor.callLater(self.BACKUP_TIMEOUT, self.doBackupTimeout)

    def sendSig(self, interruptSignal):
        hit = 0
        # try signalling the process group
        if not hit and self.useProcGroup and runtime.platformType == "posix":
            sig = getattr(signal, "SIG" + interruptSignal, None)

            if sig is None:
                self.log_msg(f"signal module is missing SIG{interruptSignal}")
            elif not hasattr(os, "kill"):
                self.log_msg("os module is missing the 'kill' function")
            elif self.process.pgid is None:
                self.log_msg("self.process has no pgid")
            else:
                self.log_msg(f"trying to kill process group {self.process.pgid}")
                try:
                    os.killpg(self.process.pgid, sig)
                    self.log_msg(f" signal {sig} sent successfully")
                    self.process.pgid = None
                    hit = 1
                except OSError:
                    self.log_msg(f'failed to kill process group (ignored): {sys.exc_info()[1]}')
                    # probably no-such-process, maybe because there is no process
                    # group

        elif runtime.platformType == "win32":
            if interruptSignal is None:
                self.log_msg("interruptSignal==None, only pretending to kill child")
            elif self.process.pid is not None or self.job_object is not None:
                if interruptSignal == "TERM":
                    self._win32_taskkill(self.process.pid, force=False)
                    hit = 1
                elif interruptSignal == "KILL":
                    self._win32_taskkill(self.process.pid, force=True)
                    hit = 1

        # try signalling the process itself (works on Windows too, sorta)
        if not hit:
            try:
                self.log_msg(f"trying process.signalProcess('{interruptSignal}')")
                self.process.signalProcess(interruptSignal)
                self.log_msg(f" signal {interruptSignal} sent successfully")
                hit = 1
            except OSError:
                log.err("from process.signalProcess:")
                # could be no-such-process, because they finished very recently
            except error.ProcessExitedAlready:
                self.log_msg("Process exited already - can't kill")
                # the process has already exited, and likely finished() has
                # been called already or will be called shortly

        return hit

    def _win32_taskkill(self, pid, force):
        try:
            if force:
                cmd = f"TASKKILL /F /PID {pid} /T"
            else:
                cmd = f"TASKKILL /PID {pid} /T"
            if self.job_object is not None:
                pr_info = win32job.QueryInformationJobObject(
                    self.job_object, win32job.JobObjectBasicProcessIdList
                )
                if force or len(pr_info) < 2:
                    win32job.TerminateJobObject(self.job_object, 1)
            self.log_msg(f"terminating job object with pids {pr_info!s}")
            if pid is None:
                return
            self.log_msg(f"using {cmd} to kill pid {pid}")
            subprocess.check_call(cmd)
            self.log_msg(f"taskkill'd pid {pid}")
        except win32job.error:
            self.log_msg("failed to terminate job object")
        except subprocess.CalledProcessError as e:
            # taskkill may return 128 or 255 as exit code when the child has already exited.
            # We can't handle this race condition in any other way than just interpreting the kill
            # action as successful
            if e.returncode in (128, 255):
                self.log_msg(f"taskkill didn't find pid {pid} to kill")
            else:
                self.log_msg(f"taskkill failed to kill process {pid}: {e}")

    def kill(self, msg):
        # This may be called by the timeout, or when the user has decided to
        # abort this build.
        self._cancelTimers()
        msg += ", attempting to kill"
        self.log_msg(msg)
        self.send_update([('header', "\n" + msg + "\n")])

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
        self.log_msg("we tried to kill the process, and it wouldn't die.. finish anyway")
        self.killTimer = None
        signalName = "SIG" + self.interruptSignal
        self.send_update([('header', signalName + " failed to kill process\n")])
        if self.sendRC:
            self.send_update([('header', "using fake rc=-1\n"), ('rc', -1)])
        self.failed(RuntimeError(signalName + " failed to kill process"))

    def _cancelTimers(self):
        for timerName in ('ioTimeoutTimer', 'killTimer', 'maxTimeoutTimer', 'sigtermTimer'):
            timer = getattr(self, timerName, None)
            if timer:
                timer.cancel()
                setattr(self, timerName, None)
