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


DEFAULT_TIMEOUT="DEFAULT_TIMEOUT"
DEFAULT_MAXTIME="DEFAULT_MAXTIME"
DEFAULT_USEPTY="DEFAULT_USEPTY"

class FakeRemoteCommand(object):

    def __init__(self, remote_command, args):
        # copy the args and set a few defaults
        self.remote_command = remote_command
        self.args = args.copy()

    def run(self, step, remote):
        # delegate back to the test case
        return self.testcase._remotecommand_run(self, step, remote)


class FakeLoggedRemoteCommand(FakeRemoteCommand):

    def __init__(self, *args, **kwargs):
        FakeRemoteCommand.__init__(self, *args, **kwargs)
        self.logs = {}
        self.rc = -999

    def useLog(self, loog, closeWhenFinished=False, logfileName=None):
        if not logfileName:
            logfileName = loog.getName()
        self.logs[logfileName] = loog


class FakeRemoteShellCommand(FakeLoggedRemoteCommand):

    def __init__(self, workdir, command, env=None,
                 want_stdout=1, want_stderr=1,
                 timeout=DEFAULT_TIMEOUT, maxTime=DEFAULT_MAXTIME, logfiles={},
                 usePTY=DEFAULT_USEPTY, logEnviron=True):
        args = dict(workdir=workdir, command=command, env=env or {},
                want_stdout=want_stdout, want_stderr=want_stderr,
                timeout=timeout, maxTime=maxTime, logfiles=logfiles,
                usePTY=usePTY, logEnviron=logEnviron)
        FakeLoggedRemoteCommand.__init__(self, "shell", args)


class FakeLogFile(object):

    def __init__(self, name):
        self.name = name
        self.header = ''
        self.stdout = ''
        self.stderr = ''

    def getName(self):
        return self.name

    def addHeader(self, data):
        self.header += data

    def addStdout(self, data):
        self.stdout += data

    def addStderr(self, data):
        self.stderr += data

    def readlines(self): # TODO: remove channel arg from logfile.py
        return self.stdout.split('\n')

    def getText(self):
        return self.stdout


class Expect(object):
    """
    Define an expected L{RemoteCommand}, with the same arguments
    """

    def __init__(self, remote_command, args):
        """
        Expect a command named C{remote_command}, with args C{args}.
        """
        self.remote_command = remote_command
        self.args = args
        self.result = None
        self.updates = []

    @classmethod
    def log(self, name, **streams):
        return ('log', name, streams)

    def __add__(self, other):
        if isinstance(other, int):
            self.updates.append(('rc', other))
        elif isinstance(other, failure.Failure):
            self.updates.append(('err', other))
        else:
            self.updates.append(other)
        return self

    def runBehaviors(self, command):
        # apply updates
        for upd in self.updates:
            if upd[0] == 'rc':
                command.rc = upd[1]
            elif upd[0] == 'err':
                return defer.fail(upd[1])
            elif upd[0] == 'log':
                name, streams = upd[1:]
                if 'header' in streams:
                    command.logs[name].addHeader(streams['header'])
                if 'stdout' in streams:
                    command.logs[name].addStdout(streams['stdout'])
                if 'stderr' in streams:
                    command.logs[name].addStderr(streams['stderr'])
        return defer.succeed(self)

class ExpectLogged(Expect):
    """
    Define an expected L{LoggedRemoteCommand}, with the same arguments

    Extra attributes of the logged remote command can be added to
    the instance, using class methods to specify the attributes::

        ExpectLogged('somecommand', { args='foo' })
            + ExpectLogged.log('stdio', stdout='foo!')
            + ExpectLogged.log('config.log', stdout='some info')
            + 0,      # (specifies the rc)
        ...

    """
    def __init__(self, remote_command, args):
        Expect.__init__(self, remote_command, args)

class ExpectShell(ExpectLogged):
    """
    Define an expected L{RemoteShellCommand}, with the same arguments Any
    non-default arguments must be specified explicitly (e.g., usePTY).
    """
    def __init__(self, workdir, command, env={},
                 want_stdout=1, want_stderr=1,
                 timeout=DEFAULT_TIMEOUT, maxTime=DEFAULT_MAXTIME, logfiles={},
                 usePTY=DEFAULT_USEPTY, logEnviron=True):
        args = dict(workdir=workdir, command=command, env=env,
                want_stdout=want_stdout, want_stderr=want_stderr,
                timeout=timeout, maxTime=maxTime, logfiles=logfiles,
                usePTY=usePTY, logEnviron=logEnviron)
        ExpectLogged.__init__(self, "shell", args)
