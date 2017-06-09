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

# N.B.: don't import anything that might pull in a reactor yet. Some of our
# subcommands want to load modules that need the gtk reactor.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import re
import sys
import textwrap

from twisted.python import log
from twisted.python import reflect
from twisted.python import usage

# the create/start/stop commands should all be run as the same user,
# preferably a separate 'buildbot' account.

# Note that the terms 'options' and 'config' are used interchangeably here - in
# fact, they are interchanged several times.  Caveat legator.


class MakerBase(usage.Options):
    optFlags = [
        ['help', 'h', "Display this message"],
        ["quiet", "q", "Do not emit the commands being run"],
    ]

    longdesc = textwrap.dedent("""
    Operates upon the specified <basedir> (or the current directory, if not
    specified).
    """)

    # on tab completion, suggest directories as first argument
    if hasattr(usage, 'Completions'):
        # only set completion suggestion if running with
        # twisted version (>=11.1.0) that supports it
        compData = usage.Completions(
            extraActions=[usage.CompleteDirs(descr="worker base directory")])

    opt_h = usage.Options.opt_help

    def parseArgs(self, *args):
        if args:
            self['basedir'] = args[0]
        else:
            # Use the current directory if no basedir was specified.
            self['basedir'] = os.getcwd()
        if len(args) > 1:
            raise usage.UsageError("I wasn't expecting so many arguments")

    def postOptions(self):
        self['basedir'] = os.path.abspath(self['basedir'])


class StartOptions(MakerBase):
    subcommandFunction = "buildbot_worker.scripts.start.startCommand"
    optFlags = [
        ['quiet', 'q', "Don't display startup log messages"],
        ['nodaemon', None, "Don't daemonize (stay in foreground)"],
    ]

    def getSynopsis(self):
        return "Usage:    buildbot-worker start [<basedir>]"


class StopOptions(MakerBase):
    subcommandFunction = "buildbot_worker.scripts.stop.stop"

    def getSynopsis(self):
        return "Usage:    buildbot-worker stop [<basedir>]"


class RestartOptions(MakerBase):
    subcommandFunction = "buildbot_worker.scripts.restart.restart"
    optFlags = [
        ['quiet', 'q', "Don't display startup log messages"],
        ['nodaemon', None, "Don't daemonize (stay in foreground)"],
    ]

    def getSynopsis(self):
        return "Usage:    buildbot-worker restart [<basedir>]"


class CreateWorkerOptions(MakerBase):
    subcommandFunction = "buildbot_worker.scripts.create_worker.createWorker"
    optFlags = [
        ["force", "f", "Re-use an existing directory"],
        ["relocatable", "r",
         "Create a relocatable buildbot.tac"],
        ["no-logrotate", "n",
         "Do not permit buildmaster rotate logs by itself"]
    ]
    optParameters = [
        ["keepalive", "k", 600,
         "Interval at which keepalives should be sent (in seconds)"],
        ["umask", None, "None",
         "controls permissions of generated files. "
         "Use --umask=0o22 to be world-readable"],
        ["maxdelay", None, 300,
         "Maximum time between connection attempts"],
        ["numcpus", None, "None",
         "Number of available cpus to use on a build. "],
        ["log-size", "s", "10000000",
         "size at which to rotate twisted log files"],
        ["log-count", "l", "10",
         "limit the number of kept old twisted log files "
         "(None for unlimited)"],
        ["allow-shutdown", "a", None,
         "Allows the worker to initiate a graceful shutdown. One of "
         "'signal' or 'file'"]
    ]

    longdesc = textwrap.dedent("""
    This command creates a buildbot worker directory and buildbot.tac
    file. The bot will use the <name> and <passwd> arguments to authenticate
    itself when connecting to the master. All commands are run in a
    build-specific subdirectory of <basedir>. <master> is a string of the
    form 'hostname[:port]', and specifies where the buildmaster can be reached.
    port defaults to 9989.

    The appropriate values for <name>, <passwd>, and <master> should be
    provided to you by the buildmaster administrator. You must choose <basedir>
    yourself.
    """)

    def validateMasterArgument(self, master_arg):
        """
        Parse the <master> argument.

        @param master_arg: the <master> argument to parse

        @return: tuple of master's host and port
        @raise UsageError: on errors parsing the argument
        """
        if master_arg[:5] == "http:":
            raise usage.UsageError("<master> is not a URL - do not use URL")

        if ":" not in master_arg:
            master = master_arg
            port = 9989
        else:
            master, port = master_arg.split(":")

        if len(master) < 1:
            raise usage.UsageError("invalid <master> argument '%s'" %
                                   master_arg)
        try:
            port = int(port)
        except ValueError:
            raise usage.UsageError("invalid master port '%s', "
                                   "needs to be a number" % port)

        return master, port

    def getSynopsis(self):
        return "Usage:    buildbot-worker create-worker " \
            "[options] <basedir> <master> <name> <passwd>"

    def parseArgs(self, *args):
        if len(args) != 4:
            raise usage.UsageError("incorrect number of arguments")
        basedir, master, name, passwd = args
        self['basedir'] = basedir
        self['host'], self['port'] = self.validateMasterArgument(master)
        self['name'] = name
        self['passwd'] = passwd

    def postOptions(self):
        MakerBase.postOptions(self)

        # check and convert numeric parameters
        for argument in ["keepalive", "maxdelay", "log-size"]:
            try:
                self[argument] = int(self[argument])
            except ValueError:
                raise usage.UsageError("%s parameter needs to be a number"
                                       % argument)

        if not re.match(r'^\d+$', self['log-count']) and \
                self['log-count'] != 'None':
            raise usage.UsageError("log-count parameter needs to be a number"
                                   " or None")

        if not re.match(r'^(0o)?\d+$', self['umask']) and \
                self['umask'] != 'None':
            raise usage.UsageError("umask parameter needs to be a number"
                                   " or None")

        if not re.match(r'^\d+$', self['numcpus']) and \
                self['numcpus'] != 'None':
            raise usage.UsageError("numcpus parameter needs to be a number"
                                   " or None")

        if self['allow-shutdown'] not in [None, 'signal', 'file']:
            raise usage.UsageError("allow-shutdown needs to be one of"
                                   " 'signal' or 'file'")


class Options(usage.Options):
    synopsis = "Usage:    buildbot-worker <command> [command options]"

    subCommands = [
        # the following are all admin commands
        ['create-worker', None, CreateWorkerOptions,
         "Create and populate a directory for a new worker"],
        ['start', None, StartOptions, "Start a worker"],
        ['stop', None, StopOptions, "Stop a worker"],
        ['restart', None, RestartOptions,
         "Restart a worker"],
    ]

    def opt_version(self):
        import buildbot_worker
        print("worker version: %s" % buildbot_worker.version)
        usage.Options.opt_version(self)

    def opt_verbose(self):
        log.startLogging(sys.stderr)

    def postOptions(self):
        if not hasattr(self, 'subOptions'):
            raise usage.UsageError("must specify a command")


def run():
    config = Options()
    try:
        config.parseOptions()
    except usage.error as e:
        print("%s:  %s" % (sys.argv[0], e))
        print()
        c = getattr(config, 'subOptions', config)
        print(str(c))
        sys.exit(1)

    subconfig = config.subOptions
    subcommandFunction = reflect.namedObject(subconfig.subcommandFunction)
    sys.exit(subcommandFunction(subconfig))
