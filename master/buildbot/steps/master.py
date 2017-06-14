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

from __future__ import absolute_import
from __future__ import print_function
from future.utils import iteritems
from future.utils import string_types

import os
import pprint
import re
from builtins import bytes
from builtins import str

from twisted.internet import defer
from twisted.internet import error
from twisted.internet import reactor
from twisted.internet.protocol import ProcessProtocol
from twisted.python import runtime

from buildbot.process.buildstep import FAILURE
from buildbot.process.buildstep import SUCCESS
from buildbot.process.buildstep import BuildStep


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

        BuildStep.__init__(self, **kwargs)

        self.command = command
        self.masterWorkdir = self.workdir

    class LocalPP(ProcessProtocol):

        def __init__(self, step):
            self.step = step

        def outReceived(self, data):
            self.step.stdio_log.addStdout(data)

        def errReceived(self, data):
            self.step.stdio_log.addStderr(data)

        def processEnded(self, status_object):
            if status_object.value.exitCode is not None:
                self.step.stdio_log.addHeader(
                    "exit status %d\n" % status_object.value.exitCode)
            if status_object.value.signal is not None:
                self.step.stdio_log.addHeader(
                    "signal %s\n" % status_object.value.signal)
            self.step.processEnded(status_object)

    def start(self):
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

        self.stdio_log = stdio_log = self.addLog("stdio")

        if isinstance(command, str):
            stdio_log.addHeader(command.strip() + "\n\n")
        else:
            stdio_log.addHeader(" ".join(command) + "\n\n")
        stdio_log.addHeader("** RUNNING ON BUILDMASTER **\n")
        stdio_log.addHeader(" in dir %s\n" % os.getcwd())
        stdio_log.addHeader(" argv: %s\n" % (argv,))
        self.step_status.setText(self.describe())

        if self.env is None:
            env = os.environ
        else:
            assert isinstance(self.env, dict)
            env = self.env
            for key, v in iteritems(self.env):
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
            for key, v in iteritems(env):
                if v is not None:
                    if not isinstance(v, string_types):
                        raise RuntimeError("'env' values must be strings or "
                                           "lists; key '%s' is incorrect" % (key,))
                    newenv[key] = p.sub(subst, env[key])
            env = newenv

        if self.logEnviron:
            stdio_log.addHeader(" env: %r\n" % (env,))

        # TODO add a timeout?
        self.process = reactor.spawnProcess(self.LocalPP(self), argv[0], argv,
                                            path=self.masterWorkdir, usePTY=self.usePTY, env=env)
        # (the LocalPP object will call processEnded for us)

    def processEnded(self, status_object):
        if status_object.value.signal is not None:
            self.descriptionDone = ["killed (%s)" % status_object.value.signal]
            self.step_status.setText(self.describe(done=True))
            self.finished(FAILURE)
        elif status_object.value.exitCode != 0:
            self.descriptionDone = [
                "failed (%d)" % status_object.value.exitCode]
            self.step_status.setText(self.describe(done=True))
            self.finished(FAILURE)
        else:
            self.step_status.setText(self.describe(done=True))
            self.finished(SUCCESS)

    def interrupt(self, reason):
        try:
            self.process.signalProcess(self.interruptSignal)
        except KeyError:  # Process not started yet
            pass
        except error.ProcessExitedAlready:
            pass
        BuildStep.interrupt(self, reason)


class SetProperty(BuildStep):
    name = 'SetProperty'
    description = ['Setting']
    descriptionDone = ['Set']
    renderables = ['property', 'value']

    def __init__(self, property, value, **kwargs):
        BuildStep.__init__(self, **kwargs)
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
        BuildStep.__init__(self, **kwargs)
        self.properties = properties

    def run(self):
        if self.properties is None:
            return defer.succeed(SUCCESS)
        for k, v in iteritems(self.properties):
            self.setProperty(k, v, self.name, runtime=True)
        return defer.succeed(SUCCESS)


class Assert(BuildStep):
    name = 'Assert'
    description = ['Checking..']
    descriptionDone = ["checked"]
    renderables = ['check']

    def __init__(self, check, **kwargs):
        BuildStep.__init__(self, **kwargs)
        self.check = check
        self.descriptionDone = ["checked {}".format(repr(self.check))]

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
        BuildStep.__init__(self, **kwargs)
        self.content = content

    def start(self):
        content = pprint.pformat(self.content)
        self.addCompleteLog(name='Output', text=content)
        self.step_status.setText(self.describe(done=True))
        self.finished(SUCCESS)
