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

import functools

from twisted.internet import defer
from twisted.python import failure

from buildbot.process.results import CANCELLED
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS


class FakeRemoteCommand:

    # callers should set this to the running TestCase instance
    testcase = None

    active = False

    interrupted = False

    _waiting_for_interrupt = False

    def __init__(self, remote_command, args,
                 ignore_updates=False, collectStdout=False, collectStderr=False,
                 decodeRC=None,
                 stdioLogName='stdio'):
        if decodeRC is None:
            decodeRC = {0: SUCCESS}
        # copy the args and set a few defaults
        self.remote_command = remote_command
        self.args = args.copy()
        self.logs = {}
        self._log_close_when_finished = {}
        self.delayedLogs = {}
        self.rc = -999
        self.collectStdout = collectStdout
        self.collectStderr = collectStderr
        self.updates = {}
        self.decodeRC = decodeRC
        self.stdioLogName = stdioLogName
        if collectStdout:
            self.stdout = ''
        if collectStderr:
            self.stderr = ''

    @defer.inlineCallbacks
    def run(self, step, conn, builder_name):
        if self._waiting_for_interrupt:
            yield step.interrupt('interrupt reason')
            if not self.interrupted:
                raise RuntimeError("Interrupted step, but command was not interrupted")

        # delegate back to the test case
        cmd = yield self.testcase._remotecommand_run(self, step, conn, builder_name)
        for name, log_ in self.logs.items():
            if self._log_close_when_finished[name]:
                log_.finish()
        return cmd

    def useLog(self, log_, closeWhenFinished=False, logfileName=None):
        if not logfileName:
            logfileName = log_.getName()
        assert logfileName not in self.logs
        assert logfileName not in self.delayedLogs
        self.logs[logfileName] = log_
        self._log_close_when_finished[logfileName] = closeWhenFinished

    def useLogDelayed(self, logfileName, activateCallBack, closeWhenFinished=False):
        assert logfileName not in self.logs
        assert logfileName not in self.delayedLogs
        self.delayedLogs[logfileName] = (activateCallBack, closeWhenFinished)

    def addStdout(self, data):
        if self.collectStdout:
            self.stdout += data
        if self.stdioLogName is not None and self.stdioLogName in self.logs:
            self.logs[self.stdioLogName].addStdout(data)

    def addStderr(self, data):
        if self.collectStderr:
            self.stderr += data
        if self.stdioLogName is not None and self.stdioLogName in self.logs:
            self.logs[self.stdioLogName].addStderr(data)

    def addHeader(self, data):
        if self.stdioLogName is not None and self.stdioLogName in self.logs:
            self.logs[self.stdioLogName].addHeader(data)

    @defer.inlineCallbacks
    def addToLog(self, logname, data):
        # Activate delayed logs on first data.
        if logname in self.delayedLogs:
            (activate_callback, close_when_finished) = self.delayedLogs[logname]
            del self.delayedLogs[logname]
            loog = yield activate_callback(self)
            self.logs[logname] = loog
            self._log_close_when_finished[logname] = close_when_finished

        if logname in self.logs:
            self.logs[logname].addStdout(data)
        else:
            raise Exception("{}.addToLog: no such log {}".format(self, logname))

    def interrupt(self, why):
        if not self._waiting_for_interrupt:
            raise RuntimeError("Got interrupt, but FakeRemoteCommand was not expecting it")
        self._waiting_for_interrupt = False
        self.interrupted = True

    def results(self):
        if self.interrupted:
            return CANCELLED
        if self.rc in self.decodeRC:
            return self.decodeRC[self.rc]
        return FAILURE

    def didFail(self):
        return self.results() == FAILURE

    def set_run_interrupt(self):
        self._waiting_for_interrupt = True

    def __repr__(self):
        return "FakeRemoteCommand(" + repr(self.remote_command) + "," + repr(self.args) + ")"


class FakeRemoteShellCommand(FakeRemoteCommand):

    def __init__(self, workdir, command, env=None,
                 want_stdout=1, want_stderr=1,
                 timeout=20 * 60, maxTime=None, sigtermTime=None, logfiles=None,
                 usePTY=None, logEnviron=True, collectStdout=False,
                 collectStderr=False,
                 interruptSignal=None, initialStdin=None, decodeRC=None,
                 stdioLogName='stdio'):
        if logfiles is None:
            logfiles = {}
        if decodeRC is None:
            decodeRC = {0: SUCCESS}
        args = dict(workdir=workdir, command=command, env=env or {},
                    want_stdout=want_stdout, want_stderr=want_stderr,
                    initial_stdin=initialStdin,
                    timeout=timeout, maxTime=maxTime, logfiles=logfiles,
                    usePTY=usePTY, logEnviron=logEnviron)

        if interruptSignal is not None and interruptSignal != 'KILL':
            args['interruptSignal'] = interruptSignal
        super().__init__("shell", args,
                         collectStdout=collectStdout,
                         collectStderr=collectStderr,
                         decodeRC=decodeRC,
                         stdioLogName=stdioLogName)


class ExpectRemoteRef:

    """
    Define an expected RemoteReference in the args to an L{Expect} class
    """

    def __init__(self, rrclass):
        self.rrclass = rrclass

    def __eq__(self, other):
        return isinstance(other, self.rrclass)


