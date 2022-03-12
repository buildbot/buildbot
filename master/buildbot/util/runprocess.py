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

import io
import os
import subprocess

from twisted.internet import defer
from twisted.internet import error
from twisted.internet import protocol
from twisted.python import failure
from twisted.python import log
from twisted.python import runtime

from buildbot.util import unicode2bytes


class RunProcessPP(protocol.ProcessProtocol):
    def __init__(self, run_process, initial_stdin=None):
        self.run_process = run_process
        self.initial_stdin = initial_stdin

    def connectionMade(self):
        if self.initial_stdin:
            self.transport.write(self.initial_stdin)
        self.transport.closeStdin()

    def outReceived(self, data):
        self.run_process.add_stdout(data)

    def errReceived(self, data):
        self.run_process.add_stderr(data)

    def processEnded(self, reason):
        self.run_process.process_ended(reason.value.signal, reason.value.exitCode)


class RunProcess:

    TIMEOUT_KILL = 5
    interrupt_signal = "KILL"

    def __init__(self, reactor, command, workdir=None, env=None,
                 collect_stdout=True, collect_stderr=True, stderr_is_error=False,
                 io_timeout=300, runtime_timeout=3600, sigterm_timeout=5, initial_stdin=None,
                 use_pty=False):

        self._reactor = reactor
        self.command = command

        self.workdir = workdir
        self.process = None

        self.environ = env

        self.initial_stdin = initial_stdin

        self.output_stdout = None
        self.consumer_stdout = None

        if collect_stdout is True:
            self.output_stdout = io.BytesIO()
            self.consumer_stdout = self.output_stdout.write
        elif callable(collect_stdout):
            self.consumer_stdout = collect_stdout

        self.output_stderr = None
        self.consumer_stderr = None

        if collect_stderr is True:
            self.output_stderr = io.BytesIO()
            self.consumer_stderr = self.output_stderr.write
        elif callable(collect_stderr):
            self.consumer_stderr = collect_stderr

        self.stderr_is_error = stderr_is_error

        self.io_timeout = io_timeout
        self.io_timer = None

        self.sigterm_timeout = sigterm_timeout
        self.sigterm_timer = None

        self.runtime_timeout = runtime_timeout
        self.runtime_timer = None

        self.killed = False
        self.kill_timer = None
        self.use_pty = use_pty

        self.result_signal = None
        self.result_rc = None

    def __repr__(self):
        return f"<{self.__class__.__name__} '{self.command}'>"

    def get_os_env(self):
        return os.environ

    def resolve_environment(self, env):
        os_env = self.get_os_env()
        if env is None:
            return os_env.copy()

        new_env = {}
        for key, value in os_env.items():
            if key not in env or env[key] is not None:
                new_env[key] = value
        for key, value in env.items():
            if value is not None:
                new_env[key] = value
        return new_env

    def start(self):
        self.deferred = defer.Deferred()
        try:
            self._start_command()
        except Exception as e:
            self.deferred.errback(failure.Failure(e))
        return self.deferred

    def _start_command(self):
        self.pp = RunProcessPP(self, initial_stdin=self.initial_stdin)

        environ = self.resolve_environment(self.environ)

        # $PWD usually indicates the current directory; spawnProcess may not
        # update this value, though, so we set it explicitly here.  This causes
        # weird problems (bug #456) on msys
        if not environ.get('MACHTYPE', None) == 'i686-pc-msys' and self.workdir is not None:
            environ['PWD'] = os.path.abspath(self.workdir)

        argv = unicode2bytes(self.command)
        self.process = self._reactor.spawnProcess(self.pp, argv[0], argv, environ, self.workdir,
                                                  usePTY=self.use_pty)

        if self.io_timeout:
            self.io_timer = self._reactor.callLater(self.io_timeout, self.io_timed_out)

        if self.runtime_timeout:
            self.runtime_timer = self._reactor.callLater(self.runtime_timeout,
                                                         self.runtime_timed_out)

    def add_stdout(self, data):
        if self.consumer_stdout is not None:
            self.consumer_stdout(data)

        if self.io_timer:
            self.io_timer.reset(self.io_timeout)

    def add_stderr(self, data):
        if self.consumer_stderr is not None:
            self.consumer_stderr(data)

        if self.stderr_is_error:
            self.kill('command produced stderr which is interpreted as error')

        if self.io_timer:
            self.io_timer.reset(self.io_timeout)

    def _build_result(self, rc):
        if self.output_stdout is not None and self.output_stderr is not None:
            return (rc, self.output_stdout.getvalue(), self.output_stderr.getvalue())
        if self.output_stdout is not None:
            return (rc, self.output_stdout.getvalue())
        if self.output_stderr is not None:
            return (rc, self.output_stderr.getvalue())
        return rc

    def process_ended(self, sig, rc):
        self.result_signal = sig
        self.result_rc = rc

        if self.killed and rc == 0:
            log.msg("process was killed, but exited with status 0; faking a failure")

            # windows returns '1' even for signalled failures, while POSIX returns -1
            if runtime.platformType == 'win32':
                rc = 1
            else:
                rc = -1

        if sig is not None:
            rc = -1

        self._cancel_timers()
        d = self.deferred
        self.deferred = None
        if d:
            d.callback(self._build_result(rc))
        else:
            log.err(f"{self}: command finished twice")

    def failed(self, why):
        self._cancel_timers()
        d = self.deferred
        self.deferred = None
        if d:
            d.errback(why)
        else:
            log.err(f"{self}: command finished twice")

    def io_timed_out(self):
        self.io_timer = None
        msg = f"{self}: command timed out: {self.io_timeout} seconds without output"
        self.kill(msg)

    def runtime_timed_out(self):
        self.runtime_timer = None
        msg = f"{self}: command timed out: {self.runtime_timeout} seconds elapsed"
        self.kill(msg)

    def is_dead(self):
        if self.process.pid is None:
            return True
        pid = int(self.process.pid)
        try:
            os.kill(pid, 0)
        except OSError:
            return True
        return False

    def check_process_was_killed(self):

        self.sigterm_timer = None
        if not self.is_dead():
            if not self.send_signal(self.interrupt_signal):
                log.msg(f"{self}: failed to kill process again")

        self.cleanup_killed_process()

    def cleanup_killed_process(self):
        if runtime.platformType == "posix":
            # we only do this under posix because the win32eventreactor
            # blocks here until the process has terminated, while closing
            # stderr. This is weird.
            self.pp.transport.loseConnection()

        if self.deferred:
            # finished ought to be called momentarily. Just in case it doesn't,
            # set a timer which will abandon the command.
            self.kill_timer = self._reactor.callLater(self.TIMEOUT_KILL, self.kill_timed_out)

    def send_signal(self, interrupt_signal):
        success = False

        log.msg(f'{self}: killing process using {interrupt_signal}')

        if runtime.platformType == "win32":
            if interrupt_signal is not None and self.process.pid is not None:
                if interrupt_signal == "TERM":
                    # TODO: blocks
                    subprocess.check_call(f"TASKKILL /PID {self.process.pid} /T")
                    success = True
                elif interrupt_signal == "KILL":
                    # TODO: blocks
                    subprocess.check_call(f"TASKKILL /F /PID {self.process.pid} /T")
                    success = True

        # try signalling the process itself (works on Windows too, sorta)
        if not success:
            try:
                self.process.signalProcess(interrupt_signal)
                success = True
            except OSError as e:
                log.err(f"{self}: from process.signalProcess: {e}")
                # could be no-such-process, because they finished very recently
            except error.ProcessExitedAlready:
                log.msg(f"{self}: process exited already - can't kill")

                # the process has already exited, and likely finished() has
                # been called already or will be called shortly

        return success

    def kill(self, msg):
        log.msg(f'{self}: killing process because {msg}')
        self._cancel_timers()

        self.killed = True

        if self.sigterm_timeout is not None:
            self.send_signal("TERM")
            self.sigterm_timer = self._reactor.callLater(self.sigterm_timeout,
                                                         self.check_process_was_killed)
        else:
            if not self.send_signal(self.interrupt_signal):
                log.msg(f"{self}: failed to kill process")

            self.cleanup_killed_process()

    def kill_timed_out(self):
        self.kill_timer = None
        log.msg(f"{self}: attempted to kill process, but it wouldn't die")

        self.failed(RuntimeError(f"SIG{self.interrupt_signal} failed to kill process"))

    def _cancel_timers(self):
        for name in ('io_timer', 'kill_timer', 'runtime_timer', 'sigterm_timer'):
            timer = getattr(self, name, None)
            if timer:
                timer.cancel()
                setattr(self, name, None)


def create_process(*args, **kwargs):
    return RunProcess(*args, **kwargs)


def run_process(*args, **kwargs):
    process = create_process(*args, **kwargs)
    return process.start()
