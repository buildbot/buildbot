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

from twisted.internet import defer
from twisted.python import failure
from buildbot.status.logfile import STDOUT, STDERR, HEADER


DEFAULT_TIMEOUT="DEFAULT_TIMEOUT"
DEFAULT_MAXTIME="DEFAULT_MAXTIME"
DEFAULT_USEPTY="DEFAULT_USEPTY"

class FakeRemoteCommand:

    def __init__(self, remote_command, args, collectStdout=False, ignore_updates=False):
        # copy the args and set a few defaults
        self.remote_command = remote_command
        self.args = args.copy()
        self.logs = {}
        self.rc = -999
        self.collectStdout = collectStdout
        self.updates = {}
        if collectStdout:
            self.stdout = ''

    def useLog(self, loog, closeWhenFinished=False, logfileName=None):
        if not logfileName:
            logfileName = loog.getName()
        self.logs[logfileName] = loog

    def run(self, step, remote):
        # delegate back to the test case
        return self.testcase._remotecommand_run(self, step, remote)


class FakeRemoteShellCommand(FakeRemoteCommand):

    def __init__(self, workdir, command, env=None,
                 want_stdout=1, want_stderr=1,
                 timeout=DEFAULT_TIMEOUT, maxTime=DEFAULT_MAXTIME, logfiles={},
                 initial_stdin=None,
                 usePTY=DEFAULT_USEPTY, logEnviron=True, collectStdout=False):
        args = dict(workdir=workdir, command=command, env=env or {},
                want_stdout=want_stdout, want_stderr=want_stderr,
                initial_stdin=initial_stdin,
                timeout=timeout, maxTime=maxTime, logfiles=logfiles,
                usePTY=usePTY, logEnviron=logEnviron)
        FakeRemoteCommand.__init__(self, "shell", args,
                collectStdout=collectStdout)


class FakeLogFile(object):

    def __init__(self, name, step):
        self.name = name
        self.header = ''
        self.stdout = ''
        self.stderr = ''
        self.chunks = []
        self.step = step

    def getName(self):
        return self.name

    def addHeader(self, data):
        self.header += data
        self.chunks.append((HEADER, data))

    def addStdout(self, data):
        self.stdout += data
        self.chunks.append((STDOUT, data))
        if self.name in self.step.logobservers:
            for obs in self.step.logobservers[self.name]:
                obs.outReceived(data)

    def addStderr(self, data):
        self.stderr += data
        self.chunks.append((STDERR, data))
        if self.name in self.step.logobservers:
            for obs in self.step.logobservers[self.name]:
                obs.errReceived(data)

    def readlines(self): # TODO: remove channel arg from logfile.py
        return self.stdout.split('\n')

    def getText(self):
        return self.stdout

    def getChunks(self, channels=[], onlyText=False):
        if onlyText:
            return [ data
                        for (ch, data) in self.chunks
                        if ch in channels ]
        else:
            return [ (ch, data)
                        for (ch, data) in self.chunks
                        if ch in channels ]

    def finish(self):
        pass


class ExpectRemoteRef(object):
    """
    Define an expected RemoteReference in the args to an L{Expect} class
    """

    def __init__(self, rrclass):
        self.rrclass = rrclass

    def __eq__(self, other):
        return isinstance(other, self.rrclass)

class Expect(object):
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

    def __init__(self, remote_command, args):
        """
        Expect a command named C{remote_command}, with args C{args}.
        """
        self.remote_command = remote_command
        self.args = args
        self.result = None
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
        elif behavior == 'err':
            return defer.fail(args[0])
        elif behavior == 'update':
            command.updates.setdefault(args[0], []).append(args[1])
        elif behavior == 'log':
            name, streams = args
            if 'header' in streams:
                command.logs[name].addHeader(streams['header'])
            if 'stdout' in streams:
                command.logs[name].addStdout(streams['stdout'])
                if command.collectStdout:
                    command.stdout += streams['stdout']
            if 'stderr' in streams:
                command.logs[name].addStderr(streams['stderr'])
        elif behavior == 'callable':
            return defer.maybeDeferred(lambda : args[0](command))
        else:
            return defer.fail(failure.Failure(
                        AssertionError('invalid behavior %s' % behavior)))
        return defer.succeed(None)

    @defer.deferredGenerator
    def runBehaviors(self, command):
        """
        Run all expected behaviors for this command
        """
        for behavior in self.behaviors:
            wfd = defer.waitForDeferred(
                    self.runBehavior(behavior[0], behavior[1:], command))
            yield wfd
            wfd.getResult()


class ExpectShell(Expect):
    """
    Define an expected L{RemoteShellCommand}, with the same arguments Any
    non-default arguments must be specified explicitly (e.g., usePTY).
    """
    def __init__(self, workdir, command, env={},
                 want_stdout=1, want_stderr=1, initial_stdin=None,
                 timeout=DEFAULT_TIMEOUT, maxTime=DEFAULT_MAXTIME, logfiles={},
                 usePTY=DEFAULT_USEPTY, logEnviron=True):
        args = dict(workdir=workdir, command=command, env=env,
                want_stdout=want_stdout, want_stderr=want_stderr,
                initial_stdin=initial_stdin,
                timeout=timeout, maxTime=maxTime, logfiles=logfiles,
                usePTY=usePTY, logEnviron=logEnviron)
        Expect.__init__(self, "shell", args)