class Expect:

    """
    Define an expected L{RemoteCommand}, with the same arguments

    Extra behaviors of the remote command can be added to the instance, using
    class methods.  Use L{Expect.log} to add a logfile, L{Expect.update} to add
    an arbitrary update, or add an integer to specify the return code (rc), or
    add a Failure instance to raise an exception. Additionally, use
    L{Expect.behavior}, passing a callable that will be invoked with the real
    command and can do what it likes:

        def custom_behavior(command):
            ...
        Expect('somecommand', { args='foo' })
            + Expect.behavior(custom_behavior),
        ...

        Expect('somecommand', { args='foo' })
            + Expect.log('stdio', stdout='foo!')
            + Expect.log('config.log', stdout='some info')
            + Expect.update('status', 'running')
            + 0,      # (specifies the rc)
        ...

    """

    def __init__(self, remote_command, args, interrupted=False):
        """
        Expect a command named C{remote_command}, with args C{args}.
        """
        self.remote_command = remote_command
        self.args = args
        self.result = None
        self.interrupted = interrupted
        self.behaviors = []

    @classmethod
    def behavior(cls, callable):
        """
        Add an arbitrary behavior that is expected of this command.
        C{callable} will be invoked with the real command as an argument, and
        can do what it wishes.  It will be invoked with maybeDeferred, in case
        the operation is asynchronous.
        """
        return ('callable', callable)

    @classmethod
    def log(self, name, **streams):
        return ('log', name, streams)

    @classmethod
    def update(self, name, value):
        return ('update', name, value)

    def __add__(self, other):
        # special-case adding an integer (return code) or failure (error)
        if isinstance(other, int):
            self.behaviors.append(('rc', other))
        elif isinstance(other, failure.Failure):
            self.behaviors.append(('err', other))
        else:
            self.behaviors.append(other)
        return self

    def runBehavior(self, behavior, args, command):
        """
        Implement the given behavior.  Returns a Deferred.
        """
        if behavior == 'rc':
            command.rc = args[0]
            d = defer.succeed(None)
            for log in command.logs.values():
                if hasattr(log, 'unwrap'):
                    # We're handling an old style log that was
                    # used in an old style step. We handle the necessary
                    # stuff to make the make sync/async log hack work.
                    d.addCallback(
                        functools.partial(lambda log, _: log.unwrap(), log))
                    d.addCallback(lambda l: l.flushFakeLogfile())
            return d
        elif behavior == 'err':
            return defer.fail(args[0])
        elif behavior == 'update':
            command.updates.setdefault(args[0], []).append(args[1])
        elif behavior == 'log':
            name, streams = args
            for stream in streams:
                if stream not in ['header', 'stdout', 'stderr']:
                    raise Exception('Log stream {} is not recognized'.format(stream))

            if name == command.stdioLogName:
                if 'header' in streams:
                    command.addHeader(streams['header'])
                if 'stdout' in streams:
                    command.addStdout(streams['stdout'])
                if 'stderr' in streams:
                    command.addStderr(streams['stderr'])
            else:
                if 'header' in streams or 'stderr' in streams:
                    raise Exception('Non stdio streams only support stdout')
                return command.addToLog(name, streams['stdout'])
        elif behavior == 'callable':
            return defer.maybeDeferred(lambda: args[0](command))
        else:
            return defer.fail(failure.Failure(AssertionError('invalid behavior {}'.format(
                    behavior))))
        return defer.succeed(None)

    @defer.inlineCallbacks
    def runBehaviors(self, command):
        """
        Run all expected behaviors for this command
        """
        for behavior in self.behaviors:
            yield self.runBehavior(behavior[0], behavior[1:], command)

    def expectationPassed(self, exp):
        """
        Some expectations need to be able to distinguish pass/fail of
        nested expectations.

        This will get invoked once for every nested exception and once
        for self unless anything fails.  Failures are passed to raiseExpectationFailure for
        handling.

        @param exp: The nested exception that passed or self.
        """

    def raiseExpectationFailure(self, exp, failure):
        """
        Some expectations may wish to suppress failure.
        The default expectation does not.

        This will get invoked if the expectations fails on a command.

        @param exp: the expectation that failed.  this could be self or a nested exception
        """
        raise failure

    def shouldAssertCommandEqualExpectation(self):
        """
        Whether or not we should validate that the current command matches the expectation.
        Some expectations may not have a way to match a command.
        """
        return True

    def shouldRunBehaviors(self):
        """
        Whether or not, once the command matches the expectation,
        the behaviors should be run for this step.
        """
        return True

    def shouldKeepMatchingAfter(self, command):
        """
        Expectations are by default not kept matching multiple commands.

        Return True if you want to re-use a command for multiple commands.
        """
        return False

    def nestedExpectations(self):
        """
        Any sub-expectations that should be validated.
        """
        return []

    def __repr__(self):
        return "Expect(" + repr(self.remote_command) + ")"


class ExpectShell(Expect):

    """
    Define an expected L{RemoteShellCommand}, with the same arguments Any
    non-default arguments must be specified explicitly (e.g., usePTY).
    """

    def __init__(self, workdir, command, env=None,
                 want_stdout=1, want_stderr=1, initialStdin=None,
                 timeout=20 * 60, maxTime=None, logfiles=None,
                 usePTY=None, logEnviron=True, interruptSignal=None):
        if env is None:
            env = {}
        if logfiles is None:
            logfiles = {}
        args = dict(workdir=workdir, command=command, env=env,
                    want_stdout=want_stdout, want_stderr=want_stderr,
                    initial_stdin=initialStdin,
                    timeout=timeout, maxTime=maxTime, logfiles=logfiles,
                    usePTY=usePTY, logEnviron=logEnviron)
        if interruptSignal is not None:
            args['interruptSignal'] = interruptSignal
        super().__init__("shell", args)

    def __repr__(self):
        return "ExpectShell(" + repr(self.remote_command) + repr(self.args['command']) + ")"
