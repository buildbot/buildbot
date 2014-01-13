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
from buildbot.process import buildstep
from buildbot.process import remotecommand
from buildbot.status import results
from twisted.internet import defer
from twisted.internet import error


class ShellArg(object):
    __invalid_log_name_chars = ['/', '(', ')']

    def __init__(self, cmd=None, logfile=None):
        name = self.__class__.__name__
        if cmd is None:
            config.error("the 'cmd' parameter of %s "
                         "must not be None" % (name,))
        self.validateLogfileName(logfile)
        self.cmd = cmd
        self.logfile = logfile

    def validateLogfileName(self, logfile):
        """
        Only make the check if we have a string,
        we will make the check during the run else.
        """
        if logfile is not None and isinstance(logfile, str):
            if any([logfile.find(c) != -1 for c in self.__invalid_log_name_chars]):
                config.error("%s is an invalid logfile, "
                             "it must not contain any of %r" % (logfile,
                                                                self.__invalid_log_name_chars))

    @defer.inlineCallbacks
    def getRenderingFor(self, build):
        self.cmd = yield build.render(self.cmd)
        self.logfile = yield build.render(self.logfile)
        defer.returnValue(self)


class ListOfShellCommands(buildstep.ShellBaseStep):
    renderables = ['commands']

    def __init__(self, commands=None, **kwargs):
        self.commands = commands
        self.currCmd = None
        super(ListOfShellCommands, self).__init__(**kwargs)

    def getCurrCommand(self):
        return self.currCmd

    def setCommands(self, commands):
        """
        can be used by a step that dynamically creates
        the commands list.
        """
        self.commands = commands

    # Methods that configure how the sequences of shell command should be run.
    # That configuration can be setup by overriding those methods.
    def doIContinue(self, obtainedResults):
        """
        @type obtainedResults: list
        @param obtainedResults: the results obtained up to know,
        in the same order as they were run.
        @rtype: bool
        @return: whether the other steps should be executed.
        """
        return all(x in [results.SKIPPED, results.WARNINGS, results.SUCCESS]
                   for x in obtainedResults)

    def doIRunTheCommand(self, cmd):
        """
        returns whether the cmd should be run. If not
        the result of that command will be recorded as results.SKIPPED.
        """
        return cmd != ""

    def computeResult(self, allRes):
        """
        @type allRes: list
        @param allRes: the obtained results
        @rtype: a result (see results)
        @return: the result to take for all the step according to
        the ones obtained by the executed steps.
        """
        return results.reduceResults([x for x in allRes if x != results.SKIPPED])

    def getFinalState(self):
        """
        the strings to set to step status before ending it.
        """
        return self.describe(True)

    @defer.inlineCallbacks
    def runAllCmds(self):
        """
        runs all shell commands according to the configuration
        defined by the steps above.
        """
        warnings = []
        all_res = []
        if self.commands is None:
            yield self.setStateStrings(["commands == None"])
            defer.returnValue(results.EXCEPTION)
        for arg in self.commands:
            if not isinstance(arg, ShellArg):
                yield self.setStateStrings([str(arg), "not", "ShellArg"])
                defer.returnValue(results.EXCEPTION)
            self.currCmd = arg.cmd
            if not self.doIRunTheCommand(self.currCmd):
                all_res.append(results.SKIPPED)
                continue
            # handle the log
            logObj = None
            if arg.logfile is not None:
                if not arg.logfile.startswith("stdio"):
                    arg.logfile = "stdio " + arg.logfile
                try:
                    arg.validateLogfileName(arg.logfile)
                except config.ConfigErrors:
                    yield self.setStateStrings([arg.logfile, "invalid", "logfile"])
                    defer.returnValue(results.EXCEPTION)
                logObj = yield self.addLog(arg.logfile)

            # create the actual RemoteShellCommand instance
            kwargs = self.buildCommandKwargs(self.currCmd, warnings)
            cmd = remotecommand.RemoteShellCommand(**kwargs)
            self.setupEnvironment(cmd)
            try:
                # run it
                res = yield self.runCmd(cmd, stdioLog=logObj, stdioLogName=arg.logfile)
                all_res.append(res)
                if not self.doIContinue(all_res):
                    break
            except error.ConnectionLost:
                self.setConnectionLostInStatus()
                yield self.setStateStrings(self.describe(True))
                defer.returnValue(results.RETRY)
        yield self.setStateStrings(self.getFinalState())
        defer.returnValue(self.computeResult(all_res))

    # If one ones to make some computation before and/or after the sequence of commands are run
    # the method below must be overriden. There, one can call self.runAllCmds according to its
    # needs, provided commands are set. One can use self.setCommands to set it dynamically.
    def run(self):
        return self.runAllCmds()
