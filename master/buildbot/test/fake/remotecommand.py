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

from buildbot import interfaces
from buildbot.status.logfile import HEADER
from buildbot.status.logfile import STDERR
from buildbot.status.logfile import STDOUT
from buildbot.status.results import FAILURE
from buildbot.status.results import SUCCESS
from cStringIO import StringIO
from twisted.internet import defer
from twisted.python import failure
from zope.interface import implements


class FakeRemoteCommand(object):

    # callers should set this to the running TestCase instance
    testcase = None

    active = False

    def __init__(self, remote_command, args,
                 ignore_updates=False, collectStdout=False, collectStderr=False,
                 decodeRC={0: SUCCESS},
                 stdioLogName='stdio'):
        # copy the args and set a few defaults
        self.remote_command = remote_command
        self.args = args.copy()
        self.logs = {}
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

    def run(self, step, remote):
        # delegate back to the test case
        return self.testcase._remotecommand_run(self, step, remote)

    def useLog(self, log, closeWhenFinished=False, logfileName=None):
        if not logfileName:
            logfileName = log.getName()
        self.logs[logfileName] = log

    def useLogDelayed(self, logfileName, activateCallBack, closeWhenFinished=False):
        self.delayedLogs[logfileName] = (activateCallBack, closeWhenFinished)

    def interrupt(self, why):
        raise NotImplementedError

    def results(self):
        if self.rc in self.decodeRC:
            return self.decodeRC[self.rc]
        return FAILURE

    def didFail(self):
        return self.results() == FAILURE

    def fakeLogData(self, step, log, header='', stdout='', stderr=''):
        # note that this should not be used in the same test as useLog(Delayed)
        self.logs[log] = l = FakeLogFile(log, step)
        l.fakeData(header=header, stdout=stdout, stderr=stderr)

    def __repr__(self):
        return "FakeRemoteCommand(" + repr(self.remote_command) + "," + repr(self.args) + ")"


class FakeRemoteShellCommand(FakeRemoteCommand):

    def __init__(self, workdir, command, env=None,
                 want_stdout=1, want_stderr=1,
                 timeout=20 * 60, maxTime=None, sigtermTime=None, logfiles={},
                 usePTY="slave-config", logEnviron=True, collectStdout=False,
                 collectStderr=False,
                 interruptSignal=None, initialStdin=None, decodeRC={0: SUCCESS},
                 stdioLogName='stdio'):
        args = dict(workdir=workdir, command=command, env=env or {},
                    want_stdout=want_stdout, want_stderr=want_stderr,
                    initial_stdin=initialStdin,
                    timeout=timeout, maxTime=maxTime, logfiles=logfiles,
                    usePTY=usePTY, logEnviron=logEnviron)
        FakeRemoteCommand.__init__(self, "shell", args,
                                   collectStdout=collectStdout,
                                   collectStderr=collectStderr,
                                   decodeRC=decodeRC,
                                   stdioLogName=stdioLogName)


class FakeLogFile(object):
    implements(interfaces.IStatusLog, interfaces.ILogFile)

    def __init__(self, name, step):
        self.name = name
        self.header = ''
        self.stdout = ''
        self.stderr = ''
        self.chunks = []
        self.step = step

    def getName(self):
        return self.name

    def addHeader(self, text):
        self.header += text
        self.chunks.append((HEADER, text))

    def addStdout(self, text):
        self.stdout += text
        self.chunks.append((STDOUT, text))
        if self.name in self.step.logobservers:
            for obs in self.step.logobservers[self.name]:
                obs.outReceived(text)

    def addStderr(self, text):
        self.stderr += text
        self.chunks.append((STDERR, text))
        if self.name in self.step.logobservers:
            for obs in self.step.logobservers[self.name]:
                obs.errReceived(text)

    def readlines(self):
        io = StringIO(self.stdout)
        return io.readlines()

    def getText(self):
        return ''.join([c for str, c in self.chunks
                        if str in (STDOUT, STDERR)])

    def getTextWithHeaders(self):
        return ''.join([c for str, c in self.chunks])

    def getChunks(self, channels=[], onlyText=False):
        if onlyText:
            return [data
                    for (ch, data) in self.chunks
                    if not channels or ch in channels]
        else:
            return [(ch, data)
                    for (ch, data) in self.chunks
                    if not channels or ch in channels]

    def finish(self):
        pass

    def fakeData(self, header='', stdout='', stderr=''):
        if header:
            self.header += header
            self.chunks.append((HEADER, header))
        if stdout:
            self.stdout += stdout
            self.chunks.append((STDOUT, stdout))
        if stderr:
            self.stderr += stderr
            self.chunks.append((STDERR, stderr))


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

    def __init__(self, remote_command, args, incomparable_args=[]):
        """

        Expect a command named C{remote_command}, with args C{args}.  Any args
        in C{incomparable_args} are not cmopared, but must exist.

        """
        self.remote_command = remote_command
        self.incomparable_args = incomparable_args
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
                if command.collectStderr:
                    command.stderr += streams['stderr']
        elif behavior == 'callable':
            return defer.maybeDeferred(lambda: args[0](command))
        else:
            return defer.fail(failure.Failure(
                AssertionError('invalid behavior %s' % behavior)))
        return defer.succeed(None)

    @defer.inlineCallbacks
    def runBehaviors(self, command):
        """
        Run all expected behaviors for this command
        """
        for behavior in self.behaviors:
            yield self.runBehavior(behavior[0], behavior[1:], command)

    def __repr__(self):
        return "Expect(" + repr(self.remote_command) + ")"


class ExpectShell(Expect):

    """
    Define an expected L{RemoteShellCommand}, with the same arguments Any
    non-default arguments must be specified explicitly (e.g., usePTY).
    """

    def __init__(self, workdir, command, env={},
                 want_stdout=1, want_stderr=1, initialStdin=None,
                 timeout=20 * 60, maxTime=None, logfiles={},
                 usePTY="slave-config", logEnviron=True):
        args = dict(workdir=workdir, command=command, env=env,
                    want_stdout=want_stdout, want_stderr=want_stderr,
                    initial_stdin=initialStdin,
                    timeout=timeout, maxTime=maxTime, logfiles=logfiles,
                    usePTY=usePTY, logEnviron=logEnviron)
        Expect.__init__(self, "shell", args)

    def __repr__(self):
        return "ExpectShell(" + repr(self.remote_command) + repr(self.args['command']) + ")"
