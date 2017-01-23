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

from twisted.internet import defer
from twisted.python import log

from buildbot import config
from buildbot.process import buildstep
from buildbot.process import results


class ShellArg(results.ResultComputingConfigMixin):
    publicAttributes = (
        results.ResultComputingConfigMixin.resultConfig +
        ["command", "logfile"])

    def __init__(self, command=None, logfile=None, **kwargs):
        name = self.__class__.__name__
        if command is None:
            config.error("the 'command' parameter of %s "
                         "must not be None" % (name,))
        self.command = command
        self.logfile = logfile
        for k, v in iteritems(kwargs):
            if k not in self.resultConfig:
                config.error("the parameter '%s' is not "
                             "handled by ShellArg" % (k,))
            setattr(self, k, v)
        # we don't validate anything yet as we can have renderables.

    def validateAttributes(self):
        # only make the check if we have a list
        if not isinstance(self.command, (str, list)):
            config.error("%s is an invalid command, "
                         "it must be a string or a list" % (self.command,))
        if isinstance(self.command, list):
            if not all([isinstance(x, str) for x in self.command]):
                config.error("%s must only have strings in it" %
                             (self.command,))
        runConfParams = [(p_attr, getattr(self, p_attr))
                         for p_attr in self.resultConfig]
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


class ShellSequence(buildstep.ShellMixin, buildstep.BuildStep):
    last_command = None
    renderables = ['commands']

    def __init__(self, commands=None, **kwargs):
        self.commands = commands
        kwargs = self.setupShellMixin(kwargs, prohibitArgs=['command'])
        buildstep.BuildStep.__init__(self, **kwargs)

    def shouldRunTheCommand(self, cmd):
        return bool(cmd)

    def getFinalState(self):
        return self.describe(True)

    @defer.inlineCallbacks
    def runShellSequence(self, commands):
        terminate = False
        if commands is None:
            log.msg("After rendering, ShellSequence `commands` is None")
            defer.returnValue(results.EXCEPTION)
        overall_result = results.SUCCESS
        for arg in commands:
            if not isinstance(arg, ShellArg):
                log.msg("After rendering, ShellSequence `commands` list "
                        "contains something that is not a ShellArg")
                defer.returnValue(results.EXCEPTION)
            try:
                arg.validateAttributes()
            except config.ConfigErrors as e:
                log.msg("After rendering, ShellSequence `commands` is "
                        "invalid: %s" % (e,))
                defer.returnValue(results.EXCEPTION)

            # handle the command from the arg
            command = arg.command
            if not self.shouldRunTheCommand(command):
                continue

            # keep the command around so we can describe it
            self.last_command = command

            cmd = yield self.makeRemoteShellCommand(command=command,
                                                    stdioLogName=arg.logfile)
            yield self.runCommand(cmd)
            overall_result, terminate = results.computeResultAndTermination(
                arg, cmd.results(), overall_result)
            if terminate:
                break
        defer.returnValue(overall_result)

    def run(self):
        return self.runShellSequence(self.commands)
