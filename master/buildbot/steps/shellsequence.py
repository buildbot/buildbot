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

from buildbot import config
from buildbot import interfaces
from buildbot.process import buildstep
from buildbot.process import remotecommand
from buildbot.status import results
from twisted.internet import defer
from zope.interface import implements


class ShellArg(object):
    implements(interfaces.IResComputingConfig)
    iResComputingParams = ["haltOnFailure", "flunkOnWarnings", "flunkOnFailure",
                           "warnOnWarnings", "warnOnFailure"]
    publicAttributes = iResComputingParams + ["cmd", "logfile"]

    haltOnFailure = False
    flunkOnWarnings = False
    flunkOnFailure = True
    warnOnWarnings = False
    warnOnFailure = False

    def __init__(self, cmd=None, logfile=None, **kwargs):
        name = self.__class__.__name__
        if cmd is None:
            config.error("the 'cmd' parameter of %s "
                         "must not be None" % (name,))
        self.cmd = cmd
        self.logfile = logfile
        for k, v in kwargs.iteritems():
            if k not in self.iResComputingParams:
                config.error("the parameter '%s' is not "
                             "handled by ShellArg" % (k,))
            setattr(self, k, v)
        # we don't validate anything yet as we can have renderables.

    def validateAttributes(self):
        """
        Only make the check if we have a list
        """
        if not isinstance(self.cmd, (str, list)):
            config.error("%s is an invalid command, "
                         "it must be a string or a list" % (self.cmd,))
        if isinstance(self.cmd, list):
            if not all([isinstance(x, str) for x in self.cmd]):
                config.error("%s must only have strings in it" % (self.cmd,))
        runConfParams = [(p_attr, getattr(self, p_attr)) for p_attr in self.iResComputingParams]
        not_bool = [(p_attr, p_val) for (p_attr, p_val) in runConfParams if not isinstance(p_val,
                                                                                           bool)]
        if not_bool:
            config.error("%r must be booleans" % (not_bool,))

    @defer.inlineCallbacks
    def getRenderingFor(self, build):
        for p_attr in self.publicAttributes:
            res = yield build.render(getattr(self, p_attr))
            setattr(self, p_attr, res)
        defer.returnValue(self)


class ShellSequence(buildstep.ShellBaseStep):
    renderables = ['commands']

    def __init__(self, commands=None, **kwargs):
        self.commands = commands
        self.currCmd = None
        self.alreadyUsedLog = []
        self.result = results.SUCCESS
        super(ShellSequence, self).__init__(**kwargs)

    def getCurrCommand(self):
        return self.currCmd

    def setCommands(self, commands):
        """
        can be used by a step that dynamically creates
        the commands list.
        """
        self.commands = commands

    def shouldRunTheCommand(self, cmd):
        return bool(cmd)

    def getFinalState(self):
        return self.describe(True)

    @defer.inlineCallbacks
    def runShellSequence(self):
        """
        runs all shell commands according to the configuration
        defined by the steps above.
        """
        warnings = []
        terminate = False
        if self.commands is None:
            yield self.setStateStrings(["commands == None"])
            defer.returnValue(results.EXCEPTION)
        for arg in self.commands:
            if not isinstance(arg, ShellArg):
                yield self.setStateStrings([str(arg), "not", "ShellArg"])
                defer.returnValue(results.EXCEPTION)
            try:
                arg.validateAttributes()
            except config.ConfigErrors:
                yield self.setStateStrings([arg.cmd, "invalid", "params"])
                defer.returnValue(results.EXCEPTION)

            # handle cmd
            self.currCmd = arg.cmd
            result = results.SKIPPED
            if self.shouldRunTheCommand(self.currCmd):
                # handle the log
                logObj = None
                if arg.logfile is not None:
                    if not arg.logfile.startswith("stdio"):
                        arg.logfile = "stdio " + arg.logfile
                    logObj = yield self.addLog(arg.logfile)

                # create the actual RemoteShellCommand instance
                kwargs = self.buildCommandKwargs(self.currCmd, warnings)
                cmd = remotecommand.RemoteShellCommand(**kwargs)
                self.setupEnvironment(cmd)

                # run it
                result = yield self.startCommandAndSetStatus(cmd, stdioLog=logObj)
            self.result, terminate = results.computeResultAndContinuation(arg, result,
                                                                          self.result)
            if terminate:
                break
        yield self.setStateStrings(self.getFinalState())
        defer.returnValue(self.result)

    # If one ones to make some computation before and/or after the sequence of commands are run
    # the method below must be overriden. There, one can call self.runShellSequence according to its
    # needs, provided commands are set. One can use self.setCommands to set it dynamically.
    def run(self):
        return self.runShellSequence()
