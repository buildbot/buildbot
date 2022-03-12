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
import pprint
import re

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import runtime

from buildbot.process.buildstep import CANCELLED
from buildbot.process.buildstep import FAILURE
from buildbot.process.buildstep import SUCCESS
from buildbot.process.buildstep import BuildStep
from buildbot.util import deferwaiter
from buildbot.util import runprocess


class MasterShellCommand(BuildStep):

    """
    Run a shell command locally - on the buildmaster.  The shell command
    COMMAND is specified just as for a RemoteShellCommand.  Note that extra
    logfiles are not supported.
    """
    name = 'MasterShellCommand'
    description = 'Running'
    descriptionDone = 'Ran'
    descriptionSuffix = None
    renderables = ['command', 'env']
    haltOnFailure = True
    flunkOnFailure = True

    def __init__(self, command, **kwargs):
        self.env = kwargs.pop('env', None)
        self.usePTY = kwargs.pop('usePTY', 0)
        self.interruptSignal = kwargs.pop('interruptSignal', 'KILL')
        self.logEnviron = kwargs.pop('logEnviron', True)

        super().__init__(**kwargs)

        self.command = command
        self.process = None
        self.masterWorkdir = self.workdir
        self._deferwaiter = deferwaiter.DeferWaiter()

    @defer.inlineCallbacks
    def run(self):
        # render properties
        command = self.command
        # set up argv
        if isinstance(command, (str, bytes)):
            if runtime.platformType == 'win32':
                # allow %COMSPEC% to have args
                argv = os.environ['COMSPEC'].split()
                if '/c' not in argv:
                    argv += ['/c']
                argv += [command]
            else:
                # for posix, use /bin/sh. for other non-posix, well, doesn't
                # hurt to try
                argv = ['/bin/sh', '-c', command]
        else:
            if runtime.platformType == 'win32':
                # allow %COMSPEC% to have args
                argv = os.environ['COMSPEC'].split()
                if '/c' not in argv:
                    argv += ['/c']
                argv += list(command)
            else:
                argv = command

        self.stdio_log = yield self.addLog("stdio")

        if isinstance(command, (str, bytes)):
            yield self.stdio_log.addHeader(command.strip() + "\n\n")
        else:
            yield self.stdio_log.addHeader(" ".join(command) + "\n\n")
        yield self.stdio_log.addHeader("** RUNNING ON BUILDMASTER **\n")
        yield self.stdio_log.addHeader(f" in dir {os.getcwd()}\n")
        yield self.stdio_log.addHeader(f" argv: {argv}\n")

        os_env = os.environ
        if self.env is None:
            env = os_env
        else:
            assert isinstance(self.env, dict)
            env = self.env
            for key, v in self.env.items():
                if isinstance(v, list):
                    # Need to do os.pathsep translation.  We could either do that
                    # by replacing all incoming ':'s with os.pathsep, or by
                    # accepting lists.  I like lists better.
                    # If it's not a string, treat it as a sequence to be
                    # turned in to a string.
                    self.env[key] = os.pathsep.join(self.env[key])

            # do substitution on variable values matching pattern: ${name}
            p = re.compile(r'\${([0-9a-zA-Z_]*)}')

            def subst(match):
                return os.environ.get(match.group(1), "")
            newenv = {}
            for key, v in env.items():
                if v is not None:
                    if not isinstance(v, (str, bytes)):
                        raise RuntimeError("'env' values must be strings or "
                                           f"lists; key '{key}' is incorrect")
                    newenv[key] = p.sub(subst, env[key])

            # RunProcess will take environment values from os.environ in cases of env not having
            # the keys that are in os.environ. Prevent this by putting None into those keys.
            for key in os_env:
                if key not in env:
                    env[key] = None

            env = newenv

        if self.logEnviron:
            yield self.stdio_log.addHeader(f" env: {repr(env)}\n")

        if self.stopped:
            return CANCELLED

        on_stdout = lambda data: self._deferwaiter.add(self.stdio_log.addStdout(data))
        on_stderr = lambda data: self._deferwaiter.add(self.stdio_log.addStderr(data))

        # TODO add a timeout?
        self.process = runprocess.create_process(reactor, argv, workdir=self.masterWorkdir,
                                                 use_pty=self.usePTY, env=env,
                                                 collect_stdout=on_stdout, collect_stderr=on_stderr)

        yield self.process.start()
        yield self._deferwaiter.wait()

        if self.process.result_signal is not None:
            yield self.stdio_log.addHeader(f"signal {self.process.result_signal}\n")
            self.descriptionDone = [f"killed ({self.process.result_signal})"]
            return FAILURE
        elif self.process.result_rc != 0:
            yield self.stdio_log.addHeader(f"exit status {self.process.result_signal}\n")
            self.descriptionDone = [f"failed ({self.process.result_rc})"]
            return FAILURE
        else:
            return SUCCESS

    @defer.inlineCallbacks
    def interrupt(self, reason):
        yield super().interrupt(reason)
        if self.process is not None:
            self.process.send_signal(self.interruptSignal)


class SetProperty(BuildStep):
    name = 'SetProperty'
    description = ['Setting']
    descriptionDone = ['Set']
    renderables = ['property', 'value']

    def __init__(self, property, value, **kwargs):
        super().__init__(**kwargs)
        self.property = property
        self.value = value

    def run(self):
        properties = self.build.getProperties()
        properties.setProperty(
            self.property, self.value, self.name, runtime=True)
        return defer.succeed(SUCCESS)


class SetProperties(BuildStep):
    name = 'SetProperties'
    description = ['Setting Properties..']
    descriptionDone = ['Properties Set']
    renderables = ['properties']

    def __init__(self, properties=None, **kwargs):
        super().__init__(**kwargs)
        self.properties = properties

    def run(self):
        if self.properties is None:
            return defer.succeed(SUCCESS)
        for k, v in self.properties.items():
            self.setProperty(k, v, self.name, runtime=True)
        return defer.succeed(SUCCESS)


class Assert(BuildStep):
    name = 'Assert'
    description = ['Checking..']
    descriptionDone = ["checked"]
    renderables = ['check']

    def __init__(self, check, **kwargs):
        super().__init__(**kwargs)
        self.check = check
        self.descriptionDone = [f"checked {repr(self.check)}"]

    def run(self):
        if self.check:
            return defer.succeed(SUCCESS)
        return defer.succeed(FAILURE)


class LogRenderable(BuildStep):
    name = 'LogRenderable'
    description = ['Logging']
    descriptionDone = ['Logged']
    renderables = ['content']

    def __init__(self, content, **kwargs):
        super().__init__(**kwargs)
        self.content = content

    @defer.inlineCallbacks
    def run(self):
        content = pprint.pformat(self.content)
        yield self.addCompleteLog(name='Output', text=content)
        return SUCCESS
