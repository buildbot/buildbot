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

import os, types, re
from twisted.python import runtime
from twisted.internet import reactor
from buildbot.process.buildstep import BuildStep
from buildbot.process.buildstep import SUCCESS, FAILURE
from twisted.internet import error
from twisted.internet.protocol import ProcessProtocol

class MasterShellCommand(BuildStep):
    """
    Run a shell command locally - on the buildmaster.  The shell command
    COMMAND is specified just as for a RemoteShellCommand.  Note that extra
    logfiles are not supported.
    """
    name='MasterShellCommand'
    description='Running'
    descriptionDone='Ran'
    descriptionSuffix = None
    renderables = [ 'command', 'env', 'description', 'descriptionDone', 'descriptionSuffix' ]
    haltOnFailure = True
    flunkOnFailure = True

    def __init__(self, command,
                 description=None, descriptionDone=None, descriptionSuffix=None,
                 env=None, path=None, usePTY=0, interruptSignal="KILL",
                 **kwargs):
        BuildStep.__init__(self, **kwargs)

        self.command=command
        if description:
            self.description = description
        if isinstance(self.description, str):
            self.description = [self.description]
        if descriptionDone:
            self.descriptionDone = descriptionDone
        if isinstance(self.descriptionDone, str):
            self.descriptionDone = [self.descriptionDone]
        if descriptionSuffix:
            self.descriptionSuffix = descriptionSuffix
        if isinstance(self.descriptionSuffix, str):
            self.descriptionSuffix = [self.descriptionSuffix]
        self.env=env
        self.path=path
        self.usePTY=usePTY
        self.interruptSignal = interruptSignal

    class LocalPP(ProcessProtocol):
        def __init__(self, step):
            self.step = step

        def outReceived(self, data):
            self.step.stdio_log.addStdout(data)

        def errReceived(self, data):
            self.step.stdio_log.addStderr(data)

        def processEnded(self, status_object):
            if status_object.value.exitCode is not None:
                self.step.stdio_log.addHeader("exit status %d\n" % status_object.value.exitCode)
            if status_object.value.signal is not None:
                self.step.stdio_log.addHeader("signal %s\n" % status_object.value.signal)
            self.step.processEnded(status_object)

    def start(self):
        # render properties
        command = self.command
        # set up argv
        if type(command) in types.StringTypes:
            if runtime.platformType  == 'win32':
                argv = os.environ['COMSPEC'].split() # allow %COMSPEC% to have args
                if '/c' not in argv: argv += ['/c']
                argv += [command]
            else:
                # for posix, use /bin/sh. for other non-posix, well, doesn't
                # hurt to try
                argv = ['/bin/sh', '-c', command]
        else:
            if runtime.platformType  == 'win32':
                argv = os.environ['COMSPEC'].split() # allow %COMSPEC% to have args
                if '/c' not in argv: argv += ['/c']
                argv += list(command)
            else:
                argv = command

        self.stdio_log = stdio_log = self.addLog("stdio")

        if type(command) in types.StringTypes:
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
            for key, v in self.env.iteritems():
                if isinstance(v, list):
                    # Need to do os.pathsep translation.  We could either do that
                    # by replacing all incoming ':'s with os.pathsep, or by
                    # accepting lists.  I like lists better.
                    # If it's not a string, treat it as a sequence to be
                    # turned in to a string.
                    self.env[key] = os.pathsep.join(self.env[key])

            # do substitution on variable values matching pattern: ${name}
            p = re.compile('\${([0-9a-zA-Z_]*)}')
            def subst(match):
                return os.environ.get(match.group(1), "")
            newenv = {}
            for key, v in env.iteritems():
                if v is not None:
                    if not isinstance(v, basestring):
                        raise RuntimeError("'env' values must be strings or "
                                "lists; key '%s' is incorrect" % (key,))
                    newenv[key] = p.sub(subst, env[key])
            env = newenv
        stdio_log.addHeader(" env: %r\n" % (env,))

        # TODO add a timeout?
        self.process = reactor.spawnProcess(self.LocalPP(self), argv[0], argv,
                path=self.path, usePTY=self.usePTY, env=env )
        # (the LocalPP object will call processEnded for us)

    def processEnded(self, status_object):
        if status_object.value.signal is not None:
            self.descriptionDone = ["killed (%s)" % status_object.value.signal]
            self.step_status.setText(self.describe(done=True))
            self.finished(FAILURE)
        elif status_object.value.exitCode != 0:
            self.descriptionDone = ["failed (%d)" % status_object.value.exitCode]
            self.step_status.setText(self.describe(done=True))
            self.finished(FAILURE)
        else:
            self.step_status.setText(self.describe(done=True))
            self.finished(SUCCESS)

    def describe(self, done=False):
        desc = self.descriptionDone if done else self.description
        if self.descriptionSuffix:
            desc = desc[:]
            desc.extend(self.descriptionSuffix)
        return desc

    def interrupt(self, reason):
        try:
            self.process.signalProcess(self.interruptSignal)
        except KeyError: # Process not started yet
            pass
        except error.ProcessExitedAlready:
            pass
        BuildStep.interrupt(self, reason)
